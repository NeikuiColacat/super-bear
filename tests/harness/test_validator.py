from packages.core import EvidenceStatus
from packages.harness import (
    AllowedAction,
    Budget,
    InvestigatorRequest,
    InvestigatorResult,
    ResultStatus,
    validate_investigator_result,
)


def _request() -> InvestigatorRequest:
    return InvestigatorRequest(
        schema_version="investigator.v0",
        investigator_run_id="investigator_run_20260628T080100Z",
        harness_name="pi",
        task_type="verify_evidence_gap",
        budgets=Budget(
            query_budget=3,
            read_budget=5,
            token_budget=50000,
            latency_budget_ms=120000,
        ),
        allowed_actions=(AllowedAction.READ_DOCUMENT, AllowedAction.STOP),
        event_pack={
            "event": {"event_id": "event:issuer:test"},
            "claims": [{"claim_id": "sec:apple:10q:claim:000000"}],
            "evidence_spans": [{"span_id": "sec:apple:10q:span:000000"}],
            "chunks": [],
            "open_questions": [],
        },
    )


def test_validator_accepts_citations_inside_event_pack() -> None:
    result = InvestigatorResult(
        schema_version="investigator_result.v0",
        investigator_run_id="investigator_run_20260628T080100Z",
        status=ResultStatus.STOP,
        evidence_status=EvidenceStatus.SUFFICIENT,
        citations=[
            {
                "claim_id": "sec:apple:10q:claim:000000",
                "evidence_span_id": "sec:apple:10q:span:000000",
            }
        ],
    )

    validation = validate_investigator_result(_request(), result)

    assert validation.ok is True
    assert validation.errors == ()


def test_validator_rejects_unallowed_tool_action() -> None:
    result = InvestigatorResult(
        schema_version="investigator_result.v0",
        investigator_run_id="investigator_run_20260628T080100Z",
        status=ResultStatus.STOP,
        evidence_status=EvidenceStatus.SUFFICIENT,
        tool_calls=[
            {
                "action": "SEARCH_PRIMARY_SOURCE",
                "input": {},
                "output_ref": "search:1",
            }
        ],
    )

    validation = validate_investigator_result(_request(), result)

    assert validation.ok is False
    assert validation.errors == ("tool_action_not_allowed:SEARCH_PRIMARY_SOURCE",)
