from datetime import datetime, timezone
import json

from packages.core import OutputKind
from packages.ingestion.adapters.base import AdapterBatch, AdapterError, BaseSourceAdapter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.runner import main, run_ingestion


def _ts(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 28, hour, minute, tzinfo=timezone.utc)


class FailingSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.failure(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            error=AdapterError(
                code="network_timeout",
                message="SEC request timed out",
                retryable=True,
            ),
        )


def test_runner_executes_available_adapters_and_skips_unimplemented_sources(
    tmp_path,
) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert result.manifest.run_id == "run_20260628T080000Z"
    assert result.manifest_path == (
        tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json"
    )
    assert [source.source_id for source in result.manifest.sources] == [
        "sec_edgar",
        "company_ir",
        "yfinance",
        "tavily",
        "brave_search",
        "stock_sentiment",
    ]

    sec = result.manifest.sources[0]
    assert sec.status == "success"
    assert sec.records_seen == 0
    assert sec.records_written == 0
    assert sec.skipped_reason == "no_records"
    assert sec.output_path == str(tmp_path / "normalized" / "documents.jsonl")

    skipped = result.manifest.sources[1:]
    assert {source.status for source in skipped} == {"skipped"}
    assert {source.skipped_reason for source in skipped} == {"adapter_not_implemented"}

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["sources"][0]["source_id"] == "sec_edgar"
    assert payload["sources"][0]["status"] == "success"
    assert payload["sources"][1]["status"] == "skipped"


def test_runner_records_failed_adapter_batch(tmp_path) -> None:
    registry = SourceRegistry.from_items(
        [
            {
                "source_id": "sec_edgar",
                "enabled": True,
                "adapter": "sec_edgar",
                "output_kind": "document",
                "default_source_type": "sec_filing",
                "allowed_source_types": ["sec_filing"],
                "source_tier": "regulatory_primary",
                "source_family_strategy": "issuer",
                "requires_api_key": False,
                "rate_limit_per_second": 8,
                "license_notes": "test source",
            }
        ]
    )

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": FailingSecAdapter},
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    source_result = result.manifest.sources[0]
    assert source_result.status == "failed"
    assert source_result.records_seen == 0
    assert source_result.records_written == 0
    assert source_result.output_kind is OutputKind.DOCUMENT
    assert source_result.error is not None
    assert source_result.error.code == "network_timeout"
    assert source_result.skipped_reason == "batch_failed"


def test_runner_can_limit_sources_from_run_config(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        source_ids=("sec_edgar",),
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert [source.source_id for source in result.manifest.sources] == ["sec_edgar"]


def test_runner_cli_uses_yaml_config_and_prints_summary(tmp_path, capsys) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        f"""
version: 1
source_registry_path: configs/sources.yaml
normalized_dir: {tmp_path / "normalized"}
runs_dir: {tmp_path / "runs"}
default_limit: null
enabled_source_ids:
  - sec_edgar
  - tavily
skip_unimplemented_adapters: true
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--run-id",
            "run_20260628T080000Z",
            "--source",
            "sec_edgar",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "run_id: run_20260628T080000Z" in captured.out
    assert f"manifest: {tmp_path / 'runs' / 'run_20260628T080000Z' / 'manifest.json'}" in captured.out
    assert "- sec_edgar: success, records_written=0, skipped_reason=no_records" in captured.out

    payload = json.loads(
        (tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert [source["source_id"] for source in payload["sources"]] == ["sec_edgar"]
