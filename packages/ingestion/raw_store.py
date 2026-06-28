from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from packages.core import make_content_hash


class RawWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    path: Path
    raw_uri: str
    content_hash: str


class RawStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def write_bytes(self, relative_path: str | Path, content: bytes) -> RawWriteResult:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("raw store requires a safe relative path")

        output_path = self.root_dir / path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        return RawWriteResult(
            path=output_path,
            raw_uri=str(output_path),
            content_hash=make_content_hash(content),
        )
