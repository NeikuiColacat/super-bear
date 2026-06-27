from datetime import datetime, timezone
import json

from packages.core import OutputKind
from packages.ingestion.adapters.base import AdapterBatch, AdapterError
from packages.ingestion.jsonl_writer import JsonlWriter


def _retrieved_at() -> datetime:
    return datetime(2026, 6, 27, 8, 30, tzinfo=timezone.utc)


def test_jsonl_writer_maps_output_kinds_to_normalized_files(tmp_path) -> None:
    writer = JsonlWriter(tmp_path)

    assert writer.output_path_for(OutputKind.DOCUMENT) == tmp_path / "documents.jsonl"
    assert (
        writer.output_path_for(OutputKind.MARKET_CONTEXT)
        == tmp_path / "market_context.jsonl"
    )
    assert writer.output_path_for(OutputKind.SEARCH_LEAD) == tmp_path / "search_leads.jsonl"
    assert (
        writer.output_path_for(OutputKind.ATTENTION_SIGNAL)
        == tmp_path / "attention_signals.jsonl"
    )


def test_jsonl_writer_writes_successful_records_as_one_json_object_per_line(tmp_path) -> None:
    writer = JsonlWriter(tmp_path)
    batch = AdapterBatch.success(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        retrieved_at=_retrieved_at(),
        records=[
            {
                "doc_id": "sec:0000320193:0000320193-26-000013",
                "source_id": "sec_edgar",
                "title": "Apple 10-Q",
            },
            {
                "doc_id": "sec:0000320193:0000320193-26-000014",
                "source_id": "sec_edgar",
                "title": "Apple 8-K",
            },
        ],
        raw_uris=["data/raw/sec_edgar/submissions.json"],
    )

    result = writer.write_batch(batch)

    assert result.source_id == "sec_edgar"
    assert result.output_kind is OutputKind.DOCUMENT
    assert result.output_path == tmp_path / "documents.jsonl"
    assert result.records_written == 2
    assert result.skipped_reason is None

    lines = (tmp_path / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["doc_id"] for line in lines] == [
        "sec:0000320193:0000320193-26-000013",
        "sec:0000320193:0000320193-26-000014",
    ]


def test_jsonl_writer_appends_without_overwriting_existing_records(tmp_path) -> None:
    writer = JsonlWriter(tmp_path)

    first = AdapterBatch.success(
        source_id="tavily",
        output_kind=OutputKind.SEARCH_LEAD,
        retrieved_at=_retrieved_at(),
        records=[{"lead_id": "lead-1", "title": "first"}],
    )
    second = AdapterBatch.success(
        source_id="tavily",
        output_kind=OutputKind.SEARCH_LEAD,
        retrieved_at=_retrieved_at(),
        records=[{"lead_id": "lead-2", "title": "second"}],
    )

    writer.write_batch(first)
    writer.write_batch(second)

    lines = (tmp_path / "search_leads.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["lead_id"] for line in lines] == ["lead-1", "lead-2"]


def test_jsonl_writer_skips_failed_batches(tmp_path) -> None:
    writer = JsonlWriter(tmp_path)
    batch = AdapterBatch.failure(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        retrieved_at=_retrieved_at(),
        error=AdapterError(
            code="network_timeout",
            message="SEC request timed out",
            retryable=True,
        ),
    )

    result = writer.write_batch(batch)

    assert result.records_written == 0
    assert result.output_path is None
    assert result.skipped_reason == "batch_failed"
    assert not (tmp_path / "documents.jsonl").exists()


def test_jsonl_writer_skips_empty_success_batches(tmp_path) -> None:
    writer = JsonlWriter(tmp_path)
    batch = AdapterBatch.success(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        retrieved_at=_retrieved_at(),
        records=[],
    )

    result = writer.write_batch(batch)

    assert result.records_written == 0
    assert result.output_path == tmp_path / "documents.jsonl"
    assert result.skipped_reason == "no_records"
    assert not (tmp_path / "documents.jsonl").exists()
