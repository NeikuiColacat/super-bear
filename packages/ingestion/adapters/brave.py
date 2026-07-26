from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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
from .http import HttpAdapterError, fetch_json, required_env


FetchJson = Callable[[str, dict[str, str], float], dict[str, Any]]


class BraveFetchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    queries: tuple[str, ...] = ()
    count: int = Field(default=5, ge=1, le=20)
    freshness: str | None = None
    text_decorations: bool = False
    request_timeout_seconds: float = Field(default=20.0, gt=0)


class BraveSearchAdapter(BaseSourceAdapter):
    source_id = "brave_search"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        fetch_json: FetchJson | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = BraveFetchOptions.model_validate(self.options)
        self._fetch_json = fetch_json or _fetch_json_payload

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        queries = (
            self.fetch_options.queries[:limit] if limit else self.fetch_options.queries
        )
        if not queries:
            return self._failure(
                code="missing_queries",
                message="Brave Search fetch requires at least one query",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        if self.raw_dir is None:
            return self._failure(
                code="missing_raw_dir",
                message="Brave Search fetch requires a raw_dir",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        try:
            api_key = required_env(self.source.api_key_env or "BRAVE_SEARCH_API_KEY")
        except HttpAdapterError as exc:
            return self._from_http_error(exc, retrieved_at)

        raw_store = RawStore(self.raw_dir)
        records: list[dict[str, JsonValue]] = []
        raw_uris: list[str] = []
        for query in queries:
            url = _search_url(
                str(self.source.base_url).rstrip("/"),
                query=query,
                count=self.fetch_options.count,
                freshness=self.fetch_options.freshness,
                text_decorations=self.fetch_options.text_decorations,
            )
            try:
                payload = self._fetch_json(
                    url,
                    {
                        "Accept": "application/json",
                        "X-Subscription-Token": api_key,
                    },
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
            for rank, item in enumerate(_items(payload), start=1):
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


def _fetch_json_payload(
    url: str,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    response, _metadata = fetch_json(
        url,
        headers=headers,
        timeout_seconds=timeout,
    )
    return response


def _search_url(
    base_url: str,
    *,
    query: str,
    count: int,
    freshness: str | None,
    text_decorations: bool,
) -> str:
    params: dict[str, str | int] = {
        "q": query,
        "count": count,
        "text_decorations": str(text_decorations).lower(),
    }
    if freshness:
        params["freshness"] = freshness
    return f"{base_url}/res/v1/web/search?{urlencode(params)}"


def _items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    web = payload.get("web")
    if not isinstance(web, Mapping):
        return []
    value = web.get("results", [])
    return [item for item in value if isinstance(item, Mapping)]


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
    snippet = str(item.get("description") or item.get("content") or "").strip()
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
        retrieved_at=retrieved_at,
        rank=rank,
        raw_object_uri=raw_object_uri,
        content_hash=content_hash,
        metadata={"provider": source_id, "age": str(item.get("age") or "")},
    )
