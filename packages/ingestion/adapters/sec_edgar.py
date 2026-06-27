from __future__ import annotations

from datetime import datetime, timezone

from .base import AdapterBatch, BaseSourceAdapter


DATA_SEC_BASE_URL = "https://data.sec.gov"
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"


def normalize_cik(cik: str | int) -> str:
    value = str(cik).strip()
    if not value.isdigit():
        raise ValueError(f"CIK must contain only digits: {cik!r}")
    if not 1 <= len(value) <= 10:
        raise ValueError(f"CIK must be 1 to 10 digits: {cik!r}")
    return value.zfill(10)


def _archive_cik_path(cik: str | int) -> str:
    return str(int(normalize_cik(cik)))


def _archive_accession_path(accession_number: str) -> str:
    value = accession_number.strip()
    if not value:
        raise ValueError("accession_number cannot be empty")
    return value.replace("-", "")


def build_submissions_url(cik: str | int) -> str:
    return f"{DATA_SEC_BASE_URL}/submissions/CIK{normalize_cik(cik)}.json"


def build_companyfacts_url(cik: str | int) -> str:
    return f"{DATA_SEC_BASE_URL}/api/xbrl/companyfacts/CIK{normalize_cik(cik)}.json"


def build_archive_index_url(cik: str | int, accession_number: str) -> str:
    cik_path = _archive_cik_path(cik)
    accession_path = _archive_accession_path(accession_number)
    return f"{ARCHIVES_BASE_URL}/{cik_path}/{accession_path}/index.json"


def build_primary_document_url(
    cik: str | int,
    accession_number: str,
    primary_document: str,
) -> str:
    document_name = primary_document.strip()
    if not document_name:
        raise ValueError("primary_document cannot be empty")
    cik_path = _archive_cik_path(cik)
    accession_path = _archive_accession_path(accession_number)
    return f"{ARCHIVES_BASE_URL}/{cik_path}/{accession_path}/{document_name}"


def build_request_headers(user_agent: str) -> dict[str, str]:
    value = user_agent.strip()
    if not value:
        raise ValueError("SEC requests require a non-empty user_agent")
    return {
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "User-Agent": value,
    }


class SecEdgarAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=[],
            raw_uris=[],
            retrieved_at=datetime.now(timezone.utc),
        )
