from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field
from pydantic import JsonValue

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

    issuers: tuple[CompanyIrIssuerOptions, ...] = ()
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


class CompanyIrAdapter(BaseSourceAdapter):
    source_id = "company_ir"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        fetch_bytes: FetchBytes | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = CompanyIrFetchOptions.model_validate(self.options)
        self._fetch_bytes = fetch_bytes or _fetch_url_bytes

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        if not self.fetch_options.issuers:
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

        for issuer in self.fetch_options.issuers:
            for feed in issuer.feeds:
                try:
                    content = self._fetch_bytes(
                        feed.url,
                        _request_headers(),
                        self.fetch_options.request_timeout_seconds,
                    )
                except HttpAdapterError as exc:
                    return AdapterBatch.failure(
                        source_id=self.source.source_id,
                        output_kind=self.source.output_kind,
                        retrieved_at=retrieved_at,
                        error=exc.error,
                    )
                except OSError as exc:
                    return self._failure(
                        code="network_error",
                        message=f"Company IR request failed: {exc}",
                        retrieved_at=retrieved_at,
                        retryable=True,
                    )

                raw_result = raw_store.write_bytes(
                    Path(self.source.source_id)
                    / issuer.ticker
                    / f"{make_content_hash(feed.url)[7:23]}.xml",
                    content,
                )
                raw_uris.append(raw_result.raw_uri)
                documents = _parse_feed_documents(
                    content=content,
                    feed=feed,
                    issuer=issuer,
                    source_id=self.source.source_id,
                    raw_object_uri=raw_result.raw_uri,
                    retrieved_at=retrieved_at,
                )
                for document in documents:
                    records.append(document.model_dump(mode="json"))
                    if limit is not None and len(records) >= limit:
                        return AdapterBatch.success(
                            source_id=self.source.source_id,
                            output_kind=self.source.output_kind,
                            records=records,
                            raw_uris=raw_uris,
                            retrieved_at=retrieved_at,
                        )

        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=records,
            raw_uris=raw_uris,
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


def _fetch_url_bytes(url: str, headers: Mapping[str, str], timeout: float) -> bytes:
    content, _response = fetch_bytes(
        url,
        headers=headers,
        timeout_seconds=timeout,
    )
    return content


def _request_headers() -> dict[str, str]:
    return {
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        "User-Agent": "super-bear-dev",
    }


def _parse_feed_documents(
    *,
    content: bytes,
    feed: CompanyIrFeedOptions,
    issuer: CompanyIrIssuerOptions,
    source_id: str,
    raw_object_uri: str,
    retrieved_at: datetime,
) -> tuple[Document, ...]:
    root = ET.fromstring(content)
    items = _rss_items(root) or _atom_entries(root)
    documents: list[Document] = []
    for item in items:
        title = _child_text(item, "title")
        url = _entry_url(item)
        if not title or not url:
            continue
        published_at = _entry_datetime(item) or retrieved_at
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
    return tuple(documents)


def _rss_items(root: ET.Element) -> tuple[ET.Element, ...]:
    return tuple(root.findall("./channel/item"))


def _atom_entries(root: ET.Element) -> tuple[ET.Element, ...]:
    return tuple(child for child in root if _local_name(child.tag) == "entry")


def _entry_url(item: ET.Element) -> str:
    link = _child(item, "link")
    if link is None:
        return ""
    return link.attrib.get("href", "").strip() or (link.text or "").strip()


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
