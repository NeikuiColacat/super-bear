from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from packages.harness.contracts import InvestigatorRequest, InvestigatorResult


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

    allowed_actions = set(request.allowed_actions)
    for call in result.tool_calls:
        if call.action not in allowed_actions:
            errors.append(f"tool_action_not_allowed:{call.action}")

    claim_ids = {
        str(claim.get("claim_id"))
        for claim in request.event_pack.get("claims", [])
        if isinstance(claim, dict) and claim.get("claim_id")
    }
    span_ids = {
        str(span.get("span_id"))
        for span in request.event_pack.get("evidence_spans", [])
        if isinstance(span, dict) and span.get("span_id")
    }
    for citation in result.citations:
        if citation.claim_id not in claim_ids:
            errors.append(f"citation_claim_missing:{citation.claim_id}")
        if citation.evidence_span_id not in span_ids:
            errors.append(f"citation_evidence_span_missing:{citation.evidence_span_id}")

    return HarnessValidationResult(ok=not errors, errors=tuple(errors))
