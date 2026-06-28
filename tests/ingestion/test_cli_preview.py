from packages.core import OutputKind
from packages.ingestion.cli_preview import (
    CliSourcePreview,
    build_cli_preview,
    format_cli_preview,
)
from packages.ingestion.run_manifest import RunDerivedOutput, RunSourceResult


def test_build_cli_preview_summarizes_current_document_records() -> None:
    source_result = RunSourceResult(
        source_id="sec_edgar",
        adapter="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        status="success",
        records_seen=3,
        records_written=3,
        raw_uris=("data/raw/sec_edgar/0000320193/submissions.json",),
        output_path="data/normalized/documents.jsonl",
    )

    preview = build_cli_preview(
        source_result,
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
            {
                "doc_id": "sec:apple:8k-2",
                "title": "Apple Inc. 8-K filed 2026-04-20",
                "url": "https://www.sec.gov/aapl-8k-2.htm",
                "metadata": {"form": "8-K"},
            },
        ],
        sample_limit=2,
    )

    assert preview.source_id == "sec_edgar"
    assert preview.status == "success"
    assert preview.records_written == 3
    assert preview.raw_uris == ("data/raw/sec_edgar/0000320193/submissions.json",)
    assert preview.output_path == "data/normalized/documents.jsonl"
    assert preview.form_counts == {"8-K": 2, "10-Q": 1}
    assert [sample.title for sample in preview.samples] == [
        "Apple Inc. 10-Q filed 2026-05-01",
        "Apple Inc. 8-K filed 2026-04-30",
    ]


def test_format_cli_preview_prints_source_summary() -> None:
    output = format_cli_preview(
        run_id="run_20260628T080000Z",
        manifest_path="data/runs/run_20260628T080000Z/manifest.json",
        previews=[
            CliSourcePreview(
                source_id="sec_edgar",
                status="success",
                output_kind=OutputKind.DOCUMENT,
                records_written=3,
                raw_uris=("data/raw/sec_edgar/0000320193/submissions.json",),
                output_path="data/normalized/documents.jsonl",
                form_counts={"8-K": 2, "10-Q": 1},
                samples=(
                    {
                        "doc_id": "sec:apple:10q",
                        "title": "Apple Inc. 10-Q filed 2026-05-01",
                        "url": "https://www.sec.gov/aapl-10q.htm",
                    },
                ),
            ),
            CliSourcePreview(
                source_id="tavily",
                status="skipped",
                output_kind=OutputKind.SEARCH_LEAD,
                records_written=0,
                skipped_reason="adapter_not_implemented",
            ),
        ],
    )

    assert "CLI preview" in output
    assert "run_id: run_20260628T080000Z" in output
    assert "manifest: data/runs/run_20260628T080000Z/manifest.json" in output
    assert "- sec_edgar: success, records_written=3" in output
    assert "raw:" in output
    assert "data/raw/sec_edgar/0000320193/submissions.json" in output
    assert "forms:" in output
    assert "8-K: 2" in output
    assert "10-Q: 1" in output
    assert "samples:" in output
    assert "Apple Inc. 10-Q filed 2026-05-01" in output
    assert (
        "- tavily: skipped, records_written=0, "
        "skipped_reason=adapter_not_implemented"
    ) in output


def test_cli_preview_summarizes_derived_document_chunks() -> None:
    source_result = RunSourceResult(
        source_id="sec_edgar",
        adapter="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        status="success",
        records_seen=1,
        records_written=1,
        output_path="data/normalized/documents.jsonl",
        derived_outputs=(
            RunDerivedOutput(
                output_kind=OutputKind.DOCUMENT_CHUNK,
                output_path="data/normalized/document_chunks.jsonl",
                records_written=2,
            ),
            RunDerivedOutput(
                output_kind=OutputKind.CLAIM,
                output_path="data/normalized/claims.jsonl",
                records_written=1,
            ),
            RunDerivedOutput(
                output_kind=OutputKind.EVIDENCE_SPAN,
                output_path="data/normalized/evidence_spans.jsonl",
                records_written=1,
            ),
            RunDerivedOutput(
                output_kind=OutputKind.EVENT,
                output_path="data/normalized/events.jsonl",
                records_written=1,
            ),
            RunDerivedOutput(
                output_kind=OutputKind.VALIDATION_ERROR,
                output_path="data/normalized/validation_errors.jsonl",
                records_written=0,
                skipped_reason="no_records",
            ),
        ),
    )

    preview = build_cli_preview(
        source_result,
        records=[
            {
                "doc_id": "sec:apple:10q",
                "title": "Apple Inc. 10-Q filed 2026-05-01",
                "metadata": {"form": "10-Q"},
            },
        ],
        chunk_records=[
            {
                "chunk_id": "sec:apple:10q:chunk:000000",
                "doc_id": "sec:apple:10q",
                "text": "Apple reported quarterly results.",
            }
        ],
    )

    output = format_cli_preview(
        run_id="run_20260628T080000Z",
        manifest_path="data/runs/run_20260628T080000Z/manifest.json",
        previews=[preview],
    )

    assert preview.derived_outputs[0].records_written == 2
    assert preview.chunk_samples[0].text == "Apple reported quarterly results."
    assert "derived:" in output
    assert "document_chunk: records_written=2" in output
    assert "claim: records_written=1" in output
    assert "evidence_span: records_written=1" in output
    assert "event: records_written=1" in output
    assert "validation_error: records_written=0, skipped_reason=no_records" in output
    assert "chunk samples:" in output
    assert "Apple reported quarterly results." in output
