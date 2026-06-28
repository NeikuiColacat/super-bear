from datetime import datetime, timezone
import json

from packages.core import OutputKind
from packages.ingestion.adapters.base import (
    AdapterBatch,
    AdapterError,
    BaseSourceAdapter,
)
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


class EmptySecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[],
            raw_uris=[],
        )


class InspectingSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        assert self.raw_dir is not None
        assert self.options["ciks"] == ["0000320193"]
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[],
            raw_uris=[
                str(
                    self.raw_dir
                    / "sec_edgar"
                    / "0000320193"
                    / "submissions.json"
                )
            ],
        )


class PreviewSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            retrieved_at=_ts(8, 1),
            records=[
                {
                    "doc_id": "sec:apple:10q",
                    "title": "Apple Inc. 10-Q filed 2026-05-01",
                    "url": "https://www.sec.gov/aapl-10q.htm",
                    "metadata": {"form": "10-Q"},
                },
                {
                    "doc_id": "sec:apple:8k",
                    "title": "Apple Inc. 8-K filed 2026-04-30",
                    "url": "https://www.sec.gov/aapl-8k.htm",
                    "metadata": {"form": "8-K"},
                },
            ],
            raw_uris=["data/raw/sec_edgar/0000320193/submissions.json"],
        )


def test_runner_executes_available_adapters_and_skips_unimplemented_sources(
    tmp_path,
) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": EmptySecAdapter},
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
        raw_dir=tmp_path / "raw",
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
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": EmptySecAdapter},
        source_ids=("sec_edgar",),
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert [source.source_id for source in result.manifest.sources] == ["sec_edgar"]


def test_runner_passes_raw_dir_and_source_options_to_adapter(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": InspectingSecAdapter},
        source_ids=("sec_edgar",),
        source_options={"sec_edgar": {"ciks": ["0000320193"]}},
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    assert result.manifest.sources[0].raw_uris == (
        str(tmp_path / "raw" / "sec_edgar" / "0000320193" / "submissions.json"),
    )


def test_runner_collects_cli_previews_from_current_batches(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    result = run_ingestion(
        registry=registry,
        normalized_dir=tmp_path / "normalized",
        raw_dir=tmp_path / "raw",
        runs_dir=tmp_path / "runs",
        run_id="run_20260628T080000Z",
        adapter_classes={"sec_edgar": PreviewSecAdapter},
        source_ids=("sec_edgar",),
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
    )

    preview = result.cli_previews[0]
    assert preview.source_id == "sec_edgar"
    assert preview.records_written == 2
    assert preview.output_path == str(tmp_path / "normalized" / "documents.jsonl")
    assert preview.raw_uris == ("data/raw/sec_edgar/0000320193/submissions.json",)
    assert preview.form_counts == {"10-Q": 1, "8-K": 1}
    assert [sample.title for sample in preview.samples] == [
        "Apple Inc. 10-Q filed 2026-05-01",
        "Apple Inc. 8-K filed 2026-04-30",
    ]


def test_runner_cli_uses_yaml_config_and_prints_summary(tmp_path, capsys) -> None:
    config_path = tmp_path / "ingestion_run.yaml"
    config_path.write_text(
        f"""
version: 1
source_registry_path: configs/sources.yaml
raw_dir: {tmp_path / "raw"}
normalized_dir: {tmp_path / "normalized"}
runs_dir: {tmp_path / "runs"}
default_limit: null
enabled_source_ids:
  - sec_edgar
  - tavily
skip_unimplemented_adapters: true
source_options:
  sec_edgar:
    ciks:
      - "0000320193"
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
            "tavily",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "CLI preview" in captured.out
    assert "run_id: run_20260628T080000Z" in captured.out
    expected_manifest = tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json"
    assert f"manifest: {expected_manifest}" in captured.out
    assert (
        "- tavily: skipped, records_written=0, "
        "skipped_reason=adapter_not_implemented"
    ) in captured.out

    payload = json.loads(
        (tmp_path / "runs" / "run_20260628T080000Z" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert [source["source_id"] for source in payload["sources"]] == ["tavily"]
