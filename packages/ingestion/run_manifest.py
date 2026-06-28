from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from packages.core import OutputKind
from packages.ingestion.adapters.base import AdapterBatch, AdapterError
from packages.ingestion.jsonl_writer import JsonlWriteResult
from packages.ingestion.registry import SourceConfig


class RunSourceStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunDerivedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    output_kind: OutputKind
    output_path: str | None = None
    records_written: int = Field(ge=0)
    skipped_reason: str | None = None


class RunSourceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    adapter: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    output_kind: OutputKind
    status: RunSourceStatus
    records_seen: int = Field(ge=0)
    records_written: int = Field(ge=0)
    raw_uris: tuple[str, ...] = ()
    output_path: str | None = None
    derived_outputs: tuple[RunDerivedOutput, ...] = ()
    error: AdapterError | None = None
    skipped_reason: str | None = None

    @classmethod
    def from_batch(
        cls,
        *,
        source: SourceConfig,
        batch: AdapterBatch,
        write_result: JsonlWriteResult,
        derived_outputs: tuple[RunDerivedOutput, ...] = (),
    ) -> RunSourceResult:
        if batch.source_id != source.source_id:
            raise ValueError("batch source_id must match source config")
        if write_result.source_id != source.source_id:
            raise ValueError("write_result source_id must match source config")
        if batch.output_kind is not write_result.output_kind:
            raise ValueError("batch and write_result output_kind must match")

        return cls(
            source_id=source.source_id,
            adapter=source.adapter,
            output_kind=source.output_kind,
            status=RunSourceStatus.SUCCESS if batch.ok else RunSourceStatus.FAILED,
            records_seen=batch.records_seen,
            records_written=write_result.records_written,
            raw_uris=batch.raw_uris,
            output_path=str(write_result.output_path) if write_result.output_path else None,
            derived_outputs=derived_outputs,
            error=batch.error,
            skipped_reason=write_result.skipped_reason,
        )

    @classmethod
    def skipped(
        cls,
        *,
        source_id: str,
        adapter: str,
        output_kind: OutputKind,
        skipped_reason: str,
    ) -> RunSourceResult:
        return cls(
            source_id=source_id,
            adapter=adapter,
            output_kind=output_kind,
            status=RunSourceStatus.SKIPPED,
            records_seen=0,
            records_written=0,
            skipped_reason=skipped_reason,
        )

    @model_validator(mode="after")
    def _validate_status_shape(self) -> RunSourceResult:
        if self.status is RunSourceStatus.SUCCESS and self.error is not None:
            raise ValueError("successful source results cannot include an error")
        if self.status is RunSourceStatus.FAILED and self.error is None:
            raise ValueError("failed source results must include an error")
        if self.status is RunSourceStatus.SKIPPED and not self.skipped_reason:
            raise ValueError("skipped source results must include skipped_reason")
        return self


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]*$")
    started_at: datetime
    finished_at: datetime
    sources: tuple[RunSourceResult, ...]

    @field_validator("started_at", "finished_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @field_serializer("started_at", "finished_at")
    def _serialize_utc(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def _validate_time_order(self) -> RunManifest:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must be after started_at")
        return self


class RunManifestWriter:
    def __init__(self, runs_dir: str | Path) -> None:
        self.runs_dir = Path(runs_dir)

    def output_path_for(self, manifest: RunManifest) -> Path:
        return self.runs_dir / manifest.run_id / "manifest.json"

    def write(self, manifest: RunManifest) -> Path:
        output_path = self.output_path_for(manifest)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump(mode="json")
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path
