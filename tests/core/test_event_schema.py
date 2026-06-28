from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.core import (
    DocumentEntity,
    EntityKind,
    Event,
    EventStatus,
    EventType,
    EvidenceStatus,
)


def test_event_schema_records_claims_documents_and_assembly_key() -> None:
    event = Event(
        event_id="event:issuer:0000320193:sec_filing:20260628:4e4cc7bb",
        canonical_title="Apple SEC filing update",
        event_type=EventType.SEC_FILING,
        entities=(
            DocumentEntity(
                kind=EntityKind.CIK,
                value="0000320193",
                identifiers={"ticker": "AAPL"},
            ),
        ),
        event_time=datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc),
        status=EventStatus.NEW,
        related_doc_ids=("sec:apple:10q",),
        claim_ids=("sec:apple:10q:claim:000000",),
        evidence_status=EvidenceStatus.INSUFFICIENT,
        assembly_key="issuer:0000320193|sec_filing|20260628",
        metadata={"assembly_version": "event_assembler_v0.1"},
    )

    assert event.event_type is EventType.SEC_FILING
    assert event.status is EventStatus.NEW
    assert event.evidence_status is EvidenceStatus.INSUFFICIENT
    assert event.claim_ids == ("sec:apple:10q:claim:000000",)


def test_event_schema_requires_timezone_aware_event_time() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Event(
            event_id="event:issuer:0000320193:sec_filing:20260628:4e4cc7bb",
            canonical_title="Apple SEC filing update",
            event_type=EventType.SEC_FILING,
            event_time=datetime(2026, 6, 28, 8, 1),
            status=EventStatus.NEW,
            related_doc_ids=("sec:apple:10q",),
            claim_ids=("sec:apple:10q:claim:000000",),
            evidence_status=EvidenceStatus.INSUFFICIENT,
            assembly_key="issuer:0000320193|sec_filing|20260628",
        )


def test_event_schema_rejects_duplicate_claims_or_documents() -> None:
    with pytest.raises(ValidationError, match="claim_ids must be unique"):
        Event(
            event_id="event:issuer:0000320193:sec_filing:20260628:4e4cc7bb",
            canonical_title="Apple SEC filing update",
            event_type=EventType.SEC_FILING,
            event_time=datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc),
            status=EventStatus.NEW,
            related_doc_ids=("sec:apple:10q",),
            claim_ids=(
                "sec:apple:10q:claim:000000",
                "sec:apple:10q:claim:000000",
            ),
            evidence_status=EvidenceStatus.INSUFFICIENT,
            assembly_key="issuer:0000320193|sec_filing|20260628",
        )

    with pytest.raises(ValidationError, match="related_doc_ids must be unique"):
        Event(
            event_id="event:issuer:0000320193:sec_filing:20260628:4e4cc7bb",
            canonical_title="Apple SEC filing update",
            event_type=EventType.SEC_FILING,
            event_time=datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc),
            status=EventStatus.NEW,
            related_doc_ids=("sec:apple:10q", "sec:apple:10q"),
            claim_ids=("sec:apple:10q:claim:000000",),
            evidence_status=EvidenceStatus.INSUFFICIENT,
            assembly_key="issuer:0000320193|sec_filing|20260628",
        )
