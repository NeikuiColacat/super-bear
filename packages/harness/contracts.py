from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.core import (
    ClaimCandidate,
    EvidenceSpanCandidate,
    EvidenceStatus,
)


class AllowedAction(StrEnum):
    SEARCH_PRIMARY_SOURCE = "SEARCH_PRIMARY_SOURCE"
    SEARCH_INDEPENDENT_CONFIRMATION = "SEARCH_INDEPENDENT_CONFIRMATION"
    SEARCH_UPDATE_OR_CORRECTION = "SEARCH_UPDATE_OR_CORRECTION"
    READ_DOCUMENT = "READ_DOCUMENT"
    EXTRACT_CLAIMS = "EXTRACT_CLAIMS"
    VERIFY_EVIDENCE = "VERIFY_EVIDENCE"
    CHECK_SOURCE_INDEPENDENCE = "CHECK_SOURCE_INDEPENDENCE"
    CHECK_TEMPORAL_VALIDITY = "CHECK_TEMPORAL_VALIDITY"
    STOP = "STOP"
    ABSTAIN = "ABSTAIN"


class ResultStatus(StrEnum):
    STOP = "stop"
    ABSTAIN = "abstain"


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_budget: int = Field(ge=0)
    read_budget: int = Field(ge=0)
    token_budget: int = Field(ge=1)
    latency_budget_ms: int = Field(ge=1)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: AllowedAction
    input: dict[str, Any] = Field(default_factory=dict)
    output_ref: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("tool call timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_time_order(self) -> ToolCall:
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    evidence_span_id: str


class InvestigatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["investigator.v0"]
    investigator_run_id: str = Field(min_length=1)
    harness_name: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    budgets: Budget
    allowed_actions: tuple[AllowedAction, ...]
    event_pack: dict[str, Any]


class InvestigatorResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["investigator_result.v0"]
    investigator_run_id: str = Field(min_length=1)
    status: ResultStatus
    evidence_status: EvidenceStatus
    new_claim_candidates: tuple[ClaimCandidate, ...] = ()
    new_evidence_span_candidates: tuple[EvidenceSpanCandidate, ...] = ()
    conflicts: tuple[str, ...] = ()
    abstain_reason: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    citations: tuple[Citation, ...] = ()
