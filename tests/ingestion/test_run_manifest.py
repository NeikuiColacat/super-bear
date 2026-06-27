from datetime import datetime, timezone
import json

import pytest
from pydantic import ValidationError

from packages.core import OutputKind
from packages.ingestion.adapters.base import AdapterBatch, AdapterError
from packages.ingestion.jsonl_writer import JsonlWriteResult
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.run_manifest import (
    RunManifest,
    RunManifestWriter,
    RunSourceResult,
    RunSourceStatus,
)


def _ts(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 27, hour, minute, tzinfo=timezone.utc)


def test_source_run_result_records_successful_adapter_batch() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    source = registry.get("sec_edgar")
    batch = AdapterBatch.success(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        retrieved_at=_ts(8, 1),
        records=[{"doc_id": "sec:0000320193:0000320193-26-000013"}],
        raw_uris=["data/raw/sec_edgar/0000320193/submissions.json"],
    )
    write_result = JsonlWriteResult(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        output_path="data/normalized/documents.jsonl",
        records_written=1,
    )

    result = RunSourceResult.from_batch(
        source=source,
        batch=batch,
        write_result=write_result,
    )

    assert result.source_id == "sec_edgar"
    assert result.adapter == "sec_edgar"
    assert result.output_kind is OutputKind.DOCUMENT
    assert result.status is RunSourceStatus.SUCCESS
    assert result.records_seen == 1
    assert result.records_written == 1
    assert result.output_path == "data/normalized/documents.jsonl"
    assert result.raw_uris == ("data/raw/sec_edgar/0000320193/submissions.json",)
    assert result.error is None


def test_source_run_result_records_failed_adapter_batch_without_output() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    source = registry.get("sec_edgar")
    error = AdapterError(
        code="network_timeout",
        message="SEC request timed out",
        retryable=True,
    )
    batch = AdapterBatch.failure(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        retrieved_at=_ts(8, 1),
        error=error,
    )
    write_result = JsonlWriteResult(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        output_path=None,
        records_written=0,
        skipped_reason="batch_failed",
    )

    result = RunSourceResult.from_batch(
        source=source,
        batch=batch,
        write_result=write_result,
    )

    assert result.status is RunSourceStatus.FAILED
    assert result.records_seen == 0
    assert result.records_written == 0
    assert result.output_path is None
    assert result.error == error
    assert result.skipped_reason == "batch_failed"


def test_run_manifest_writer_persists_auditable_json(tmp_path) -> None:
    manifest = RunManifest(
        run_id="run_20260627T080000Z",
        started_at=_ts(8, 0),
        finished_at=_ts(8, 2),
        sources=(
            RunSourceResult.skipped(
                source_id="tavily",
                adapter="tavily_search",
                output_kind=OutputKind.SEARCH_LEAD,
                skipped_reason="adapter_not_implemented",
            ),
        ),
    )

    output_path = RunManifestWriter(tmp_path).write(manifest)

    assert output_path == tmp_path / "run_20260627T080000Z" / "manifest.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run_20260627T080000Z"
    assert payload["started_at"] == "2026-06-27T08:00:00Z"
    assert payload["finished_at"] == "2026-06-27T08:02:00Z"
    assert payload["sources"][0]["status"] == "skipped"
    assert payload["sources"][0]["skipped_reason"] == "adapter_not_implemented"


def test_run_manifest_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        RunManifest(
            run_id="run_20260627T080000Z",
            started_at=datetime(2026, 6, 27, 8, 0),
            finished_at=_ts(8, 2),
            sources=(),
        )
