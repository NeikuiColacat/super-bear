from datetime import datetime, timezone

from packages.core import (
    ClaimStatus,
    ClaimType,
    DocumentChunk,
    EvidenceRelation,
    SourceTier,
    SourceType,
    make_content_hash,
)
from packages.evidence import build_pre_event_ledger


def _chunk() -> DocumentChunk:
    text = "First filing sentence. Net sales increased year over year."
    return DocumentChunk(
        chunk_id="sec:apple:10q:chunk:000000",
        doc_id="sec:apple:10q",
        chunk_index=0,
        text=text,
        char_start=100,
        char_end=100 + len(text),
        content_hash=make_content_hash(text),
        metadata={
            "source_type": SourceType.SEC_FILING,
            "source_tier": SourceTier.REGULATORY_PRIMARY,
            "source_family_id": "issuer:0000320193",
            "published_at": "2026-05-01T10:01:00Z",
        },
    )


def _claim_record() -> dict:
    return {
        "claim_candidate_id": "sec:apple:10q:claim_candidate:000000",
        "doc_id": "sec:apple:10q",
        "chunk_id": "sec:apple:10q:chunk:000000",
        "claim_text": "Net sales increased year over year.",
        "claim_type": ClaimType.FACT,
        "confidence": 0.3,
        "metadata": {"extractor": "rule_stub_v0.1"},
    }


def _evidence_record() -> dict:
    chunk = _chunk()
    start = chunk.text.index("Net sales increased year over year.") + chunk.char_start
    return {
        "span_candidate_id": "sec:apple:10q:evidence_span_candidate:000000",
        "claim_candidate_id": "sec:apple:10q:claim_candidate:000000",
        "doc_id": "sec:apple:10q",
        "chunk_id": "sec:apple:10q:chunk:000000",
        "relation": EvidenceRelation.SUPPORT,
        "text": "Net sales increased year over year.",
        "char_start": start,
        "char_end": start + len("Net sales increased year over year."),
        "source_type": "sec_filing",
        "source_tier": "regulatory_primary",
        "source_family_id": "issuer:0000320193",
        "published_at": datetime(2026, 5, 1, 10, 1, tzinfo=timezone.utc),
        "confidence": 0.3,
        "metadata": {"extractor": "rule_stub_v0.1"},
    }


def test_build_pre_event_ledger_promotes_valid_candidates() -> None:
    result = build_pre_event_ledger(
        claim_records=[_claim_record()],
        evidence_records=[_evidence_record()],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert result.validation_errors == ()
    assert len(result.claims) == 1
    assert len(result.evidence_spans) == 1

    claim = result.claims[0]
    evidence = result.evidence_spans[0]
    assert claim.claim_id == "sec:apple:10q:claim:000000"
    assert claim.event_id is None
    assert claim.status is ClaimStatus.SUPPORTED
    assert evidence.span_id == "sec:apple:10q:span:000000"
    assert evidence.claim_id == claim.claim_id
    assert evidence.text == "Net sales increased year over year."


def test_build_pre_event_ledger_skips_bad_offsets_and_records_error() -> None:
    evidence = _evidence_record()
    evidence["char_start"] = 100
    evidence["char_end"] = 100 + len(evidence["text"])

    result = build_pre_event_ledger(
        claim_records=[_claim_record()],
        evidence_records=[evidence],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert result.claims == ()
    assert result.evidence_spans == ()
    assert len(result.validation_errors) == 1
    assert result.validation_errors[0].code == "evidence_text_offset_mismatch"
    assert result.validation_errors[0].object_id == (
        "sec:apple:10q:evidence_span_candidate:000000"
    )


def test_build_pre_event_ledger_rejects_source_provenance_mismatch() -> None:
    evidence = _evidence_record()
    evidence["source_family_id"] = "issuer:0000789019"

    result = build_pre_event_ledger(
        claim_records=[_claim_record()],
        evidence_records=[evidence],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert result.claims == ()
    assert result.evidence_spans == ()
    assert result.validation_errors[0].code == "source_family_id_mismatch"


def test_build_pre_event_ledger_reports_orphan_evidence_candidate() -> None:
    evidence = _evidence_record()
    evidence["claim_candidate_id"] = "sec:apple:10q:claim_candidate:999999"

    result = build_pre_event_ledger(
        claim_records=[_claim_record()],
        evidence_records=[evidence],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert result.claims == ()
    assert result.evidence_spans == ()
    assert result.validation_errors[0].code == "claim_candidate_missing"
    assert result.validation_errors[0].object_id == (
        "sec:apple:10q:evidence_span_candidate:000000"
    )


def test_build_pre_event_ledger_requires_claim_text_to_match_evidence_text() -> None:
    claim = _claim_record()
    claim["claim_text"] = "Revenue increased year over year."

    result = build_pre_event_ledger(
        claim_records=[claim],
        evidence_records=[_evidence_record()],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert result.claims == ()
    assert result.evidence_spans == ()
    assert result.validation_errors[0].code == "claim_text_evidence_text_mismatch"


def test_build_pre_event_ledger_reports_duplicate_claim_candidate_ids() -> None:
    result = build_pre_event_ledger(
        claim_records=[_claim_record(), _claim_record()],
        evidence_records=[_evidence_record()],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert len(result.claims) == 1
    assert len(result.evidence_spans) == 1
    assert [error.code for error in result.validation_errors] == [
        "duplicate_claim_candidate_id"
    ]


def test_build_pre_event_ledger_reports_duplicate_span_candidate_ids() -> None:
    result = build_pre_event_ledger(
        claim_records=[_claim_record()],
        evidence_records=[_evidence_record(), _evidence_record()],
        chunk_records=[_chunk().model_dump(mode="json")],
    )

    assert len(result.claims) == 1
    assert len(result.evidence_spans) == 1
    assert [error.code for error in result.validation_errors] == [
        "duplicate_span_candidate_id"
    ]
