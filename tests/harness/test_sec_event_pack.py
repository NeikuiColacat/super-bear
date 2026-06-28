from datetime import datetime, timezone

from packages.core import EvidenceStatus, make_content_hash
from packages.harness import (
    InvestigatorResult,
    ResultStatus,
    validate_investigator_result,
)
from packages.harness.sec_event_pack import build_sec_event_pack_request


def test_build_sec_event_pack_request_from_document_record() -> None:
    text = (
        "Apple filed a quarterly report. "
        "Net sales increased year over year. "
        "Ordinary closing text."
    )
    record = {
        "doc_id": "sec:0000320193:0000320193-26-000013:aapl-20260328.htm",
        "source_id": "sec_edgar",
        "source_type": "sec_filing",
        "source_tier": "regulatory_primary",
        "source_family_id": "issuer:0000320193",
        "title": "Apple Inc. 10-Q filed 2026-05-01",
        "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm",
        "published_at": datetime(2026, 5, 1, 10, 1, tzinfo=timezone.utc),
        "retrieved_at": datetime(2026, 6, 28, 9, 5, tzinfo=timezone.utc),
        "raw_object_uri": "data/raw/sec_edgar/0000320193/submissions.json",
        "content_hash": make_content_hash(text),
        "parser_version": "sec_submissions_v0.1",
        "language": "en",
        "entities": [],
        "metadata": {
            "form": "10-Q",
            "filing_date": "2026-05-01",
            "primary_document_text_excerpt": text,
        },
    }

    request = build_sec_event_pack_request(
        record,
        investigator_run_id="investigator_run_sec_10q_smoke",
        max_claims=1,
    )

    event_pack = request.event_pack
    assert event_pack["event"]["event_type"] == "sec_filing"
    assert len(event_pack["chunks"]) == 1
    assert len(event_pack["claims"]) == 1
    assert len(event_pack["evidence_spans"]) == 1
    assert (
        event_pack["claims"][0]["claim_text"] == "Net sales increased year over year."
    )
    assert event_pack["event_card"]["key_claim_ids"] == [
        event_pack["claims"][0]["claim_id"]
    ]

    result = InvestigatorResult(
        schema_version="investigator_result.v0",
        investigator_run_id=request.investigator_run_id,
        status=ResultStatus.STOP,
        evidence_status=EvidenceStatus.SUFFICIENT,
        citations=[
            {
                "claim_id": event_pack["claims"][0]["claim_id"],
                "evidence_span_id": event_pack["evidence_spans"][0]["span_id"],
            }
        ],
    )

    assert validate_investigator_result(request, result).ok is True


def test_build_sec_event_pack_request_keeps_only_evidence_chunks() -> None:
    text = "Net sales increased year over year. " + ("ordinary background text " * 140)
    record = {
        "doc_id": "sec:0000320193:0000320193-26-000013:aapl-20260328.htm",
        "source_id": "sec_edgar",
        "source_type": "sec_filing",
        "source_tier": "regulatory_primary",
        "source_family_id": "issuer:0000320193",
        "title": "Apple Inc. 10-Q filed 2026-05-01",
        "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm",
        "published_at": datetime(2026, 5, 1, 10, 1, tzinfo=timezone.utc),
        "retrieved_at": datetime(2026, 6, 28, 9, 5, tzinfo=timezone.utc),
        "raw_object_uri": "data/raw/sec_edgar/0000320193/submissions.json",
        "content_hash": make_content_hash(text),
        "parser_version": "sec_submissions_v0.1",
        "language": "en",
        "entities": [],
        "metadata": {
            "form": "10-Q",
            "filing_date": "2026-05-01",
            "primary_document_text_excerpt": text,
        },
    }

    request = build_sec_event_pack_request(
        record,
        investigator_run_id="investigator_run_sec_10q_smoke",
        max_claims=1,
    )

    referenced_chunk_ids = {
        span["chunk_id"] for span in request.event_pack["evidence_spans"]
    }

    assert len(request.event_pack["chunks"]) == len(referenced_chunk_ids)


def test_build_sec_event_pack_request_prefers_operating_claims_over_toc_risk() -> None:
    text = (
        "Quantitative and Qualitative Disclosures About Market Risk 19 Item 4. "
        "Note 2 - Revenue The following table shows disaggregated net sales."
    )
    record = {
        "doc_id": "sec:0000320193:0000320193-26-000013:aapl-20260328.htm",
        "source_id": "sec_edgar",
        "source_type": "sec_filing",
        "source_tier": "regulatory_primary",
        "source_family_id": "issuer:0000320193",
        "title": "Apple Inc. 10-Q filed 2026-05-01",
        "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm",
        "published_at": datetime(2026, 5, 1, 10, 1, tzinfo=timezone.utc),
        "retrieved_at": datetime(2026, 6, 28, 9, 5, tzinfo=timezone.utc),
        "raw_object_uri": "data/raw/sec_edgar/0000320193/submissions.json",
        "content_hash": make_content_hash(text),
        "parser_version": "sec_submissions_v0.1",
        "language": "en",
        "entities": [],
        "metadata": {
            "form": "10-Q",
            "filing_date": "2026-05-01",
            "primary_document_text_excerpt": text,
        },
    }

    request = build_sec_event_pack_request(
        record,
        investigator_run_id="investigator_run_sec_10q_smoke",
        max_claims=1,
    )

    assert "net sales" in request.event_pack["claims"][0]["claim_text"].lower()
