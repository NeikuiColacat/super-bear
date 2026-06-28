from __future__ import annotations

from typing import Any

from packages.core import OutputKind
from packages.tools.jsonl_store import JsonlStore


class ReadApi:
    def __init__(self, store: JsonlStore) -> None:
        self.store = store

    def read_document(self, doc_id: str) -> dict[str, Any] | None:
        return self.store.find_one(OutputKind.DOCUMENT, "doc_id", doc_id)

    def list_chunks(self, doc_id: str) -> tuple[dict[str, Any], ...]:
        return tuple(
            chunk
            for chunk in self.store.records(OutputKind.DOCUMENT_CHUNK)
            if chunk.get("doc_id") == doc_id
        )

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        return self.store.find_one(OutputKind.EVENT, "event_id", event_id)

    def get_claim(self, claim_id: str) -> dict[str, Any] | None:
        return self.store.find_one(OutputKind.CLAIM, "claim_id", claim_id)

    def get_evidence_span(self, span_id: str) -> dict[str, Any] | None:
        return self.store.find_one(OutputKind.EVIDENCE_SPAN, "span_id", span_id)

    def get_event_pack(self, event_id: str) -> dict[str, Any]:
        event = self.get_event(event_id)
        if event is None:
            raise KeyError(event_id)
        claims = [
            claim
            for claim_id in event.get("claim_ids", [])
            if (claim := self.get_claim(str(claim_id))) is not None
        ]
        evidence_spans = [
            span
            for claim in claims
            for span in self.store.records(OutputKind.EVIDENCE_SPAN)
            if span.get("claim_id") == claim.get("claim_id")
        ]
        chunks = [
            chunk
            for span in evidence_spans
            if (chunk_id := span.get("chunk_id"))
            for chunk in self.store.records(OutputKind.DOCUMENT_CHUNK)
            if chunk.get("chunk_id") == chunk_id
        ]
        return {
            "event": event,
            "claims": claims,
            "evidence_spans": evidence_spans,
            "chunks": chunks,
            "open_questions": [],
        }

    def validate_evidence_span(
        self,
        *,
        doc_id: str,
        text: str,
        char_start: int,
        char_end: int,
    ) -> dict[str, Any]:
        for chunk in self.list_chunks(doc_id):
            if char_start < chunk["char_start"] or char_end > chunk["char_end"]:
                continue
            relative_start = char_start - chunk["char_start"]
            relative_end = char_end - chunk["char_start"]
            if chunk["text"][relative_start:relative_end] == text:
                return {"ok": True, "chunk_id": chunk["chunk_id"]}
        return {"ok": False, "chunk_id": None}
