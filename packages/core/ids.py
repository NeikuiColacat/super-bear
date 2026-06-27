from __future__ import annotations

import hashlib
import re


_DOC_ID_UNSAFE_CHARS = re.compile(r"[^a-z0-9._/-]+")


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
