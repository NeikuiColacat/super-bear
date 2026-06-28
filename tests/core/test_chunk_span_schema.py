from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.core import (
    Document,
    DocumentChunk,
    DocumentEntity,
    EntityKind,
    EvidenceRelation,
    EvidenceSpan,
    SourceTier,
    SourceType,
    make_content_hash,
    make_doc_id,
    make_issuer_family_id,
)


def _document() -> Document:
    return Document(
        doc_id=make_doc_id("sec", "0000320193", "0000320193-26-000013"),
        source_id="sec_edgar",
        source_type=SourceType.SEC_FILING,
        source_tier=SourceTier.REGULATORY_PRIMARY,
        source_family_id=make_issuer_family_id("0000320193"),
        title="Apple Inc. 10-Q filed 2026-05-01",
        url="https://www.sec.gov/example.htm",
        published_at=datetime(2026, 5, 1, 22, 3, tzinfo=timezone.utc),
        retrieved_at=datetime(2026, 6, 28, 8, 30, tzinfo=timezone.utc),
        raw_object_uri="data/raw/sec_edgar/0000320193/submissions.json",
        content_hash=make_content_hash("document metadata"),
        parser_version="sec_submissions_v0.1",
        entities=[
            DocumentEntity(kind=EntityKind.COMPANY, value="Apple Inc."),
            DocumentEntity(kind=EntityKind.TICKER, value="AAPL"),
        ],
    )


def test_document_chunk_records_stable_text_coordinates() -> None:
    text = "Apple reported higher services revenue."
    chunk = DocumentChunk(
        chunk_id=f"{_document().doc_id}:chunk:000000",
        doc_id=_document().doc_id,
        chunk_index=0,
        text=text[6:14],
        char_start=6,
        char_end=14,
        section_label="body",
        content_hash=make_content_hash(text[6:14]),
    )

    assert text[chunk.char_start : chunk.char_end] == chunk.text
    assert chunk.content_hash == make_content_hash("reported")


def test_document_chunk_rejects_empty_or_reversed_ranges() -> None:
    with pytest.raises(
        ValidationError, match="char_end must be greater than char_start"
    ):
        DocumentChunk(
            chunk_id="sec:test:chunk:000000",
            doc_id="sec:test",
            chunk_index=0,
            text="Apple",
            char_start=10,
            char_end=5,
            content_hash=make_content_hash("Apple"),
        )


def test_evidence_span_carries_source_provenance_for_a_claim() -> None:
    document = _document()
    text = "Services revenue increased year over year."
    span = EvidenceSpan(
        span_id=f"{document.doc_id}:span:000000",
        doc_id=document.doc_id,
        claim_id=f"{document.doc_id}:claim:000000",
        chunk_id=f"{document.doc_id}:chunk:000000",
        relation=EvidenceRelation.SUPPORT,
        text=text,
        char_start=120,
        char_end=120 + len(text),
        source_type=document.source_type,
        source_tier=document.source_tier,
        source_family_id=document.source_family_id,
        published_at=document.published_at,
        valid_from=document.published_at,
        confidence=0.91,
    )

    assert span.relation is EvidenceRelation.SUPPORT
    assert span.chunk_id == f"{document.doc_id}:chunk:000000"
    assert span.source_tier is SourceTier.REGULATORY_PRIMARY
    assert span.source_family_id == "issuer:0000320193"


def test_evidence_span_rejects_invalid_confidence_and_non_document_source() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        EvidenceSpan(
            span_id="sec:test:span:000000",
            doc_id="sec:test",
            claim_id="sec:test:claim:000000",
            relation=EvidenceRelation.SUPPORT,
            text="Apple",
            char_start=0,
            char_end=5,
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id="issuer:0000320193",
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            confidence=1.1,
        )

    with pytest.raises(ValidationError, match="not a document source_type"):
        EvidenceSpan(
            span_id="search:test:span:000000",
            doc_id="search:test",
            claim_id="search:test:claim:000000",
            relation=EvidenceRelation.SUPPORT,
            text="Apple",
            char_start=0,
            char_end=5,
            source_type=SourceType.SEARCH,
            source_tier=SourceTier.SEARCH_LEAD,
            source_family_id="provider:tavily",
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            confidence=0.5,
        )


def test_evidence_span_rejects_text_length_that_does_not_match_range() -> None:
    with pytest.raises(ValidationError, match="span text length must match char range"):
        EvidenceSpan(
            span_id="sec:test:span:000000",
            doc_id="sec:test",
            claim_id="sec:test:claim:000000",
            relation=EvidenceRelation.SUPPORT,
            text="Apple",
            char_start=0,
            char_end=10,
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id="issuer:0000320193",
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            confidence=0.5,
        )
