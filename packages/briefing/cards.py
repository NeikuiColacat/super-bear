from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import re

from packages.core import Claim, Event, EventCard, EvidenceSpan, EvidenceStatus


def build_event_cards(
    *,
    events: Iterable[Event],
    claims: Iterable[Claim],
    evidence_spans: Iterable[EvidenceSpan],
    created_at: datetime | None = None,
) -> tuple[EventCard, ...]:
    actual_created_at = created_at or datetime.now(timezone.utc)
    claims_by_id = {claim.claim_id: claim for claim in claims}
    spans_by_claim: dict[str, list[EvidenceSpan]] = {}
    for span in evidence_spans:
        spans_by_claim.setdefault(span.claim_id, []).append(span)

    cards: list[EventCard] = []
    for event in events:
        event_claims = [
            claims_by_id[claim_id]
            for claim_id in event.claim_ids
            if claim_id in claims_by_id
        ]
        event_spans = [
            span
            for claim_id in event.claim_ids
            for span in spans_by_claim.get(claim_id, [])
        ]
        if not event_claims or not event_spans:
            continue

        cards.append(
            EventCard(
                event_card_id=f"event_card:{_slug(event.event_id.removeprefix('event:'))}",
                event_id=event.event_id,
                title=event.canonical_title,
                what_happened=event_claims[0].claim_text,
                evidence_status=event.evidence_status,
                source_summary=tuple(
                    sorted(
                        {
                            f"{span.source_tier}:{span.source_type}"
                            for span in event_spans
                        }
                    )
                ),
                key_claim_ids=tuple(claim.claim_id for claim in event_claims),
                key_evidence_span_ids=tuple(span.span_id for span in event_spans),
                uncertainties=_uncertainties(event),
                monitoring_status=_monitoring_status(event.evidence_status),
                created_at=actual_created_at,
                metadata={"generator": "rule_event_card_v0.1"},
            )
        )
    return tuple(cards)


def _uncertainties(event: Event) -> tuple[str, ...]:
    reasons = event.metadata.get("evidence_check_reasons")
    if isinstance(reasons, list):
        return tuple(str(reason) for reason in reasons)
    if event.evidence_status is EvidenceStatus.SUFFICIENT:
        return ()
    return (str(event.evidence_status),)


def _monitoring_status(evidence_status: EvidenceStatus) -> str:
    if evidence_status is EvidenceStatus.SUFFICIENT:
        return "monitor_for_updates"
    return "needs_follow_up"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9:._/-]+", "-", value.lower()).strip("-")
