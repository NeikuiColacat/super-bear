from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from packages.core import Briefing, EventCard


def render_daily_brief(
    *,
    cards: Iterable[EventCard],
    created_at: datetime | None = None,
) -> Briefing:
    actual_created_at = created_at or datetime.now(timezone.utc)
    card_tuple = tuple(cards)
    day = actual_created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Super Bear Brief {day}", ""]
    for index, card in enumerate(card_tuple, start=1):
        lines.extend(
            [
                f"## {index}. {card.title}",
                "",
                card.what_happened,
                "",
                f"- claims: {', '.join(card.key_claim_ids)}",
                f"- evidence: {', '.join(card.key_evidence_span_ids)}",
                f"- evidence_status: {card.evidence_status}",
                "",
            ]
        )

    return Briefing(
        briefing_id=f"briefing:{actual_created_at.astimezone(timezone.utc).strftime('%Y%m%d')}",
        title=f"Super Bear Brief {day}",
        created_at=actual_created_at,
        event_card_ids=tuple(card.event_card_id for card in card_tuple),
        markdown="\n".join(lines).strip() + "\n",
        metadata={"generator": "rule_brief_markdown_v0.1"},
    )
