from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from packages.core import (
    SearchLead,
    SourceTier,
    SourceType,
    make_content_hash,
    make_doc_id,
    make_provider_family_id,
)
from packages.ingestion.raw_store import RawStore
from packages.ingestion.registry import SourceConfig

from .base import AdapterBatch, AdapterError, BaseSourceAdapter
from .http import HttpAdapterError, post_json, required_env


PostJson = Callable[[str, dict[str, str], dict[str, object], float], dict[str, Any]]


class TavilyFetchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    queries: tuple[str, ...] = ()
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: str = Field(default="basic", pattern=r"^(basic|advanced)$")
    include_raw_content: bool = False
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()
    request_timeout_seconds: float = Field(default=20.0, gt=0)


class TavilySearchAdapter(BaseSourceAdapter):
    source_id = "tavily"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        post_json: PostJson | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = TavilyFetchOptions.model_validate(self.options)
        self._post_json = post_json or _post_json_payload

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        queries = (
            self.fetch_options.queries[:limit] if limit else self.fetch_options.queries
        )
        if not queries:
            return self._failure(
                code="missing_queries",
                message="Tavily fetch requires at least one query",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        if self.raw_dir is None:
            return self._failure(
                code="missing_raw_dir",
                message="Tavily fetch requires a raw_dir",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        try:
            api_key = required_env(self.source.api_key_env or "TAVILY_API_KEY")
        except HttpAdapterError as exc:
            return self._from_http_error(exc, retrieved_at)

        raw_store = RawStore(self.raw_dir)
        records: list[dict[str, JsonValue]] = []
        raw_uris: list[str] = []
        endpoint = f"{str(self.source.base_url).rstrip('/')}/search"
        for query in queries:
            try:
                payload = self._post_json(
                    endpoint,
                    {"Authorization": f"Bearer {api_key}"},
                    self._payload(query),
                    self.fetch_options.request_timeout_seconds,
                )
            except HttpAdapterError as exc:
                return self._from_http_error(exc, retrieved_at)

            raw_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
            raw_result = raw_store.write_bytes(
                Path(self.source.source_id) / f"{make_content_hash(query)[7:23]}.json",
                raw_bytes,
            )
            raw_uris.append(raw_result.raw_uri)
            items = [
                item for item in _items(payload) if self._is_allowed_item_url(item)
            ]
            for rank, item in enumerate(items, start=1):
                lead = _lead_from_item(
                    source_id=self.source.source_id,
                    query=query,
                    rank=rank,
                    item=item,
                    raw_object_uri=raw_result.raw_uri,
                    content_hash=raw_result.content_hash,
                    retrieved_at=retrieved_at,
                )
                if lead is not None:
                    records.append(lead.model_dump(mode="json"))

        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=records,
            raw_uris=raw_uris,
            retrieved_at=retrieved_at,
        )

    def _from_http_error(
        self,
        exc: HttpAdapterError,
        retrieved_at: datetime,
    ) -> AdapterBatch:
        return AdapterBatch.failure(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=retrieved_at,
            error=exc.error,
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

    def _payload(self, query: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "query": query,
            "max_results": self.fetch_options.max_results,
            "search_depth": self.fetch_options.search_depth,
            "include_raw_content": self.fetch_options.include_raw_content,
        }
        if self.fetch_options.include_domains:
            payload["include_domains"] = list(self.fetch_options.include_domains)
        if self.fetch_options.exclude_domains:
            payload["exclude_domains"] = list(self.fetch_options.exclude_domains)
        return payload

    def _is_allowed_item_url(self, item: Mapping[str, Any]) -> bool:
        url = str(item.get("url") or "").strip()
        if not url:
            return False
        host = _normalized_host(url)
        if not host:
            return False
        include_domains = self.fetch_options.include_domains
        if include_domains and not _host_matches_any(host, include_domains):
            return False
        exclude_domains = self.fetch_options.exclude_domains
        return not (exclude_domains and _host_matches_any(host, exclude_domains))


def _post_json_payload(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, Any]:
    response, _metadata = post_json(
        url,
        headers=headers,
        payload=payload,
        timeout_seconds=timeout,
    )
    return response


def _items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = payload.get("results", [])
    return [item for item in value if isinstance(item, Mapping)]


def _normalized_host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _host_matches_any(host: str, domains: tuple[str, ...]) -> bool:
    normalized_domains = tuple(
        domain.strip().lower().removeprefix("www.")
        for domain in domains
        if domain.strip()
    )
    return any(
        host == domain or host.endswith(f".{domain}") for domain in normalized_domains
    )


def _lead_from_item(
    *,
    source_id: str,
    query: str,
    rank: int,
    item: Mapping[str, Any],
    raw_object_uri: str,
    content_hash: str,
    retrieved_at: datetime,
) -> SearchLead | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or "").strip()
    snippet = str(item.get("content") or item.get("description") or "").strip()
    if not title or not url or not snippet:
        return None
    return SearchLead(
        search_lead_id=make_doc_id("search", source_id, query, str(rank)),
        source_id=source_id,
        source_type=SourceType.SEARCH,
        source_tier=SourceTier.SEARCH_LEAD,
        source_family_id=make_provider_family_id(source_id),
        query=query,
        title=title,
        url=url,
        snippet=snippet,
        published_at=_parse_datetime(item.get("published_date")),
        retrieved_at=retrieved_at,
        score=_optional_float(item.get("score")),
        rank=rank,
        raw_object_uri=raw_object_uri,
        content_hash=content_hash,
        metadata={"provider": source_id},
    )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
