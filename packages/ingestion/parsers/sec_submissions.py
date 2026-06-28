from __future__ import annotations

from datetime import datetime, timezone
import json

from packages.core import (
    Document,
    DocumentEntity,
    EntityKind,
    SourceTier,
    SourceType,
    make_doc_id,
    make_issuer_family_id,
)
from packages.ingestion.adapters.sec_edgar import (
    build_primary_document_url,
    normalize_cik,
)


DEFAULT_SEC_DOCUMENT_FORMS = ("8-K", "10-K", "10-Q", "DEF 14A")
SEC_SUBMISSIONS_PARSER_VERSION = "sec_submissions_v0.1"


def parse_sec_submissions_bytes(
    content: bytes,
    *,
    raw_object_uri: str,
    content_hash: str,
    retrieved_at: datetime,
    include_forms: tuple[str, ...] = DEFAULT_SEC_DOCUMENT_FORMS,
    source_id: str = "sec_edgar",
    limit: int | None = None,
) -> tuple[Document, ...]:
    payload = json.loads(content)
    cik = normalize_cik(payload["cik"])
    company_name = str(payload.get("name") or cik).strip()
    ticker = _first_text(payload.get("tickers"))
    recent = payload.get("filings", {}).get("recent", {})
    include_form_set = {form.strip().upper() for form in include_forms if form.strip()}

    documents: list[Document] = []
    accession_numbers = recent.get("accessionNumber") or []
    for index, accession_number in enumerate(accession_numbers):
        accession_number = str(accession_number).strip()
        form = _recent_text(recent, "form", index)
        primary_document = _recent_text(recent, "primaryDocument", index)
        filing_date = _recent_text(recent, "filingDate", index)
        if not accession_number or not form or not primary_document or not filing_date:
            continue
        if include_form_set and form.upper() not in include_form_set:
            continue

        published_at = _parse_sec_datetime(
            _recent_text(recent, "acceptanceDateTime", index),
            fallback_date=filing_date,
        )
        document = Document(
            doc_id=make_doc_id("sec", cik, accession_number, primary_document),
            source_id=source_id,
            source_type=SourceType.SEC_FILING,
            source_tier=SourceTier.REGULATORY_PRIMARY,
            source_family_id=make_issuer_family_id(cik),
            title=f"{company_name} {form} filed {filing_date}",
            url=build_primary_document_url(cik, accession_number, primary_document),
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw_object_uri=raw_object_uri,
            content_hash=content_hash,
            parser_version=SEC_SUBMISSIONS_PARSER_VERSION,
            entities=_build_entities(
                company_name=company_name,
                ticker=ticker,
                cik=cik,
                form=form,
                accession_number=accession_number,
            ),
            metadata={
                "accession_number": accession_number,
                "form": form,
                "filing_date": filing_date,
                "report_date": _recent_text(recent, "reportDate", index),
                "acceptance_datetime": _recent_text(
                    recent,
                    "acceptanceDateTime",
                    index,
                ),
                "primary_document": primary_document,
                "primary_doc_description": _recent_text(
                    recent,
                    "primaryDocDescription",
                    index,
                ),
                "items": _recent_text(recent, "items", index),
                "size": _recent_int(recent, "size", index),
                "is_xbrl": _recent_bool(recent, "isXBRL", index),
                "is_inline_xbrl": _recent_bool(recent, "isInlineXBRL", index),
                "source_raw_kind": "sec_submissions_recent",
            },
        )
        documents.append(document)
        if limit is not None and len(documents) >= limit:
            break

    return tuple(documents)


def _build_entities(
    *,
    company_name: str,
    ticker: str,
    cik: str,
    form: str,
    accession_number: str,
) -> list[DocumentEntity]:
    entities = [
        DocumentEntity(
            kind=EntityKind.COMPANY,
            value=company_name,
            identifiers={"cik": cik},
        ),
        DocumentEntity(kind=EntityKind.CIK, value=cik),
        DocumentEntity(kind=EntityKind.FORM, value=form),
        DocumentEntity(kind=EntityKind.ACCESSION_NUMBER, value=accession_number),
    ]
    if ticker:
        entities.insert(1, DocumentEntity(kind=EntityKind.TICKER, value=ticker))
    return entities


def _parse_sec_datetime(value: str, *, fallback_date: str) -> datetime:
    text = value.strip()
    if text:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        parsed = datetime.fromisoformat(fallback_date)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recent_text(recent: dict[str, object], field: str, index: int) -> str:
    value = _recent_value(recent, field, index)
    return "" if value is None else str(value).strip()


def _recent_int(recent: dict[str, object], field: str, index: int) -> int | None:
    value = _recent_value(recent, field, index)
    if value in (None, ""):
        return None
    return int(value)


def _recent_bool(recent: dict[str, object], field: str, index: int) -> bool | None:
    value = _recent_value(recent, field, index)
    if value in (None, ""):
        return None
    return bool(int(value))


def _recent_value(recent: dict[str, object], field: str, index: int) -> object | None:
    values = recent.get(field)
    if not isinstance(values, list):
        return None
    if index >= len(values):
        return None
    return values[index]


def _first_text(values: object) -> str:
    if not isinstance(values, list) or not values:
        return ""
    return str(values[0]).strip().upper()
