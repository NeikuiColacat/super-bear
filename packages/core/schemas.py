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
    ClaimStatus,
    ClaimType,
    EntityKind,
    EvidenceRelation,
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


class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*:chunk:[0-9]{6}$")
    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*$")
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    section_label: str | None = Field(default=None, min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_text_coordinates(self) -> DocumentChunk:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.char_end - self.char_start != len(self.text):
            raise ValueError("chunk text length must match char range")
        return self


class ClaimCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_candidate_id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9:._/-]*:claim_candidate:[0-9]{6}$"
    )
    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*$")
    chunk_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*:chunk:[0-9]{6}$")
    claim_text: str = Field(min_length=1)
    claim_type: ClaimType
    confidence: float = Field(ge=0, le=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*:claim:[0-9]{6}$")
    event_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9:._/-]*$")
    claim_text: str = Field(min_length=1)
    claim_type: ClaimType
    mandatory: bool
    status: ClaimStatus
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class EvidenceSpanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    span_candidate_id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9:._/-]*:evidence_span_candidate:[0-9]{6}$"
    )
    claim_candidate_id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9:._/-]*:claim_candidate:[0-9]{6}$"
    )
    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*$")
    chunk_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*:chunk:[0-9]{6}$")
    relation: EvidenceRelation
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
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
    published_at: datetime
    confidence: float = Field(ge=0, le=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("published_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_candidate_span(self) -> EvidenceSpanCandidate:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.char_end - self.char_start != len(self.text):
            raise ValueError("candidate text length must match char range")
        if not is_document_source_type(self.source_type):
            raise ValueError(f"{self.source_type} is not a document source_type")
        if not is_valid_source_type_tier_pair(self.source_type, self.source_tier):
            raise ValueError(
                f"{self.source_tier} is not valid for source_type {self.source_type}"
            )
        return self


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*:span:[0-9]{6}$")
    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*$")
    claim_id: str = Field(pattern=r"^[a-z0-9][a-z0-9:._/-]*:claim:[0-9]{6}$")
    chunk_id: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9:._/-]*:chunk:[0-9]{6}$",
    )
    relation: EvidenceRelation
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
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
    published_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = Field(ge=0, le=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("published_at", "valid_from", "valid_to")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_span(self) -> EvidenceSpan:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.char_end - self.char_start != len(self.text):
            raise ValueError("span text length must match char range")
        if not is_document_source_type(self.source_type):
            raise ValueError(f"{self.source_type} is not a document source_type")
        if not is_valid_source_type_tier_pair(self.source_type, self.source_tier):
            raise ValueError(
                f"{self.source_tier} is not valid for source_type {self.source_type}"
            )
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class PipelineValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_error_id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9:._/-]*:validation_error:[0-9]{6}$"
    )
    record_kind: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    object_id: str | None = None
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    message: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
