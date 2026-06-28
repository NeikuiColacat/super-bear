from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import re

from packages.core import (
    ClaimCandidate,
    ClaimType,
    DocumentChunk,
    EvidenceRelation,
    EvidenceSpanCandidate,
    SourceTier,
    SourceType,
)


_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
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
    "risk",
    "sales",
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
                metadata={"extractor": "rule_stub_v0.1"},
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
                metadata={"extractor": "rule_stub_v0.1"},
            )
            pairs.append((claim, evidence))
    return tuple(pairs)


def _iter_sentences(text: str) -> Iterable[tuple[int, str]]:
    for match in _SENTENCE.finditer(text):
        sentence = match.group(0)
        leading = len(sentence) - len(sentence.lstrip())
        stripped = sentence.strip()
        if stripped:
            yield match.start() + leading, stripped


def _looks_material(sentence: str) -> bool:
    text = sentence.lower()
    return any(keyword in text for keyword in _MATERIAL_KEYWORDS)


def _metadata_required(chunk: DocumentChunk, key: str) -> str:
    value = chunk.metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"chunk metadata missing {key}")
    return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
