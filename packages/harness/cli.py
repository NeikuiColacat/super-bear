from __future__ import annotations

import json
import sys
from typing import Any

from pydantic import ValidationError

from packages.harness.contracts import InvestigatorRequest, InvestigatorResult
from packages.harness.validator import validate_investigator_result


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("result_text does not contain a JSON object")


def _result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "result" in payload:
        result = payload["result"]
        if not isinstance(result, dict):
            raise ValueError("result must be a JSON object")
        return result
    result_text = payload.get("result_text")
    if isinstance(result_text, str):
        return _extract_json_object(result_text)
    raise KeyError("result")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    request = InvestigatorRequest.model_validate(payload["request"])
    result = InvestigatorResult.model_validate(_result_payload(payload))
    validation = validate_investigator_result(request, result)
    return {"ok": validation.ok, "errors": list(validation.errors)}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        output = run(payload)
    except (KeyError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        output = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(output, sort_keys=True), end="")
        return 1
    print(json.dumps(output, sort_keys=True), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
