from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict, Field

from packages.core import Document, DocumentChunk, make_content_hash
from packages.ingestion.parsers.sec_filing_html import extract_sec_filing_text


DEFAULT_CHUNK_MAX_CHARS = 1800
DEFAULT_CHUNK_OVERLAP_CHARS = 150

_WHITESPACE = re.compile(r"\s+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class ExtractedText(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    source: str = Field(min_length=1)


def extract_text_for_chunking(record: Mapping[str, object]) -> ExtractedText | None:
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}

    raw_uri = metadata.get("primary_document_raw_uri")
    if isinstance(raw_uri, str) and raw_uri.strip():
        raw_path = Path(raw_uri)
        if raw_path.is_file():
            text = extract_sec_filing_text(raw_path.read_bytes())
            if text:
                return ExtractedText(
                    text=text,
                    source="metadata.primary_document_raw_uri",
                )

    for key in ("text", "content", "body"):
        extracted = _text_value(record.get(key))
        if extracted:
            return ExtractedText(text=extracted, source=key)

    for key in (
        "primary_document_text",
        "primary_document_text_excerpt",
        "text",
        "excerpt",
        "summary",
    ):
        extracted = _text_value(metadata.get(key))
        if extracted:
            return ExtractedText(text=extracted, source=f"metadata.{key}")

    return None


def chunk_document_record(
    record: Mapping[str, object],
    *,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    section_label: str = "body",
) -> tuple[DocumentChunk, ...]:
    document = Document.model_validate(record)
    extracted = extract_text_for_chunking(record)
    if extracted is None:
        return ()

    chunk_metadata = {
        "text_source": extracted.source,
        "source_type": document.source_type,
        "source_tier": document.source_tier,
        "source_family_id": document.source_family_id,
        "published_at": document.published_at.isoformat().replace("+00:00", "Z"),
    }
    form = document.metadata.get("form")
    if isinstance(form, str) and form:
        chunk_metadata["form"] = form

    return chunk_text(
        document=document,
        text=extracted.text,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        section_label=section_label,
        metadata=chunk_metadata,
    )


def chunk_text(
    *,
    document: Document,
    text: str,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    section_label: str = "body",
    metadata: Mapping[str, object] | None = None,
) -> tuple[DocumentChunk, ...]:
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    chunks: list[DocumentChunk] = []
    start = _skip_whitespace(text, 0)
    chunk_metadata = dict(metadata or {})

    while start < len(text):
        end = _choose_chunk_end(text, start, max_chars)
        char_start = _skip_whitespace(text, start)
        char_end = _trim_trailing_whitespace(text, end)

        if char_end <= char_start:
            break

        chunk_text_value = text[char_start:char_end]
        chunks.append(
            DocumentChunk(
                chunk_id=f"{document.doc_id}:chunk:{len(chunks):06d}",
                doc_id=document.doc_id,
                chunk_index=len(chunks),
                text=chunk_text_value,
                char_start=char_start,
                char_end=char_end,
                section_label=section_label,
                content_hash=make_content_hash(chunk_text_value),
                metadata=chunk_metadata,
            )
        )

        if char_end >= len(text):
            break

        next_start = char_end - overlap_chars if overlap_chars else char_end
        if next_start <= start:
            next_start = char_end
        start = _skip_whitespace(text, next_start)

    return tuple(chunks)


def _choose_chunk_end(text: str, start: int, max_chars: int) -> int:
    hard_end = min(len(text), start + max_chars)
    if hard_end >= len(text):
        return len(text)

    window = text[start:hard_end]
    minimum_boundary = max(1, max_chars // 3)

    sentence_boundaries = [
        start + match.start()
        for match in _SENTENCE_BOUNDARY.finditer(window)
        if match.start() >= minimum_boundary
    ]
    if sentence_boundaries:
        return sentence_boundaries[-1]

    whitespace_boundaries = [
        start + match.start()
        for match in _WHITESPACE.finditer(window)
        if match.start() >= minimum_boundary
    ]
    if whitespace_boundaries:
        return whitespace_boundaries[-1]

    return hard_end


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _trim_trailing_whitespace(text: str, index: int) -> int:
    while index > 0 and text[index - 1].isspace():
        index -= 1
    return index


def _text_value(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()
