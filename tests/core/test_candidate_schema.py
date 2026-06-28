from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.core import (
    Claim,
    ClaimCandidate,
    ClaimStatus,
    ClaimType,
    EvidenceRelation,
    EvidenceSpanCandidate,
    SourceTier,
    SourceType,
)


def _published_at() -> datetime:
    return datetime(2026, 5, 1, 10, 1, tzinfo=timezone.utc)


def test_claim_candidate_records_source_chunk_and_claim_type() -> None:
    candidate = ClaimCandidate(
        claim_candidate_id="sec:apple:10q:claim_candidate:000000",
        doc_id="sec:apple:10q",
        chunk_id="sec:apple:10q:chunk:000000",
        claim_text="Net sales increased year over year.",
        claim_type=ClaimType.FACT,
        confidence=0.3,
    )

    assert candidate.claim_type is ClaimType.FACT
    assert candidate.confidence == 0.3


def test_claim_allows_pre_event_ledger_entry() -> None:
    claim = Claim(
        claim_id="sec:apple:10q:claim:000000",
        event_id=None,
        claim_text="Net sales increased year over year.",
        claim_type=ClaimType.FACT,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
        metadata={"source_candidate_id": "sec:apple:10q:claim_candidate:000000"},
    )

    assert claim.event_id is None
    assert claim.status is ClaimStatus.SUPPORTED
    assert (
        claim.metadata["source_candidate_id"] == "sec:apple:10q:claim_candidate:000000"
    )


def test_evidence_span_candidate_keeps_absolute_document_offsets() -> None:
    source_text = "Apple reported that net sales increased year over year."
    text = "net sales increased year over year"
    start = source_text.index(text)
    candidate = EvidenceSpanCandidate(
        span_candidate_id="sec:apple:10q:evidence_span_candidate:000000",
        claim_candidate_id="sec:apple:10q:claim_candidate:000000",
        doc_id="sec:apple:10q",
        chunk_id="sec:apple:10q:chunk:000000",
        relation=EvidenceRelation.SUPPORT,
        text=text,
        char_start=start,
        char_end=start + len(text),
        source_type=SourceType.SEC_FILING,
        source_tier=SourceTier.REGULATORY_PRIMARY,
        source_family_id="issuer:0000320193",
        published_at=_published_at(),
        confidence=0.3,
    )

    assert source_text[candidate.char_start : candidate.char_end] == candidate.text


def test_candidate_models_reject_bad_ranges_or_confidence() -> None:
    with pytest.raises(ValidationError, match="greater than char_start"):
        EvidenceSpanCandidate(
            span_candidate_id="sec:apple:10q:evidence_span_candidate:000000",
            claim_candidate_id="sec:apple:10q:claim_candidate:000000",
            doc_id="sec:apple:10q",
            chunk_id="sec:apple:10q:chunk:000000",
            relation=EvidenceRelation.SUPPORT,
            text="net sales",
            char_start=10,
            char_end=5,
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id="issuer:0000320193",
            published_at=_published_at(),
            confidence=0.3,
        )

    with pytest.raises(ValidationError, match="less than or equal to 1"):
        ClaimCandidate(
            claim_candidate_id="sec:apple:10q:claim_candidate:000000",
            doc_id="sec:apple:10q",
            chunk_id="sec:apple:10q:chunk:000000",
            claim_text="Net sales increased year over year.",
            claim_type=ClaimType.FACT,
            confidence=1.1,
        )
