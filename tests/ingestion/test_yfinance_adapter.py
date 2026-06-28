from datetime import datetime, timezone
import json

import pandas as pd

from packages.core import OutputKind, SourceTier, SourceType
from packages.ingestion.adapters.yfinance import YFinanceAdapter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.runner import run_ingestion


class _FakeTicker:
    def __init__(self, ticker: str) -> None:
        self.ticker = ticker

    def history(self, *, period: str, interval: str, actions: bool) -> pd.DataFrame:
        assert period == "5d"
        assert interval == "1d"
        assert actions is True
        if self.ticker == "EMPTY":
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "Open": [100.0],
                "High": [103.0],
                "Low": [99.0],
                "Close": [102.0],
                "Volume": [123456],
                "Dividends": [0.0],
                "Stock Splits": [0.0],
            },
            index=pd.DatetimeIndex(
                [datetime(2026, 6, 29, tzinfo=timezone.utc)],
                name="Date",
            ),
        )


def _registry() -> SourceRegistry:
    return SourceRegistry.from_yaml("configs/sources.yaml")


def test_yfinance_adapter_writes_market_context_records(tmp_path) -> None:
    adapter = YFinanceAdapter(
        _registry().get("yfinance"),
        raw_dir=tmp_path / "raw",
        options={"tickers": ["AAPL"], "period": "5d", "interval": "1d"},
        ticker_factory=_FakeTicker,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert batch.output_kind is OutputKind.MARKET_CONTEXT
    assert len(batch.records) == 1
    record = batch.records[0]
    assert record["source_type"] == SourceType.MARKET_DATA
    assert record["source_tier"] == SourceTier.MARKET_CONTEXT
    assert record["source_family_id"] == "provider:yfinance"
    assert record["ticker"] == "AAPL"
    assert record["rows"][0]["close"] == 102.0
    assert batch.raw_uris[0].endswith(".json")


def test_yfinance_adapter_handles_empty_history(tmp_path) -> None:
    adapter = YFinanceAdapter(
        _registry().get("yfinance"),
        raw_dir=tmp_path / "raw",
        options={"tickers": ["EMPTY"], "period": "5d", "interval": "1d"},
        ticker_factory=_FakeTicker,
    )

    batch = adapter.fetch()

    assert batch.ok is False
    assert batch.error is not None
    assert batch.error.code == "empty_market_history"


def test_yfinance_runner_does_not_create_document_derived_outputs(tmp_path) -> None:
    class FakeYFinanceAdapter(YFinanceAdapter):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs, ticker_factory=_FakeTicker)

    result = run_ingestion(
        registry=_registry(),
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260629T100000Z",
        adapter_classes={"yfinance": FakeYFinanceAdapter},
        source_ids=("yfinance",),
        source_options={
            "yfinance": {"tickers": ["AAPL"], "period": "5d", "interval": "1d"}
        },
        write_ledger=True,
        write_events=True,
    )

    source = result.manifest.sources[0]
    rows = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "market_context.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert source.status == "success"
    assert source.derived_outputs == ()
    assert rows[0]["ticker"] == "AAPL"
    assert not (tmp_path / "normalized" / "claims.jsonl").exists()
