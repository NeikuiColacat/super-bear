from datetime import datetime, timezone
import json
from urllib.error import HTTPError

import pytest

from packages.core import OutputKind
from packages.ingestion.adapters.sec_edgar import (
    SecEdgarAdapter,
    build_archive_index_url,
    build_companyfacts_url,
    build_primary_document_url,
    build_request_headers,
    build_submissions_url,
    normalize_cik,
)
from packages.ingestion.registry import SourceRegistry


def test_normalize_cik_zero_pads_to_ten_digits() -> None:
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("0000320193") == "0000320193"
    assert normalize_cik(320193) == "0000320193"


@pytest.mark.parametrize("bad_cik", ["", "AAPL", "00000000000", "-320193"])
def test_normalize_cik_rejects_invalid_values(bad_cik: str) -> None:
    with pytest.raises(ValueError, match="CIK"):
        normalize_cik(bad_cik)


def test_sec_edgar_url_builders_use_official_archive_shapes() -> None:
    assert (
        build_submissions_url("320193")
        == "https://data.sec.gov/submissions/CIK0000320193.json"
    )
    assert (
        build_companyfacts_url("320193")
        == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )
    assert (
        build_archive_index_url("0000320193", "0000320193-26-000013")
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/index.json"
    )
    assert (
        build_primary_document_url(
            "0000320193",
            "0000320193-26-000013",
            "aapl-20260328.htm",
        )
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm"
    )


def test_build_request_headers_includes_user_agent() -> None:
    assert build_request_headers("super-bear-dev contact@example.com") == {
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "User-Agent": "super-bear-dev contact@example.com",
    }


def test_sec_edgar_adapter_requires_user_agent_before_network_fetch(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    adapter = SecEdgarAdapter(
        registry.get("sec_edgar"),
        raw_dir=tmp_path / "raw",
        options={"ciks": ["320193"]},
        fetch_bytes=lambda url, headers, timeout: pytest.fail("network should not run"),
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is False
    assert batch.error is not None
    assert batch.error.code == "missing_user_agent"
    assert batch.records == ()
    assert batch.raw_uris == ()


def test_sec_edgar_adapter_fetches_submissions_json_to_raw_store(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    seen_requests = []

    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        seen_requests.append((url, headers, timeout))
        return json.dumps(
            {
                "cik": "0000320193",
                "name": "Apple Inc.",
                "tickers": ["AAPL"],
                "filings": {
                    "recent": {
                        "accessionNumber": ["0000320193-26-000010"],
                        "filingDate": ["2026-05-01"],
                        "reportDate": ["2026-03-28"],
                        "acceptanceDateTime": ["2026-05-01T22:03:00.000Z"],
                        "form": ["10-Q"],
                        "primaryDocument": ["aapl-20260328.htm"],
                        "primaryDocDescription": ["10-Q"],
                        "items": [""],
                        "size": [123],
                        "isXBRL": [1],
                        "isInlineXBRL": [1],
                    }
                },
            }
        ).encode("utf-8")

    adapter = SecEdgarAdapter(
        registry.get("sec_edgar"),
        raw_dir=tmp_path / "raw",
        options={
            "ciks": ["320193"],
            "user_agent": "super-bear-dev contact@example.com",
            "request_timeout_seconds": 7,
        },
        fetch_bytes=fake_fetch,
    )

    batch = adapter.fetch(limit=1)

    raw_path = tmp_path / "raw" / "sec_edgar" / "0000320193" / "submissions.json"
    assert batch.ok is True
    assert batch.source_id == "sec_edgar"
    assert batch.output_kind is OutputKind.DOCUMENT
    assert len(batch.records) == 1
    assert batch.records[0]["doc_id"] == (
        "sec:0000320193:0000320193-26-000010:aapl-20260328.htm"
    )
    assert batch.records[0]["metadata"]["form"] == "10-Q"
    assert batch.raw_uris == (str(raw_path),)
    assert json.loads(raw_path.read_text(encoding="utf-8"))["name"] == "Apple Inc."

    assert seen_requests == [
        (
            "https://data.sec.gov/submissions/CIK0000320193.json",
            {
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "User-Agent": "super-bear-dev contact@example.com",
            },
            7,
        )
    ]


def test_sec_edgar_adapter_throttles_between_sec_requests(tmp_path) -> None:
    registry = SourceRegistry.from_items(
        [
            {
                "source_id": "sec_edgar",
                "enabled": True,
                "adapter": "sec_edgar",
                "output_kind": "document",
                "default_source_type": "sec_filing",
                "allowed_source_types": ["sec_filing"],
                "source_tier": "regulatory_primary",
                "source_family_strategy": "issuer",
                "requires_api_key": False,
                "rate_limit_per_second": 4,
                "license_notes": "test source",
            }
        ]
    )
    seen_urls: list[str] = []
    sleeps: list[float] = []

    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        seen_urls.append(url)
        return json.dumps(
            {
                "cik": "0000000000",
                "name": "Test Co.",
                "tickers": ["TEST"],
                "filings": {"recent": {"accessionNumber": []}},
            }
        ).encode("utf-8")

    adapter = SecEdgarAdapter(
        registry.get("sec_edgar"),
        raw_dir=tmp_path / "raw",
        options={
            "ciks": ["1", "2"],
            "user_agent": "super-bear-dev contact@example.com",
        },
        fetch_bytes=fake_fetch,
        sleep=sleeps.append,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert seen_urls == [
        "https://data.sec.gov/submissions/CIK0000000001.json",
        "https://data.sec.gov/submissions/CIK0000000002.json",
    ]
    assert sleeps == [0.25]


def test_sec_edgar_adapter_can_fetch_primary_document_html(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    seen_urls = []

    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        seen_urls.append(url)
        if url == "https://data.sec.gov/submissions/CIK0000320193.json":
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
                            ],
                            "filingDate": ["2026-05-01", "2026-04-30"],
                            "reportDate": ["2026-03-28", "2026-04-30"],
                            "acceptanceDateTime": [
                                "2026-05-01T22:03:00.000Z",
                                "2026-04-30T12:00:00.000Z",
                            ],
                            "form": ["10-Q", "8-K"],
                            "primaryDocument": [
                                "aapl-20260328.htm",
                                "aapl-20260430.htm",
                            ],
                            "primaryDocDescription": ["10-Q", "8-K"],
                            "items": ["", "2.02"],
                            "size": [123, 456],
                            "isXBRL": [1, 0],
                            "isInlineXBRL": [1, 1],
                        }
                    },
                }
            ).encode("utf-8")
        if url.endswith("/aapl-20260328.htm"):
            return b"<html><body><p>Revenue increased year over year.</p></body></html>"
        raise AssertionError(f"unexpected URL: {url}")

    adapter = SecEdgarAdapter(
        registry.get("sec_edgar"),
        raw_dir=tmp_path / "raw",
        options={
            "ciks": ["320193"],
            "user_agent": "super-bear-dev contact@example.com",
            "fetch_primary_documents": True,
            "primary_document_limit": 1,
            "text_excerpt_chars": 64,
        },
        fetch_bytes=fake_fetch,
    )

    batch = adapter.fetch(limit=1)

    html_path = (
        tmp_path
        / "raw"
        / "sec_edgar"
        / "0000320193"
        / "000032019326000010"
        / "aapl-20260328.htm"
    )
    assert batch.ok is True
    assert len(batch.records) == 2
    assert html_path.read_bytes() == (
        b"<html><body><p>Revenue increased year over year.</p></body></html>"
    )
    assert str(html_path) in batch.raw_uris
    first_metadata = batch.records[0]["metadata"]
    assert first_metadata["primary_document_raw_uri"] == str(html_path)
    assert first_metadata["primary_document_text_excerpt"] == (
        "Revenue increased year over year."
    )
    assert first_metadata["primary_document_content_hash"].startswith("sha256:")
    assert "primary_document_raw_uri" not in batch.records[1]["metadata"]
    assert seen_urls == [
        "https://data.sec.gov/submissions/CIK0000320193.json",
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019326000010/aapl-20260328.htm",
    ]


def test_sec_edgar_adapter_filters_recent_filings_before_body_fetch(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    def fake_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        if url == "https://data.sec.gov/submissions/CIK0000320193.json":
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
                            "filingDate": [
                                "2026-06-29",
                                "2026-06-28",
                                "2026-05-01",
                            ],
                            "reportDate": [
                                "2026-06-29",
                                "2026-06-28",
                                "2026-03-28",
                            ],
                            "acceptanceDateTime": [
                                "2026-06-29T20:00:00.000Z",
                                "2026-06-28T20:00:00.000Z",
                                "2026-05-01T22:03:00.000Z",
                            ],
                            "form": ["8-K", "8-K", "10-Q"],
                            "primaryDocument": [
                                "aapl-20260629.htm",
                                "aapl-20260628.htm",
                                "aapl-20260328.htm",
                            ],
                            "primaryDocDescription": ["8-K", "8-K", "10-Q"],
                            "items": ["2.02", "5.02", ""],
                            "size": [123, 456, 789],
                            "isXBRL": [0, 0, 1],
                            "isInlineXBRL": [1, 1, 1],
                        }
                    },
                }
            ).encode("utf-8")
        if url.endswith("/aapl-20260629.htm"):
            return b"<html><body><p>Revenue increased.</p></body></html>"
        raise AssertionError(f"unexpected URL: {url}")

    adapter = SecEdgarAdapter(
        registry.get("sec_edgar"),
        raw_dir=tmp_path / "raw",
        options={
            "ciks": ["320193"],
            "user_agent": "super-bear-dev contact@example.com",
            "include_forms": ["8-K"],
            "published_after": datetime(2026, 6, 29, tzinfo=timezone.utc),
            "max_filings_per_cik": 1,
            "fetch_primary_documents": True,
            "primary_document_limit": 1,
        },
        fetch_bytes=fake_fetch,
    )

    batch = adapter.fetch()

    assert batch.ok is True
    assert len(batch.records) == 1
    assert batch.records[0]["metadata"]["accession_number"] == ("0000320193-26-000010")
    assert batch.records[0]["metadata"]["primary_document_raw_uri"].endswith(
        "aapl-20260629.htm"
    )


def test_sec_edgar_adapter_records_http_errors(tmp_path) -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    def failing_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    adapter = SecEdgarAdapter(
        registry.get("sec_edgar"),
        raw_dir=tmp_path / "raw",
        options={
            "ciks": ["320193"],
            "user_agent": "super-bear-dev contact@example.com",
        },
        fetch_bytes=failing_fetch,
    )

    batch = adapter.fetch(limit=1)

    assert batch.ok is False
    assert batch.source_id == "sec_edgar"
    assert batch.output_kind is OutputKind.DOCUMENT
    assert batch.records == ()
    assert batch.raw_uris == ()
    assert batch.records_seen == 0
    assert batch.records_written == 0
    assert batch.retrieved_at <= datetime.now(timezone.utc)
    assert batch.error is not None
    assert batch.error.code == "http_error"
    assert batch.error.retryable is False
    assert batch.error.details["status_code"] == 403
