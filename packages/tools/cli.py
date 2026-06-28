from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from packages.tools import JsonlStore, ReadApi


def run(payload: dict[str, Any]) -> dict[str, Any]:
    api = ReadApi(JsonlStore(Path(payload["normalized_dir"])))
    action = str(payload["action"])
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be a JSON object")

    if action == "read_document":
        result = api.read_document(str(arguments["doc_id"]))
    elif action == "list_chunks":
        result = list(api.list_chunks(str(arguments["doc_id"])))
    elif action == "get_event":
        result = api.get_event(str(arguments["event_id"]))
    elif action == "get_claim":
        result = api.get_claim(str(arguments["claim_id"]))
    elif action == "get_evidence_span":
        result = api.get_evidence_span(str(arguments["span_id"]))
    elif action == "get_event_pack":
        result = api.get_event_pack(str(arguments["event_id"]))
    elif action == "validate_evidence_span":
        result = api.validate_evidence_span(
            doc_id=str(arguments["doc_id"]),
            text=str(arguments["text"]),
            char_start=int(arguments["char_start"]),
            char_end=int(arguments["char_end"]),
        )
    else:
        raise ValueError(f"unsupported action: {action}")

    return {"ok": True, "result": result}


def main() -> int:
    try:
        output = run(json.loads(sys.stdin.read()))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True), end="")
        return 1
    print(json.dumps(output, sort_keys=True), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
