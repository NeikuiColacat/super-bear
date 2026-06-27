from __future__ import annotations

import hashlib
import re


_DOC_ID_UNSAFE_CHARS = re.compile(r"[^a-z0-9._/-]+")
_SOURCE_ID_CHARS = re.compile(r"[^a-z0-9_]+")
_TICKER_CHARS = re.compile(r"^[A-Z][A-Z0-9.-]*$")


def make_doc_id(*parts: str) -> str:
    """Build a stable, readable identifier from source-specific parts."""
    normalized = []
    for part in parts:
        cleaned = _DOC_ID_UNSAFE_CHARS.sub("-", part.strip().lower()).strip("-")
        if cleaned:
            normalized.append(cleaned)
    if not normalized:
        raise ValueError("doc_id requires at least one non-empty part")
    return ":".join(normalized)


def make_content_hash(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def make_issuer_family_id(cik: str | int) -> str:
    value = str(cik).strip()
    if not value.isdigit():
        raise ValueError(f"CIK must contain only digits: {cik!r}")
    if not 1 <= len(value) <= 10:
        raise ValueError(f"CIK must be 1 to 10 digits: {cik!r}")
    return f"issuer:{value.zfill(10)}"


def make_issuer_ticker_family_id(ticker: str) -> str:
    value = ticker.strip().upper()
    if not _TICKER_CHARS.fullmatch(value):
        raise ValueError(f"ticker is not canonical: {ticker!r}")
    return f"issuer_ticker:{value}"


def make_provider_family_id(source_id: str) -> str:
    value = _SOURCE_ID_CHARS.sub("_", source_id.strip().lower()).strip("_")
    if not value:
        raise ValueError("source_id requires at least one safe character")
    return f"provider:{value}"
