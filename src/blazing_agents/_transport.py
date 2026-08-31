from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast, overload

import httpx
from pydantic import BaseModel, ValidationError

from ._downloads import AsyncByteStream, ByteStream
from ._errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    BlazingAgentsError,
    StreamError,
)
from ._models import CredentialSafeResponseModel, McpConnectionAuthorization
from ._responses import Completion
from ._types import Timeout

if TYPE_CHECKING:
    from pydantic_core import InitErrorDetails

_LOGGER = logging.getLogger("blazing_agents")
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_StreamT = TypeVar("_StreamT")
_MIN_SUBSTRING_SECRET_LENGTH = 8


class _RequestIdModel(Protocol):
    _request_id: str | None


class _Omitted:
    pass


OMITTED = _Omitted()


class _ResponseStatus:
    pass


RESPONSE_STATUS = _ResponseStatus()


class _ResponseBytes:
    pass


RESPONSE_BYTES = _ResponseBytes()


class _ResponseText:
    pass


RESPONSE_TEXT = _ResponseText()


class _ResponseObjectText:
    pass


RESPONSE_OBJECT_TEXT = _ResponseObjectText()


@dataclass(frozen=True)
class ResponseObservation:
    method: str
    path: str
    status: int
    duration_ms: float
    request_id: str | None
    client_request_id: str | None


@dataclass(frozen=True)
class _Request:
    method: str
    path: str
    client_request_id: str | None = None
    query: Mapping[str, str | int] | None = None
    json_body: object = OMITTED
    files: object = OMITTED
    content: object = OMITTED
    extra_headers: Mapping[str, str] | None = None
    timeout: Timeout | _Omitted = OMITTED
    sensitive_values: tuple[str, ...] = ()


class _TransportConfig:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_headers: Mapping[str, str] | None,
        timeout: Timeout,
        user_agent: str,
        on_response: Callable[[ResponseObservation], None] | None,
        client_request_id: str | None,
    ) -> None:
        normalized_url = base_url.rstrip("/")
        if not normalized_url:
            msg = "base_url must not be empty"
            raise ValueError(msg)
        self.api_key = api_key
        self.base_url = normalized_url
        self.default_headers = httpx.Headers(default_headers)
        self.timeout = timeout
        self.user_agent = user_agent
        self.on_response = on_response
        self.client_request_id = client_request_id

    def with_client_request_id(self, client_request_id: str) -> _TransportConfig:
        return _TransportConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self.default_headers,
            timeout=self.timeout,
            user_agent=self.user_agent,
            on_response=self.on_response,
            client_request_id=client_request_id,
        )

    def resolved_client_request_id(self, request: _Request) -> str | None:
        return (
            request.client_request_id
            if request.client_request_id is not None
            else self.client_request_id
        )

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def headers(self, request: _Request) -> httpx.Headers:
        headers = httpx.Headers({"user-agent": self.user_agent})
        headers.update(self.default_headers)
        if request.extra_headers is not None:
            headers.update(request.extra_headers)
        headers.pop("x-request-id", None)
        headers["authorization"] = f"Bearer {self.api_key}"
        resolved = self.resolved_client_request_id(request)
        if resolved is not None:
            headers["x-client-request-id"] = resolved
        return headers

    def observe(
        self,
        request: _Request,
        *,
        started_at: float,
        response: httpx.Response,
    ) -> None:
        if self.on_response is None:
            return
        with suppress(Exception):
            self.on_response(
                ResponseObservation(
                    method=request.method,
                    path=request.path,
                    status=response.status_code,
                    duration_ms=(perf_counter() - started_at) * 1_000,
                    request_id=response.headers.get("x-request-id"),
                    client_request_id=response.request.headers.get(
                        "x-client-request-id"
                    ),
                )
            )

    def request_timeout(self, timeout: Timeout | _Omitted) -> Timeout:
        return self.timeout if isinstance(timeout, _Omitted) else timeout

    def log(
        self,
        request: _Request,
        *,
        started_at: float,
        response: httpx.Response | None,
    ) -> None:
        request_id = (
            response.headers.get("x-request-id") if response is not None else None
        )
        _LOGGER.debug(
            "HTTP request method=%s path=%s status=%s elapsed_ms=%.3f request_id=%s",
            request.method,
            request.path,
            response.status_code if response is not None else None,
            (perf_counter() - started_at) * 1_000,
            request_id,
        )


def _status_error(
    response: httpx.Response,
    sensitive_values: tuple[str, ...],
) -> APIStatusError:
    raw_body = response.text
    code = "invalid_response"
    message = "The server returned an invalid error response."
    details: Mapping[str, Any] | None = None
    param: str | None = None
    try:
        parsed: object = json.loads(raw_body)
    except json.JSONDecodeError:
        parsed = None
        body = "[REDACTED]" if sensitive_values else raw_body
    else:
        parsed = _redact_sensitive_values(parsed, sensitive_values)
        body = json.dumps(parsed, separators=(",", ":"))
    if isinstance(parsed, dict):
        parsed_mapping = cast(dict[str, object], parsed)
        error = parsed_mapping.get("error")
        if isinstance(error, dict):
            error_mapping = cast(dict[str, object], error)
            parsed_code = error_mapping.get("code")
            parsed_message = error_mapping.get("message")
            parsed_details = error_mapping.get("details")
            parsed_param = error_mapping.get("param")
            if isinstance(parsed_code, str) and isinstance(parsed_message, str):
                code = parsed_code
                message = parsed_message
                if isinstance(parsed_details, dict):
                    details = cast(dict[str, Any], parsed_details)
                if isinstance(parsed_param, str):
                    param = parsed_param
    headers = _redact_headers(response.headers, sensitive_values)
    return APIStatusError(
        message,
        status_code=response.status_code,
        headers=headers,
        code=code,
        details=details,
        param=param,
        request_id=headers.get("x-request-id"),
        response_body=body,
    )


def _redact_headers(
    headers: httpx.Headers,
    sensitive_values: tuple[str, ...],
) -> httpx.Headers:
    if not sensitive_values:
        return headers
    return httpx.Headers(
        [
            (name, _redact_string(value, sensitive_values))
            for name, value in headers.multi_items()
        ]
    )


def _redact_string(value: str, sensitive_values: tuple[str, ...]) -> str:
    for secret in sensitive_values:
        if len(secret) >= _MIN_SUBSTRING_SECRET_LENGTH:
            value = value.replace(secret, "[REDACTED]")
        elif value == secret:
            return "[REDACTED]"
    return value


def _redact_sensitive_values(
    value: object,
    sensitive_values: tuple[str, ...],
) -> object:
    if isinstance(value, dict):
        fields = cast(dict[str, object], value)
        return {
            key: _redact_sensitive_values(item, sensitive_values)
            for key, item in fields.items()
        }
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_redact_sensitive_values(item, sensitive_values) for item in items]
    if isinstance(value, str):
        return _redact_string(value, sensitive_values)
    return value


def _model(
    response: httpx.Response,
    model: type[_ModelT],
    sensitive_values: tuple[str, ...],
) -> _ModelT:
    if issubclass(model, CredentialSafeResponseModel):
        try:
            decoded: object = json.loads(response.content)
        except json.JSONDecodeError:
            msg = "The server returned an invalid credential-safe response."
            raise BlazingAgentsError(msg) from None
        if _contains_credential_material(
            decoded,
            sensitive_values=sensitive_values,
            credential_fields=model._credential_fields,
        ):
            msg = "The server returned credential material in a response."
            raise BlazingAgentsError(msg)
    value: _ModelT | None = None
    validation_error: ValidationError | None = None
    try:
        value = model.model_validate_json(response.content)
    except ValidationError as error:
        if model is McpConnectionAuthorization:
            errors = error.errors()
            for item in errors:
                item["input"] = "[REDACTED]"
            validation_error = ValidationError.from_exception_data(
                error.title,
                cast("list[InitErrorDetails]", errors),
            )
        else:
            raise
    if validation_error is not None:
        raise validation_error from None
    assert value is not None
    cast(_RequestIdModel, value)._request_id = response.headers.get("x-request-id")
    return value


def _contains_credential_material(
    value: object,
    *,
    sensitive_values: tuple[str, ...],
    credential_fields: frozenset[str],
) -> bool:
    if isinstance(value, dict):
        fields = cast(dict[str, object], value)
        return any(
            key in credential_fields
            or _contains_credential_material(
                item,
                sensitive_values=sensitive_values,
                credential_fields=credential_fields,
            )
            for key, item in fields.items()
        )
    if isinstance(value, list):
        items = cast(list[object], value)
        return any(
            _contains_credential_material(
                item,
                sensitive_values=sensitive_values,
                credential_fields=credential_fields,
            )
            for item in items
        )
    if isinstance(value, str):
        return any(
            value == secret
            or (len(secret) >= _MIN_SUBSTRING_SECRET_LENGTH and secret in value)
            for secret in sensitive_values
        )
    return False


def _request_options(
    config: _TransportConfig,
    request: _Request,
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "params": request.query,
        "headers": config.headers(request),
        "timeout": config.request_timeout(request.timeout),
    }
    if request.json_body is not OMITTED:
        options["json"] = request.json_body
    if request.files is not OMITTED:
        options["files"] = request.files
    if request.content is not OMITTED:
        options["content"] = request.content
    return options


def _stream_request_options(
    config: _TransportConfig,
    request: _Request,
) -> dict[str, Any]:
    options = _request_options(config, request)
    configured = config.request_timeout(request.timeout)
    if configured is None:
        options["timeout"] = None
    else:
        timeout = (
            configured
            if isinstance(configured, httpx.Timeout)
            else httpx.Timeout(configured)
        )
        options["timeout"] = httpx.Timeout(
            connect=timeout.connect,
            read=None,
            write=timeout.write,
            pool=timeout.pool,
        )
    return options


@overload
def _response_value(
    response: httpx.Response,
    model: type[_ModelT],
    sensitive_values: tuple[str, ...],
) -> _ModelT: ...


@overload
def _response_value(
    response: httpx.Response,
    model: None,
    sensitive_values: tuple[str, ...],
) -> None: ...


@overload
def _response_value(
    response: httpx.Response,
    model: _ResponseStatus,
    sensitive_values: tuple[str, ...],
) -> int: ...


@overload
def _response_value(
    response: httpx.Response,
    model: _ResponseBytes,
    sensitive_values: tuple[str, ...],
) -> bytes: ...


@overload
def _response_value(
    response: httpx.Response,
    model: _ResponseText,
    sensitive_values: tuple[str, ...],
) -> Completion: ...


@overload
def _response_value(
    response: httpx.Response,
    model: _ResponseObjectText,
    sensitive_values: tuple[str, ...],
) -> Completion: ...


def _response_value(
    response: httpx.Response,
    model: (
        type[_ModelT]
        | _ResponseBytes
        | _ResponseObjectText
        | _ResponseStatus
        | _ResponseText
        | None
    ),
    sensitive_values: tuple[str, ...],
) -> _ModelT | Completion | bytes | int | None:
    if not response.is_success:
        raise _status_error(response, sensitive_values)
    if model is None:
        return None
    if isinstance(model, _ResponseStatus):
        return response.status_code
    if isinstance(model, _ResponseBytes):
        return response.content
    if isinstance(model, (_ResponseObjectText, _ResponseText)):
        return Completion(response.text, response)
    return _model(response, model, sensitive_values)


class SyncTransport:
    def __init__(
        self,
        config: _TransportConfig,
        http_client: httpx.Client | None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client()

    def with_client_request_id(self, client_request_id: str) -> SyncTransport:
        return SyncTransport(
            self._config.with_client_request_id(client_request_id),
            self._client,
        )

    @overload
    def request(self, request: _Request, model: type[_ModelT]) -> _ModelT: ...

    @overload
    def request(self, request: _Request, model: None) -> None: ...

    @overload
    def request(self, request: _Request, model: _ResponseStatus) -> int: ...

    @overload
    def request(self, request: _Request, model: _ResponseBytes) -> bytes: ...

    @overload
    def request(self, request: _Request, model: _ResponseText) -> Completion: ...

    @overload
    def request(self, request: _Request, model: _ResponseObjectText) -> Completion: ...

    def request(
        self,
        request: _Request,
        model: (
            type[_ModelT]
            | _ResponseBytes
            | _ResponseObjectText
            | _ResponseStatus
            | _ResponseText
            | None
        ),
    ) -> _ModelT | Completion | bytes | int | None:
        started_at = perf_counter()
        response: httpx.Response | None = None
        transport_error: APIConnectionError | None = None
        try:
            if model is RESPONSE_OBJECT_TEXT:
                built = self._client.build_request(
                    request.method,
                    self._config.url(request.path),
                    **_request_options(self._config, request),
                )
                response = self._client.send(built, stream=True)
                self._config.observe(request, started_at=started_at, response=response)
                try:
                    response.read()
                except httpx.HTTPError as error:
                    raise StreamError(
                        "Response body read failed.",
                        response=response,
                    ) from error
            else:
                response = self._client.request(
                    request.method,
                    self._config.url(request.path),
                    **_request_options(self._config, request),
                )
                self._config.observe(request, started_at=started_at, response=response)
        except httpx.TimeoutException:
            transport_error = APITimeoutError("Request timed out.")
        except httpx.RequestError:
            transport_error = APIConnectionError("Connection failed.")
        finally:
            if model is RESPONSE_OBJECT_TEXT and response is not None:
                response.close()
            self._config.log(request, started_at=started_at, response=response)
        if transport_error is not None:
            raise transport_error from None
        assert response is not None
        return _response_value(response, model, request.sensitive_values)

    @overload
    def stream(self, request: _Request) -> ByteStream: ...

    @overload
    def stream(
        self,
        request: _Request,
        response_factory: Callable[[httpx.Response], _StreamT],
    ) -> _StreamT: ...

    def stream(
        self,
        request: _Request,
        response_factory: Callable[[httpx.Response], _StreamT] | None = None,
    ) -> ByteStream | _StreamT:
        started_at = perf_counter()
        response: httpx.Response | None = None
        transport_error: APIConnectionError | None = None
        stream_error: StreamError | None = None
        try:
            built = self._client.build_request(
                request.method,
                self._config.url(request.path),
                **_stream_request_options(self._config, request),
            )
            response = self._client.send(built, stream=True)
            self._config.observe(request, started_at=started_at, response=response)
            if not response.is_success:
                read_failed = False
                try:
                    response.read()
                except httpx.HTTPError:
                    read_failed = True
                finally:
                    response.close()
                if read_failed:
                    stream_error = StreamError(
                        "Stream read failed.",
                        response=response,
                    )
                else:
                    raise _status_error(response, request.sensitive_values)
            if stream_error is None:
                factory = ByteStream if response_factory is None else response_factory
                try:
                    return factory(response)
                except BaseException:
                    response.close()
                    raise
        except httpx.TimeoutException:
            transport_error = APITimeoutError("Request timed out.")
        except httpx.RequestError:
            transport_error = APIConnectionError("Connection failed.")
        finally:
            self._config.log(request, started_at=started_at, response=response)
        if stream_error is not None:
            raise stream_error from None
        if transport_error is not None:
            raise transport_error from None
        assert response is not None
        # A non-successful response always raises before this point.
        raise AssertionError("stream response did not produce a stream")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AsyncTransport:
    def __init__(
        self,
        config: _TransportConfig,
        http_client: httpx.AsyncClient | None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient()

    def with_client_request_id(self, client_request_id: str) -> AsyncTransport:
        return AsyncTransport(
            self._config.with_client_request_id(client_request_id),
            self._client,
        )

    @overload
    async def request(self, request: _Request, model: type[_ModelT]) -> _ModelT: ...

    @overload
    async def request(self, request: _Request, model: None) -> None: ...

    @overload
    async def request(self, request: _Request, model: _ResponseStatus) -> int: ...

    @overload
    async def request(self, request: _Request, model: _ResponseBytes) -> bytes: ...

    @overload
    async def request(self, request: _Request, model: _ResponseText) -> Completion: ...

    @overload
    async def request(
        self, request: _Request, model: _ResponseObjectText
    ) -> Completion: ...

    async def request(
        self,
        request: _Request,
        model: (
            type[_ModelT]
            | _ResponseBytes
            | _ResponseObjectText
            | _ResponseStatus
            | _ResponseText
            | None
        ),
    ) -> _ModelT | Completion | bytes | int | None:
        started_at = perf_counter()
        response: httpx.Response | None = None
        transport_error: APIConnectionError | None = None
        try:
            if model is RESPONSE_OBJECT_TEXT:
                built = self._client.build_request(
                    request.method,
                    self._config.url(request.path),
                    **_request_options(self._config, request),
                )
                response = await self._client.send(built, stream=True)
                self._config.observe(request, started_at=started_at, response=response)
                try:
                    await response.aread()
                except httpx.HTTPError as error:
                    raise StreamError(
                        "Response body read failed.",
                        response=response,
                    ) from error
            else:
                response = await self._client.request(
                    request.method,
                    self._config.url(request.path),
                    **_request_options(self._config, request),
                )
                self._config.observe(request, started_at=started_at, response=response)
        except httpx.TimeoutException:
            transport_error = APITimeoutError("Request timed out.")
        except httpx.RequestError:
            transport_error = APIConnectionError("Connection failed.")
        finally:
            if model is RESPONSE_OBJECT_TEXT and response is not None:
                await response.aclose()
            self._config.log(request, started_at=started_at, response=response)
        if transport_error is not None:
            raise transport_error from None
        assert response is not None
        return _response_value(response, model, request.sensitive_values)

    @overload
    async def stream(self, request: _Request) -> AsyncByteStream: ...

    @overload
    async def stream(
        self,
        request: _Request,
        response_factory: Callable[[httpx.Response], _StreamT],
    ) -> _StreamT: ...

    async def stream(
        self,
        request: _Request,
        response_factory: Callable[[httpx.Response], _StreamT] | None = None,
    ) -> AsyncByteStream | _StreamT:
        started_at = perf_counter()
        response: httpx.Response | None = None
        transport_error: APIConnectionError | None = None
        stream_error: StreamError | None = None
        try:
            built = self._client.build_request(
                request.method,
                self._config.url(request.path),
                **_stream_request_options(self._config, request),
            )
            response = await self._client.send(built, stream=True)
            self._config.observe(request, started_at=started_at, response=response)
            if not response.is_success:
                read_failed = False
                try:
                    await response.aread()
                except httpx.HTTPError:
                    read_failed = True
                finally:
                    await response.aclose()
                if read_failed:
                    stream_error = StreamError(
                        "Stream read failed.",
                        response=response,
                    )
                else:
                    raise _status_error(response, request.sensitive_values)
            if stream_error is None:
                factory = (
                    AsyncByteStream if response_factory is None else response_factory
                )
                try:
                    return factory(response)
                except BaseException:
                    await response.aclose()
                    raise
        except httpx.TimeoutException:
            transport_error = APITimeoutError("Request timed out.")
        except httpx.RequestError:
            transport_error = APIConnectionError("Connection failed.")
        finally:
            self._config.log(request, started_at=started_at, response=response)
        if stream_error is not None:
            raise stream_error from None
        if transport_error is not None:
            raise transport_error from None
        assert response is not None
        raise AssertionError("stream response did not produce a stream")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
