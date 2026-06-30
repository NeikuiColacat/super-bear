from datetime import datetime, timezone

from packages.core import (
    DocumentChunk,
    EvidenceRelation,
    SourceTier,
    SourceType,
    make_content_hash,
)
from packages.extraction.rule_stub import extract_candidate_pairs


def test_rule_stub_extracts_material_sentence_as_claim_and_evidence_candidate() -> None:
    text = (
        "Apple opened the filing with boilerplate. "
        "Net sales increased year over year. "
        "This closing sentence has no keyword."
    )
    chunk = DocumentChunk(
        chunk_id="sec:apple:10q:chunk:000000",
        doc_id="sec:apple:10q",
        chunk_index=0,
        text=text,
        char_start=100,
        char_end=100 + len(text),
        section_label="body",
        content_hash=make_content_hash(text),
        metadata={
            "source_type": SourceType.SEC_FILING,
            "source_tier": SourceTier.REGULATORY_PRIMARY,
            "source_family_id": "issuer:0000320193",
            "published_at": "2026-05-01T10:01:00Z",
        },
    )

    pairs = extract_candidate_pairs([chunk])

    assert len(pairs) == 1
    claim, evidence = pairs[0]
    assert claim.claim_text == "Net sales increased year over year."
    assert claim.chunk_id == chunk.chunk_id
    assert evidence.claim_candidate_id == claim.claim_candidate_id
    assert evidence.relation is EvidenceRelation.SUPPORT
    assert evidence.text == claim.claim_text
    assert evidence.char_start == text.index(claim.claim_text) + chunk.char_start
    assert evidence.char_end == evidence.char_start + len(evidence.text)
    assert evidence.published_at == datetime(2026, 5, 1, 10, 1, tzinfo=timezone.utc)


def test_rule_stub_skips_chunks_without_material_keywords() -> None:
    text = "This paragraph has ordinary background text."
    chunk = DocumentChunk(
        chunk_id="sec:apple:10q:chunk:000000",
        doc_id="sec:apple:10q",
        chunk_index=0,
        text=text,
        char_start=0,
        char_end=len(text),
        content_hash=make_content_hash(text),
    )

    assert extract_candidate_pairs([chunk]) == ()


def test_rule_stub_keeps_decimal_amounts_inside_sentence() -> None:
    text = "Record revenue $7.10 billion, up 12 percent year over year."
    chunk = DocumentChunk(
        chunk_id="sec:apple:10q:chunk:000000",
        doc_id="sec:apple:10q",
        chunk_index=0,
        text=text,
        char_start=0,
        char_end=len(text),
        section_label="body",
        content_hash=make_content_hash(text),
        metadata={
            "source_type": SourceType.SEC_FILING,
            "source_tier": SourceTier.REGULATORY_PRIMARY,
            "source_family_id": "issuer:0000320193",
            "published_at": "2026-05-01T10:01:00Z",
        },
    )

    pairs = extract_candidate_pairs([chunk])

    assert len(pairs) == 1
    claim, evidence = pairs[0]
    assert claim.claim_text == text
    assert evidence.text == text
