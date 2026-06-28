from datetime import datetime, timezone

from packages.briefing import build_event_cards, render_daily_brief
from packages.core import (
    Claim,
    ClaimStatus,
    ClaimType,
    EvidenceRelation,
    EvidenceStatus,
    EvidenceSpan,
)
from packages.events import assemble_events
from packages.harness import (
    AllowedAction,
    Budget,
    InvestigatorRequest,
    InvestigatorResult,
    ResultStatus,
    validate_investigator_result,
)


def test_event_to_brief_to_fake_pi_validation_loop() -> None:
    ts = datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc)
    claim = Claim(
        claim_id="sec:apple:10q:claim:000000",
        claim_text="Net sales increased year over year.",
        claim_type=ClaimType.FACT,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
    )
    span = EvidenceSpan(
        span_id="sec:apple:10q:span:000000",
        doc_id="sec:apple:10q",
        claim_id=claim.claim_id,
        chunk_id="sec:apple:10q:chunk:000000",
        relation=EvidenceRelation.SUPPORT,
        text=claim.claim_text,
        char_start=0,
        char_end=len(claim.claim_text),
        source_type="sec_filing",
        source_tier="regulatory_primary",
        source_family_id="issuer:0000320193",
        published_at=ts,
        valid_from=ts,
        confidence=0.8,
        metadata={"form": "10-Q"},
    )
    event = assemble_events(claims=(claim,), evidence_spans=(span,))[0]
    card = build_event_cards(
        events=(event,),
        claims=(claim,),
        evidence_spans=(span,),
        created_at=ts,
    )[0]
    brief = render_daily_brief(cards=(card,), created_at=ts)
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
            "event": event.model_dump(mode="json"),
            "event_card": card.model_dump(mode="json"),
            "brief": brief.model_dump(mode="json"),
            "claims": [claim.model_dump(mode="json")],
            "evidence_spans": [span.model_dump(mode="json")],
            "chunks": [],
            "open_questions": [],
        },
    )
    result = InvestigatorResult(
        schema_version="investigator_result.v0",
        investigator_run_id=request.investigator_run_id,
        status=ResultStatus.STOP,
        evidence_status=EvidenceStatus.SUFFICIENT,
        citations=[
            {
                "claim_id": claim.claim_id,
                "evidence_span_id": span.span_id,
            }
        ],
    )

    assert brief.event_card_ids == (card.event_card_id,)
    assert validate_investigator_result(request, result).ok is True
