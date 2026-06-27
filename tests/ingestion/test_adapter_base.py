from datetime import datetime, timezone

import pytest

from packages.core import OutputKind
from packages.ingestion.adapters.base import (
    AdapterBatch,
    AdapterError,
    BaseSourceAdapter,
)
from packages.ingestion.registry import SourceRegistry


class FakeSecAdapter(BaseSourceAdapter):
    source_id = "sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        record_count = 1 if limit is None else min(limit, 1)
        return AdapterBatch.success(
            source_id=self.source.source_id,
            output_kind=self.source.output_kind,
            records=[{"accession_number": "0000320193-26-000013"}][:record_count],
            retrieved_at=datetime(2026, 6, 27, 8, 30, tzinfo=timezone.utc),
            raw_uris=[
                "data/raw/sec_edgar/0000320193/0000320193-26-000013/submission.json"
            ][:record_count],
        )


class BrokenSourceAdapter(BaseSourceAdapter):
    source_id = "not_sec_edgar"

    def fetch(self, *, limit: int | None = None) -> AdapterBatch:
        raise AssertionError("not used")


def test_adapter_binds_to_matching_source_config() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    adapter = FakeSecAdapter(registry.get("sec_edgar"))

    assert adapter.source.source_id == "sec_edgar"
    assert adapter.output_kind is OutputKind.DOCUMENT


def test_adapter_rejects_mismatched_source_config() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")

    with pytest.raises(ValueError, match="not_sec_edgar"):
        BrokenSourceAdapter(registry.get("sec_edgar"))


def test_adapter_success_batch_records_counts_and_raw_uris() -> None:
    registry = SourceRegistry.from_yaml("configs/sources.yaml")
    adapter = FakeSecAdapter(registry.get("sec_edgar"))

    batch = adapter.fetch(limit=1)

    assert batch.ok is True
    assert batch.source_id == "sec_edgar"
    assert batch.output_kind is OutputKind.DOCUMENT
    assert batch.records_seen == 1
    assert batch.records_written == 1
    assert batch.error is None
    assert batch.raw_uris == (
        "data/raw/sec_edgar/0000320193/0000320193-26-000013/submission.json",
    )


def test_adapter_failure_batch_keeps_auditable_error() -> None:
    error = AdapterError(
        code="network_timeout",
        message="SEC request timed out",
        retryable=True,
    )

    batch = AdapterBatch.failure(
        source_id="sec_edgar",
        output_kind=OutputKind.DOCUMENT,
        error=error,
        retrieved_at=datetime(2026, 6, 27, 8, 30, tzinfo=timezone.utc),
    )

    assert batch.ok is False
    assert batch.records_seen == 0
    assert batch.records_written == 0
    assert batch.error == error
    assert batch.error.retryable is True
