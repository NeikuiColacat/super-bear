from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict

from packages.ingestion.adapters import BaseSourceAdapter, SecEdgarAdapter
from packages.ingestion.jsonl_writer import JsonlWriter
from packages.ingestion.registry import SourceRegistry
from packages.ingestion.run_config import IngestionRunConfig
from packages.ingestion.run_manifest import (
    RunManifest,
    RunManifestWriter,
    RunSourceResult,
)


DEFAULT_ADAPTER_CLASSES: Mapping[str, type[BaseSourceAdapter]] = {
    SecEdgarAdapter.source_id: SecEdgarAdapter,
}


class IngestionRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    manifest: RunManifest
    manifest_path: Path


def run_ingestion(
    *,
    registry: SourceRegistry,
    normalized_dir: str | Path,
    runs_dir: str | Path,
    run_id: str,
    adapter_classes: Mapping[str, type[BaseSourceAdapter]] | None = None,
    limit: int | None = None,
    source_ids: tuple[str, ...] = (),
    skip_unimplemented_adapters: bool = True,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> IngestionRunResult:
    adapters = adapter_classes or DEFAULT_ADAPTER_CLASSES
    writer = JsonlWriter(normalized_dir)

    actual_started_at = started_at or datetime.now(timezone.utc)
    source_results: list[RunSourceResult] = []

    selected_source_ids = set(source_ids)
    for source in registry.enabled_sources():
        if selected_source_ids and source.source_id not in selected_source_ids:
            continue

        adapter_class = adapters.get(source.source_id)
        if adapter_class is None:
            if not skip_unimplemented_adapters:
                raise ValueError(f"adapter not implemented: {source.adapter}")
            source_results.append(
                RunSourceResult.skipped(
                    source_id=source.source_id,
                    adapter=source.adapter,
                    output_kind=source.output_kind,
                    skipped_reason="adapter_not_implemented",
                )
            )
            continue

        adapter = adapter_class(source)
        batch = adapter.fetch(limit=limit)
        write_result = writer.write_batch(batch)
        source_results.append(
            RunSourceResult.from_batch(
                source=source,
                batch=batch,
                write_result=write_result,
            )
        )

    manifest = RunManifest(
        run_id=run_id,
        started_at=actual_started_at,
        finished_at=finished_at or datetime.now(timezone.utc),
        sources=tuple(source_results),
    )
    manifest_path = RunManifestWriter(runs_dir).write(manifest)
    return IngestionRunResult(manifest=manifest, manifest_path=manifest_path)


def make_run_id(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return f"run_{value.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic source ingestion.")
    parser.add_argument(
        "--config",
        default="configs/ingestion_run.yaml",
        help="Path to the ingestion run YAML config.",
    )
    parser.add_argument("--run-id", default=None, help="Run identifier for manifest output.")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Source id to run. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Temporary per-source fetch limit override.",
    )
    return parser


def _print_summary(result: IngestionRunResult) -> None:
    print(f"run_id: {result.manifest.run_id}")
    print(f"manifest: {result.manifest_path}")
    print("sources:")
    for source in result.manifest.sources:
        print(
            f"- {source.source_id}: {source.status}, "
            f"records_written={source.records_written}, "
            f"skipped_reason={source.skipped_reason}"
        )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = IngestionRunConfig.from_yaml(args.config)
    registry = SourceRegistry.from_yaml(config.source_registry_path)
    result = run_ingestion(
        registry=registry,
        normalized_dir=config.normalized_dir,
        runs_dir=config.runs_dir,
        run_id=args.run_id or make_run_id(),
        limit=args.limit if args.limit is not None else config.default_limit,
        source_ids=config.selected_source_ids(tuple(args.source)),
        skip_unimplemented_adapters=config.skip_unimplemented_adapters,
    )
    _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
