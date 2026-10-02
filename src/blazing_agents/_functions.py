from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar, cast, get_args
from urllib.parse import quote

import httpx
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
)

from ._errors import APIStatusError, BlazingAgentsError, StreamError
from ._transport import AsyncTransport, SyncTransport, _Request
from ._types import BuiltinToolName

if TYPE_CHECKING:
    from typing_extensions import TypeForm
else:
    TypeForm = type

_LOGGER = logging.getLogger("blazing_agents")
_InputT = TypeVar("_InputT")

MAX_FUNCTIONS = 32
MAX_DEFINITIONS_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 256 * 1024
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_RESERVED_NAMES = frozenset(get_args(BuiltinToolName))
_EVENT_TYPE = "data-ba-function-call"
_FRAME_END = re.compile(rb"\r\n\r\n|\n\n")
_RESULT_GRACE_SECONDS = 30.0
_FIRST_RETRY_DELAY = 0.25
_MAX_RETRY_DELAY = 2.0
_RETRYABLE_STATUS = frozenset({408, 429})

EXECUTION_FAILED = "Function execution failed."
INVALID_INPUT = "Invalid function input."
INVALID_RESULT = "Function returned an invalid result."


def _unknown_function(name: str) -> str:
    return f"Function {name} is not available."


def _valid_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and _NAME.fullmatch(name) is not None
        and name not in _RESERVED_NAMES
        and not name.startswith("mcp__")
    )


def _function_name(name: str) -> str:
    if not _valid_name(name):
        raise ValueError("Invalid or reserved function name.")
    return name


@dataclass(frozen=True)
class FunctionContext:
    """Per-execution context for a chat function handler.

    ``idempotency_key`` identifies this execution attempt. ``cancelled`` is set
    when the call deadline passes or the chat stream closes; cancellation is
    cooperative and cannot undo effects.
    """

    idempotency_key: str
    deadline_at: datetime
    cancelled: threading.Event


@dataclass(frozen=True, eq=False)
class ChatFunction:
    """A backend function the agent may call during one chat invocation."""

    description: str
    json_schema: Mapping[str, Any]
    _adapter: TypeAdapter[Any]
    _execute: Callable[[Any, FunctionContext], object]


def define_function(
    *,
    description: str,
    input_schema: TypeForm[_InputT],
    execute: Callable[[_InputT, FunctionContext], object],
) -> ChatFunction:
    """Define a chat function whose input is validated by ``input_schema``."""
    if not description.strip():
        raise ValueError("description must not be empty.")
    adapter: TypeAdapter[Any] = TypeAdapter(input_schema)
    schema = adapter.json_schema()
    if schema.get("type") != "object":
        raise ValueError("input_schema must describe a JSON object.")
    return ChatFunction(description, schema, adapter, execute)


def function_definitions(
    functions: Mapping[str, ChatFunction],
    *,
    asynchronous: bool,
) -> dict[str, object]:
    if len(functions) > MAX_FUNCTIONS:
        raise ValueError(f"At most {MAX_FUNCTIONS} functions are allowed.")
    definitions: dict[str, object] = {}
    for name, function in functions.items():
        if not _valid_name(name):
            raise ValueError(f"Invalid or reserved function name: {name!r}.")
        if not isinstance(function, ChatFunction):
            raise TypeError("functions values must be created with define_function.")
        if not asynchronous and inspect.iscoroutinefunction(function._execute):
            raise ValueError(
                f"Function {name} is async; use AsyncBlazingAgents for async handlers."
            )
        definitions[name] = {
            "description": function.description,
            "inputSchema": function.json_schema,
        }
    encoded = json.dumps(definitions, separators=(",", ":")).encode()
    if len(encoded) > MAX_DEFINITIONS_BYTES:
        raise ValueError(
            f"Function definitions exceed {MAX_DEFINITIONS_BYTES} serialized bytes."
        )
    return definitions


class _FunctionCall(BaseModel):
    id: str = Field(pattern=r"^fc_[0-9A-Za-z]{16}$")
    name: Annotated[str, AfterValidator(_function_name)]
    input: object
    deadline_at: AwareDatetime = Field(alias="deadlineAt")


class _FunctionCallEvent(BaseModel):
    type: Literal["data-ba-function-call"]
    data: _FunctionCall
    transient: Literal[True]


class SseFrames:
    """Splits an SSE byte stream into complete events, preserving their bytes."""

    def __init__(self) -> None:
        self._buffer = b""

    def feed(self, chunk: bytes) -> list[bytes]:
        self._buffer += chunk
        frames: list[bytes] = []
        start = 0
        for match in _FRAME_END.finditer(self._buffer):
            frames.append(self._buffer[start : match.end()])
            start = match.end()
        self._buffer = self._buffer[start:]
        return frames

    def flush(self) -> bytes:
        rest, self._buffer = self._buffer, b""
        return rest


def function_call(frame: bytes, response: httpx.Response) -> _FunctionCall | None:
    """The function call a frame authorizes, or None to relay it unchanged.

    A frame naming the private event that does not parse or validate never
    reaches the consumer; it fails the stream instead.
    """
    if _EVENT_TYPE.encode() not in frame:
        return None
    data = "\n".join(
        line[5:].removeprefix(" ")
        for line in frame.decode("utf-8", "replace").splitlines()
        if line.startswith("data:")
    )
    if _EVENT_TYPE not in data:
        return None
    try:
        payload: object = json.loads(data)
        if (
            not isinstance(payload, dict)
            or cast(dict[str, object], payload).get("type") != _EVENT_TYPE
        ):
            return None
        return _FunctionCallEvent.model_validate(payload).data
    except (ValueError, ValidationError):
        raise StreamError(
            "The server sent a malformed function call event.",
            response=response,
        ) from None


def _prepare(
    functions: Mapping[str, ChatFunction],
    call: _FunctionCall,
) -> tuple[ChatFunction, object] | dict[str, object]:
    function = functions.get(call.name)
    if function is None:
        return _error(_unknown_function(call.name))
    try:
        return function, function._adapter.validate_python(call.input)
    except ValidationError:
        return _error(INVALID_INPUT)


def _error(message: str) -> dict[str, object]:
    return {"kind": "error", "message": message}


def _output(name: str, value: object) -> dict[str, object]:
    """Accept only plain JSON: no NaN, Infinity, tuples, non-str keys or objects."""
    outcome: dict[str, object] = {"kind": "output", "value": value}
    encoded = ""
    try:
        encoded = json.dumps(
            outcome, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        plain = json.loads(encoded) == outcome
    except (TypeError, ValueError, RecursionError):
        plain = False
    if not plain:
        _LOGGER.warning("Function %s returned a non-JSON value", name)
        return _error(INVALID_RESULT)
    if len(encoded.encode()) > MAX_PAYLOAD_BYTES:
        _LOGGER.warning("Function %s result exceeds %s bytes", name, MAX_PAYLOAD_BYTES)
        return _error(INVALID_RESULT)
    return outcome


def _retry_delay(error: BlazingAgentsError, attempt: int) -> float | None:
    """Delay before retrying a claim or result, or None for a permanent failure."""
    if isinstance(error, APIStatusError):
        if error.status_code < 500 and error.status_code not in _RETRYABLE_STATUS:
            return None
        retry_after: str | None = error.retry_after
        if retry_after is not None and retry_after.isdigit():
            return float(retry_after)
        try:
            retry_at = parsedate_to_datetime(cast(str, retry_after))
        except (TypeError, ValueError):
            pass
        else:
            return max(0.0, retry_at.timestamp() - time.time())
    return min(_FIRST_RETRY_DELAY * 2.0**attempt, _MAX_RETRY_DELAY)


@dataclass(frozen=True)
class _CallScope:
    agent_id: str
    session_id: str
    extra_headers: Mapping[str, str] | None

    def request(self, call_id: str, action: str, body: object) -> _Request:
        return _Request(
            "POST",
            (
                f"/v1/agents/{quote(self.agent_id, safe='')}"
                f"/sessions/{quote(self.session_id, safe='')}"
                f"/function-calls/{quote(call_id, safe='')}/{action}"
            ),
            json_body=body,
            extra_headers=self.extra_headers,
        )


def _log_execution_failure(call: _FunctionCall) -> None:
    _LOGGER.warning("Function %s (%s) raised an exception", call.name, call.id)


class _Runner:
    failure: BlazingAgentsError | None = None
    """A permanent claim or result failure the stream must raise."""

    def _give_up(
        self, action: str, call: _FunctionCall, error: BlazingAgentsError
    ) -> None:
        if isinstance(error, APIStatusError) and error.status_code == 409:
            _LOGGER.debug("Function call %s %s was refused", call.id, action)
            return
        _LOGGER.warning("Function call %s %s failed: %s", call.id, action, error)
        if _retry_delay(error, 0) is None:
            self.failure = self.failure or error


class SyncFunctionRunner(_Runner):
    def __init__(
        self,
        transport: SyncTransport,
        scope: _CallScope,
        functions: Mapping[str, ChatFunction],
    ) -> None:
        self._transport = transport
        self._scope = scope
        self._functions = dict(functions)
        self._seen: set[str] = set()
        self._active: set[threading.Event] = set()
        self._lock = threading.Lock()
        self._closed = threading.Event()

    def dispatch(self, call: _FunctionCall) -> None:
        if call.id in self._seen or self._closed.is_set():
            return
        self._seen.add(call.id)
        threading.Thread(
            target=self._run,
            args=(call,),
            name=f"blazing-agents-function-{call.id}",
            daemon=True,
        ).start()

    def close(self) -> None:
        self._closed.set()
        with self._lock:
            for cancelled in self._active:
                cancelled.set()

    def _run(self, call: _FunctionCall) -> None:
        cancelled = threading.Event()
        with self._lock:
            if self._closed.is_set():
                return
            self._active.add(cancelled)
        deadline = call.deadline_at.timestamp()
        claim = {"claimRequestId": str(uuid.uuid4())}
        try:
            if not self._post(call, "claim", claim, until=deadline):
                return
            if self._closed.is_set() or time.time() >= deadline:
                return
            outcome = self._execute(call, cancelled, deadline)
            if outcome is not None:
                self._post(
                    call,
                    "result",
                    {**claim, "outcome": outcome},
                    until=deadline + _RESULT_GRACE_SECONDS,
                )
        finally:
            with self._lock:
                self._active.discard(cancelled)

    def _execute(
        self,
        call: _FunctionCall,
        cancelled: threading.Event,
        deadline: float,
    ) -> dict[str, object] | None:
        prepared = _prepare(self._functions, call)
        if isinstance(prepared, dict):
            return prepared
        function, value = prepared
        timer = threading.Timer(max(0.0, deadline - time.time()), cancelled.set)
        timer.daemon = True
        timer.start()
        try:
            result = function._execute(
                value, FunctionContext(call.id, call.deadline_at, cancelled)
            )
            if inspect.iscoroutine(result):
                result.close()
                raise TypeError("A synchronous client cannot await a function result.")
        except Exception:
            _log_execution_failure(call)
            outcome = _error(EXECUTION_FAILED)
        else:
            outcome = _output(call.name, result)
        finally:
            timer.cancel()
        return None if cancelled.is_set() else outcome

    def _post(
        self,
        call: _FunctionCall,
        action: str,
        body: object,
        *,
        until: float,
    ) -> bool:
        attempt = 0
        while True:
            try:
                self._transport.request(
                    self._scope.request(call.id, action, body), None
                )
                return True
            except BlazingAgentsError as error:
                delay = _retry_delay(error, attempt)
                if delay is None or time.time() + delay >= until:
                    self._give_up(action, call, error)
                    return False
            if self._closed.wait(delay):
                return False
            attempt += 1


async def _invoke(
    function: ChatFunction, value: object, context: FunctionContext
) -> object:
    if inspect.iscoroutinefunction(function._execute):
        return await function._execute(value, context)
    result = await asyncio.to_thread(function._execute, value, context)
    return await result if inspect.isawaitable(result) else result


class AsyncFunctionRunner(_Runner):
    def __init__(
        self,
        transport: AsyncTransport,
        scope: _CallScope,
        functions: Mapping[str, ChatFunction],
    ) -> None:
        self._transport = transport
        self._scope = scope
        self._functions = dict(functions)
        self._seen: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    def dispatch(self, call: _FunctionCall) -> None:
        if call.id in self._seen or self._closed:
            return
        self._seen.add(call.id)
        task = asyncio.get_running_loop().create_task(self._run(call))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def aclose(self) -> None:
        self._closed = True
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, call: _FunctionCall) -> None:
        deadline = call.deadline_at.timestamp()
        claim = {"claimRequestId": str(uuid.uuid4())}
        if not await self._post(call, "claim", claim, until=deadline):
            return
        if self._closed or time.time() >= deadline:
            return
        await self._submit(call, claim, await self._execute(call, deadline))

    async def _submit(
        self,
        call: _FunctionCall,
        claim: dict[str, str],
        outcome: dict[str, object] | None,
    ) -> None:
        if outcome is None:
            return
        await self._post(
            call,
            "result",
            {**claim, "outcome": outcome},
            until=call.deadline_at.timestamp() + _RESULT_GRACE_SECONDS,
        )

    async def _execute(
        self,
        call: _FunctionCall,
        deadline: float,
    ) -> dict[str, object] | None:
        prepared = _prepare(self._functions, call)
        if isinstance(prepared, dict):
            return prepared
        function, value = prepared
        cancelled = threading.Event()
        context = FunctionContext(call.id, call.deadline_at, cancelled)
        limit = asyncio.timeout_at(
            asyncio.get_running_loop().time() + deadline - time.time()
        )
        try:
            async with limit:
                result = await _invoke(function, value, context)
        except TimeoutError:
            if not limit.expired():
                _log_execution_failure(call)
                return _error(EXECUTION_FAILED)
            cancelled.set()
            return None
        except asyncio.CancelledError:
            cancelled.set()
            raise
        except Exception:
            _log_execution_failure(call)
            return _error(EXECUTION_FAILED)
        return _output(call.name, result)

    async def _post(
        self,
        call: _FunctionCall,
        action: str,
        body: object,
        *,
        until: float,
    ) -> bool:
        attempt = 0
        while True:
            try:
                await self._transport.request(
                    self._scope.request(call.id, action, body), None
                )
                return True
            except BlazingAgentsError as error:
                delay = _retry_delay(error, attempt)
                if delay is None or time.time() + delay >= until:
                    self._give_up(action, call, error)
                    return False
            await asyncio.sleep(delay)
            attempt += 1
