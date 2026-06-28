import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "examples/harness/validation_payload.sample.json",
        "examples/harness/validation_payload_from_pi_text.sample.json",
        "examples/harness/sec_10q_validation_payload_from_pi_text.sample.json",
    ],
)
def test_harness_validation_payload_examples_pass_cli(path: str) -> None:
    payload = Path(path).read_text(encoding="utf-8")

    completed = subprocess.run(
        ["uv", "run", "python", "-m", "packages.harness.cli"],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout == '{"errors": [], "ok": true}'
