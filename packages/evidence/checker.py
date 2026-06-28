from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from packages.core import (
    Claim,
    EvidenceRelation,
    EvidenceSpan,
    EvidenceStatus,
    Event,
    EventStatus,
)


CHECKER_VERSION = "evidence_checker_v0.1"


class EvidenceCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    evidence_status: EvidenceStatus
    event_status: EventStatus
    checked_claim_ids: tuple[str, ...]
    supported_claim_ids: tuple[str, ...] = ()
    missing_claim_ids: tuple[str, ...] = ()
    conflicting_claim_ids: tuple[str, ...] = ()
    stale_claim_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...]
    checker_version: str = CHECKER_VERSION


def check_event_evidence(
    *,
    event: Event,
    claims: Iterable[Claim],
    evidence_spans: Iterable[EvidenceSpan],
    checked_at: datetime | None = None,
) -> EvidenceCheckResult:
    if checked_at is not None and (
        checked_at.tzinfo is None or checked_at.utcoffset() is None
    ):
        raise ValueError("checked_at must be timezone-aware")

    event_claim_ids = set(event.claim_ids)
    provided_claim_ids = {claim.claim_id for claim in claims if claim.claim_id in event_claim_ids}
    spans_by_claim = _group_current_event_spans(
        event_claim_ids,
        evidence_spans,
        checked_at=checked_at,
    )

    supported: list[str] = []
    missing: list[str] = []
    conflicting: list[str] = []
    stale: list[str] = []
    has_update = False

    for claim_id in event.claim_ids:
        if claim_id not in provided_claim_ids:
            missing.append(claim_id)
            continue

        current_spans, stale_spans = spans_by_claim.get(claim_id, ((), ()))
        current_relations = {span.relation for span in current_spans}
        if EvidenceRelation.UPDATE in current_relations:
            has_update = True
        if (
            EvidenceRelation.SUPPORT in current_relations
            and EvidenceRelation.REFUTE in current_relations
        ):
            conflicting.append(claim_id)
            continue
        if EvidenceRelation.SUPPORT in current_relations:
            supported.append(claim_id)
            continue
        if stale_spans:
            stale.append(claim_id)
            continue
        missing.append(claim_id)

    return _result(
        event=event,
        supported=tuple(supported),
        missing=tuple(missing),
        conflicting=tuple(conflicting),
        stale=tuple(stale),
        has_update=has_update,
    )


def _group_current_event_spans(
    event_claim_ids: set[str],
    evidence_spans: Iterable[EvidenceSpan],
    *,
    checked_at: datetime | None,
) -> dict[str, tuple[tuple[EvidenceSpan, ...], tuple[EvidenceSpan, ...]]]:
    grouped: dict[str, tuple[list[EvidenceSpan], list[EvidenceSpan]]] = {}
    for span in evidence_spans:
        if span.claim_id not in event_claim_ids:
            continue
        current_spans, stale_spans = grouped.setdefault(span.claim_id, ([], []))
        if _is_stale(span, checked_at):
            stale_spans.append(span)
        else:
            current_spans.append(span)
    return {
        claim_id: (tuple(current), tuple(stale))
        for claim_id, (current, stale) in grouped.items()
    }


def _is_stale(span: EvidenceSpan, checked_at: datetime | None) -> bool:
    if checked_at is None or span.valid_to is None:
        return False
    return span.valid_to <= checked_at


def _result(
    *,
    event: Event,
    supported: tuple[str, ...],
    missing: tuple[str, ...],
    conflicting: tuple[str, ...],
    stale: tuple[str, ...],
    has_update: bool,
) -> EvidenceCheckResult:
    if conflicting:
        return EvidenceCheckResult(
            event_id=event.event_id,
            evidence_status=EvidenceStatus.CONFLICTING,
            event_status=EventStatus.DEVELOPING,
            checked_claim_ids=event.claim_ids,
            supported_claim_ids=supported,
            missing_claim_ids=missing,
            conflicting_claim_ids=conflicting,
            stale_claim_ids=stale,
            reasons=("support_refute_conflict",),
        )
    if stale:
        return EvidenceCheckResult(
            event_id=event.event_id,
            evidence_status=EvidenceStatus.INSUFFICIENT,
            event_status=event.status,
            checked_claim_ids=event.claim_ids,
            supported_claim_ids=supported,
            missing_claim_ids=missing,
            stale_claim_ids=stale,
            reasons=("evidence_temporally_invalid",),
        )
    if missing:
        return EvidenceCheckResult(
            event_id=event.event_id,
            evidence_status=EvidenceStatus.INSUFFICIENT,
            event_status=event.status,
            checked_claim_ids=event.claim_ids,
            supported_claim_ids=supported,
            missing_claim_ids=missing,
            reasons=("supporting_evidence_missing",),
        )
    if has_update:
        return EvidenceCheckResult(
            event_id=event.event_id,
            evidence_status=EvidenceStatus.SUFFICIENT,
            event_status=EventStatus.DEVELOPING,
            checked_claim_ids=event.claim_ids,
            supported_claim_ids=supported,
            reasons=("update_evidence_present",),
        )
    return EvidenceCheckResult(
        event_id=event.event_id,
        evidence_status=EvidenceStatus.SUFFICIENT,
        event_status=event.status,
        checked_claim_ids=event.claim_ids,
        supported_claim_ids=supported,
        reasons=("all_event_claims_supported",),
    )
