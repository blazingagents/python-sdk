from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, Self, TypeVar, cast

from ._chat import AsyncChatStream
from ._client import AsyncBlazingAgents, AsyncUserClient
from ._functions import ChatFunction
from ._relay_wire import (
    HISTORY_PAGE_SIZE,
    ChatBody,
    HistoryBody,
    RelayBody,
    RelayFailure,
    SteerBody,
    UIMessage,
    failure_of,
    parse_body,
    parse_message,
    rejected,
)
from ._transport import OMITTED

RequestT = TypeVar("RequestT")
RequestT_contra = TypeVar("RequestT_contra", contravariant=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class RelayContext:
    """The End-user and Agent that one relayed request acts for.

    Your sign-in resolves it. The relay never reads the End-user or the Agent from
    the request body.
    """

    agent_id: str
    """Agent that serves the request. The End-user must own it, and its Workspace,
    or the API answers 404."""
    user_id: str
    """The signed-in End-user, as `for_user` takes it: printable ASCII, at most 256
    characters, no surrounding spaces. The relay sends every API request as this
    End-user, so the API reaches only their Agents, Sessions and Workspaces."""
    functions: Mapping[str, ChatFunction] | None = None
    """Functions for this request and for the continuation of its Tool approval."""
    metadata: Mapping[str, object] | None = None
    """Attribution metadata stored with each Turn the request starts."""


class AsyncResolveContext(Protocol[RequestT_contra]):
    async def __call__(self, request: RequestT_contra, /) -> RelayContext | None:
        """Resolve the signed-in End-user and their Agent for one request.

        Args:
            request: Whatever your framework's request object is. The relay passes
                it through from `handle`.

        Returns:
            The context, or None when nobody is signed in.
        """
        ...


class AsyncRelayResponse:
    """The relay's answer, ready to hand to your framework's response class.

    Iterate it for the body. A chat answer streams the API's bytes while you
    iterate, so pass it to a streaming response without reading it first. When the
    browser disconnects, stop iterating and call `aclose`: that closes the API
    request, which cancels the Turn. Your framework's disconnect handling normally
    does both.
    """

    status_code: int
    """HTTP status."""
    headers: dict[str, str]
    """Lowercase header names."""

    def __init__(
        self,
        status_code: int,
        headers: dict[str, str],
        body: bytes | AsyncChatStream,
    ) -> None:
        """Wrap an answer. The relay creates it; apps do not.

        Args:
            status_code: HTTP status.
            headers: Response headers.
            body: A complete body, or a chat stream to relay.
        """
        self.status_code = status_code
        self.headers = headers
        self._body = body

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Return the single-consumer iterator over the body chunks.

        Returns:
            Iterator over the body chunks.

        Raises:
            StreamError: A chat stream is consumed, closed, or fails to complete.
        """
        if isinstance(self._body, bytes):
            return self._once(self._body)
        return self._body.__aiter__()

    @staticmethod
    async def _once(chunk: bytes) -> AsyncIterator[bytes]:
        yield chunk

    async def aclose(self) -> None:
        """Close the API request behind a chat stream, if one is open."""
        if not isinstance(self._body, bytes):
            await self._body.aclose()

    @classmethod
    def _json(
        cls,
        status_code: int,
        body: object,
        headers: dict[str, str] | None = None,
    ) -> Self:
        return cls(
            status_code,
            {"content-type": "application/json", **(headers or {})},
            json.dumps(body, separators=(",", ":")).encode(),
        )

    @classmethod
    def _failure(cls, failure: RelayFailure) -> Self:
        return cls._json(failure.status_code, failure.body, failure.headers)

    @classmethod
    def _stream(cls, stream: AsyncChatStream) -> Self:
        headers = {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            "x-accel-buffering": "no",
            "x-ba-turn-id": stream.turn_id,
            "x-vercel-ai-ui-message-stream": "v1",
        }
        if (location := stream.headers.get("location")) is not None:
            headers["location"] = location
        if stream.request_id is not None:
            headers["x-request-id"] = stream.request_id
        return cls(stream.status_code, headers, stream)


class AsyncChatRelay(Generic[RequestT]):
    """The one endpoint a browser chat posts to, answered as the signed-in End-user.

    `useBlazingAgentsChat` and `BlazingAgentsChatTransport` from the TypeScript SDK
    send every request to one URL of your backend, because the browser holds no API
    key. The JSON body's `op` selects the operation: `chat` streams a Turn,
    `history` returns one page of the Session's stored messages, and `steer` sends a
    user message into the Turn running now. Your backend adds only its sign-in, in
    `resolve_context`. The wire contract is the TypeScript SDK's
    `docs/relay-contract.md`.

    The relay depends on no web framework. `handle` takes your framework's request
    and the raw body bytes, and returns a response to pass to the framework's
    streaming response class.

    Every error body is `{"error": {"code": ..., "message": ...}}`: 400
    `invalid_request` for a malformed body or unknown `op`, 401 `unauthorized`, the
    API's own status and code (such as 404 `not_found` or 409 `steer_not_available`)
    with its `X-Request-Id`, 502 `network_error` or `stream_error` for other SDK
    failures, and 500 `internal_error` otherwise, which names no cause and logs it
    to the `blazing_agents` logger. A browser disconnect never reaches `handle`
    as a request error, so there is no 499: your framework stops iterating the
    response and closes it.
    """

    def __init__(
        self,
        *,
        client: AsyncBlazingAgents,
        resolve_context: AsyncResolveContext[RequestT],
    ) -> None:
        """Create the relay for one client and one sign-in.

        Args:
            client: Tenant client. The relay scopes each request with
                `client.for_user(context.user_id)`.
            resolve_context: Authenticates one request and returns its End-user and
                Agent, or None for an unauthenticated request.
        """
        self._client = client
        self._resolve_context = resolve_context

    async def handle(self, request: RequestT, body: bytes) -> AsyncRelayResponse:
        """Answer one browser request.

        Args:
            request: The framework's request. Only `resolve_context` reads it.
            body: The raw JSON request body.

        Returns:
            The answer, which never raises for a failed request.
        """
        try:
            context = await self._resolve_context(request)
            if context is None:
                return AsyncRelayResponse._failure(
                    RelayFailure(401, "unauthorized", "Authentication required.")
                )
            user = self._client.for_user(context.user_id)
            parsed = parse_body(body)
            if parsed is None:
                return AsyncRelayResponse._failure(rejected("Invalid request body."))
            return await self._answer(user, context, parsed)
        except Exception as error:
            return AsyncRelayResponse._failure(failure_of(error))

    async def _answer(
        self, user: AsyncUserClient, context: RelayContext, body: RelayBody
    ) -> AsyncRelayResponse:
        match body:
            case ChatBody():
                return await self._chat(user, context, body)
            case HistoryBody():
                return await self._history(user, context, body)
            case _:  # Narrowed to SteerBody; a new op in RelayBody fails type checks.
                return await self._steer(user, context, body)

    async def _chat(
        self, user: AsyncUserClient, context: RelayContext, body: ChatBody
    ) -> AsyncRelayResponse:
        message = parse_message(body.message)
        if message is None:
            return AsyncRelayResponse._failure(rejected("Invalid chat message."))
        if message.role == "assistant":
            return await self._continue(user, context, body, message)
        if message.role != "user":
            return AsyncRelayResponse._failure(
                rejected("Chat submission requires a user message.")
            )
        functions = OMITTED if context.functions is None else context.functions
        metadata = OMITTED if context.metadata is None else dict(context.metadata)
        message_id = OMITTED if body.message_id is None else body.message_id
        user_message = cast(dict[str, object], body.message)
        if body.session_id is None:
            stream = await user.chat(
                agent_id=context.agent_id,
                message=user_message,
                message_id=message_id,
                metadata=metadata,
                functions=functions,
                trigger="submit-message",
            )
        else:
            stream = await user.chat(
                agent_id=context.agent_id,
                session_id=body.session_id,
                message=user_message,
                message_id=message_id,
                metadata=metadata,
                functions=functions,
                trigger=body.trigger,
            )
        return AsyncRelayResponse._stream(stream)

    async def _continue(
        self,
        user: AsyncUserClient,
        context: RelayContext,
        body: ChatBody,
        message: UIMessage,
    ) -> AsyncRelayResponse:
        if body.session_id is None:
            return AsyncRelayResponse._failure(
                rejected("Tool approval requires an existing Session.")
            )
        decisions = message.approval_decisions()
        if not decisions:
            return AsyncRelayResponse._failure(
                rejected("The message has no tool approval responses.")
            )
        stream = await user.continue_chat(
            agent_id=context.agent_id,
            session_id=body.session_id,
            decisions=decisions,
            functions={} if context.functions is None else context.functions,
        )
        return AsyncRelayResponse._stream(stream)

    async def _history(
        self, user: AsyncUserClient, context: RelayContext, body: HistoryBody
    ) -> AsyncRelayResponse:
        page = await user.sessions.messages(
            agent_id=context.agent_id,
            session_id=body.session_id,
            cursor=OMITTED if body.cursor is None else body.cursor,
            limit=HISTORY_PAGE_SIZE,
        )
        return AsyncRelayResponse._json(
            200,
            {
                "data": [
                    message.model_dump(mode="json", by_alias=True, exclude_unset=True)
                    for message in page.data
                ],
                "nextCursor": page.next_cursor,
            },
        )

    async def _steer(
        self, user: AsyncUserClient, context: RelayContext, body: SteerBody
    ) -> AsyncRelayResponse:
        message = parse_message(body.message)
        if message is None or message.role != "user":
            return AsyncRelayResponse._failure(
                rejected("Steering requires a user message.")
            )
        receipt = await user.sessions.submit_input(
            agent_id=context.agent_id,
            session_id=body.session_id,
            request_id=body.request_id,
            message=cast(dict[str, object], body.message),
        )
        return AsyncRelayResponse._json(202, {"state": receipt.data.state})
