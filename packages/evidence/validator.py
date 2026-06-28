from __future__ import annotations

from datetime import datetime, timezone

from packages.core import DocumentChunk, EvidenceSpanCandidate


def validate_evidence_candidate_against_chunk(
    evidence: EvidenceSpanCandidate,
    chunk: DocumentChunk,
) -> tuple[str, ...]:
    errors: list[str] = []

    if evidence.doc_id != chunk.doc_id:
        errors.append("evidence_doc_id_mismatch")
    if evidence.chunk_id != chunk.chunk_id:
        errors.append("evidence_chunk_id_mismatch")
    if evidence.char_start < chunk.char_start or evidence.char_end > chunk.char_end:
        errors.append("evidence_offset_outside_chunk")
        return tuple(errors)

    relative_start = evidence.char_start - chunk.char_start
    relative_end = evidence.char_end - chunk.char_start
    if chunk.text[relative_start:relative_end] != evidence.text:
        errors.append("evidence_text_offset_mismatch")

    errors.extend(_validate_source_provenance(evidence, chunk))

    return tuple(errors)


def _validate_source_provenance(
    evidence: EvidenceSpanCandidate,
    chunk: DocumentChunk,
) -> tuple[str, ...]:
    checks = {
        "source_type": str(evidence.source_type),
        "source_tier": str(evidence.source_tier),
        "source_family_id": evidence.source_family_id,
        "published_at": evidence.published_at.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }

    errors: list[str] = []
    for key, expected in checks.items():
        raw_value = chunk.metadata.get(key)
        if not isinstance(raw_value, str) or not raw_value:
            errors.append(f"{key}_missing")
            continue
        value = _normalize_datetime(raw_value) if key == "published_at" else raw_value
        if value != expected:
            errors.append(f"{key}_mismatch")
    return tuple(errors)


def _normalize_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
