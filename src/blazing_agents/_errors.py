from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import ValidationError


class BlazingAgentsError(Exception):
    """Base class for errors raised by the SDK."""


class APIStatusError(BlazingAgentsError):
    """A non-successful HTTP response from the Blazing Agents API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        headers: httpx.Headers,
        code: str,
        details: Mapping[str, Any] | None,
        param: str | None,
        request_id: str | None,
        response_body: str,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers
        self.code = code
        self.details = details
        self.param = param
        self.request_id = request_id
        self.response_body = response_body
        self.retry_after = headers.get("retry-after")


class APIConnectionError(BlazingAgentsError):
    """A network failure before a complete HTTP response."""


class APITimeoutError(APIConnectionError):
    """An HTTP timeout."""


class StreamError(BlazingAgentsError):
    """A transport or decoding failure after streaming headers arrive."""

    def __init__(
        self,
        message: str,
        *,
        response: httpx.Response,
    ) -> None:
        super().__init__(message)
        self.status_code = response.status_code
        self.headers = httpx.Headers(response.headers)
        self.request_id = self.headers.get("x-request-id")
        self.retry_after = self.headers.get("retry-after")


class ObjectTruncationError(StreamError):
    """A cleanly terminated object response containing incomplete JSON."""

    def __init__(
        self,
        *,
        response: httpx.Response,
        json_error: json.JSONDecodeError,
    ) -> None:
        super().__init__("The agent produced truncated JSON.", response=response)
        self.json_error = json_error


class ObjectJSONDecodeError(StreamError):
    """A cleanly terminated object response containing invalid JSON."""

    def __init__(
        self,
        *,
        response: httpx.Response,
        json_error: json.JSONDecodeError,
    ) -> None:
        super().__init__("The agent produced invalid JSON.", response=response)
        self.json_error = json_error


class ObjectValidationError(StreamError):
    """A decoded object that does not satisfy the requested output type."""

    def __init__(
        self,
        *,
        response: httpx.Response,
        validation_error: ValidationError,
    ) -> None:
        super().__init__(
            "The generated object did not match the requested output type.",
            response=response,
        )
        self.validation_error = validation_error
