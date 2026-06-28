from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.core import OutputKind
from packages.ingestion.jsonl_writer import JsonlWriter


class JsonlStore:
    def __init__(self, normalized_dir: str | Path) -> None:
        self.normalized_dir = Path(normalized_dir)
        self.writer = JsonlWriter(self.normalized_dir)

    def records(self, output_kind: OutputKind) -> tuple[dict[str, Any], ...]:
        path = self.writer.output_path_for(output_kind)
        if not path.exists():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    def find_one(
        self,
        output_kind: OutputKind,
        field: str,
        value: str,
    ) -> dict[str, Any] | None:
        for record in self.records(output_kind):
            if record.get(field) == value:
                return record
        return None
