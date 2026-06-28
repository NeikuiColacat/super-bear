from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from packages.core import (
    MarketContext,
    MarketDataRow,
    SourceTier,
    SourceType,
    make_doc_id,
    make_provider_family_id,
)
from packages.ingestion.raw_store import RawStore
from packages.ingestion.registry import SourceConfig

from .base import AdapterBatch, AdapterError, BaseSourceAdapter


TickerFactory = Callable[[str], Any]


class YFinanceFetchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tickers: tuple[str, ...] = ()
    period: str = Field(default="5d", min_length=1)
    interval: str = Field(default="1d", min_length=1)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class YFinanceAdapter(BaseSourceAdapter):
    source_id = "yfinance"

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, object] | None = None,
        ticker_factory: TickerFactory | None = None,
    ) -> None:
        super().__init__(source, raw_dir=raw_dir, options=options)
        self.fetch_options = YFinanceFetchOptions.model_validate(self.options)
        self._ticker_factory = ticker_factory or _default_ticker_factory

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        retrieved_at = datetime.now(timezone.utc)
        tickers = (
            self.fetch_options.tickers[:limit] if limit else self.fetch_options.tickers
        )
        if not tickers:
            return self._failure(
                code="missing_tickers",
                message="YFinance fetch requires at least one ticker",
                retrieved_at=retrieved_at,
                retryable=False,
            )
        if self.raw_dir is None:
            return self._failure(
                code="missing_raw_dir",
                message="YFinance fetch requires a raw_dir",
                retrieved_at=retrieved_at,
                retryable=False,
            )

        raw_store = RawStore(self.raw_dir)
        records: list[dict[str, JsonValue]] = []
        raw_uris: list[str] = []
        skipped: list[str] = []

        for ticker in tickers:
            try:
                history = self._ticker_factory(ticker).history(
                    period=self.fetch_options.period,
                    interval=self.fetch_options.interval,
                    actions=True,
                )
            except Exception as exc:  # pragma: no cover - provider-specific failures
                return self._failure(
                    code="market_fetch_error",
                    message=f"YFinance fetch failed for {ticker}: {exc}",
                    retrieved_at=retrieved_at,
                    retryable=True,
                )
            rows = _market_rows(history)
            if not rows:
                skipped.append(ticker)
                continue

            row_payload = [row.model_dump(mode="json") for row in rows]
            raw_payload = json.dumps(
                {
                    "ticker": ticker,
                    "period": self.fetch_options.period,
                    "interval": self.fetch_options.interval,
                    "rows": row_payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            raw_result = raw_store.write_bytes(
                Path(self.source.source_id) / ticker / "history.json",
                raw_payload,
            )
            raw_uris.append(raw_result.raw_uri)
            context = MarketContext(
                market_context_id=make_doc_id(
                    "market",
                    self.source.source_id,
                    ticker,
                    self.fetch_options.period,
                    self.fetch_options.interval,
                ),
                source_id=self.source.source_id,
                source_type=SourceType.MARKET_DATA,
                source_tier=SourceTier.MARKET_CONTEXT,
                source_family_id=make_provider_family_id(self.source.source_id),
                ticker=ticker,
                window_start=rows[0].timestamp,
                window_end=rows[-1].timestamp,
                retrieved_at=retrieved_at,
                interval=self.fetch_options.interval,
                currency=self.fetch_options.currency,
                rows=tuple(rows),
                raw_object_uri=raw_result.raw_uri,
                content_hash=raw_result.content_hash,
                metadata={"period": self.fetch_options.period, "skipped": skipped},
            )
            records.append(context.model_dump(mode="json"))

        if not records:
            return self._failure(
                code="empty_market_history",
                message="YFinance returned no market history",
                retrieved_at=retrieved_at,
                retryable=False,
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


def _default_ticker_factory(ticker: str) -> Any:
    import yfinance

    return yfinance.Ticker(ticker)


def _market_rows(history: Any) -> list[MarketDataRow]:
    if getattr(history, "empty", True):
        return []
    rows: list[MarketDataRow] = []
    for timestamp, row in history.iterrows():
        dt = timestamp.to_pydatetime()
        if dt.tzinfo is None or dt.utcoffset() is None:
            dt = dt.replace(tzinfo=timezone.utc)
        rows.append(
            MarketDataRow(
                timestamp=dt.astimezone(timezone.utc),
                open=float(row.get("Open", 0) or 0),
                high=float(row.get("High", 0) or 0),
                low=float(row.get("Low", 0) or 0),
                close=float(row.get("Close", 0) or 0),
                volume=int(row.get("Volume", 0) or 0),
                dividends=float(row.get("Dividends", 0) or 0),
                stock_splits=float(row.get("Stock Splits", 0) or 0),
            )
        )
    return rows
