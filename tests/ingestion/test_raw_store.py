import pytest

from packages.core import make_content_hash
from packages.ingestion.raw_store import RawStore


def test_raw_store_writes_bytes_under_root(tmp_path) -> None:
    store = RawStore(tmp_path / "raw")

    result = store.write_bytes(
        "sec_edgar/0000320193/submissions.json",
        b'{"cik":"0000320193"}',
    )

    assert result.path == tmp_path / "raw" / "sec_edgar" / "0000320193" / "submissions.json"
    assert result.raw_uri == str(result.path)
    assert result.content_hash == make_content_hash(b'{"cik":"0000320193"}')
    assert result.path.read_bytes() == b'{"cik":"0000320193"}'


def test_raw_store_rejects_paths_outside_root(tmp_path) -> None:
    store = RawStore(tmp_path / "raw")

    with pytest.raises(ValueError, match="relative path"):
        store.write_bytes("../escape.json", b"{}")
