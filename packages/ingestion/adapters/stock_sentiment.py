from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from packages.core import (
    AttentionSignal,
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


class StockSentimentFetchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tickers: tuple[str, ...] = ()
    sources: tuple[str, ...] = ("reddit",)
    lookback: str = Field(default="24h", min_length=1)
    endpoint_template: str | None = None
    request_timeout_seconds: float = Field(default=20.0, gt=0)


class StockSentimentAdapter(BaseSourceAdapter):
    source_id = "stock_sentiment"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        fetch_json: FetchJson | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = StockSentimentFetchOptions.model_validate(self.options)
        self._fetch_json = fetch_json or _fetch_json_payload

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        tickers = (
            self.fetch_options.tickers[:limit] if limit else self.fetch_options.tickers
        )
        if not tickers:
            return self._failure(
                code="missing_tickers",
                message="Stock Sentiment fetch requires at least one ticker",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        if self.raw_dir is None:
            return self._failure(
                code="missing_raw_dir",
                message="Stock Sentiment fetch requires a raw_dir",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        try:
            api_key = required_env(self.source.api_key_env or "STOCK_SENTIMENT_API_KEY")
        except HttpAdapterError as exc:
            return self._from_http_error(exc, retrieved_at)

        raw_store = RawStore(self.raw_dir)
        records: list[dict[str, JsonValue]] = []
        raw_uris: list[str] = []
        for ticker in tickers:
            for signal_family in self.fetch_options.sources:
                url = self._endpoint(ticker=ticker, signal_family=signal_family)
                try:
                    payload = self._fetch_json(
                        url,
                        {"Authorization": f"Bearer {api_key}"},
                        self.fetch_options.request_timeout_seconds,
                    )
                except HttpAdapterError as exc:
                    return self._from_http_error(exc, retrieved_at)

                raw_bytes = json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
                raw_result = raw_store.write_bytes(
                    Path(self.source.source_id)
                    / ticker
                    / f"{signal_family}-{make_content_hash(url)[7:23]}.json",
                    raw_bytes,
                )
                raw_uris.append(raw_result.raw_uri)
                for metric_name, metric_value in _metrics(payload):
                    signal = AttentionSignal(
                        attention_signal_id=make_doc_id(
                            "attention",
                            self.source.source_id,
                            ticker,
                            signal_family,
                            metric_name,
                        ),
                        source_id=self.source.source_id,
                        source_type=SourceType.SOCIAL_SENTIMENT,
                        source_tier=SourceTier.ATTENTION_SIGNAL,
                        source_family_id=make_provider_family_id(self.source.source_id),
                        ticker=ticker,
                        signal_family=signal_family,
                        window_start=_parse_datetime(payload.get("window_start"))
                        or retrieved_at,
                        window_end=_parse_datetime(payload.get("window_end"))
                        or retrieved_at,
                        retrieved_at=retrieved_at,
                        metric_name=metric_name,
                        metric_value=metric_value,
                        sample_size=_sample_size(payload),
                        raw_object_uri=raw_result.raw_uri,
                        content_hash=raw_result.content_hash,
                        metadata={"lookback": self.fetch_options.lookback},
                    )
                    records.append(signal.model_dump(mode="json"))

        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=records,
            raw_uris=raw_uris,
            retrieved_at=retrieved_at,
        )

    def _endpoint(self, *, ticker: str, signal_family: str) -> str:
        template = self.fetch_options.endpoint_template
        if template is None:
            template = (
                "{base_url}/v1/{signal_family}/stocks/{ticker}?lookback={lookback}"
            )
        return template.format(
            base_url=str(self.source.base_url).rstrip("/"),
            ticker=quote(ticker),
            signal_family=quote(signal_family),
            lookback=quote(self.fetch_options.lookback),
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


def _metrics(payload: Mapping[str, Any]) -> list[tuple[str, float]]:
    metrics = payload.get("metrics", payload)
    if not isinstance(metrics, Mapping):
        return []
    skipped = {"sample_size", "window_start", "window_end"}
    return [
        (str(key), float(value))
        for key, value in metrics.items()
        if key not in skipped and isinstance(value, int | float)
    ]


def _sample_size(payload: Mapping[str, Any]) -> int | None:
    value = payload.get("sample_size")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
