from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict

from packages.briefing import build_event_cards, render_daily_brief
from packages.core import DocumentChunk, OutputKind
from packages.evidence import build_pre_event_ledger
from packages.events import assemble_events
from packages.extraction import extract_candidate_pairs
from packages.ingestion.chunker import (
    DEFAULT_CHUNK_MAX_CHARS,
    DEFAULT_CHUNK_OVERLAP_CHARS,
    chunk_document_record,
)
from packages.ingestion.adapters import (
    AdapterBatch,
    BaseSourceAdapter,
    BraveSearchAdapter,
    CompanyIrAdapter,
    SecEdgarAdapter,
    StockSentimentAdapter,
    TavilySearchAdapter,
    YFinanceAdapter,
)
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
    CompanyIrAdapter.source_id: CompanyIrAdapter,
    YFinanceAdapter.source_id: YFinanceAdapter,
    TavilySearchAdapter.source_id: TavilySearchAdapter,
    BraveSearchAdapter.source_id: BraveSearchAdapter,
    StockSentimentAdapter.source_id: StockSentimentAdapter,
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
    write_event_cards: bool = False,
    write_brief: bool = False,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    chunk_overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> IngestionRunResult:
    adapters = adapter_classes or DEFAULT_ADAPTER_CLASSES
    writer = JsonlWriter(normalized_dir)
    adapter_options = source_options or {}
    effective_write_events = write_events or write_event_cards or write_brief
    effective_write_ledger = write_ledger or effective_write_events

    actual_started_at = started_at or datetime.now(timezone.utc)
    source_results: list[RunSourceResult] = []
    cli_previews: list[CliSourcePreview] = []
    document_records_for_derivation: list[dict] = []
    derivation_source_index: int | None = None
    derivation_retrieved_at: datetime | None = None
    records_by_source_index: dict[int, tuple[dict, ...]] = {}

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
            write_events=effective_write_events,
            write_event_cards=write_event_cards or write_brief,
            write_brief=write_brief,
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
        source_index = len(source_results)
        if (
            (write_chunks or write_candidates or effective_write_ledger)
            and batch.ok
            and batch.output_kind is OutputKind.DOCUMENT
            and batch.records
        ):
            if derivation_source_index is None:
                derivation_source_index = source_index
            document_records_for_derivation.extend(batch.records)
            derivation_retrieved_at = (
                batch.retrieved_at
                if derivation_retrieved_at is None
                else max(derivation_retrieved_at, batch.retrieved_at)
            )
        records_by_source_index[source_index] = batch.records
        source_result = RunSourceResult.from_batch(
            source=source,
            batch=batch,
            write_result=write_result,
        )
        source_results.append(source_result)
        cli_previews.append(
            build_cli_preview(
                source_result,
                records=batch.records,
            )
        )

    if derivation_source_index is not None and derivation_retrieved_at is not None:
        derived_outputs, chunk_records = _write_document_derived_outputs(
            writer=writer,
            source_id=source_results[derivation_source_index].source_id,
            retrieved_at=derivation_retrieved_at,
            records=tuple(document_records_for_derivation),
            write_chunks=write_chunks,
            write_candidates=write_candidates,
            write_ledger=effective_write_ledger,
            write_events=effective_write_events,
            write_event_cards=write_event_cards or write_brief,
            write_brief=write_brief,
            chunk_max_chars=chunk_max_chars,
            chunk_overlap_chars=chunk_overlap_chars,
        )
        # ponytail: run-level derived outputs live on the first document source
        # until the manifest needs a real run-level derived_outputs field.
        source_result = source_results[derivation_source_index].model_copy(
            update={"derived_outputs": tuple(derived_outputs)}
        )
        source_results[derivation_source_index] = source_result
        cli_previews[derivation_source_index] = build_cli_preview(
            source_result,
            records=records_by_source_index[derivation_source_index],
            chunk_records=chunk_records,
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


def _write_document_derived_outputs(
    *,
    writer: JsonlWriter,
    source_id: str,
    retrieved_at: datetime,
    records: tuple[dict, ...],
    write_chunks: bool,
    write_candidates: bool,
    write_ledger: bool,
    write_events: bool,
    write_event_cards: bool,
    write_brief: bool,
    chunk_max_chars: int,
    chunk_overlap_chars: int,
) -> tuple[list[RunDerivedOutput], list[dict]]:
    derived_outputs: list[RunDerivedOutput] = []

    chunk_records = _build_document_chunk_records(
        records,
        max_chars=chunk_max_chars,
        overlap_chars=chunk_overlap_chars,
    )
    if write_chunks or write_candidates or write_ledger:
        derived_outputs.append(
            _write_derived_batch(
                writer=writer,
                source_id=source_id,
                output_kind=OutputKind.DOCUMENT_CHUNK,
                retrieved_at=retrieved_at,
                records=chunk_records,
            )
        )

    claim_records: list[dict] = []
    evidence_records: list[dict] = []
    if write_candidates or write_ledger:
        claim_records, evidence_records = _build_candidate_records(chunk_records)
        for output_kind, derived_records in (
            (OutputKind.CLAIM_CANDIDATE, claim_records),
            (OutputKind.EVIDENCE_SPAN_CANDIDATE, evidence_records),
        ):
            derived_outputs.append(
                _write_derived_batch(
                    writer=writer,
                    source_id=source_id,
                    output_kind=output_kind,
                    retrieved_at=retrieved_at,
                    records=derived_records,
                )
            )

    if write_ledger:
        ledger = build_pre_event_ledger(
            claim_records=claim_records,
            evidence_records=evidence_records,
            chunk_records=chunk_records,
        )
        for output_kind, derived_records in (
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
                [error.model_dump(mode="json") for error in ledger.validation_errors],
            ),
        ):
            derived_outputs.append(
                _write_derived_batch(
                    writer=writer,
                    source_id=source_id,
                    output_kind=output_kind,
                    retrieved_at=retrieved_at,
                    records=derived_records,
                )
            )

        if write_events:
            events = assemble_events(
                claims=ledger.claims,
                evidence_spans=ledger.evidence_spans,
            )
            derived_outputs.append(
                _write_derived_batch(
                    writer=writer,
                    source_id=source_id,
                    output_kind=OutputKind.EVENT,
                    retrieved_at=retrieved_at,
                    records=[event.model_dump(mode="json") for event in events],
                )
            )
            if write_event_cards or write_brief:
                cards = build_event_cards(
                    events=events,
                    claims=ledger.claims,
                    evidence_spans=ledger.evidence_spans,
                    created_at=retrieved_at,
                )
                derived_outputs.append(
                    _write_derived_batch(
                        writer=writer,
                        source_id=source_id,
                        output_kind=OutputKind.EVENT_CARD,
                        retrieved_at=retrieved_at,
                        records=[card.model_dump(mode="json") for card in cards],
                    )
                )
            if write_brief:
                brief = render_daily_brief(
                    cards=cards,
                    created_at=retrieved_at,
                )
                derived_outputs.append(
                    _write_derived_batch(
                        writer=writer,
                        source_id=source_id,
                        output_kind=OutputKind.BRIEFING,
                        retrieved_at=retrieved_at,
                        records=[brief.model_dump(mode="json")],
                    )
                )

    return derived_outputs, chunk_records


def _write_derived_batch(
    *,
    writer: JsonlWriter,
    source_id: str,
    output_kind: OutputKind,
    retrieved_at: datetime,
    records: list[dict],
) -> RunDerivedOutput:
    write_result = writer.write_batch(
        AdapterBatch.success(
            source_id=source_id,
            output_kind=output_kind,
            retrieved_at=retrieved_at,
            records=records,
        )
    )
    return RunDerivedOutput(
        output_kind=write_result.output_kind,
        output_path=str(write_result.output_path) if write_result.output_path else None,
        records_written=write_result.records_written,
        skipped_reason=write_result.skipped_reason,
    )


def _clear_output_files(
    writer: JsonlWriter,
    *,
    output_kinds: set[OutputKind],
    write_chunks: bool,
    write_candidates: bool,
    write_ledger: bool,
    write_events: bool,
    write_event_cards: bool,
    write_brief: bool,
) -> None:
    if (
        write_chunks or write_candidates or write_ledger
    ) and OutputKind.DOCUMENT in output_kinds:
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
    if write_event_cards and OutputKind.DOCUMENT in output_kinds:
        output_kinds.add(OutputKind.EVENT_CARD)
    if write_brief and OutputKind.DOCUMENT in output_kinds:
        output_kinds.add(OutputKind.BRIEFING)
    if OutputKind.DOCUMENT in output_kinds:
        output_kinds.update(
            {
                OutputKind.DOCUMENT_CHUNK,
                OutputKind.CLAIM_CANDIDATE,
                OutputKind.EVIDENCE_SPAN_CANDIDATE,
                OutputKind.CLAIM,
                OutputKind.EVIDENCE_SPAN,
                OutputKind.EVENT,
                OutputKind.EVENT_CARD,
                OutputKind.BRIEFING,
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
                OutputKind.EVENT_CARD,
                OutputKind.BRIEFING,
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
    parser.add_argument(
        "--write-event-cards",
        action="store_true",
        help="Also generate event cards. Implies --write-events.",
    )
    parser.add_argument(
        "--write-brief",
        action="store_true",
        help="Also generate a markdown briefing record. Implies --write-event-cards.",
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
        write_event_cards=args.write_event_cards or config.write_event_cards,
        write_brief=args.write_brief or config.write_brief,
        chunk_max_chars=config.chunk_max_chars,
        chunk_overlap_chars=config.chunk_overlap_chars,
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
