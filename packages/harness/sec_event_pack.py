from __future__ import annotations

from collections.abc import Mapping

from packages.briefing import build_event_cards, render_daily_brief
from packages.core import ClaimCandidate, Document, EvidenceSpanCandidate
from packages.events import assemble_events
from packages.evidence import build_pre_event_ledger
from packages.extraction.rule_stub import extract_candidate_pairs
from packages.harness.contracts import AllowedAction, Budget, InvestigatorRequest
from packages.ingestion.chunker import chunk_document_record


_PREFERRED_SEC_CLAIM_KEYWORDS = (
    "net sales",
    "revenue",
    "net income",
    "cash and cash equivalents",
    "earnings per share",
    "operating income",
    "gross margin",
)


def build_sec_event_pack_request(
    record: Mapping[str, object],
    *,
    investigator_run_id: str,
    harness_name: str = "pi",
    harness_version: str | None = None,
    adapter_version: str = "super_bear_sec_event_pack_v0",
    model_name: str | None = "deepseek-v4-flash",
    prompt_version: str = "sec_event_pack_smoke_v0",
    max_claims: int = 1,
) -> InvestigatorRequest:
    if max_claims < 1:
        raise ValueError("max_claims must be at least 1")

    document = Document.model_validate(record)
    chunks = chunk_document_record(record)
    if not chunks:
        raise ValueError("document produced no chunks")

    pairs = tuple(sorted(extract_candidate_pairs(chunks), key=_candidate_rank))[
        :max_claims
    ]
    if not pairs:
        raise ValueError("document produced no claim/evidence candidates")

    ledger = build_pre_event_ledger(
        claim_records=[claim.model_dump(mode="json") for claim, _ in pairs],
        evidence_records=[evidence.model_dump(mode="json") for _, evidence in pairs],
        chunk_records=[chunk.model_dump(mode="json") for chunk in chunks],
    )
    if not ledger.claims or not ledger.evidence_spans:
        raise ValueError("document produced no valid ledger claims or evidence spans")

    events = assemble_events(
        claims=ledger.claims,
        evidence_spans=ledger.evidence_spans,
    )
    if not events:
        raise ValueError("ledger produced no events")

    cards = build_event_cards(
        events=events[:1],
        claims=ledger.claims,
        evidence_spans=ledger.evidence_spans,
        created_at=document.retrieved_at,
    )
    if not cards:
        raise ValueError("event produced no event cards")

    brief = render_daily_brief(cards=cards, created_at=document.retrieved_at)
    event = events[0]
    evidence_chunk_ids = {
        span.chunk_id for span in ledger.evidence_spans if span.chunk_id is not None
    }
    event_chunks = tuple(
        chunk for chunk in chunks if chunk.chunk_id in evidence_chunk_ids
    )

    return InvestigatorRequest(
        schema_version="investigator.v0",
        investigator_run_id=investigator_run_id,
        harness_name=harness_name,
        harness_version=harness_version,
        adapter_version=adapter_version,
        model_name=model_name,
        prompt_version=prompt_version,
        task_type="verify_evidence_gap",
        budgets=Budget(
            query_budget=0,
            read_budget=1,
            token_budget=8000,
            latency_budget_ms=60000,
        ),
        allowed_actions=(
            AllowedAction.READ_DOCUMENT,
            AllowedAction.VERIFY_EVIDENCE,
            AllowedAction.STOP,
            AllowedAction.ABSTAIN,
        ),
        event_pack={
            "document": document.model_dump(mode="json"),
            "event": event.model_dump(mode="json"),
            "event_card": cards[0].model_dump(mode="json"),
            "brief": brief.model_dump(mode="json"),
            "claims": [claim.model_dump(mode="json") for claim in ledger.claims],
            "evidence_spans": [
                span.model_dump(mode="json") for span in ledger.evidence_spans
            ],
            "chunks": [chunk.model_dump(mode="json") for chunk in event_chunks],
            "open_questions": (
                "Decide whether the existing SEC evidence supports the mandatory claim.",
            ),
        },
    )


def _candidate_rank(pair: tuple[ClaimCandidate, EvidenceSpanCandidate]) -> int:
    claim, _ = pair
    text = claim.claim_text.lower()
    if any(keyword in text for keyword in _PREFERRED_SEC_CLAIM_KEYWORDS):
        return 0
    return 1
