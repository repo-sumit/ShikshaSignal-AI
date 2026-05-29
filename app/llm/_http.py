"""Minimal stdlib HTTP helper for the LLM providers.

We intentionally use ``urllib`` instead of pulling ``requests`` into the dependency set
— Milestone 4 should not add a runtime dep just to call three REST APIs. Tests
monkeypatch ``post_json`` directly, so providers stay easy to exercise offline.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping


DEFAULT_TIMEOUT_SECONDS: float = 20.0


class HttpError(RuntimeError):
    """Wraps any non-2xx response or transport failure with a single class."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def post_json(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """POST a JSON payload and return the decoded JSON body. Raises HttpError on failure."""
    data = json.dumps(payload).encode("utf-8")
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=merged_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return json.loads(raw) if raw else {}
            except json.JSONDecodeError as e:
                raise HttpError(f"Non-JSON response: {e}", status=resp.status, body=raw) from e
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        raise HttpError(f"HTTP {e.code}: {e.reason}", status=e.code, body=body) from e
    except urllib.error.URLError as e:
        raise HttpError(f"Network failure: {e.reason}") from e
    except TimeoutError as e:
        raise HttpError(f"Request timed out after {timeout}s") from e
