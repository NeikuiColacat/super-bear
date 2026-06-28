import json
from urllib.error import URLError
from urllib.request import Request

import pytest

from packages.ingestion.adapters.http import (
    HttpAdapterError,
    fetch_json,
    post_json,
    required_env,
)


class _Headers:
    def __init__(self, content_type: str) -> None:
        self._content_type = content_type

    def get_content_type(self) -> str:
        return self._content_type


class _Response:
    status = 200
    headers = _Headers("application/json")

    def __init__(self, body: bytes, url: str = "https://example.com/result") -> None:
        self._body = body
        self._url = url

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url


def test_fetch_json_returns_payload_and_response_metadata(monkeypatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> _Response:
        assert request.full_url == "https://api.example.com/search"
        assert timeout == 3
        return _Response(b'{"ok": true}')

    monkeypatch.setattr("packages.ingestion.adapters.http.urlopen", fake_urlopen)

    payload, response = fetch_json(
        "https://api.example.com/search",
        headers={"Accept": "application/json"},
        timeout_seconds=3,
    )

    assert payload == {"ok": True}
    assert response.status_code == 200
    assert response.content_type == "application/json"


def test_post_json_sends_json_body(monkeypatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> _Response:
        assert timeout == 5
        assert request.data == json.dumps({"query": "AAPL"}).encode("utf-8")
        assert request.get_header("Content-type") == "application/json"
        return _Response(b'{"results": []}')

    monkeypatch.setattr("packages.ingestion.adapters.http.urlopen", fake_urlopen)

    payload, _response = post_json(
        "https://api.example.com/search",
        headers={"Authorization": "Bearer secret"},
        payload={"query": "AAPL"},
        timeout_seconds=5,
    )

    assert payload == {"results": []}


def test_required_env_returns_value_without_logging_it(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "secret-value")

    assert required_env("TAVILY_API_KEY") == "secret-value"


def test_required_env_error_does_not_include_secret_value(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(HttpAdapterError) as exc_info:
        required_env("TAVILY_API_KEY")

    error = exc_info.value.error
    assert error.code == "missing_api_key"
    assert "TAVILY_API_KEY" in error.message
    assert "secret" not in error.message


def test_network_errors_become_adapter_errors(monkeypatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> _Response:
        raise URLError("temporary outage")

    monkeypatch.setattr("packages.ingestion.adapters.http.urlopen", fake_urlopen)

    with pytest.raises(HttpAdapterError) as exc_info:
        fetch_json(
            "https://api.example.com/search",
            headers={},
            timeout_seconds=1,
        )

    assert exc_info.value.error.code == "network_error"
    assert exc_info.value.error.retryable is True
