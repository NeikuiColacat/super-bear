from datetime import datetime, timezone

from packages.core import (
    Claim,
    ClaimStatus,
    ClaimType,
    EvidenceRelation,
    EvidenceSpan,
    EventType,
    make_content_hash,
)
from packages.events import assemble_events


def _ts(day: int, hour: int = 8) -> datetime:
    return datetime(2026, 6, day, hour, 1, tzinfo=timezone.utc)


def _claim(index: int, text: str, *, doc_id: str = "sec:apple:10q") -> Claim:
    return Claim(
        claim_id=f"{doc_id}:claim:{index:06d}",
        event_id=None,
        claim_text=text,
        claim_type=ClaimType.FACT,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
        metadata={"extractor": "rule_stub_v0.1"},
    )


def _span(
    index: int,
    text: str,
    *,
    doc_id: str = "sec:apple:10q",
    claim_index: int | None = None,
    source_family_id: str = "issuer:0000320193",
    published_at: datetime | None = None,
    form: str = "10-Q",
) -> EvidenceSpan:
    claim_id = f"{doc_id}:claim:{claim_index if claim_index is not None else index:06d}"
    return EvidenceSpan(
        span_id=f"{doc_id}:span:{index:06d}",
        doc_id=doc_id,
        claim_id=claim_id,
        chunk_id=f"{doc_id}:chunk:000000",
        relation=EvidenceRelation.SUPPORT,
        text=text,
        char_start=0,
        char_end=len(text),
        source_type="sec_filing",
        source_tier="regulatory_primary",
        source_family_id=source_family_id,
        published_at=published_at or _ts(28),
        valid_from=published_at or _ts(28),
        confidence=0.3,
        metadata={
            "form": form,
            "content_hash": make_content_hash(text),
        },
    )


def test_assembler_groups_claims_from_same_document_into_one_event() -> None:
    claims = (
        _claim(0, "Net sales increased year over year."),
        _claim(1, "Operating income increased year over year."),
    )
    evidence_spans = (
        _span(0, claims[0].claim_text),
        _span(1, claims[1].claim_text),
    )

    events = assemble_events(claims=claims, evidence_spans=evidence_spans)

    assert len(events) == 1
    event = events[0]
    assert event.event_type is EventType.SEC_FILING
    assert event.related_doc_ids == ("sec:apple:10q",)
    assert event.claim_ids == (
        "sec:apple:10q:claim:000000",
        "sec:apple:10q:claim:000001",
    )
    assert event.assembly_key == "issuer:0000320193|sec_filing|10-Q|20260628"


def test_assembler_keeps_different_issuers_separate() -> None:
    claims = (
        _claim(0, "Net sales increased year over year.", doc_id="sec:apple:10q"),
        _claim(0, "Net sales increased year over year.", doc_id="sec:msft:10q"),
    )
    evidence_spans = (
        _span(0, claims[0].claim_text, doc_id="sec:apple:10q"),
        _span(
            0,
            claims[1].claim_text,
            doc_id="sec:msft:10q",
            source_family_id="issuer:0000789019",
        ),
    )

    events = assemble_events(claims=claims, evidence_spans=evidence_spans)

    assert len(events) == 2
    assert [event.assembly_key for event in events] == [
        "issuer:0000320193|sec_filing|10-Q|20260628",
        "issuer:0000789019|sec_filing|10-Q|20260628",
    ]


def test_assembler_keeps_different_date_windows_separate() -> None:
    claims = (
        _claim(0, "Net sales increased year over year.", doc_id="sec:apple:10q"),
        _claim(0, "Net sales increased year over year.", doc_id="sec:apple:10q-next"),
    )
    evidence_spans = (
        _span(0, claims[0].claim_text, doc_id="sec:apple:10q", published_at=_ts(28)),
        _span(
            0,
            claims[1].claim_text,
            doc_id="sec:apple:10q-next",
            published_at=_ts(29),
        ),
    )

    events = assemble_events(claims=claims, evidence_spans=evidence_spans)

    assert len(events) == 2
    assert [event.assembly_key for event in events] == [
        "issuer:0000320193|sec_filing|10-Q|20260628",
        "issuer:0000320193|sec_filing|10-Q|20260629",
    ]


def test_assembler_produces_stable_event_ids_for_input_order() -> None:
    claims = (
        _claim(0, "Net sales increased year over year."),
        _claim(1, "Operating income increased year over year."),
    )
    evidence_spans = (
        _span(0, claims[0].claim_text),
        _span(1, claims[1].claim_text),
    )

    forward = assemble_events(claims=claims, evidence_spans=evidence_spans)
    reversed_events = assemble_events(
        claims=tuple(reversed(claims)),
        evidence_spans=tuple(reversed(evidence_spans)),
    )

    assert [event.event_id for event in forward] == [
        event.event_id for event in reversed_events
    ]


def test_assembler_assigns_multiple_spans_for_one_claim_to_their_own_buckets() -> None:
    claim = _claim(0, "Net sales increased year over year.")
    evidence_spans = (
        _span(0, claim.claim_text, published_at=_ts(28), form="10-Q"),
        _span(1, claim.claim_text, claim_index=0, published_at=_ts(29), form="8-K"),
    )

    events = assemble_events(claims=(claim,), evidence_spans=evidence_spans)

    assert len(events) == 2
    assert [event.assembly_key for event in events] == [
        "issuer:0000320193|sec_filing|10-Q|20260628",
        "issuer:0000320193|sec_filing|8-K|20260629",
    ]
    assert all(event.claim_ids == (claim.claim_id,) for event in events)
