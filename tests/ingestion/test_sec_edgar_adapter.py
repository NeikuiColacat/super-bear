from datetime import datetime, timezone

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


def test_sec_edgar_adapter_returns_empty_success_batch_until_network_fetch_exists() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    adapter = SecEdgarAdapter(registry.get("sec_edgar"))

    batch = adapter.fetch(limit=3)

    assert batch.ok is True
    assert batch.source_id == "sec_edgar"
    assert batch.output_kind is OutputKind.DOCUMENT
    assert batch.records == ()
    assert batch.raw_uris == ()
    assert batch.records_seen == 0
    assert batch.records_written == 0
    assert batch.retrieved_at <= datetime.now(timezone.utc)
