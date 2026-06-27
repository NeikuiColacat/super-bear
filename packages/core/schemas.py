from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    field_validator,
    model_validator,
)

from .source_types import EntityKind, SourceTier, SourceType


_DOCUMENT_SOURCE_TYPES = {
    SourceType.SEC_FILING,
    SourceType.SEC_EXHIBIT,
    SourceType.COMPANY_IR,
    SourceType.COMPANY_NEWSROOM,
    SourceType.COMPANY_EARNINGS_RELEASE,
    SourceType.PRESS_RELEASE_WIRE,
}

_DOCUMENT_SOURCE_TIERS = {
    SourceTier.REGULATORY_PRIMARY,
    SourceTier.COMPANY_PRIMARY,
    SourceTier.COMPANY_DISTRIBUTED,
}


class DocumentEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: EntityKind
    value: str = Field(min_length=1)
    identifiers: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*$")
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    source_type: SourceType
    source_tier: SourceTier
    source_family_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    published_at: datetime
    updated_at: datetime | None = None
    retrieved_at: datetime
    raw_object_uri: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    parser_version: str = Field(pattern=r"^[a-z0-9_.-]+$")
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]+)?$")
    entities: list[DocumentEntity] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("published_at", "updated_at", "retrieved_at")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _require_document_source(self) -> Document:
        if self.source_type not in _DOCUMENT_SOURCE_TYPES:
            raise ValueError(f"{self.source_type} is not a document source_type")
        if self.source_tier not in _DOCUMENT_SOURCE_TIERS:
            raise ValueError(f"{self.source_tier} is not a document source_tier")
        return self
