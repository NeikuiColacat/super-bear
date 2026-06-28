from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from packages.core import OutputKind
from packages.ingestion.run_manifest import RunDerivedOutput, RunSourceResult


class CliDocumentSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str | None = None
    title: str = Field(min_length=1)
    url: str | None = None


class CliChunkSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str | None = None
    doc_id: str | None = None
    text: str = Field(min_length=1)


class CliSourcePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    status: str
    output_kind: OutputKind
    records_written: int = Field(ge=0)
    raw_uris: tuple[str, ...] = ()
    output_path: str | None = None
    derived_outputs: tuple[RunDerivedOutput, ...] = ()
    skipped_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    form_counts: dict[str, int] = Field(default_factory=dict)
    samples: tuple[CliDocumentSample, ...] = ()
    chunk_samples: tuple[CliChunkSample, ...] = ()


def build_cli_preview(
    source_result: RunSourceResult,
    *,
    records: Iterable[Mapping[str, Any]] = (),
    chunk_records: Iterable[Mapping[str, Any]] = (),
    sample_limit: int = 5,
) -> CliSourcePreview:
    record_list = list(records)
    chunk_record_list = list(chunk_records)
    return CliSourcePreview(
        source_id=source_result.source_id,
        status=str(source_result.status),
        output_kind=source_result.output_kind,
        records_written=source_result.records_written,
        raw_uris=source_result.raw_uris,
        output_path=source_result.output_path,
        derived_outputs=source_result.derived_outputs,
        skipped_reason=source_result.skipped_reason,
        error_code=source_result.error.code if source_result.error else None,
        error_message=source_result.error.message if source_result.error else None,
        form_counts=_count_forms(record_list),
        samples=tuple(_iter_samples(record_list, sample_limit=sample_limit)),
        chunk_samples=tuple(
            _iter_chunk_samples(chunk_record_list, sample_limit=sample_limit)
        ),
    )


def format_cli_preview(
    *,
    run_id: str,
    manifest_path: str | Path,
    previews: Iterable[CliSourcePreview],
) -> str:
    lines = [
        "CLI preview",
        f"run_id: {run_id}",
        f"manifest: {manifest_path}",
        "sources:",
    ]
    for preview in previews:
        summary = (
            f"- {preview.source_id}: {preview.status}, "
            f"records_written={preview.records_written}"
        )
        if preview.skipped_reason:
            summary += f", skipped_reason={preview.skipped_reason}"
        lines.append(summary)
        if preview.error_code:
            lines.append(f"  error: {preview.error_code} - {preview.error_message}")
        if preview.output_path:
            lines.append(f"  output: {preview.output_path}")
        if preview.raw_uris:
            lines.append("  raw:")
            lines.extend(f"    - {raw_uri}" for raw_uri in preview.raw_uris)
        if preview.derived_outputs:
            lines.append("  derived:")
            for output in preview.derived_outputs:
                line = (
                    f"    {output.output_kind}: "
                    f"records_written={output.records_written}"
                )
                if output.skipped_reason:
                    line += f", skipped_reason={output.skipped_reason}"
                lines.append(line)
                if output.output_path:
                    lines.append(f"      output: {output.output_path}")
        if preview.form_counts:
            lines.append("  forms:")
            for form, count in _sorted_counts(preview.form_counts):
                lines.append(f"    {form}: {count}")
        if preview.samples:
            lines.append("  samples:")
            for sample in preview.samples:
                lines.append(f"    - {sample.title}")
                if sample.url:
                    lines.append(f"      url: {sample.url}")
        if preview.chunk_samples:
            lines.append("  chunk samples:")
            for sample in preview.chunk_samples:
                lines.append(f"    - {_truncate(sample.text, limit=120)}")
                if sample.doc_id:
                    lines.append(f"      doc_id: {sample.doc_id}")
    return "\n".join(lines) + "\n"


def _count_forms(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        metadata = record.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        form = metadata.get("form")
        if form:
            counts[str(form)] += 1
    return dict(counts)


def _iter_samples(
    records: Iterable[Mapping[str, Any]],
    *,
    sample_limit: int,
) -> Iterable[CliDocumentSample]:
    for record in list(records)[:sample_limit]:
        title = str(record.get("title") or record.get("doc_id") or "(untitled)")
        doc_id = record.get("doc_id")
        url = record.get("url")
        yield CliDocumentSample(
            doc_id=str(doc_id) if doc_id else None,
            title=title,
            url=str(url) if url else None,
        )


def _iter_chunk_samples(
    records: Iterable[Mapping[str, Any]],
    *,
    sample_limit: int,
) -> Iterable[CliChunkSample]:
    for record in list(records)[:sample_limit]:
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        chunk_id = record.get("chunk_id")
        doc_id = record.get("doc_id")
        yield CliChunkSample(
            chunk_id=str(chunk_id) if chunk_id else None,
            doc_id=str(doc_id) if doc_id else None,
            text=text,
        )


def _sorted_counts(counts: Mapping[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _truncate(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."
