from datetime import datetime, timezone
import json

from packages.core import EntityKind, SourceTier, SourceType, make_content_hash
from packages.ingestion.parsers.sec_submissions import (
    DEFAULT_SEC_DOCUMENT_FORMS,
    parse_sec_submissions_bytes,
)


def _raw_payload() -> bytes:
    return json.dumps(
        {
            "cik": "0000320193",
            "name": "Apple Inc.",
            "tickers": ["AAPL"],
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0000320193-26-000010",
                        "0000320193-26-000011",
                        "0000320193-26-000012",
                    ],
                    "filingDate": ["2026-05-01", "2026-05-02", "2026-05-03"],
                    "reportDate": ["2026-03-28", "2026-05-01", "2026-05-03"],
                    "acceptanceDateTime": [
                        "2026-05-01T22:03:00.000Z",
                        "2026-05-02T12:00:00.000Z",
                        "",
                    ],
                    "form": ["10-Q", "4", "8-K"],
                    "primaryDocument": [
                        "aapl-20260328.htm",
                        "xslF345X06/form4.xml",
                        "aapl-8k.htm",
                    ],
                    "primaryDocDescription": ["10-Q", "FORM 4", "8-K"],
                    "items": ["", "", "2.02"],
                    "size": [123, 456, 789],
                    "isXBRL": [1, 0, 0],
                    "isInlineXBRL": [1, 0, 1],
                }
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def test_sec_submissions_parser_builds_document_records_from_recent_filings() -> None:
    raw = _raw_payload()
    retrieved_at = datetime(2026, 6, 28, 8, 30, tzinfo=timezone.utc)

    documents = parse_sec_submissions_bytes(
        raw,
        raw_object_uri="data/raw/sec_edgar/0000320193/submissions.json",
        content_hash=make_content_hash(raw),
        retrieved_at=retrieved_at,
    )

    assert [document.metadata["form"] for document in documents] == ["10-Q", "8-K"]
    first = documents[0]
    assert first.doc_id == "sec:0000320193:0000320193-26-000010:aapl-20260328.htm"
    assert first.source_id == "sec_edgar"
    assert first.source_type is SourceType.SEC_FILING
    assert first.source_tier is SourceTier.REGULATORY_PRIMARY
    assert first.source_family_id == "issuer:0000320193"
    assert first.title == "Apple Inc. 10-Q filed 2026-05-01"
    assert (
        str(first.url)
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000010/aapl-20260328.htm"
    )
    assert first.published_at == datetime(2026, 5, 1, 22, 3, tzinfo=timezone.utc)
    assert first.retrieved_at == retrieved_at
    assert first.raw_object_uri == "data/raw/sec_edgar/0000320193/submissions.json"
    assert first.content_hash == make_content_hash(raw)
    assert first.parser_version == "sec_submissions_v0.1"
    assert {entity.kind for entity in first.entities} >= {
        EntityKind.COMPANY,
        EntityKind.TICKER,
        EntityKind.CIK,
        EntityKind.FORM,
        EntityKind.ACCESSION_NUMBER,
    }
    assert first.metadata["accession_number"] == "0000320193-26-000010"
    assert first.metadata["primary_document"] == "aapl-20260328.htm"
    assert first.metadata["report_date"] == "2026-03-28"

    second = documents[1]
    assert second.published_at == datetime(2026, 5, 3, tzinfo=timezone.utc)
    assert second.metadata["items"] == "2.02"


def test_sec_submissions_parser_allows_custom_form_filter() -> None:
    documents = parse_sec_submissions_bytes(
        _raw_payload(),
        raw_object_uri="data/raw/sec_edgar/0000320193/submissions.json",
        content_hash=make_content_hash(_raw_payload()),
        retrieved_at=datetime(2026, 6, 28, 8, 30, tzinfo=timezone.utc),
        include_forms=("4",),
    )

    assert [document.metadata["form"] for document in documents] == ["4"]


def test_default_sec_document_forms_match_first_mvp_scope() -> None:
    assert DEFAULT_SEC_DOCUMENT_FORMS == ("8-K", "10-K", "10-Q", "DEF 14A")
