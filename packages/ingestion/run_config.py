from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
import yaml


class IngestionRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    source_registry_path: Path
    raw_dir: Path
    normalized_dir: Path
    runs_dir: Path
    default_limit: int | None = Field(default=None, ge=1)
    enabled_source_ids: tuple[str, ...] = ()
    skip_unimplemented_adapters: bool = True
    write_chunks: bool = False
    write_candidates: bool = False
    write_ledger: bool = False
    write_events: bool = False
    chunk_max_chars: int = Field(default=1800, ge=1)
    chunk_overlap_chars: int = Field(default=150, ge=0)
    source_options: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> IngestionRunConfig:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("ingestion run YAML must contain a mapping")
        return cls.model_validate(raw)

    @model_validator(mode="after")
    def _validate_chunking_options(self) -> IngestionRunConfig:
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_max_chars")
        return self

    def selected_source_ids(self, override: tuple[str, ...] = ()) -> tuple[str, ...]:
        return override or self.enabled_source_ids
