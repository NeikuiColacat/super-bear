from datetime import datetime, timezone

from packages.core import EvidenceStatus
from packages.harness import (
    AllowedAction,
    Budget,
    InvestigatorRequest,
    InvestigatorResult,
    ResultStatus,
)


def test_investigator_contract_accepts_bounded_event_pack() -> None:
    request = InvestigatorRequest(
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
            "claims": [],
            "evidence_spans": [],
            "chunks": [],
            "open_questions": [],
        },
    )

    assert request.harness_name == "pi"
    assert request.allowed_actions == (
        AllowedAction.READ_DOCUMENT,
        AllowedAction.STOP,
    )


def test_investigator_result_records_tool_calls_and_citations() -> None:
    result = InvestigatorResult(
        schema_version="investigator_result.v0",
        investigator_run_id="investigator_run_20260628T080100Z",
        status=ResultStatus.STOP,
        evidence_status=EvidenceStatus.SUFFICIENT,
        tool_calls=[
            {
                "action": "READ_DOCUMENT",
                "input": {"doc_id": "sec:apple:10q"},
                "output_ref": "sec:apple:10q",
                "started_at": datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc),
                "ended_at": datetime(2026, 6, 28, 8, 2, tzinfo=timezone.utc),
            }
        ],
        citations=[
            {
                "claim_id": "sec:apple:10q:claim:000000",
                "evidence_span_id": "sec:apple:10q:span:000000",
            }
        ],
    )

    assert result.status is ResultStatus.STOP
    assert result.tool_calls[0].action is AllowedAction.READ_DOCUMENT
