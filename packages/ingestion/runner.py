from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict

from packages.core import DocumentChunk, OutputKind
from packages.evidence import build_pre_event_ledger
from packages.events import assemble_events
from packages.extraction import extract_candidate_pairs
from packages.ingestion.chunker import (
    DEFAULT_CHUNK_MAX_CHARS,
    DEFAULT_CHUNK_OVERLAP_CHARS,
    chunk_document_record,
)
from packages.ingestion.adapters import AdapterBatch, BaseSourceAdapter, SecEdgarAdapter
from packages.ingestion.cli_preview import (
    CliSourcePreview,
    build_cli_preview,
    format_cli_preview,
)
from packages.ingestion.jsonl_writer import JsonlWriter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.run_config import IngestionRunConfig
from packages.ingestion.run_manifest import (
    RunDerivedOutput,
    RunManifest,
    RunManifestWriter,
    RunSourceResult,
)


DEFAULT_ADAPTER_CLASSES: Mapping[str, type[BaseSourceAdapter]] = {
    SecEdgarAdapter.source_id: SecEdgarAdapter,
}


class IngestionRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    manifest: RunManifest
    manifest_path: Path
    cli_previews: tuple[CliSourcePreview, ...] = ()


def run_ingestion(
    *,
    registry: SourceRegistry,
    normalized_dir: str | Path,
    raw_dir: str | Path | None,
    runs_dir: str | Path,
    run_id: str,
    adapter_classes: Mapping[str, type[BaseSourceAdapter]] | None = None,
    limit: int | None = None,
    source_ids: tuple[str, ...] = (),
    source_options: Mapping[str, dict] | None = None,
    skip_unimplemented_adapters: bool = True,
    overwrite_outputs: bool = True,
    write_chunks: bool = False,
    write_candidates: bool = False,
    write_ledger: bool = False,
    write_events: bool = False,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    chunk_overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> IngestionRunResult:
    adapters = adapter_classes or DEFAULT_ADAPTER_CLASSES
    writer = JsonlWriter(normalized_dir)
    adapter_options = source_options or {}
    effective_write_ledger = write_ledger or write_events

    actual_started_at = started_at or datetime.now(timezone.utc)
    source_results: list[RunSourceResult] = []
    cli_previews: list[CliSourcePreview] = []

    selected_source_ids = set(source_ids)
    enabled_sources = tuple(
        source
        for source in registry.enabled_sources()
        if not selected_source_ids or source.source_id in selected_source_ids
    )
    if overwrite_outputs:
        _clear_output_files(
            writer,
            output_kinds={source.output_kind for source in enabled_sources},
            write_chunks=write_chunks,
            write_candidates=write_candidates,
            write_ledger=effective_write_ledger,
            write_events=write_events,
        )

    for source in enabled_sources:
        adapter_class = adapters.get(source.source_id)
        if adapter_class is None:
            if not skip_unimplemented_adapters:
                raise ValueError(f"adapter not implemented: {source.adapter}")
            source_result = RunSourceResult.skipped(
                source_id=source.source_id,
                adapter=source.adapter,
                output_kind=source.output_kind,
                skipped_reason="adapter_not_implemented",
            )
            source_results.append(source_result)
            cli_previews.append(build_cli_preview(source_result))
            continue

        adapter = adapter_class(
            source,
            raw_dir=raw_dir,
            options=adapter_options.get(source.source_id, {}),
        )
        batch = adapter.fetch(limit=limit)
        write_result = writer.write_batch(batch)
        derived_outputs: list[RunDerivedOutput] = []
        chunk_records: list[dict] = []
        if (
            (write_chunks or write_candidates or effective_write_ledger)
            and batch.ok
            and batch.output_kind is OutputKind.DOCUMENT
        ):
            chunk_records = _build_document_chunk_records(
                batch.records,
                max_chars=chunk_max_chars,
                overlap_chars=chunk_overlap_chars,
            )
            chunk_batch = AdapterBatch.success(
                source_id=batch.source_id,
                output_kind=OutputKind.DOCUMENT_CHUNK,
                retrieved_at=batch.retrieved_at,
                records=chunk_records,
            )
            chunk_write_result = writer.write_batch(chunk_batch)
            derived_outputs.append(
                RunDerivedOutput(
                    output_kind=chunk_write_result.output_kind,
                    output_path=(
                        str(chunk_write_result.output_path)
                        if chunk_write_result.output_path
                        else None
                    ),
                    records_written=chunk_write_result.records_written,
                    skipped_reason=chunk_write_result.skipped_reason,
                )
            )
            claim_records: list[dict] = []
            evidence_records: list[dict] = []
            if write_candidates or effective_write_ledger:
                claim_records, evidence_records = _build_candidate_records(
                    chunk_records
                )
                for output_kind, records in (
                    (OutputKind.CLAIM_CANDIDATE, claim_records),
                    (OutputKind.EVIDENCE_SPAN_CANDIDATE, evidence_records),
                ):
                    candidate_batch = AdapterBatch.success(
                        source_id=batch.source_id,
                        output_kind=output_kind,
                        retrieved_at=batch.retrieved_at,
                        records=records,
                    )
                    candidate_write_result = writer.write_batch(candidate_batch)
                    derived_outputs.append(
                        RunDerivedOutput(
                            output_kind=candidate_write_result.output_kind,
                            output_path=(
                                str(candidate_write_result.output_path)
                                if candidate_write_result.output_path
                                else None
                            ),
                            records_written=candidate_write_result.records_written,
                            skipped_reason=candidate_write_result.skipped_reason,
                        )
                    )
            if effective_write_ledger:
                ledger = build_pre_event_ledger(
                    claim_records=claim_records,
                    evidence_records=evidence_records,
                    chunk_records=chunk_records,
                )
                for output_kind, records in (
                    (
                        OutputKind.CLAIM,
                        [claim.model_dump(mode="json") for claim in ledger.claims],
                    ),
                    (
                        OutputKind.EVIDENCE_SPAN,
                        [
                            evidence.model_dump(mode="json")
                            for evidence in ledger.evidence_spans
                        ],
                    ),
                    (
                        OutputKind.VALIDATION_ERROR,
                        [
                            error.model_dump(mode="json")
                            for error in ledger.validation_errors
                        ],
                    ),
                ):
                    ledger_batch = AdapterBatch.success(
                        source_id=batch.source_id,
                        output_kind=output_kind,
                        retrieved_at=batch.retrieved_at,
                        records=records,
                    )
                    ledger_write_result = writer.write_batch(ledger_batch)
                    derived_outputs.append(
                        RunDerivedOutput(
                            output_kind=ledger_write_result.output_kind,
                            output_path=(
                                str(ledger_write_result.output_path)
                                if ledger_write_result.output_path
                                else None
                            ),
                            records_written=ledger_write_result.records_written,
                            skipped_reason=ledger_write_result.skipped_reason,
                        )
                    )
                if write_events:
                    event_records = [
                        event.model_dump(mode="json")
                        for event in assemble_events(
                            claims=ledger.claims,
                            evidence_spans=ledger.evidence_spans,
                        )
                    ]
                    event_batch = AdapterBatch.success(
                        source_id=batch.source_id,
                        output_kind=OutputKind.EVENT,
                        retrieved_at=batch.retrieved_at,
                        records=event_records,
                    )
                    event_write_result = writer.write_batch(event_batch)
                    derived_outputs.append(
                        RunDerivedOutput(
                            output_kind=event_write_result.output_kind,
                            output_path=(
                                str(event_write_result.output_path)
                                if event_write_result.output_path
                                else None
                            ),
                            records_written=event_write_result.records_written,
                            skipped_reason=event_write_result.skipped_reason,
                        )
                    )
        source_result = RunSourceResult.from_batch(
            source=source,
            batch=batch,
            write_result=write_result,
            derived_outputs=tuple(derived_outputs),
        )
        source_results.append(source_result)
        cli_previews.append(
            build_cli_preview(
                source_result,
                records=batch.records,
                chunk_records=chunk_records,
            )
        )

    manifest = RunManifest(
        run_id=run_id,
        started_at=actual_started_at,
        finished_at=finished_at or datetime.now(timezone.utc),
        sources=tuple(source_results),
    )
    manifest_path = RunManifestWriter(runs_dir).write(manifest)
    return IngestionRunResult(
        manifest=manifest,
        manifest_path=manifest_path,
        cli_previews=tuple(cli_previews),
    )


def make_run_id(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return f"run_{value.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _build_document_chunk_records(
    records: tuple[dict, ...],
    *,
    max_chars: int,
    overlap_chars: int,
) -> list[dict]:
    chunk_records: list[dict] = []
    for record in records:
        for chunk in chunk_document_record(
            record,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        ):
            chunk_records.append(chunk.model_dump(mode="json"))
    return chunk_records


def _build_candidate_records(
    chunk_records: list[dict],
) -> tuple[list[dict], list[dict]]:
    chunks = [DocumentChunk.model_validate(record) for record in chunk_records]
    pairs = extract_candidate_pairs(chunks)
    return (
        [claim.model_dump(mode="json") for claim, _evidence in pairs],
        [evidence.model_dump(mode="json") for _claim, evidence in pairs],
    )


def _clear_output_files(
    writer: JsonlWriter,
    *,
    output_kinds: set[OutputKind],
    write_chunks: bool,
    write_candidates: bool,
    write_ledger: bool,
    write_events: bool,
) -> None:
    if (
        (write_chunks or write_candidates or write_ledger)
        and OutputKind.DOCUMENT in output_kinds
    ):
        output_kinds.add(OutputKind.DOCUMENT_CHUNK)
    if (write_candidates or write_ledger) and OutputKind.DOCUMENT in output_kinds:
        output_kinds.update(
            {
                OutputKind.CLAIM_CANDIDATE,
                OutputKind.EVIDENCE_SPAN_CANDIDATE,
            }
        )
    if write_ledger and OutputKind.DOCUMENT in output_kinds:
        output_kinds.update(
            {
                OutputKind.CLAIM,
                OutputKind.EVIDENCE_SPAN,
                OutputKind.VALIDATION_ERROR,
            }
        )
    if write_events and OutputKind.DOCUMENT in output_kinds:
        output_kinds.add(OutputKind.EVENT)
    if OutputKind.DOCUMENT in output_kinds:
        output_kinds.update(
            {
                OutputKind.DOCUMENT_CHUNK,
                OutputKind.CLAIM_CANDIDATE,
                OutputKind.EVIDENCE_SPAN_CANDIDATE,
                OutputKind.CLAIM,
                OutputKind.EVIDENCE_SPAN,
                OutputKind.EVENT,
                OutputKind.VALIDATION_ERROR,
            }
        )
    else:
        output_kinds.update(
            {
                OutputKind.DOCUMENT_CHUNK,
                OutputKind.CLAIM_CANDIDATE,
                OutputKind.EVIDENCE_SPAN_CANDIDATE,
                OutputKind.CLAIM,
                OutputKind.EVIDENCE_SPAN,
                OutputKind.EVENT,
                OutputKind.VALIDATION_ERROR,
            }
        )
    for output_kind in output_kinds:
        output_path = writer.output_path_for(output_kind)
        if output_path.exists():
            output_path.unlink()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic source ingestion.")
    parser.add_argument(
        "--config",
        default="configs/ingestion_run.yaml",
        help="Path to the ingestion run YAML config.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier for manifest output.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Source id to run. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Temporary per-source fetch limit override.",
    )
    parser.add_argument(
        "--write-chunks",
        action="store_true",
        help="Also derive document chunks from available full-text artifacts.",
    )
    parser.add_argument(
        "--write-candidates",
        action="store_true",
        help="Also derive rule-based claim and evidence span candidates.",
    )
    parser.add_argument(
        "--write-ledger",
        action="store_true",
        help="Also validate candidates and write the pre-event evidence ledger.",
    )
    parser.add_argument(
        "--write-events",
        action="store_true",
        help="Also assemble pre-event ledger records into events. Implies --write-ledger.",
    )
    return parser


def _print_summary(result: IngestionRunResult) -> None:
    print(
        format_cli_preview(
            run_id=result.manifest.run_id,
            manifest_path=result.manifest_path,
            previews=result.cli_previews,
        ),
        end="",
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = IngestionRunConfig.from_yaml(args.config)
    registry = SourceRegistry.from_yaml(config.source_registry_path)
    result = run_ingestion(
        registry=registry,
        normalized_dir=config.normalized_dir,
        raw_dir=config.raw_dir,
        runs_dir=config.runs_dir,
        run_id=args.run_id or make_run_id(),
        limit=args.limit if args.limit is not None else config.default_limit,
        source_ids=config.selected_source_ids(tuple(args.source)),
        source_options=config.source_options,
        skip_unimplemented_adapters=config.skip_unimplemented_adapters,
        write_chunks=args.write_chunks or config.write_chunks,
        write_candidates=args.write_candidates or config.write_candidates,
        write_ledger=args.write_ledger or config.write_ledger,
        write_events=args.write_events or config.write_events,
        chunk_max_chars=config.chunk_max_chars,
        chunk_overlap_chars=config.chunk_overlap_chars,
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
