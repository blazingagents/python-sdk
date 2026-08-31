from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar, cast

import httpx
from pydantic import TypeAdapter, ValidationError

from ._downloads import _ByteStreamBase
from ._errors import (
    ObjectJSONDecodeError,
    ObjectTruncationError,
    ObjectValidationError,
    StreamError,
)
from ._transport import _Omitted
from ._types import JsonSchema, JsonValue

if TYPE_CHECKING:
    from typing_extensions import TypeForm
else:
    TypeForm = type

_T = TypeVar("_T")
_INCOMPLETE_NUMBER = re.compile(
    r"(?:^|[\[,:])\s*-?(?:(?:0|[1-9]\d*)"
    r"(?:(?:[eE][+-]?\d*)|\.(?:\d+(?:[eE][+-]?\d*)?)?)?)?$"
)


def decode_object(
    text: str,
    response: httpx.Response,
    adapter: TypeAdapter[_T] | None,
) -> _T | JsonValue:
    def reject_constant(constant: str) -> None:
        raise json.JSONDecodeError(
            "Invalid JSON constant",
            text,
            text.find(constant),
        )

    try:
        value: JsonValue = json.loads(text, parse_constant=reject_constant)
    except json.JSONDecodeError as error:
        error_type = (
            ObjectTruncationError
            if _is_truncated(error, text)
            else ObjectJSONDecodeError
        )
        raise error_type(response=response, json_error=error) from error
    if adapter is None:
        return value
    try:
        return adapter.validate_python(value)
    except ValidationError as error:
        raise ObjectValidationError(
            response=response,
            validation_error=error,
        ) from error


def _is_truncated(error: json.JSONDecodeError, text: str) -> bool:
    stripped = text.rstrip()
    suffix = stripped[error.pos :].strip()
    return (
        error.pos >= len(stripped)
        or error.msg.startswith("Unterminated string")
        or any(
            literal.startswith(suffix) and literal != suffix
            for literal in ("true", "false", "null")
        )
        or _INCOMPLETE_NUMBER.search(stripped) is not None
        or re.search(r"\\(?:u[0-9a-fA-F]{0,3})?$", stripped) is not None
    )


class _ObjectStreamBase(_ByteStreamBase, Generic[_T]):
    def __init__(
        self,
        response: httpx.Response,
        adapter: TypeAdapter[_T] | None,
    ) -> None:
        super().__init__(response)
        self._adapter = adapter
        self._deltas: list[str] = []
        self._complete = False
        self._failure: StreamError | None = None
        self._final: _T | JsonValue | None = None
        self._validated = False

    def _final_object(self) -> _T:
        if self._failure is not None:
            raise self._failure
        if not self._complete:
            raise StreamError(
                "Stream did not complete successfully.",
                response=self._response,
            )
        if not self._validated:
            try:
                self._final = decode_object(
                    "".join(self._deltas),
                    self._response,
                    self._adapter,
                )
            except StreamError as failure:
                self._failure = failure
                raise
            self._validated = True
        return cast(_T, self._final)


class ObjectStream(_ObjectStreamBase[_T]):
    """A single-consumer stream of raw JSON text deltas."""

    def __init__(
        self,
        response: httpx.Response,
        adapter: TypeAdapter[_T] | None,
    ) -> None:
        super().__init__(response, adapter)
        self._text_iterator: Iterator[str] | None = None

    def __iter__(self) -> Iterator[str]:
        self._claim()
        self._text_iterator = self._consume_text()
        return self._text_iterator

    def _consume_text(self) -> Iterator[str]:
        try:
            for delta in self._response.iter_text():
                self._deltas.append(delta)
                yield delta
            self._complete = True
        except httpx.HTTPError as error:
            failure = StreamError("Stream read failed.", response=self._response)
            self._failure = failure
            raise failure from error
        finally:
            self.close()

    def get_final_object(self) -> _T:
        if not self._complete and self._failure is None:
            if self._text_iterator is None:
                self._claim()
                self._text_iterator = self._consume_text()
            for _ in self._text_iterator:
                pass
        return self._final_object()

    def close(self) -> None:
        self._response.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncObjectStream(_ObjectStreamBase[_T]):
    """An asynchronous single-consumer stream of raw JSON text deltas."""

    def __init__(
        self,
        response: httpx.Response,
        adapter: TypeAdapter[_T] | None,
    ) -> None:
        super().__init__(response, adapter)
        self._text_iterator: AsyncIterator[str] | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        self._claim()
        self._text_iterator = self._consume_text()
        return self._text_iterator

    async def _consume_text(self) -> AsyncIterator[str]:
        try:
            async for delta in self._response.aiter_text():
                self._deltas.append(delta)
                yield delta
            self._complete = True
        except httpx.HTTPError as error:
            failure = StreamError("Stream read failed.", response=self._response)
            self._failure = failure
            raise failure from error
        finally:
            await self.aclose()

    async def get_final_object(self) -> _T:
        if not self._complete and self._failure is None:
            if self._text_iterator is None:
                self._claim()
                self._text_iterator = self._consume_text()
            async for _ in self._text_iterator:
                pass
        return self._final_object()

    async def aclose(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()


def resolve_output(
    output_type: TypeForm[Any] | None | _Omitted,
    json_schema: JsonSchema | None | _Omitted,
) -> tuple[TypeAdapter[Any] | None, JsonSchema]:
    has_output_type = output_type is not None and not isinstance(
        output_type,
        _Omitted,
    )
    has_json_schema = json_schema is not None and not isinstance(
        json_schema,
        _Omitted,
    )
    if has_output_type == has_json_schema:
        raise ValueError("Provide exactly one of output_type or json_schema.")
    if has_output_type:
        adapter: TypeAdapter[Any] = TypeAdapter(output_type)
        return adapter, cast(JsonSchema, adapter.json_schema())
    return None, cast(JsonSchema, json_schema)
