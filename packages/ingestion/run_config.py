from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
import yaml


class IngestionRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    source_registry_path: Path
    normalized_dir: Path
    runs_dir: Path
    default_limit: int | None = Field(default=None, ge=1)
    enabled_source_ids: tuple[str, ...] = ()
    skip_unimplemented_adapters: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> IngestionRunConfig:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("ingestion run YAML must contain a mapping")
        return cls.model_validate(raw)

    def selected_source_ids(self, override: tuple[str, ...] = ()) -> tuple[str, ...]:
        return override or self.enabled_source_ids
