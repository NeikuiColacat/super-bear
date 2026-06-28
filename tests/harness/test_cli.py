import json
import subprocess


def test_harness_cli_validates_fake_pi_result() -> None:
    payload = {
        "request": {
            "schema_version": "investigator.v0",
            "investigator_run_id": "investigator_run_20260628T080100Z",
            "harness_name": "pi",
            "task_type": "verify_evidence_gap",
            "budgets": {
                "query_budget": 3,
                "read_budget": 5,
                "token_budget": 50000,
                "latency_budget_ms": 120000,
            },
            "allowed_actions": ["READ_DOCUMENT", "STOP"],
            "event_pack": {
                "event": {"event_id": "event:issuer:test"},
                "claims": [{"claim_id": "sec:apple:10q:claim:000000"}],
                "evidence_spans": [{"span_id": "sec:apple:10q:span:000000"}],
                "chunks": [],
                "open_questions": [],
            },
        },
        "result": {
            "schema_version": "investigator_result.v0",
            "investigator_run_id": "investigator_run_20260628T080100Z",
            "status": "stop",
            "evidence_status": "sufficient",
            "citations": [
                {
                    "claim_id": "sec:apple:10q:claim:000000",
                    "evidence_span_id": "sec:apple:10q:span:000000",
                }
            ],
        },
    }

    completed = subprocess.run(
        ["uv", "run", "python", "-m", "packages.harness.cli"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"ok": True, "errors": []}


def test_harness_cli_validates_fenced_pi_result_text() -> None:
    payload = {
        "request": {
            "schema_version": "investigator.v0",
            "investigator_run_id": "investigator_run_20260629T000000Z_pi_smoke",
            "harness_name": "pi",
            "task_type": "verify_evidence_gap",
            "budgets": {
                "query_budget": 0,
                "read_budget": 1,
                "token_budget": 8000,
                "latency_budget_ms": 60000,
            },
            "allowed_actions": ["READ_DOCUMENT", "VERIFY_EVIDENCE", "STOP"],
            "event_pack": {
                "event": {"event_id": "event:issuer:0000320193:sec:2026_q2_10q"},
                "claims": [
                    {
                        "claim_id": (
                            "sec:0000320193:0000320193-26-000013:"
                            "aapl-20260328.htm:claim:000000"
                        )
                    }
                ],
                "evidence_spans": [
                    {
                        "span_id": (
                            "sec:0000320193:0000320193-26-000013:"
                            "aapl-20260328.htm:span:000000"
                        )
                    }
                ],
            },
        },
        "result_text": """
```json
{
  "schema_version": "investigator_result.v0",
  "investigator_run_id": "investigator_run_20260629T000000Z_pi_smoke",
  "status": "stop",
  "evidence_status": "sufficient",
  "citations": [
    {
      "claim_id": "sec:0000320193:0000320193-26-000013:aapl-20260328.htm:claim:000000",
      "evidence_span_id": "sec:0000320193:0000320193-26-000013:aapl-20260328.htm:span:000000"
    }
  ]
}
```
""",
    }

    completed = subprocess.run(
        ["uv", "run", "python", "-m", "packages.harness.cli"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"ok": True, "errors": []}
