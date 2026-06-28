from datetime import datetime, timezone
import json

from packages.core import (
    Claim,
    ClaimStatus,
    ClaimType,
    Document,
    DocumentChunk,
    EvidenceRelation,
    EvidenceSpan,
    EvidenceStatus,
    Event,
    EventStatus,
    EventType,
    SourceTier,
    SourceType,
    make_content_hash,
)
from packages.tools import JsonlStore, ReadApi


def _ts() -> datetime:
    return datetime(2026, 6, 28, 8, 1, tzinfo=timezone.utc)


def _write_jsonl(path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _seed(normalized_dir) -> tuple[str, str, str]:
    doc = Document(
        doc_id="sec:apple:10q",
        source_id="sec_edgar",
        source_type=SourceType.SEC_FILING,
        source_tier=SourceTier.REGULATORY_PRIMARY,
        source_family_id="issuer:0000320193",
        title="Apple 10-Q",
        url="https://www.sec.gov/aapl-10q.htm",
        published_at=_ts(),
        retrieved_at=_ts(),
        raw_object_uri="data/raw/sec/aapl.htm",
        content_hash=make_content_hash("doc"),
        parser_version="test_v0",
    )
    chunk = DocumentChunk(
        chunk_id="sec:apple:10q:chunk:000000",
        doc_id=doc.doc_id,
        chunk_index=0,
        text="Net sales increased year over year.",
        char_start=0,
        char_end=len("Net sales increased year over year."),
        content_hash=make_content_hash("chunk"),
    )
    claim = Claim(
        claim_id="sec:apple:10q:claim:000000",
        claim_text=chunk.text,
        claim_type=ClaimType.FACT,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
    )
    span = EvidenceSpan(
        span_id="sec:apple:10q:span:000000",
        doc_id=doc.doc_id,
        claim_id=claim.claim_id,
        chunk_id=chunk.chunk_id,
        relation=EvidenceRelation.SUPPORT,
        text=chunk.text,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        source_type=SourceType.SEC_FILING,
        source_tier=SourceTier.REGULATORY_PRIMARY,
        source_family_id=doc.source_family_id,
        published_at=_ts(),
        valid_from=_ts(),
        confidence=0.8,
    )
    event = Event(
        event_id="event:issuer:0000320193:sec_filing:10-q:20260628:abcd1234",
        canonical_title="Apple filed a quarterly report.",
        event_type=EventType.SEC_FILING,
        event_time=_ts(),
        status=EventStatus.NEW,
        related_doc_ids=(doc.doc_id,),
        claim_ids=(claim.claim_id,),
        evidence_status=EvidenceStatus.SUFFICIENT,
        assembly_key="issuer:0000320193|sec_filing|10-Q|20260628",
    )
    _write_jsonl(normalized_dir / "documents.jsonl", [doc.model_dump(mode="json")])
    _write_jsonl(
        normalized_dir / "document_chunks.jsonl",
        [chunk.model_dump(mode="json")],
    )
    _write_jsonl(normalized_dir / "claims.jsonl", [claim.model_dump(mode="json")])
    _write_jsonl(
        normalized_dir / "evidence_spans.jsonl",
        [span.model_dump(mode="json")],
    )
    _write_jsonl(normalized_dir / "events.jsonl", [event.model_dump(mode="json")])
    return event.event_id, claim.claim_id, span.span_id


def test_read_api_loads_event_pack_from_jsonl(tmp_path) -> None:
    event_id, claim_id, span_id = _seed(tmp_path)

    api = ReadApi(JsonlStore(tmp_path))
    pack = api.get_event_pack(event_id)

    assert pack["event"]["event_id"] == event_id
    assert pack["claims"][0]["claim_id"] == claim_id
    assert pack["evidence_spans"][0]["span_id"] == span_id
    assert pack["chunks"][0]["chunk_id"] == "sec:apple:10q:chunk:000000"


def test_read_api_validates_evidence_span_offsets(tmp_path) -> None:
    _event_id, _claim_id, _span_id = _seed(tmp_path)

    api = ReadApi(JsonlStore(tmp_path))

    assert api.validate_evidence_span(
        doc_id="sec:apple:10q",
        text="Net sales increased year over year.",
        char_start=0,
        char_end=len("Net sales increased year over year."),
    ) == {"ok": True, "chunk_id": "sec:apple:10q:chunk:000000"}
