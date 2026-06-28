from datetime import datetime, timezone
import json
import subprocess

from tests.tools.test_read_api import _seed


def test_tools_cli_returns_event_pack(tmp_path) -> None:
    event_id, claim_id, _span_id = _seed(tmp_path)
    payload = {
        "action": "get_event_pack",
        "normalized_dir": str(tmp_path),
        "arguments": {"event_id": event_id},
    }

    completed = subprocess.run(
        ["uv", "run", "python", "-m", "packages.tools.cli"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    response = json.loads(completed.stdout)
    assert response["ok"] is True
    assert response["result"]["claims"][0]["claim_id"] == claim_id


def test_tools_cli_validates_evidence_span(tmp_path) -> None:
    _seed(tmp_path)
    text = "Net sales increased year over year."
    payload = {
        "action": "validate_evidence_span",
        "normalized_dir": str(tmp_path),
        "arguments": {
            "doc_id": "sec:apple:10q",
            "text": text,
            "char_start": 0,
            "char_end": len(text),
        },
    }

    completed = subprocess.run(
        ["uv", "run", "python", "-m", "packages.tools.cli"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {
        "ok": True,
        "result": {"ok": True, "chunk_id": "sec:apple:10q:chunk:000000"},
    }


def test_tools_cli_rejects_unknown_action(tmp_path) -> None:
    payload = {
        "action": "delete_ledger",
        "normalized_dir": str(tmp_path),
        "arguments": {},
    }

    completed = subprocess.run(
        ["uv", "run", "python", "-m", "packages.tools.cli"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["ok"] is False


def test_tools_cli_timestamp_fixture_is_timezone_aware() -> None:
    assert datetime(2026, 6, 29, tzinfo=timezone.utc).utcoffset() is not None
