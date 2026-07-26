from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from packages.core import EvidenceStatus
from packages.harness.contracts import (
    AllowedAction,
    InvestigatorRequest,
    InvestigatorResult,
    ResultStatus,
)


class HarnessValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    errors: tuple[str, ...] = ()


def validate_investigator_result(
    request: InvestigatorRequest,
    result: InvestigatorResult,
) -> HarnessValidationResult:
    errors: list[str] = []
    if result.investigator_run_id != request.investigator_run_id:
        errors.append("investigator_run_id_mismatch")

    if result.status is ResultStatus.ABSTAIN and not result.abstain_reason:
        errors.append("abstain_requires_reason")
    if (
        result.status is ResultStatus.ABSTAIN
        and result.evidence_status is not EvidenceStatus.ABSTAINED
    ):
        errors.append("abstain_status_requires_abstained_evidence")
    if (
        result.status is ResultStatus.STOP
        and result.evidence_status is EvidenceStatus.ABSTAINED
    ):
        errors.append("stop_status_cannot_be_abstained")
    if (
        result.status is ResultStatus.STOP
        and result.evidence_status is EvidenceStatus.SUFFICIENT
        and not result.citations
    ):
        errors.append("sufficient_result_requires_citation")

    allowed_actions = set(request.allowed_actions)
    for call in result.tool_calls:
        if call.action not in allowed_actions:
            errors.append(f"tool_action_not_allowed:{call.action}")

    read_calls = sum(
        1 for call in result.tool_calls if call.action is AllowedAction.READ_DOCUMENT
    )
    if read_calls > request.budgets.read_budget:
        errors.append("read_budget_exceeded")
    query_calls = sum(
        1
        for call in result.tool_calls
        if call.action
        in {
            AllowedAction.SEARCH_PRIMARY_SOURCE,
            AllowedAction.SEARCH_INDEPENDENT_CONFIRMATION,
            AllowedAction.SEARCH_UPDATE_OR_CORRECTION,
        }
    )
    if query_calls > request.budgets.query_budget:
        errors.append("query_budget_exceeded")

    claim_ids = {
        str(claim.get("claim_id"))
        for claim in request.event_pack.get("claims", [])
        if isinstance(claim, dict) and claim.get("claim_id")
    }
    span_claim_ids = {
        str(span.get("span_id")): str(span.get("claim_id"))
        for span in request.event_pack.get("evidence_spans", [])
        if isinstance(span, dict) and span.get("span_id")
    }
    for citation in result.citations:
        if citation.claim_id not in claim_ids:
            errors.append(f"citation_claim_missing:{citation.claim_id}")
        span_claim_id = span_claim_ids.get(citation.evidence_span_id)
        if span_claim_id is None:
            errors.append(f"citation_evidence_span_missing:{citation.evidence_span_id}")
        elif span_claim_id != citation.claim_id:
            errors.append(
                "citation_claim_evidence_mismatch:"
                f"{citation.claim_id}:{citation.evidence_span_id}"
            )

    return HarnessValidationResult(ok=not errors, errors=tuple(errors))
