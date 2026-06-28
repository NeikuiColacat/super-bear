from __future__ import annotations

import json
import sys
from typing import Any

from pydantic import ValidationError

from packages.harness.contracts import InvestigatorRequest, InvestigatorResult
from packages.harness.validator import validate_investigator_result


def run(payload: dict[str, Any]) -> dict[str, Any]:
    request = InvestigatorRequest.model_validate(payload["request"])
    result = InvestigatorResult.model_validate(payload["result"])
    validation = validate_investigator_result(request, result)
    return {"ok": validation.ok, "errors": list(validation.errors)}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        output = run(payload)
    except (KeyError, json.JSONDecodeError, ValidationError) as exc:
        output = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(output, sort_keys=True), end="")
        return 1
    print(json.dumps(output, sort_keys=True), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
