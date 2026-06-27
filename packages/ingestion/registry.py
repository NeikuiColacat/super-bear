from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
import yaml

from packages.core import (
    OutputKind,
    SourceTier,
    SourceType,
    is_document_source_type,
    is_valid_source_type_tier_pair,
)


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    enabled: bool = True
    adapter: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    output_kind: OutputKind
    default_source_type: SourceType
    allowed_source_types: tuple[SourceType, ...] = ()
    source_tier: SourceTier
    source_family_strategy: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    base_url: HttpUrl | None = None
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    user_agent_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    requires_api_key: bool = False
    rate_limit_per_second: float = Field(gt=0)
    license_notes: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _normalize_source_type_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "source_type" in normalized and "default_source_type" not in normalized:
            normalized["default_source_type"] = normalized.pop("source_type")
        if "allowed_source_types" not in normalized and "default_source_type" in normalized:
            normalized["allowed_source_types"] = [normalized["default_source_type"]]
        return normalized

    @property
    def source_type(self) -> SourceType:
        return self.default_source_type

    @model_validator(mode="after")
    def _validate_output_mapping(self) -> SourceConfig:
        if self.default_source_type not in self.allowed_source_types:
            raise ValueError("default_source_type must be listed in allowed_source_types")

        if self.output_kind is OutputKind.DOCUMENT:
            if not all(
                is_document_source_type(item) for item in self.allowed_source_types
            ):
                raise ValueError("document sources must use a document source_type")
            for source_type in self.allowed_source_types:
                if not is_valid_source_type_tier_pair(source_type, self.source_tier):
                    raise ValueError(
                        f"{self.source_tier} is not valid for source_type {source_type}"
                    )

        if self.output_kind is OutputKind.MARKET_CONTEXT:
            if self.default_source_type is not SourceType.MARKET_DATA:
                raise ValueError("market_context sources must use market_data")
            if self.source_tier is not SourceTier.MARKET_CONTEXT:
                raise ValueError("market_context sources must use market_context tier")

        if self.output_kind is OutputKind.SEARCH_LEAD:
            if self.default_source_type is not SourceType.SEARCH:
                raise ValueError("search_lead sources must use search")
            if self.source_tier is not SourceTier.SEARCH_LEAD:
                raise ValueError("search_lead sources must use search_lead tier")

        if self.output_kind is OutputKind.ATTENTION_SIGNAL:
            if self.default_source_type is not SourceType.SOCIAL_SENTIMENT:
                raise ValueError("attention_signal sources must use social_sentiment")
            if self.source_tier is not SourceTier.ATTENTION_SIGNAL:
                raise ValueError("attention_signal sources must use attention_signal tier")

        if self.requires_api_key and not self.api_key_env:
            raise ValueError("sources requiring an API key must set api_key_env")

        return self


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: tuple[SourceConfig, ...]

    @classmethod
    def from_yaml(cls, path: str | Path) -> SourceRegistry:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("source registry YAML must contain a mapping")
        if raw.get("version") != 1:
            raise ValueError("source registry YAML must use version: 1")
        sources = raw.get("sources")
        if not isinstance(sources, list):
            raise ValueError("source registry YAML must contain a sources list")
        return cls.from_items(sources)

    @classmethod
    def from_items(cls, items: Iterable[dict[str, Any]]) -> SourceRegistry:
        sources = tuple(SourceConfig.model_validate(item) for item in items)
        seen: set[str] = set()
        duplicates: set[str] = set()
        for source in sources:
            if source.source_id in seen:
                duplicates.add(source.source_id)
            seen.add(source.source_id)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate source_id: {duplicate_list}")
        return cls(sources=sources)

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self.sources)

    def get(self, source_id: str) -> SourceConfig:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(source_id)

    def enabled_sources(self, output_kind: OutputKind | None = None) -> tuple[SourceConfig, ...]:
        return tuple(
            source
            for source in self.sources
            if source.enabled and (output_kind is None or source.output_kind is output_kind)
        )
