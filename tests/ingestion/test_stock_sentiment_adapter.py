import json

from packages.core import OutputKind, SourceTier, SourceType
from packages.ingestion.adapters.stock_sentiment import StockSentimentAdapter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.runner import run_ingestion


def _registry() -> SourceRegistry:
    return SourceRegistry.from_yaml("configs/sources.yaml")


def test_stock_sentiment_requires_api_key_before_network(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("STOCK_SENTIMENT_API_KEY", raising=False)
    adapter = StockSentimentAdapter(
        _registry().get("stock_sentiment"),
        raw_dir=tmp_path / "raw",
        options={"tickers": ["NVDA"], "sources": ["reddit"]},
        fetch_json=lambda url, headers, timeout: (_ for _ in ()).throw(
            AssertionError("network should not run")
        ),
    )

    batch = adapter.fetch()

    assert batch.ok is False
    assert batch.error is not None
    assert batch.error.code == "missing_api_key"


def test_stock_sentiment_maps_metrics_to_attention_signals(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("STOCK_SENTIMENT_API_KEY", "secret")

    def fake_fetch(
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        assert "NVDA" in url
        assert headers["Authorization"] == "Bearer secret"
        return {
            "window_start": "2026-06-28T00:00:00Z",
            "window_end": "2026-06-29T00:00:00Z",
            "sample_size": 128,
            "metrics": {
                "mentions": 128,
                "sentiment_score": 0.71,
            },
        }

    adapter = StockSentimentAdapter(
        _registry().get("stock_sentiment"),
        raw_dir=tmp_path / "raw",
        options={"tickers": ["NVDA"], "sources": ["reddit"], "lookback": "24h"},
        fetch_json=fake_fetch,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert batch.output_kind is OutputKind.ATTENTION_SIGNAL
    assert len(batch.records) == 2
    first = batch.records[0]
    assert first["source_type"] == SourceType.SOCIAL_SENTIMENT
    assert first["source_tier"] == SourceTier.ATTENTION_SIGNAL
    assert first["source_family_id"] == "provider:stock_sentiment"
    assert first["ticker"] == "NVDA"
    assert first["signal_family"] == "reddit"
    assert first["metric_name"] == "mentions"
    assert first["sample_size"] == 128


def test_stock_sentiment_runner_does_not_create_ledger_outputs(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("STOCK_SENTIMENT_API_KEY", "secret")

    class FakeStockSentimentAdapter(StockSentimentAdapter):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(
                *args,
                **kwargs,
                fetch_json=lambda url, headers, timeout: {
                    "metrics": {"mentions": 128},
                    "sample_size": 128,
                },
            )

    result = run_ingestion(
        registry=_registry(),
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260629T120000Z",
        adapter_classes={"stock_sentiment": FakeStockSentimentAdapter},
        source_ids=("stock_sentiment",),
        source_options={
            "stock_sentiment": {"tickers": ["NVDA"], "sources": ["reddit"]}
        },
        write_ledger=True,
        write_events=True,
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "normalized" / "attention_signals.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert result.manifest.sources[0].derived_outputs == ()
    assert rows[0]["source_id"] == "stock_sentiment"
    assert not (tmp_path / "normalized" / "claims.jsonl").exists()
