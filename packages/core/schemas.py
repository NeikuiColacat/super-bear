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

from .source_types import (
    EntityKind,
    SourceTier,
    SourceType,
    is_document_source_type,
    is_valid_source_type_tier_pair,
)


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
    source_family_id: str = Field(
        pattern=(
            r"^(issuer:[0-9]{10}"
            r"|issuer_ticker:[A-Z][A-Z0-9.-]*"
            r"|provider:[a-z][a-z0-9_]*"
            r"|publisher:[a-z][a-z0-9_-]*)$"
        )
    )
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
        if not is_document_source_type(self.source_type):
            raise ValueError(f"{self.source_type} is not a document source_type")
        if not is_valid_source_type_tier_pair(self.source_type, self.source_tier):
            raise ValueError(
                f"{self.source_tier} is not valid for source_type {self.source_type}"
            )
        return self
