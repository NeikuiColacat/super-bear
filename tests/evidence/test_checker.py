from datetime import datetime, timezone

from packages.core import (
    Claim,
    ClaimStatus,
    ClaimType,
    EvidenceRelation,
    EvidenceStatus,
    EvidenceSpan,
    Event,
    EventStatus,
    EventType,
)
from packages.evidence import check_event_evidence


def _ts(day: int) -> datetime:
    return datetime(2026, 6, day, 8, 1, tzinfo=timezone.utc)


def _claim(index: int) -> Claim:
    return Claim(
        claim_id=f"sec:apple:10q:claim:{index:06d}",
        event_id=None,
        claim_text="Net sales increased year over year.",
        claim_type=ClaimType.FACT,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
    )


def _span(
    index: int,
    claim: Claim,
    *,
    relation: EvidenceRelation = EvidenceRelation.SUPPORT,
    valid_to: datetime | None = None,
) -> EvidenceSpan:
    return EvidenceSpan(
        span_id=f"sec:apple:10q:span:{index:06d}",
        doc_id="sec:apple:10q",
        claim_id=claim.claim_id,
        chunk_id="sec:apple:10q:chunk:000000",
        relation=relation,
        text=claim.claim_text,
        char_start=0,
        char_end=len(claim.claim_text),
        source_type="sec_filing",
        source_tier="regulatory_primary",
        source_family_id="issuer:0000320193",
        published_at=_ts(28),
        valid_from=_ts(26) if valid_to else _ts(28),
        valid_to=valid_to,
        confidence=0.8,
    )


def _event(*claim_ids: str) -> Event:
    return Event(
        event_id="event:issuer:0000320193:sec_filing:10-q:20260628:abcd1234",
        canonical_title="Apple filed a quarterly report.",
        event_type=EventType.SEC_FILING,
        event_time=_ts(28),
        status=EventStatus.NEW,
        related_doc_ids=("sec:apple:10q",),
        claim_ids=claim_ids,
        evidence_status=EvidenceStatus.INSUFFICIENT,
        assembly_key="issuer:0000320193|sec_filing|10-Q|20260628",
    )


def test_check_event_evidence_marks_supported_event_sufficient() -> None:
    claim = _claim(0)

    result = check_event_evidence(
        event=_event(claim.claim_id),
        claims=(claim,),
        evidence_spans=(_span(0, claim),),
        checked_at=_ts(28),
    )

    assert result.evidence_status is EvidenceStatus.SUFFICIENT
    assert result.event_status is EventStatus.NEW
    assert result.supported_claim_ids == (claim.claim_id,)
    assert result.missing_claim_ids == ()
    assert result.reasons == ("all_event_claims_supported",)


def test_check_event_evidence_marks_missing_claim_insufficient() -> None:
    supported_claim = _claim(0)
    missing_claim = _claim(1)

    result = check_event_evidence(
        event=_event(supported_claim.claim_id, missing_claim.claim_id),
        claims=(supported_claim, missing_claim),
        evidence_spans=(_span(0, supported_claim),),
        checked_at=_ts(28),
    )

    assert result.evidence_status is EvidenceStatus.INSUFFICIENT
    assert result.missing_claim_ids == (missing_claim.claim_id,)
    assert result.reasons == ("supporting_evidence_missing",)


def test_check_event_evidence_marks_support_refute_pair_conflicting() -> None:
    claim = _claim(0)

    result = check_event_evidence(
        event=_event(claim.claim_id),
        claims=(claim,),
        evidence_spans=(
            _span(0, claim, relation=EvidenceRelation.SUPPORT),
            _span(1, claim, relation=EvidenceRelation.REFUTE),
        ),
        checked_at=_ts(28),
    )

    assert result.evidence_status is EvidenceStatus.CONFLICTING
    assert result.event_status is EventStatus.DEVELOPING
    assert result.conflicting_claim_ids == (claim.claim_id,)
    assert result.reasons == ("support_refute_conflict",)


def test_check_event_evidence_marks_expired_support_temporally_invalid() -> None:
    claim = _claim(0)

    result = check_event_evidence(
        event=_event(claim.claim_id),
        claims=(claim,),
        evidence_spans=(_span(0, claim, valid_to=_ts(27)),),
        checked_at=_ts(28),
    )

    assert result.evidence_status is EvidenceStatus.STALE
    assert result.stale_claim_ids == (claim.claim_id,)
    assert result.supported_claim_ids == ()
    assert result.reasons == ("evidence_temporally_invalid",)


def test_check_event_evidence_marks_supported_update_developing() -> None:
    claim = _claim(0)

    result = check_event_evidence(
        event=_event(claim.claim_id),
        claims=(claim,),
        evidence_spans=(
            _span(0, claim, relation=EvidenceRelation.SUPPORT),
            _span(1, claim, relation=EvidenceRelation.UPDATE),
        ),
        checked_at=_ts(28),
    )

    assert result.evidence_status is EvidenceStatus.SUFFICIENT
    assert result.event_status is EventStatus.DEVELOPING
    assert result.reasons == ("update_evidence_present",)
