from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import time
from typing import NamedTuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field
from pydantic import JsonValue
import yaml

from packages.core import (
    Document,
    DocumentEntity,
    EntityKind,
    SourceTier,
    SourceType,
    make_content_hash,
    make_doc_id,
    make_issuer_ticker_family_id,
)
from packages.ingestion.raw_store import RawStore
from packages.ingestion.registry import SourceConfig

from .base import AdapterBatch, AdapterError, BaseSourceAdapter
from .http import HttpAdapterError, fetch_bytes


DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0
FetchBytes = Callable[[str, Mapping[str, str], float], bytes]
Sleep = Callable[[float], None]


class CompanyIrFeedOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1)
    source_type: SourceType = SourceType.COMPANY_NEWSROOM


class CompanyIrIssuerOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.-]*$")
    company_name: str = Field(min_length=1)
    source_family_id: str | None = None
    feeds: tuple[CompanyIrFeedOptions, ...] = ()


class CompanyIrFetchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_path: str | None = Field(default=None, min_length=1)
    issuers: tuple[CompanyIrIssuerOptions, ...] = ()
    published_after: datetime | None = None
    continue_on_feed_error: bool = True
    fetch_item_pages: bool = False
    request_timeout_seconds: float = Field(
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        gt=0,
    )


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


class _FeedParseResult(NamedTuple):
    documents: tuple[Document, ...]
    raw_item_count: int
    filtered_by_published_after_count: int
    latest_item_published_at: datetime | None


class CompanyIrAdapter(BaseSourceAdapter):
    source_id = "company_ir"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        fetch_bytes: FetchBytes | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = CompanyIrFetchOptions.model_validate(self.options)
        self.issuers = self.fetch_options.issuers + _load_catalog_issuers(
            self.fetch_options.catalog_path
        )
        self._fetch_bytes = fetch_bytes or _fetch_url_bytes
        self._sleep = sleep or time.sleep

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        if not self.issuers:
            return self._failure(
                code="missing_source_options",
                message="Company IR fetch requires at least one issuer",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        if self.raw_dir is None:
            return self._failure(
                code="missing_raw_dir",
                message="Company IR fetch requires a raw_dir",
                retrieved_at=retrieved_at,
                retryable=False,
            )

        raw_store = RawStore(self.raw_dir)
        records: list[dict[str, JsonValue]] = []
        raw_uris: list[str] = []
        warnings: list[AdapterError] = []
        feed_errors = 0
        feed_index = 0
        successful_feeds = 0

        for issuer in self.issuers:
            for feed in issuer.feeds:
                if feed_index:
                    self._sleep(1 / self.source.rate_limit_per_second)
                feed_index += 1
                try:
                    content = self._fetch_bytes(
                        feed.url,
                        _request_headers(),
                        self.fetch_options.request_timeout_seconds,
                    )
                except HttpAdapterError as exc:
                    if not self.fetch_options.continue_on_feed_error:
                        return AdapterBatch.failure(
                            source_id=self.source.source_id,
                            output_kind=self.source.output_kind,
                            retrieved_at=retrieved_at,
                            error=exc.error,
                        )
                    feed_errors += 1
                    warnings.append(exc.error)
                    continue
                except OSError as exc:
                    if not self.fetch_options.continue_on_feed_error:
                        return self._failure(
                            code="network_error",
                            message=f"Company IR request failed: {exc}",
                            retrieved_at=retrieved_at,
                            retryable=True,
                        )
                    feed_errors += 1
                    warnings.append(
                        AdapterError(
                            code="feed_error",
                            message=f"Company IR feed failed for {issuer.ticker}: {exc}",
                            retryable=True,
                            details={"ticker": issuer.ticker, "url": feed.url},
                        )
                    )
                    continue

                raw_result = raw_store.write_bytes(
                    Path(self.source.source_id)
                    / issuer.ticker
                    / f"{make_content_hash(feed.url)[7:23]}.xml",
                    content,
                )
                raw_uris.append(raw_result.raw_uri)
                try:
                    parse_result = _parse_feed_documents(
                        content=content,
                        feed=feed,
                        issuer=issuer,
                        source_id=self.source.source_id,
                        raw_object_uri=raw_result.raw_uri,
                        retrieved_at=retrieved_at,
                        published_after=self.fetch_options.published_after,
                    )
                except (ET.ParseError, ValueError) as exc:
                    if not self.fetch_options.continue_on_feed_error:
                        return self._failure(
                            code="feed_parse_error",
                            message=f"Company IR feed parse failed: {exc}",
                            retrieved_at=retrieved_at,
                            retryable=False,
                        )
                    feed_errors += 1
                    warnings.append(
                        AdapterError(
                            code="feed_parse_error",
                            message=f"Company IR feed parse failed for {issuer.ticker}: {exc}",
                            retryable=False,
                            details={"ticker": issuer.ticker, "url": feed.url},
                        )
                    )
                    continue
                successful_feeds += 1
                if parse_result.raw_item_count and not parse_result.documents:
                    details: dict[str, JsonValue] = {
                        "ticker": issuer.ticker,
                        "url": feed.url,
                        "raw_item_count": parse_result.raw_item_count,
                        "filtered_by_published_after_count": (
                            parse_result.filtered_by_published_after_count
                        ),
                        "records_written": 0,
                    }
                    if parse_result.latest_item_published_at is not None:
                        details["latest_item_published_at"] = _format_utc_z(
                            parse_result.latest_item_published_at
                        )
                    warnings.append(
                        AdapterError(
                            code="feed_no_records",
                            message=(
                                "Company IR feed produced no records for "
                                f"{issuer.ticker}"
                            ),
                            retryable=False,
                            details=details,
                        )
                    )
                for document in parse_result.documents:
                    if self.fetch_options.fetch_item_pages:
                        document = self._with_item_page_raw(
                            document=document,
                            raw_store=raw_store,
                            ticker=issuer.ticker,
                            warnings=warnings,
                        )
                        primary_raw_uri = document.metadata.get(
                            "primary_document_raw_uri"
                        )
                        if isinstance(primary_raw_uri, str):
                            raw_uris.append(primary_raw_uri)
                    records.append(document.model_dump(mode="json"))
                    if limit is not None and len(records) >= limit:
                        return AdapterBatch.success(
                            source_id=self.source.source_id,
                            output_kind=self.source.output_kind,
                            records=records,
                            raw_uris=raw_uris,
                            warnings=warnings,
                            retrieved_at=retrieved_at,
                        )

        if feed_errors and not records and successful_feeds == 0:
            return self._failure(
                code="all_feeds_failed",
                message="All Company IR feed requests failed",
                retrieved_at=retrieved_at,
                retryable=True,
            )

        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=records,
            raw_uris=raw_uris,
            warnings=warnings,
            retrieved_at=retrieved_at,
        )

    def _failure(
        self,
        *,
        code: str,
        message: str,
        retrieved_at: datetime,
        retryable: bool,
    ) -> AdapterBatch:
        return AdapterBatch.failure(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=retrieved_at,
            error=AdapterError(code=code, message=message, retryable=retryable),
        )

    def _with_item_page_raw(
        self,
        *,
        document: Document,
        raw_store: RawStore,
        ticker: str,
        warnings: list[AdapterError],
    ) -> Document:
        try:
            self._sleep(1 / self.source.rate_limit_per_second)
            content = self._fetch_bytes(
                str(document.url),
                _request_headers(),
                self.fetch_options.request_timeout_seconds,
            )
        except HttpAdapterError as exc:
            warnings.append(exc.error)
            return document
        except OSError as exc:
            warnings.append(
                AdapterError(
                    code="item_page_fetch_error",
                    message=f"Company IR item page failed for {ticker}: {exc}",
                    retryable=True,
                    details={"ticker": ticker, "url": str(document.url)},
                )
            )
            return document

        result = raw_store.write_bytes(
            Path(self.source.source_id)
            / ticker
            / f"{make_content_hash(str(document.url))[7:23]}{_raw_suffix(str(document.url), content)}",
            content,
        )
        return document.model_copy(
            update={
                "raw_object_uri": result.raw_uri,
                "content_hash": result.content_hash,
                "metadata": {
                    **document.metadata,
                    "feed_raw_object_uri": document.raw_object_uri,
                    "primary_document_raw_uri": result.raw_uri,
                    "primary_document_content_hash": result.content_hash,
                },
            }
        )


def _fetch_url_bytes(url: str, headers: Mapping[str, str], timeout: float) -> bytes:
    content, _response = fetch_bytes(
        url,
        headers=headers,
        timeout_seconds=timeout,
    )
    return content


def _load_catalog_issuers(
    catalog_path: str | None,
) -> tuple[CompanyIrIssuerOptions, ...]:
    if not catalog_path:
        return ()
    raw = yaml.safe_load(Path(catalog_path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Company IR catalog must contain a mapping")
    if raw.get("version") != 1:
        raise ValueError("Company IR catalog must use version: 1")
    issuers = raw.get("issuers", [])
    if not isinstance(issuers, list):
        raise ValueError("Company IR catalog must contain an issuers list")
    return tuple(CompanyIrIssuerOptions.model_validate(item) for item in issuers)


def _request_headers() -> dict[str, str]:
    return {
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        "User-Agent": "super-bear-dev",
    }


def _raw_suffix(url: str, content: bytes) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".htm", ".html", ".pdf", ".txt", ".xml", ".json"}:
        return suffix
    if content.lstrip().startswith(b"%PDF-"):
        return ".pdf"
    return ".html"


def _parse_feed_documents(
    *,
    content: bytes,
    feed: CompanyIrFeedOptions,
    issuer: CompanyIrIssuerOptions,
    source_id: str,
    raw_object_uri: str,
    retrieved_at: datetime,
    published_after: datetime | None = None,
) -> _FeedParseResult:
    root = ET.fromstring(content)
    items = _rss_items(root) or _atom_entries(root)
    documents: list[Document] = []
    filtered_by_published_after_count = 0
    latest_item_published_at: datetime | None = None
    for item in items:
        title = _child_text(item, "title")
        url = _entry_url(item, feed.url)
        published_at = _entry_datetime(item) or retrieved_at
        if latest_item_published_at is None or published_at > latest_item_published_at:
            latest_item_published_at = published_at
        if not title or not url:
            continue
        if published_after and published_at < published_after:
            filtered_by_published_after_count += 1
            continue
        text = _entry_text(item) or title
        source_family_id = issuer.source_family_id or make_issuer_ticker_family_id(
            issuer.ticker
        )
        document = Document(
            doc_id=make_doc_id(source_id, issuer.ticker, url, published_at.isoformat()),
            source_id=source_id,
            source_type=feed.source_type,
            source_tier=SourceTier.COMPANY_PRIMARY,
            source_family_id=source_family_id,
            title=title,
            url=url,
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw_object_uri=raw_object_uri,
            content_hash=make_content_hash(f"{title}\n{url}\n{text}"),
            parser_version="company_ir_feed_v0.1",
            language="en",
            entities=(
                DocumentEntity(
                    kind=EntityKind.TICKER,
                    value=issuer.ticker,
                    identifiers={"ticker": issuer.ticker},
                ),
                DocumentEntity(kind=EntityKind.COMPANY, value=issuer.company_name),
            ),
            metadata={
                "feed_url": feed.url,
                "primary_document_text": text,
            },
        )
        documents.append(document)
    return _FeedParseResult(
        documents=tuple(documents),
        raw_item_count=len(items),
        filtered_by_published_after_count=filtered_by_published_after_count,
        latest_item_published_at=latest_item_published_at,
    )


def _format_utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _rss_items(root: ET.Element) -> tuple[ET.Element, ...]:
    return tuple(root.findall("./channel/item"))


def _atom_entries(root: ET.Element) -> tuple[ET.Element, ...]:
    return tuple(child for child in root if _local_name(child.tag) == "entry")


def _entry_url(item: ET.Element, base_url: str) -> str:
    link = _child(item, "link")
    if link is None:
        return ""
    raw_url = link.attrib.get("href", "").strip() or (link.text or "").strip()
    return urljoin(base_url, raw_url)


def _entry_datetime(item: ET.Element) -> datetime | None:
    value = (
        _child_text(item, "pubDate")
        or _child_text(item, "published")
        or _child_text(item, "updated")
    )
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _entry_text(item: ET.Element) -> str:
    value = (
        _child_text(item, "encoded")
        or _child_text(item, "content")
        or _child_text(item, "description")
        or _child_text(item, "summary")
    )
    return _strip_html(value)


def _child_text(item: ET.Element, local_name: str) -> str:
    child = _child(item, local_name)
    if child is None:
        return ""
    return "".join(child.itertext()).strip()


def _child(item: ET.Element, local_name: str) -> ET.Element | None:
    for child in item:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _strip_html(value: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(unescape(value))
    text = " ".join(parser.parts)
    return " ".join((text or unescape(value)).split())
