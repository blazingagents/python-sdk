from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from urllib.parse import quote

import httpx

from ._downloads import AsyncByteStream, ByteStream
from ._errors import StreamError
from ._functions import (
    AsyncFunctionRunner,
    FunctionEventObserver,
    SseFrames,
    SyncFunctionRunner,
    function_call,
)
from ._models import ToolApprovalContinuation
from ._transport import OMITTED, _Omitted, _Request
from ._types import ChatTrigger, Timeout

_SESSION_ID = re.compile(r"ss_[0-9A-Za-z]{16}\Z")


class ChatStream(ByteStream):
    """A single-consumer raw chat response with its resolved Session ID.

    With functions, the stream runs handlers while it is consumed and removes
    their control events from the relayed bytes.
    """

    def __init__(
        self,
        response: httpx.Response,
        session_id: str | None,
        functions: (
            Callable[[str], SyncFunctionRunner | FunctionEventObserver] | None
        ) = None,
    ) -> None:
        super().__init__(response)
        self.session_id = _session_id(response) if session_id is None else session_id
        self._functions = None if functions is None else functions(self.session_id)

    def _consume(self) -> Iterator[bytes]:
        runner = self._functions
        if runner is None:
            yield from super()._consume()
            return
        frames = SseFrames()
        try:
            for chunk in super()._consume():
                if runner.failure is not None:
                    raise runner.failure
                for frame in frames.feed(chunk):
                    call = function_call(frame, self._response)
                    if call is None:
                        yield frame
                    else:
                        runner.dispatch(call)
            if runner.failure is not None:
                raise runner.failure
            rest = frames.flush()
            if rest:
                yield rest
        finally:
            self.close()

    def close(self) -> None:
        if self._functions is not None:
            self._functions.close()
        super().close()


class AsyncChatStream(AsyncByteStream):
    """An asynchronous single-consumer raw chat response.

    With functions, handlers run concurrently while the stream is consumed.
    """

    def __init__(
        self,
        response: httpx.Response,
        session_id: str | None,
        functions: (
            Callable[[str], AsyncFunctionRunner | FunctionEventObserver] | None
        ) = None,
    ) -> None:
        super().__init__(response)
        self.session_id = _session_id(response) if session_id is None else session_id
        self._functions = None if functions is None else functions(self.session_id)

    async def _consume(self) -> AsyncIterator[bytes]:
        runner = self._functions
        if runner is None:
            async for chunk in super()._consume():
                yield chunk
            return
        frames = SseFrames()
        try:
            async for chunk in super()._consume():
                if runner.failure is not None:
                    raise runner.failure
                for frame in frames.feed(chunk):
                    call = function_call(frame, self._response)
                    if call is None:
                        yield frame
                    else:
                        runner.dispatch(call)
            if runner.failure is not None:
                raise runner.failure
            rest = frames.flush()
            if rest:
                yield rest
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if self._functions is not None:
            await self._functions.aclose()
        await super().aclose()


def _session_id(response: httpx.Response) -> str:
    location: str | None = response.headers.get("location")
    if location is None:
        raise StreamError(
            "The server did not return a Session ID in the Location header.",
            response=response,
        )
    candidate = location.rsplit("/", 1)[-1]
    if _SESSION_ID.fullmatch(candidate) is None:
        raise StreamError(
            "The server returned a malformed Session Location header.",
            response=response,
        )
    return candidate


def _chat_body(
    *,
    message: dict[str, object] | _Omitted,
    prompt_id: str | _Omitted,
    variables: dict[str, str] | _Omitted,
    trigger: ChatTrigger | _Omitted,
    message_id: str | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    functions: dict[str, object] | _Omitted,
) -> dict[str, object]:
    has_message = not isinstance(message, _Omitted)
    has_prompt = not isinstance(prompt_id, _Omitted)
    if has_message == has_prompt:
        raise ValueError("Provide exactly one of message or prompt_id.")
    if not isinstance(variables, _Omitted) and not has_prompt:
        raise ValueError("variables can only be used with prompt_id.")
    if not isinstance(trigger, _Omitted) and trigger not in {
        "submit-message",
        "regenerate-message",
    }:
        raise ValueError("trigger must be submit-message or regenerate-message.")
    if not isinstance(message_id, _Omitted) and not message_id:
        raise ValueError("message_id must not be empty.")

    body: dict[str, object] = {}
    if has_message:
        body["message"] = message
    else:
        body["promptId"] = prompt_id
        if not isinstance(variables, _Omitted):
            body["variables"] = variables
    for wire_name, value in (
        ("trigger", trigger),
        ("messageId", message_id),
        ("userId", user_id),
        ("metadata", metadata),
        ("functions", functions),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value
    return body


def chat_request(
    *,
    agent_id: str,
    message: dict[str, object] | _Omitted = OMITTED,
    prompt_id: str | _Omitted = OMITTED,
    variables: dict[str, str] | _Omitted = OMITTED,
    trigger: ChatTrigger | _Omitted = OMITTED,
    message_id: str | _Omitted = OMITTED,
    session_id: str | _Omitted = OMITTED,
    user_id: str | _Omitted = OMITTED,
    metadata: dict[str, object] | _Omitted = OMITTED,
    functions: dict[str, object] | _Omitted = OMITTED,
    client_request_id: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
    timeout: Timeout | _Omitted = OMITTED,
) -> tuple[_Request, str | None]:
    path = f"/v1/agents/{quote(agent_id, safe='')}/sessions"
    if isinstance(session_id, _Omitted):
        resolved_session_id = None
        if trigger == "regenerate-message":
            raise ValueError("regenerate-message can only resume an existing Session.")
    else:
        resolved_session_id = session_id
        path = f"{path}/{quote(resolved_session_id, safe='')}"
    return (
        _Request(
            "POST",
            path,
            client_request_id=client_request_id,
            json_body=_chat_body(
                message=message,
                prompt_id=prompt_id,
                variables=variables,
                trigger=trigger,
                message_id=message_id,
                user_id=user_id,
                metadata=metadata,
                functions=functions,
            ),
            extra_headers=extra_headers,
            timeout=timeout,
        ),
        resolved_session_id,
    )


def path_segment(name: str, value: str) -> str:
    """Percent-encode a caller identity, rejecting values a URL would collapse."""
    if value in {"", ".", ".."}:
        raise ValueError(f"{name} must not be empty, '.' or '..'.")
    return quote(value, safe="")


def input_turn_request(
    *,
    agent_id: str,
    session_id: str,
    turn_id: str,
    extra_headers: Mapping[str, str] | None,
    timeout: Timeout | _Omitted,
) -> _Request:
    return _Request(
        "GET",
        (
            f"/v1/agents/{quote(agent_id, safe='')}"
            f"/sessions/{quote(session_id, safe='')}"
            f"/input-turns/{path_segment('turn_id', turn_id)}"
        ),
        extra_headers=extra_headers,
        timeout=timeout,
    )


def run_inputs_request(
    *,
    agent_id: str,
    session_id: str,
    functions: dict[str, object] | _Omitted,
    extra_headers: Mapping[str, str] | None,
    timeout: Timeout | _Omitted,
) -> _Request:
    return _Request(
        "POST",
        (
            f"/v1/agents/{quote(agent_id, safe='')}"
            f"/sessions/{quote(session_id, safe='')}/inputs/run"
        ),
        json_body={} if isinstance(functions, _Omitted) else {"functions": functions},
        extra_headers=extra_headers,
        timeout=timeout,
    )


def resume_request(
    *,
    agent_id: str,
    session_id: str,
    continuation: ToolApprovalContinuation | None,
    extra_headers: Mapping[str, str] | None,
    timeout: Timeout | _Omitted,
) -> _Request:
    if continuation is None:
        raise ValueError("The Session has no tool approval continuation to resume.")
    if continuation.state not in {"queued", "running"}:
        raise ValueError(
            f"The tool approval continuation is {continuation.state}; "
            "only a queued or running continuation can be resumed."
        )
    return _Request(
        "POST",
        (
            f"/v1/agents/{quote(agent_id, safe='')}"
            f"/sessions/{quote(session_id, safe='')}"
            f"/tool-approval-continuations/{quote(continuation.id, safe='')}/resume"
        ),
        json_body={},
        extra_headers=extra_headers,
        timeout=timeout,
    )
