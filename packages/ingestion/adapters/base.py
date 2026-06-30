from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from collections.abc import Mapping
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from packages.core import OutputKind
from packages.ingestion.registry import SourceConfig


class AdapterError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, JsonValue] = Field(default_factory=dict)


class AdapterBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    output_kind: OutputKind
    ok: bool
    retrieved_at: datetime
    records: tuple[dict[str, JsonValue], ...] = ()
    raw_uris: tuple[str, ...] = ()
    warnings: tuple[AdapterError, ...] = ()
    error: AdapterError | None = None

    @classmethod
    def success(
        cls,
        *,
        source_id: str,
        output_kind: OutputKind,
        records: list[dict[str, JsonValue]],
        retrieved_at: datetime,
        raw_uris: list[str] | None = None,
        warnings: list[AdapterError] | None = None,
    ) -> AdapterBatch:
        return cls(
            source_id=source_id,
            output_kind=output_kind,
            ok=True,
            records=tuple(records),
            retrieved_at=retrieved_at,
            raw_uris=tuple(raw_uris or ()),
            warnings=tuple(warnings or ()),
        )

    @classmethod
    def failure(
        cls,
        *,
        source_id: str,
        output_kind: OutputKind,
        error: AdapterError,
        retrieved_at: datetime,
    ) -> AdapterBatch:
        return cls(
            source_id=source_id,
            output_kind=output_kind,
            ok=False,
            error=error,
            retrieved_at=retrieved_at,
        )

    @property
    def records_seen(self) -> int:
        return len(self.records)

    @property
    def records_written(self) -> int:
        return len(self.records) if self.ok else 0

    @field_validator("retrieved_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_status_shape(self) -> AdapterBatch:
        if self.ok and self.error is not None:
            raise ValueError("successful batches cannot include an error")
        if not self.ok and self.error is None:
            raise ValueError("failed batches must include an error")
        if not self.ok and self.records:
            raise ValueError("failed batches cannot include records")
        return self


class BaseSourceAdapter(ABC):
    source_id: ClassVar[str]

    def __init__(
        self,
        source: SourceConfig,
        *,
        raw_dir: str | Path | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> None:
        if source.source_id != self.source_id:
            raise ValueError(
                f"{self.__class__.__name__} handles {self.source_id}, "
                f"got {source.source_id}"
            )
        self.source = source
        self.raw_dir = Path(raw_dir) if raw_dir is not None else None
        self.options = dict(options or {})

    @property
    def output_kind(self) -> OutputKind:
        return self.source.output_kind

    @abstractmethod
    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        raise NotImplementedError
