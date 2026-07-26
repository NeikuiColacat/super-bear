from datetime import datetime, timezone

from packages.briefing import build_event_cards, render_daily_brief
from packages.core import (
    Claim,
    ClaimStatus,
    ClaimType,
    EvidenceRelation,
    EvidenceSpan,
    EvidenceStatus,
    Event,
    EventStatus,
    EventType,
)


def _ts() -> datetime:
    return datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc)


def _claim() -> Claim:
    return Claim(
        claim_id="sec:apple:10q:claim:000000",
        claim_text="Net sales increased year over year.",
        claim_type=ClaimType.FACT,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
    )


def _span(claim: Claim) -> EvidenceSpan:
    return EvidenceSpan(
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
        published_at=_ts(),
        valid_from=_ts(),
        confidence=0.8,
    )


def _event(claim: Claim) -> Event:
    return Event(
        event_id="event:issuer:0000320193:sec_filing:10-q:20260628:abcd1234",
        canonical_title="Apple filed a quarterly report.",
        event_type=EventType.SEC_FILING,
        event_time=_ts(),
        status=EventStatus.NEW,
        related_doc_ids=("sec:apple:10q",),
        claim_ids=(claim.claim_id,),
        evidence_status=EvidenceStatus.SUFFICIENT,
        assembly_key="issuer:0000320193|sec_filing|10-Q|20260628",
    )


def test_build_event_cards_keeps_factual_text_traceable() -> None:
    claim = _claim()
    span = _span(claim)

    cards = build_event_cards(
        events=(_event(claim),),
        claims=(claim,),
        evidence_spans=(span,),
        created_at=_ts(),
    )

    assert len(cards) == 1
    card = cards[0]
    assert card.what_happened == claim.claim_text
    assert card.key_claim_ids == (claim.claim_id,)
    assert card.key_evidence_span_ids == (span.span_id,)
    assert card.evidence_status is EvidenceStatus.SUFFICIENT
    assert card.source_summary == ("regulatory_primary:sec_filing",)


def test_build_event_cards_uses_only_event_scoped_evidence_spans() -> None:
    claim = _claim()
    first_span = _span(claim)
    second_span = first_span.model_copy(update={"span_id": "sec:apple:10q:span:000001"})
    event = _event(claim).model_copy(
        update={"metadata": {"evidence_span_ids": [first_span.span_id]}}
    )

    cards = build_event_cards(
        events=(event,),
        claims=(claim,),
        evidence_spans=(first_span, second_span),
        created_at=_ts(),
    )

    assert len(cards) == 1
    assert cards[0].key_evidence_span_ids == (first_span.span_id,)


def test_render_daily_brief_includes_claim_and_evidence_ids() -> None:
    claim = _claim()
    card = build_event_cards(
        events=(_event(claim),),
        claims=(claim,),
        evidence_spans=(_span(claim),),
        created_at=_ts(),
    )[0]

    brief = render_daily_brief(cards=(card,), created_at=_ts())

    assert brief.event_card_ids == (card.event_card_id,)
    assert "Net sales increased year over year." in brief.markdown
    assert "sec:apple:10q:claim:000000" in brief.markdown
    assert "sec:apple:10q:span:000000" in brief.markdown
