from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence

import httpx

from ._downloads import AsyncByteStream, ByteStream
from ._errors import StreamError
from ._functions import (
    AsyncFunctionRunner,
    FunctionRunner,
    SseFrames,
    function_call,
)
from ._transport import OMITTED, _Omitted, _Request, drop_omitted, path_segment
from ._types import ChatTrigger, Timeout, ToolApprovalDecisionInput

_SESSION_ID = re.compile(r"ss_[0-9A-Za-z]{16}\Z")
_TURN_ID = re.compile(r"turn_[0-9A-Za-z]{16}\Z")


class ChatStream(ByteStream):
    """A single-consumer raw chat response with its Session and running Turn IDs.

    With functions, the stream runs handlers while it is consumed and removes
    their control events from the relayed bytes.
    """

    def __init__(
        self,
        response: httpx.Response,
        session_id: str | None,
        functions: (Callable[[str], FunctionRunner] | None) = None,
    ) -> None:
        """Wrap a raw chat response for the Session it started or resumed.

        Args:
            response: HTTPX response supplying the body and response metadata.
            session_id: Session identifier.
            functions: Factory for a function runner bound to the resolved Session,
                or None.
        """
        super().__init__(response)
        self.session_id = _session_id(response) if session_id is None else session_id
        self.turn_id = _turn_id(response)
        self._functions = None if functions is None else functions(self.session_id)

    def _consume(self) -> Iterator[bytes]:
        """Yield response chunks and close the response when consumption ends."""
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
        """Close the response and release resources."""
        if self._functions is not None:
            self._functions.close()
        super().close()


class AsyncChatStream(AsyncByteStream):
    """An asynchronous single-consumer raw chat response with its Session and Turn IDs.

    With functions, handlers run concurrently while the stream is consumed.
    """

    def __init__(
        self,
        response: httpx.Response,
        session_id: str | None,
        functions: (Callable[[str], AsyncFunctionRunner] | None) = None,
    ) -> None:
        """Wrap an async raw chat response for its Session.

        Args:
            response: HTTPX response supplying the body and response metadata.
            session_id: Session identifier.
            functions: Factory for a function runner bound to the resolved Session,
                or None.
        """
        super().__init__(response)
        self.session_id = _session_id(response) if session_id is None else session_id
        self.turn_id = _turn_id(response)
        self._functions = None if functions is None else functions(self.session_id)

    async def _consume(self) -> AsyncIterator[bytes]:
        """Yield response chunks and close the response when consumption ends."""
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
        """Close the response and release resources."""
        if self._functions is not None:
            await self._functions.aclose()
        await super().aclose()


def _session_id(response: httpx.Response) -> str:
    """Read and validate the Session ID in the Location header.

    Raises:
        StreamError: The server did not return a Session ID in the Location header.
            The server returned a malformed Session Location header.
    """
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


def _turn_id(response: httpx.Response) -> str:
    """Read and validate the running Turn ID in the X-BA-Turn-Id header.

    Raises:
        StreamError: The server did not return a Turn ID in the X-BA-Turn-Id header.
            The server returned a malformed X-BA-Turn-Id header.
    """
    turn_id: str | None = response.headers.get("x-ba-turn-id")
    if turn_id is None:
        raise StreamError(
            "The server did not return a Turn ID in the X-BA-Turn-Id header.",
            response=response,
        )
    if _TURN_ID.fullmatch(turn_id) is None:
        raise StreamError(
            "The server returned a malformed X-BA-Turn-Id header.",
            response=response,
        )
    return turn_id


def _chat_body(
    *,
    message: dict[str, object] | _Omitted,
    messages: list[dict[str, object]] | _Omitted,
    prompt_id: str | _Omitted,
    variables: dict[str, str] | _Omitted,
    trigger: ChatTrigger | _Omitted,
    message_id: str | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    functions: dict[str, object] | _Omitted,
) -> dict[str, object]:
    """Build the chat request body, omitting unspecified fields.

    Raises:
        ValueError: Provide exactly one of message, messages or prompt_id. messages
            must not be empty. regenerate-message requires exactly one message.
            variables can only be used with prompt_id. trigger must be submit-message
            or regenerate-message. message_id must not be empty.
    """
    has_message = not isinstance(message, _Omitted)
    has_prompt = not isinstance(prompt_id, _Omitted)
    has_messages = not isinstance(messages, _Omitted)
    if sum((has_message, has_messages, has_prompt)) != 1:
        raise ValueError("Provide exactly one of message, messages or prompt_id.")
    if has_messages and not messages:
        raise ValueError("messages must not be empty.")
    if (
        trigger == "regenerate-message"
        and not isinstance(messages, _Omitted)
        and len(messages) != 1
    ):
        raise ValueError("regenerate-message requires exactly one message.")
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
        body["messages"] = [message]
    elif has_messages:
        body["messages"] = messages
    else:
        body["promptId"] = prompt_id
        if not isinstance(variables, _Omitted):
            body["variables"] = variables
    body |= drop_omitted(
        ("trigger", trigger),
        ("messageId", message_id),
        ("userId", user_id),
        ("metadata", metadata),
        ("functions", functions),
    )
    return body


def chat_request(
    *,
    agent_id: str,
    message: dict[str, object] | _Omitted = OMITTED,
    messages: list[dict[str, object]] | _Omitted = OMITTED,
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
    """Build a chat request and resolve whether it resumes a Session.

    Args:
        agent_id: Agent identifier.
        message: One message. Provide exactly one of message, messages, or prompt_id.
        messages: Nonempty message batch. Regeneration accepts one message.
        prompt_id: Stored Prompt identifier.
        variables: Template substitutions. Requires prompt_id.
        trigger: Submit a message or regenerate an existing Session message.
        message_id: Message identifier for the chat trigger.
        session_id: Session identifier. Omit to create a new Session.
        user_id: Caller-defined user identifier.
        metadata: Caller-defined JSON metadata.
        functions: Factory for a function runner bound to the resolved Session,
                or None.
        client_request_id: Caller correlation ID sent as X-Client-Request-Id.
        extra_headers: Headers for this request. Authorization uses the client API
            key.
        timeout: Request timeout override. OMITTED inherits the client timeout.

    Returns:
        Prepared request and existing Session ID, or None for a new Session.

    Raises:
        ValueError: regenerate-message can only resume an existing Session.
    """
    path = f"/v1/agents/{path_segment('agent_id', agent_id)}/sessions"
    if isinstance(session_id, _Omitted):
        resolved_session_id = None
        if trigger == "regenerate-message":
            raise ValueError("regenerate-message can only resume an existing Session.")
    else:
        resolved_session_id = session_id
        path = f"{path}/{path_segment('session_id', resolved_session_id)}"
    return (
        _Request(
            "POST",
            path,
            client_request_id=client_request_id,
            json_body=_chat_body(
                message=message,
                messages=messages,
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


def continue_request(
    *,
    agent_id: str,
    session_id: str,
    decisions: Sequence[ToolApprovalDecisionInput],
    functions: dict[str, object] | _Omitted,
    client_request_id: str | None,
    extra_headers: Mapping[str, str] | None,
    timeout: Timeout | _Omitted,
) -> _Request:
    """Build the request that decides a complete approval round.

    Args:
        agent_id: Agent identifier.
        session_id: Session identifier.
        decisions: Decisions for the complete pending approval round.
        functions: Factory for a function runner bound to the resolved Session,
                or None.
        client_request_id: Caller correlation ID sent as X-Client-Request-Id.
        extra_headers: Headers for this request. Authorization uses the client API
            key.
        timeout: Request timeout override. OMITTED inherits the client timeout.

    Returns:
        Prepared HTTP request.
    """
    body: dict[str, object] = {
        "decisions": [
            {
                "approvalId": decision["approval_id"],
                "approved": decision["approved"],
                **({"reason": decision["reason"]} if "reason" in decision else {}),
            }
            for decision in decisions
        ]
    }
    if not isinstance(functions, _Omitted):
        body["functions"] = functions
    return _Request(
        "POST",
        (
            f"/v1/agents/{path_segment('agent_id', agent_id)}"
            f"/sessions/{path_segment('session_id', session_id)}"
            "/tool-approvals/continue"
        ),
        json_body=body,
        client_request_id=client_request_id,
        extra_headers=extra_headers,
        timeout=timeout,
    )
