from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from packages.core import OutputKind
from packages.ingestion.adapters.base import AdapterBatch


_OUTPUT_FILES = {
    OutputKind.DOCUMENT: "documents.jsonl",
    OutputKind.DOCUMENT_CHUNK: "document_chunks.jsonl",
    OutputKind.CLAIM_CANDIDATE: "claim_candidates.jsonl",
    OutputKind.EVIDENCE_SPAN_CANDIDATE: "evidence_span_candidates.jsonl",
    OutputKind.CLAIM: "claims.jsonl",
    OutputKind.EVIDENCE_SPAN: "evidence_spans.jsonl",
    OutputKind.EVENT: "events.jsonl",
    OutputKind.VALIDATION_ERROR: "validation_errors.jsonl",
    OutputKind.MARKET_CONTEXT: "market_context.jsonl",
    OutputKind.SEARCH_LEAD: "search_leads.jsonl",
    OutputKind.ATTENTION_SIGNAL: "attention_signals.jsonl",
}


class JsonlWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    output_kind: OutputKind
    output_path: Path | None
    records_written: int
    skipped_reason: str | None = None


class JsonlWriter:
    def __init__(self, normalized_dir: str | Path) -> None:
        self.normalized_dir = Path(normalized_dir)

    def output_path_for(self, output_kind: OutputKind) -> Path:
        return self.normalized_dir / _OUTPUT_FILES[output_kind]

    def write_batch(self, batch: AdapterBatch) -> JsonlWriteResult:
        if not batch.ok:
            return JsonlWriteResult(
                source_id=batch.source_id,
                output_kind=batch.output_kind,
                output_path=None,
                records_written=0,
                skipped_reason="batch_failed",
            )

        output_path = self.output_path_for(batch.output_kind)
        if not batch.records:
            if batch.output_kind is OutputKind.VALIDATION_ERROR:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("", encoding="utf-8")
                return JsonlWriteResult(
                    source_id=batch.source_id,
                    output_kind=batch.output_kind,
                    output_path=output_path,
                    records_written=0,
                )
            return JsonlWriteResult(
                source_id=batch.source_id,
                output_kind=batch.output_kind,
                output_path=output_path,
                records_written=0,
                skipped_reason="no_records",
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as handle:
            for record in batch.records:
                line = json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                handle.write(f"{line}\n")

        return JsonlWriteResult(
            source_id=batch.source_id,
            output_kind=batch.output_kind,
            output_path=output_path,
            records_written=len(batch.records),
        )
