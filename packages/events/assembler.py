from __future__ import annotations

from collections.abc import Iterable
from datetime import timezone
import hashlib
import re

from packages.core import (
    Claim,
    EvidenceSpan,
    EvidenceStatus,
    Event,
    EventStatus,
    EventType,
    SourceType,
)
from packages.evidence import check_event_evidence


ASSEMBLY_VERSION = "event_assembler_v0.1"


def assemble_events(
    *,
    claims: Iterable[Claim],
    evidence_spans: Iterable[EvidenceSpan],
) -> tuple[Event, ...]:
    claims_by_id = {claim.claim_id: claim for claim in claims}
    evidence_by_claim: dict[str, list[EvidenceSpan]] = {}
    for span in evidence_spans:
        if span.claim_id in claims_by_id:
            evidence_by_claim.setdefault(span.claim_id, []).append(span)

    buckets: dict[str, set[str]] = {}
    bucket_spans: dict[str, list[EvidenceSpan]] = {}
    for claim_id, spans in evidence_by_claim.items():
        for span in spans:
            key = _assembly_key(span)
            buckets.setdefault(key, set()).add(claim_id)
            bucket_spans.setdefault(key, []).append(span)

    events: list[Event] = []
    for assembly_key in sorted(buckets):
        claim_ids = tuple(sorted(buckets[assembly_key]))
        spans = bucket_spans[assembly_key]
        if not claim_ids or not spans:
            continue
        related_doc_ids = tuple(sorted({span.doc_id for span in spans}))
        event_type = _event_type(spans[0])
        source_family_id = spans[0].source_family_id
        event = Event(
            event_id=_event_id(assembly_key, claim_ids),
            canonical_title=_canonical_title(claims_by_id, claim_ids),
            event_type=event_type,
            entities=(),
            event_time=min(span.published_at for span in spans).astimezone(
                timezone.utc
            ),
            status=EventStatus.NEW,
            related_doc_ids=related_doc_ids,
            claim_ids=claim_ids,
            evidence_status=EvidenceStatus.INSUFFICIENT,
            assembly_key=assembly_key,
            metadata={
                "assembly_version": ASSEMBLY_VERSION,
                "merge_reason": "same_source_family_event_type_form_and_day",
                "source_family_id": source_family_id,
            },
        )
        check = check_event_evidence(
            event=event,
            claims=(claims_by_id[claim_id] for claim_id in claim_ids),
            evidence_spans=spans,
        )
        events.append(
            event.model_copy(
                update={
                    "status": check.event_status,
                    "evidence_status": check.evidence_status,
                    "metadata": {
                        **event.metadata,
                        "evidence_check_version": check.checker_version,
                        "evidence_check_reasons": list(check.reasons),
                    },
                }
            )
        )
    return tuple(events)


def _assembly_key(span: EvidenceSpan) -> str:
    date_bucket = span.published_at.astimezone(timezone.utc).strftime("%Y%m%d")
    form = str(span.metadata.get("form") or "unknown")
    return "|".join(
        (
            span.source_family_id,
            str(_event_type(span)),
            form,
            date_bucket,
        )
    )


def _event_type(span: EvidenceSpan) -> EventType:
    if span.source_type in {SourceType.SEC_FILING, SourceType.SEC_EXHIBIT}:
        return EventType.SEC_FILING
    if span.source_type is SourceType.COMPANY_EARNINGS_RELEASE:
        return EventType.EARNINGS
    return EventType.OTHER


def _event_id(assembly_key: str, claim_ids: tuple[str, ...]) -> str:
    digest = hashlib.sha256(
        (assembly_key + "|" + "|".join(claim_ids)).encode("utf-8")
    ).hexdigest()[:8]
    return f"event:{_slug(assembly_key)}:{digest}"


def _canonical_title(
    claims_by_id: dict[str, Claim],
    claim_ids: tuple[str, ...],
) -> str:
    return claims_by_id[claim_ids[0]].claim_text


def _slug(value: str) -> str:
    text = value.lower().replace("|", ":")
    text = re.sub(r"[^a-z0-9:._/-]+", "-", text)
    return text.strip("-")
