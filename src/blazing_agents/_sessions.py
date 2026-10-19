from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from ._models import (
    LatestSessionsPage,
    Session,
    SessionInputResponse,
    SessionInputsPage,
    SessionMessagesPage,
    SessionResponse,
    SessionsPage,
    SessionStopResponse,
    ToolApprovals,
)
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    decode_none,
    drop_omitted,
    path_segment,
)
from ._types import (
    Timeout,
)
from ._wire import session_messages_query


def _sessions_path(agent_id: str, session_id: str | None = None) -> str:
    """Build the encoded sessions endpoint path."""
    path = f"/v1/agents/{path_segment('agent_id', agent_id)}/sessions"
    if session_id is not None:
        return f"{path}/{path_segment('session_id', session_id)}"
    return path


def _inputs_body(
    request_id: str,
    message: Mapping[str, object],
) -> dict[str, object]:
    """Build the inputs request body, omitting unspecified fields."""
    path_segment("request_id", request_id)
    body: dict[str, object] = {"requestId": request_id, "message": message}
    return body


def _inputs_query(
    include_completed: bool | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    """Build the inputs query, omitting unspecified filters."""
    query: dict[str, str | int] = {}
    if not isinstance(include_completed, _Omitted):
        query["includeCompleted"] = str(include_completed).lower()
    return query | drop_omitted(("cursor", cursor), ("limit", limit))


def _sessions_query(
    user_id: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
    by_agent: bool | None = None,
) -> dict[str, str | int]:
    """Build the sessions query, omitting unspecified filters."""
    query: dict[str, str | int] = drop_omitted(
        ("userId", user_id),
        ("cursor", cursor),
        ("limit", limit),
    )
    if by_agent is not None:
        query["byAgent"] = str(by_agent).lower()
    return query


class AsyncSessionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Session operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def fork(
        self,
        agent_id: str,
        session_id: str,
        *,
        message_id: str,
        idempotency_key: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionResponse:
        """Fork a Session at the selected message.

        The idempotency_key replaces any Idempotency-Key in extra_headers.

        Retry uncertain acknowledgements with the same explicit key.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            message_id: Message at which to fork the Session.
            idempotency_key: Stable key for retrying the same operation without
                duplicating it.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Session response details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        headers = {
            name: value
            for name, value in (extra_headers or {}).items()
            if name.lower() != "idempotency-key"
        }
        headers["Idempotency-Key"] = idempotency_key
        return await self._transport.request(
            _Request(
                "POST",
                f"{_sessions_path(agent_id, session_id)}/fork",
                json_body={"messageId": message_id},
                extra_headers=headers,
                timeout=timeout,
            ),
            decode_model(SessionResponse),
        )

    async def get(
        self,
        agent_id: str,
        session_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionResponse:
        """Fetch the requested Session.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Session response details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _sessions_path(agent_id, session_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SessionResponse),
        )

    async def list(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionsPage:
        """Fetch one page of Session records.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _sessions_path(agent_id),
                query=_sessions_query(user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SessionsPage),
        )

    async def list_latest(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        by_agent: bool | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> LatestSessionsPage:
        """Fetch the latest Session for each matching user or Agent grouping.

        Args:
            user_id: Caller-defined user identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            by_agent: Whether latest Sessions are grouped by Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/sessions/latest",
                query=_sessions_query(user_id, cursor, limit, by_agent),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(LatestSessionsPage),
        )

    async def iter(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Session]:
        """Iterate Session records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            Session records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for session in page.data:
                yield session
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def messages(
        self,
        *,
        agent_id: str,
        session_id: str,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionMessagesPage:
        """Fetch a page of Session messages.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            cursor: Continuation cursor from a previous page.
            after: Message cursor for fetching later messages.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/messages",
                query=session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SessionMessagesPage),
        )

    async def tool_approvals(
        self,
        *,
        agent_id: str,
        session_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ToolApprovals:
        """Fetch pending tool approvals for the Session.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Pending approval round for the Session.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/tool-approvals",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ToolApprovals),
        )

    async def submit_input(
        self,
        *,
        agent_id: str,
        session_id: str,
        request_id: str,
        message: Mapping[str, object],
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionInputResponse:
        """Steer a running Turn with one user message.

        Retry with the same request_id and message to recover its receipt.
        If steering is unavailable, no message waits for a future Turn.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            request_id: Idempotency identifier for the submitted input.
            message: Message to queue for the Session.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Acknowledgement of the queued input.

        Raises:
            ValueError: request_id is empty or a dot segment.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_sessions_path(agent_id, session_id)}/inputs",
                json_body=_inputs_body(request_id, message),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SessionInputResponse),
        )

    async def inputs(
        self,
        *,
        agent_id: str,
        session_id: str,
        include_completed: bool | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionInputsPage:
        """List input receipts in admission order with Session activity.

        Poll without cursor to observe changes. cursor only pages the results.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            include_completed: Whether to include completed inputs.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/inputs",
                query=_inputs_query(include_completed, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SessionInputsPage),
        )

    async def stop(
        self,
        *,
        agent_id: str,
        session_id: str,
        turn_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionStopResponse:
        """Record cancellation and return immediately.

        Read the existing Turn stream to observe settlement.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            turn_id: Active Turn identifier to stop.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Result of the stop request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_sessions_path(agent_id, session_id)}/stop",
                json_body={"turnId": turn_id},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SessionStopResponse),
        )

    async def delete(
        self,
        *,
        agent_id: str,
        session_id: str,
        delete_artifacts: bool,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Session.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            delete_artifacts: Whether to delete Artifacts associated with the
                Session.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "DELETE",
                _sessions_path(agent_id, session_id),
                query={"deleteArtifacts": str(delete_artifacts).lower()},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )
