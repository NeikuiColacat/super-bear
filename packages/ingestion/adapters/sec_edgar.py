from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from packages.ingestion.raw_store import RawStore
from packages.ingestion.registry import SourceConfig

from .base import AdapterBatch, AdapterError, BaseSourceAdapter


DATA_SEC_BASE_URL = "https://data.sec.gov"
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0

FetchBytes = Callable[[str, dict[str, str], float], bytes]


def normalize_cik(cik: str | int) -> str:
    value = str(cik).strip()
    if not value.isdigit():
        raise ValueError(f"CIK must contain only digits: {cik!r}")
    if not 1 <= len(value) <= 10:
        raise ValueError(f"CIK must be 1 to 10 digits: {cik!r}")
    return value.zfill(10)


def _archive_cik_path(cik: str | int) -> str:
    return str(int(normalize_cik(cik)))


def _archive_accession_path(accession_number: str) -> str:
    value = accession_number.strip()
    if not value:
        raise ValueError("accession_number cannot be empty")
    return value.replace("-", "")


def build_submissions_url(cik: str | int) -> str:
    return f"{DATA_SEC_BASE_URL}/submissions/CIK{normalize_cik(cik)}.json"


def build_companyfacts_url(cik: str | int) -> str:
    return f"{DATA_SEC_BASE_URL}/api/xbrl/companyfacts/CIK{normalize_cik(cik)}.json"


def build_archive_index_url(cik: str | int, accession_number: str) -> str:
    cik_path = _archive_cik_path(cik)
    accession_path = _archive_accession_path(accession_number)
    return f"{ARCHIVES_BASE_URL}/{cik_path}/{accession_path}/index.json"


def build_primary_document_url(
    cik: str | int,
    accession_number: str,
    primary_document: str,
) -> str:
    document_name = primary_document.strip()
    if not document_name:
        raise ValueError("primary_document cannot be empty")
    cik_path = _archive_cik_path(cik)
    accession_path = _archive_accession_path(accession_number)
    return f"{ARCHIVES_BASE_URL}/{cik_path}/{accession_path}/{document_name}"


def build_request_headers(user_agent: str) -> dict[str, str]:
    value = user_agent.strip()
    if not value:
        raise ValueError("SEC requests require a non-empty user_agent")
    return {
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "User-Agent": value,
    }


def fetch_url_bytes(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


class SecEdgarFetchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ciks: tuple[str, ...] = ()
    include_forms: tuple[str, ...] = ()
    fetch_primary_documents: bool = False
    primary_document_limit: int = Field(default=1, ge=1)
    text_excerpt_chars: int = Field(default=500, ge=0, le=5000)
    user_agent: str | None = Field(default=None, min_length=1)
    request_timeout_seconds: float = Field(
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        gt=0,
    )


class SecEdgarAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        fetch_bytes: FetchBytes | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = SecEdgarFetchOptions.model_validate(self.options)
        self._fetch_bytes = fetch_bytes or fetch_url_bytes

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        ciks = tuple(normalize_cik(cik) for cik in self.fetch_options.ciks)
        if limit is not None:
            ciks = ciks[:limit]
        if not ciks:
            return AdapterBatch.failure(
                source_id=self.source.source_id,
                output_kind=self.source.output_kind,
                retrieved_at=retrieved_at,
                error=AdapterError(
                    code="missing_ciks",
                    message="SEC EDGAR fetch requires at least one CIK",
                    retryable=False,
                ),
            )

        user_agent = self._resolve_user_agent()
        if not user_agent:
            return AdapterBatch.failure(
                source_id=self.source.source_id,
                output_kind=self.source.output_kind,
                retrieved_at=retrieved_at,
                error=AdapterError(
                    code="missing_user_agent",
                    message=(
                        "SEC EDGAR fetch requires SEC_USER_AGENT or user_agent option"
                    ),
                    retryable=False,
                ),
            )

        if self.raw_dir is None:
            return AdapterBatch.failure(
                source_id=self.source.source_id,
                output_kind=self.source.output_kind,
                retrieved_at=retrieved_at,
                error=AdapterError(
                    code="missing_raw_dir",
                    message="SEC EDGAR fetch requires a raw_dir",
                    retryable=False,
                ),
            )

        headers = build_request_headers(user_agent)
        raw_store = RawStore(self.raw_dir)
        raw_uris: list[str] = []
        records: list[dict[str, JsonValue]] = []
        primary_documents_remaining = (
            self.fetch_options.primary_document_limit
            if self.fetch_options.fetch_primary_documents
            else 0
        )

        for cik in ciks:
            url = build_submissions_url(cik)
            try:
                content = self._fetch_bytes(
                    url,
                    headers,
                    self.fetch_options.request_timeout_seconds,
                )
                json.loads(content)
                result = raw_store.write_bytes(
                    Path(self.source.source_id) / cik / "submissions.json",
                    content,
                )
                raw_uris.append(result.raw_uri)
                from packages.ingestion.parsers.sec_submissions import (
                    DEFAULT_SEC_DOCUMENT_FORMS,
                    parse_sec_submissions_bytes,
                )

                include_forms = self.fetch_options.include_forms
                if not include_forms:
                    include_forms = DEFAULT_SEC_DOCUMENT_FORMS
                documents = parse_sec_submissions_bytes(
                    content,
                    raw_object_uri=result.raw_uri,
                    content_hash=result.content_hash,
                    retrieved_at=retrieved_at,
                    include_forms=include_forms,
                    source_id=self.source.source_id,
                )
                for document in documents:
                    record = document.model_dump(mode="json")
                    if primary_documents_remaining:
                        url = str(document.url)
                        html_content = self._fetch_bytes(
                            url,
                            headers,
                            self.fetch_options.request_timeout_seconds,
                        )
                        self._attach_primary_document_artifact(
                            record=record,
                            cik=cik,
                            content=html_content,
                            raw_store=raw_store,
                            raw_uris=raw_uris,
                        )
                        primary_documents_remaining -= 1
                    records.append(record)
            except HTTPError as exc:
                return self._failure(
                    code="http_error",
                    message=f"SEC EDGAR request failed with HTTP {exc.code}",
                    retrieved_at=retrieved_at,
                    retryable=exc.code == 429 or exc.code >= 500,
                    details={"status_code": exc.code, "url": url},
                )
            except (URLError, TimeoutError, OSError) as exc:
                return self._failure(
                    code="network_error",
                    message=f"SEC EDGAR request failed: {exc}",
                    retrieved_at=retrieved_at,
                    retryable=True,
                    details={"url": url},
                )
            except json.JSONDecodeError as exc:
                return self._failure(
                    code="invalid_json",
                    message=f"SEC EDGAR response was not valid JSON: {exc}",
                    retrieved_at=retrieved_at,
                    retryable=False,
                    details={"url": url},
                )

        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=records,
            raw_uris=raw_uris,
            retrieved_at=retrieved_at,
        )

    def _resolve_user_agent(self) -> str | None:
        if self.fetch_options.user_agent:
            return self.fetch_options.user_agent
        if self.source.user_agent_env:
            value = os.getenv(self.source.user_agent_env)
            if value:
                return value
        return None

    def _attach_primary_document_artifact(
        self,
        *,
        record: dict[str, JsonValue],
        cik: str,
        content: bytes,
        raw_store: RawStore,
        raw_uris: list[str],
    ) -> None:
        from packages.ingestion.parsers.sec_filing_html import extract_sec_filing_text

        metadata = record["metadata"]
        if not isinstance(metadata, dict):
            raise ValueError("SEC document records must include metadata")

        accession_number = str(metadata["accession_number"])
        primary_document = str(metadata["primary_document"])
        result = raw_store.write_bytes(
            Path(self.source.source_id)
            / cik
            / _archive_accession_path(accession_number)
            / primary_document,
            content,
        )
        raw_uris.append(result.raw_uri)
        metadata["primary_document_raw_uri"] = result.raw_uri
        metadata["primary_document_content_hash"] = result.content_hash

        if self.fetch_options.text_excerpt_chars:
            text = extract_sec_filing_text(content)
            excerpt = text[: self.fetch_options.text_excerpt_chars].strip()
            if excerpt:
                metadata["primary_document_text_excerpt"] = excerpt

    def _failure(
        self,
        *,
        code: str,
        message: str,
        retrieved_at: datetime,
        retryable: bool,
        details: dict[str, str | int],
    ) -> AdapterBatch:
        return AdapterBatch.failure(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=retrieved_at,
            error=AdapterError(
                code=code,
                message=message,
                retryable=retryable,
                details=details,
            ),
        )
