from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from packages.core import (
    Claim,
    ClaimCandidate,
    ClaimStatus,
    DocumentChunk,
    EvidenceRelation,
    EvidenceSpan,
    EvidenceSpanCandidate,
    PipelineValidationError,
)
from packages.evidence.validator import validate_evidence_candidate_against_chunk


class LedgerBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claims: tuple[Claim, ...] = ()
    evidence_spans: tuple[EvidenceSpan, ...] = ()
    validation_errors: tuple[PipelineValidationError, ...] = ()


def build_pre_event_ledger(
    *,
    claim_records: Iterable[Mapping[str, Any]],
    evidence_records: Iterable[Mapping[str, Any]],
    chunk_records: Iterable[Mapping[str, Any]],
) -> LedgerBuildResult:
    errors: list[PipelineValidationError] = []
    chunks_by_id = _load_chunks(chunk_records, errors)
    evidence_by_claim = _load_evidence_by_claim(evidence_records, errors)

    claims: list[Claim] = []
    spans: list[EvidenceSpan] = []
    seen_claim_candidate_ids: set[str] = set()

    for claim_record in claim_records:
        claim_candidate = _load_claim_candidate(claim_record, errors)
        if claim_candidate is None:
            continue
        if claim_candidate.claim_candidate_id in seen_claim_candidate_ids:
            errors.append(
                _error(
                    len(errors),
                    record_kind="claim_candidate",
                    object_id=claim_candidate.claim_candidate_id,
                    code="duplicate_claim_candidate_id",
                    message="duplicate claim candidate id",
                )
            )
            continue
        seen_claim_candidate_ids.add(claim_candidate.claim_candidate_id)

        evidence_candidates = evidence_by_claim.get(
            claim_candidate.claim_candidate_id,
            (),
        )
        valid_spans: list[EvidenceSpan] = []
        claim_id = _claim_id_from_candidate(claim_candidate.claim_candidate_id)

        for evidence_candidate in evidence_candidates:
            chunk = chunks_by_id.get(evidence_candidate.chunk_id)
            if chunk is None:
                errors.append(
                    _error(
                        len(errors),
                        record_kind="evidence_span_candidate",
                        object_id=evidence_candidate.span_candidate_id,
                        code="chunk_missing",
                        message="evidence candidate references a missing chunk",
                    )
                )
                continue

            validation_codes = _validate_claim_evidence_pair(
                claim_candidate,
                evidence_candidate,
                chunk,
            )
            if validation_codes:
                for code in validation_codes:
                    errors.append(
                        _error(
                            len(errors),
                            record_kind="evidence_span_candidate",
                            object_id=evidence_candidate.span_candidate_id,
                            code=code,
                            message=f"invalid evidence candidate: {code}",
                        )
                    )
                continue

            valid_spans.append(_promote_evidence(evidence_candidate, claim_id))

        if not valid_spans:
            continue

        claims.append(_promote_claim(claim_candidate, claim_id))
        spans.extend(valid_spans)

    for claim_candidate_id, evidence_candidates in evidence_by_claim.items():
        if claim_candidate_id in seen_claim_candidate_ids:
            continue
        for evidence_candidate in evidence_candidates:
            errors.append(
                _error(
                    len(errors),
                    record_kind="evidence_span_candidate",
                    object_id=evidence_candidate.span_candidate_id,
                    code="claim_candidate_missing",
                    message="evidence candidate references a missing claim candidate",
                )
            )

    return LedgerBuildResult(
        claims=tuple(claims),
        evidence_spans=tuple(spans),
        validation_errors=tuple(errors),
    )


def _load_chunks(
    records: Iterable[Mapping[str, Any]],
    errors: list[PipelineValidationError],
) -> dict[str, DocumentChunk]:
    chunks: dict[str, DocumentChunk] = {}
    for record in records:
        try:
            chunk = DocumentChunk.model_validate(record)
        except ValidationError as exc:
            errors.append(
                _error(
                    len(errors),
                    record_kind="document_chunk",
                    object_id=str(record.get("chunk_id") or ""),
                    code="schema_invalid",
                    message=str(exc.errors()[0]["msg"]),
                )
            )
            continue
        chunks[chunk.chunk_id] = chunk
    return chunks


def _load_evidence_by_claim(
    records: Iterable[Mapping[str, Any]],
    errors: list[PipelineValidationError],
) -> dict[str, tuple[EvidenceSpanCandidate, ...]]:
    grouped: dict[str, list[EvidenceSpanCandidate]] = {}
    seen_span_candidate_ids: set[str] = set()
    for record in records:
        try:
            evidence = EvidenceSpanCandidate.model_validate(record)
        except ValidationError as exc:
            errors.append(
                _error(
                    len(errors),
                    record_kind="evidence_span_candidate",
                    object_id=str(record.get("span_candidate_id") or ""),
                    code="schema_invalid",
                    message=str(exc.errors()[0]["msg"]),
                )
            )
            continue
        if evidence.span_candidate_id in seen_span_candidate_ids:
            errors.append(
                _error(
                    len(errors),
                    record_kind="evidence_span_candidate",
                    object_id=evidence.span_candidate_id,
                    code="duplicate_span_candidate_id",
                    message="duplicate evidence span candidate id",
                )
            )
            continue
        seen_span_candidate_ids.add(evidence.span_candidate_id)
        grouped.setdefault(evidence.claim_candidate_id, []).append(evidence)
    return {claim_id: tuple(items) for claim_id, items in grouped.items()}


def _load_claim_candidate(
    record: Mapping[str, Any],
    errors: list[PipelineValidationError],
) -> ClaimCandidate | None:
    try:
        return ClaimCandidate.model_validate(record)
    except ValidationError as exc:
        errors.append(
            _error(
                len(errors),
                record_kind="claim_candidate",
                object_id=str(record.get("claim_candidate_id") or ""),
                code="schema_invalid",
                message=str(exc.errors()[0]["msg"]),
            )
        )
        return None


def _validate_claim_evidence_pair(
    claim: ClaimCandidate,
    evidence: EvidenceSpanCandidate,
    chunk: DocumentChunk,
) -> tuple[str, ...]:
    errors: list[str] = []
    if evidence.claim_candidate_id != claim.claim_candidate_id:
        errors.append("claim_candidate_id_mismatch")
    if evidence.doc_id != claim.doc_id:
        errors.append("claim_doc_id_mismatch")
    if evidence.chunk_id != claim.chunk_id:
        errors.append("claim_chunk_id_mismatch")
    if evidence.text != claim.claim_text:
        errors.append("claim_text_evidence_text_mismatch")
    errors.extend(validate_evidence_candidate_against_chunk(evidence, chunk))
    return tuple(errors)


def _promote_claim(claim: ClaimCandidate, claim_id: str) -> Claim:
    return Claim(
        claim_id=claim_id,
        event_id=None,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        mandatory=False,
        status=ClaimStatus.SUPPORTED,
        metadata={
            **claim.metadata,
            "source_candidate_id": claim.claim_candidate_id,
            "ledger_stage": "pre_event",
        },
    )


def _promote_evidence(
    evidence: EvidenceSpanCandidate,
    claim_id: str,
) -> EvidenceSpan:
    return EvidenceSpan(
        span_id=_span_id_from_candidate(evidence.span_candidate_id),
        doc_id=evidence.doc_id,
        claim_id=claim_id,
        chunk_id=evidence.chunk_id,
        relation=evidence.relation,
        text=evidence.text,
        char_start=evidence.char_start,
        char_end=evidence.char_end,
        source_type=evidence.source_type,
        source_tier=evidence.source_tier,
        source_family_id=evidence.source_family_id,
        published_at=evidence.published_at,
        valid_from=evidence.published_at
        if evidence.relation is EvidenceRelation.SUPPORT
        else None,
        confidence=evidence.confidence,
        metadata={
            **evidence.metadata,
            "source_candidate_id": evidence.span_candidate_id,
            "ledger_stage": "pre_event",
        },
    )


def _claim_id_from_candidate(candidate_id: str) -> str:
    return candidate_id.replace(":claim_candidate:", ":claim:")


def _span_id_from_candidate(candidate_id: str) -> str:
    return candidate_id.replace(":evidence_span_candidate:", ":span:")


def _error(
    index: int,
    *,
    record_kind: str,
    object_id: str | None,
    code: str,
    message: str,
) -> PipelineValidationError:
    return PipelineValidationError(
        validation_error_id=f"ledger:validation_error:{index:06d}",
        record_kind=record_kind,
        object_id=object_id or None,
        code=code,
        message=message,
    )
