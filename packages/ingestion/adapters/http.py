from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from .base import AdapterError


class HttpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    status_code: int
    content_type: str


class HttpAdapterError(Exception):
    def __init__(self, error: AdapterError) -> None:
        super().__init__(error.message)
        self.error = error


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise HttpAdapterError(
        AdapterError(
            code="missing_api_key",
            message=f"Required environment variable is missing: {name}",
            retryable=False,
        )
    )


def optional_env(name: str) -> str | None:
    return os.getenv(name) or None


def fetch_bytes(
    url: str,
    *,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[bytes, HttpResponse]:
    request = Request(url, headers=dict(headers))
    return _open(request, timeout_seconds)


def fetch_json(
    url: str,
    *,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[dict[str, Any], HttpResponse]:
    content, response = fetch_bytes(
        url,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    return _decode_json(content, url), response


def post_json(
    url: str,
    *,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> tuple[dict[str, Any], HttpResponse]:
    request_headers = {"Content-Type": "application/json", **dict(headers)}
    request = Request(
        url,
        data=json.dumps(dict(payload)).encode("utf-8"),
        headers=request_headers,
    )
    content, response = _open(request, timeout_seconds)
    return _decode_json(content, url), response


def _open(request: Request, timeout_seconds: float) -> tuple[bytes, HttpResponse]:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            content = response.read()
            return content, HttpResponse(
                url=response.geturl(),
                status_code=response.status,
                content_type=response.headers.get_content_type(),
            )
    except HTTPError as exc:
        raise HttpAdapterError(
            AdapterError(
                code="http_error",
                message=f"HTTP request failed with status {exc.code}",
                retryable=exc.code == 429 or exc.code >= 500,
                details={"status_code": exc.code, "url": request.full_url},
            )
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HttpAdapterError(
            AdapterError(
                code="network_error",
                message=f"HTTP request failed: {exc.reason if isinstance(exc, URLError) else exc}",
                retryable=True,
                details={"url": request.full_url},
            )
        ) from exc


def _decode_json(content: bytes, url: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HttpAdapterError(
            AdapterError(
                code="invalid_json",
                message=f"HTTP response was not valid JSON: {exc.msg}",
                retryable=False,
                details={"url": url},
            )
        ) from exc
    if not isinstance(payload, dict):
        raise HttpAdapterError(
            AdapterError(
                code="invalid_json",
                message="HTTP response JSON must be an object",
                retryable=False,
                details={"url": url},
            )
        )
    return payload
