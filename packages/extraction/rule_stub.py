from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from packages.core import (
    ClaimCandidate,
    ClaimType,
    DocumentChunk,
    EvidenceRelation,
    EvidenceSpanCandidate,
    SourceTier,
    SourceType,
)


_MATERIAL_KEYWORDS = (
    "acquisition",
    "cash",
    "decreased",
    "expense",
    "guidance",
    "income",
    "increased",
    "margin",
    "merger",
    "net sales",
    "revenue",
)


def extract_candidate_pairs(
    chunks: Iterable[DocumentChunk],
) -> tuple[tuple[ClaimCandidate, EvidenceSpanCandidate], ...]:
    pairs: list[tuple[ClaimCandidate, EvidenceSpanCandidate]] = []
    for chunk in chunks:
        for sentence_start, sentence in _iter_sentences(chunk.text):
            if not _looks_material(sentence):
                continue
            claim_id = f"{chunk.doc_id}:claim_candidate:{len(pairs):06d}"
            span_id = f"{chunk.doc_id}:evidence_span_candidate:{len(pairs):06d}"
            char_start = chunk.char_start + sentence_start
            char_end = char_start + len(sentence)
            claim = ClaimCandidate(
                claim_candidate_id=claim_id,
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                claim_text=sentence,
                claim_type=ClaimType.FACT,
                confidence=0.3,
                metadata=_candidate_metadata(chunk),
            )
            evidence = EvidenceSpanCandidate(
                span_candidate_id=span_id,
                claim_candidate_id=claim_id,
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                relation=EvidenceRelation.SUPPORT,
                text=sentence,
                char_start=char_start,
                char_end=char_end,
                source_type=SourceType(_metadata_required(chunk, "source_type")),
                source_tier=SourceTier(_metadata_required(chunk, "source_tier")),
                source_family_id=_metadata_required(chunk, "source_family_id"),
                published_at=_parse_datetime(_metadata_required(chunk, "published_at")),
                confidence=0.3,
                metadata=_candidate_metadata(chunk),
            )
            pairs.append((claim, evidence))
    return tuple(pairs)


def _iter_sentences(text: str) -> Iterable[tuple[int, str]]:
    start = 0
    for index, char in enumerate(text):
        if char not in ".!?":
            continue
        if _is_decimal_point(text, index):
            continue
        next_index = index + 1
        if next_index < len(text) and not text[next_index].isspace():
            continue
        sentence = text[start:next_index]
        leading = len(sentence) - len(sentence.lstrip())
        stripped = sentence.strip()
        if stripped:
            yield start + leading, stripped
        start = next_index

    sentence = text[start:]
    leading = len(sentence) - len(sentence.lstrip())
    stripped = sentence.strip()
    if stripped:
        yield start + leading, stripped


def _is_decimal_point(text: str, index: int) -> bool:
    return (
        text[index] == "."
        and index > 0
        and index + 1 < len(text)
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )


def _looks_material(sentence: str) -> bool:
    text = sentence.lower()
    if _looks_sec_heading_noise(text):
        return False
    return any(keyword in text for keyword in _MATERIAL_KEYWORDS)


def _looks_sec_heading_noise(text: str) -> bool:
    return (
        text.startswith("risk factors")
        or text.startswith("quantitative and qualitative disclosures")
        or text.startswith("unregistered sales")
        or text.startswith("condensed consolidated")
        or "see accompanying notes to condensed consolidated financial statements"
        in text
        or _looks_numeric_table_row(text)
    )


def _looks_numeric_table_row(text: str) -> bool:
    tokens = text.split()
    if len(tokens) < 8:
        return False
    numeric_tokens = sum(any(char.isdigit() for char in token) for token in tokens)
    return numeric_tokens >= 8 and numeric_tokens / len(tokens) >= 0.35


def _metadata_required(chunk: DocumentChunk, key: str) -> str:
    value = chunk.metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"chunk metadata missing {key}")
    return value


def _candidate_metadata(chunk: DocumentChunk) -> dict[str, str]:
    metadata = {"extractor": "rule_stub_v0.1"}
    for key in ("form", "document_title"):
        value = chunk.metadata.get(key)
        if isinstance(value, str) and value:
            metadata[key] = value
    return metadata


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
