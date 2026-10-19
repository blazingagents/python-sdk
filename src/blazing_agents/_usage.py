from __future__ import annotations

from collections.abc import Mapping, Sequence

from ._models import (
    SessionUsageList,
    Usage,
    UsageOverview,
)
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    drop_omitted,
    path_segment,
)
from ._types import (
    Timeout,
    UsageGroupBy,
)


def _usage_query(
    *,
    from_: str | _Omitted,
    to: str | _Omitted,
    agent_id: str | _Omitted,
    session_id: str | _Omitted,
    user_id: str | _Omitted,
    group_by: UsageGroupBy | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    """Build the usage query, omitting unspecified filters."""
    query: dict[str, str | int] = drop_omitted(
        ("from", from_),
        ("to", to),
        ("agentId", agent_id),
        ("sessionId", session_id),
        ("userId", user_id),
        ("groupBy", group_by),
        ("limit", limit),
    )
    return query


def _usage_overview_query(
    *,
    from_: str | _Omitted,
    to: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    """Build the usage overview query, omitting unspecified filters."""
    query: dict[str, str | int] = drop_omitted(
        ("from", from_), ("to", to), ("limit", limit)
    )
    return query


class AsyncUserUsageResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind usage operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def get(
        self,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        group_by: UsageGroupBy | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Usage:
        """Fetch the requested usage.

        Args:
            from_: Start of the usage interval.
            to: End of the usage interval.
            agent_id: Agent identifier.
            session_id: Session identifier.
            user_id: Caller-defined user identifier.
            group_by: Dimension used to group usage totals.
            limit: Maximum number of grouped results returned.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Usage totals grouped as requested.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        query = _usage_query(
            from_=from_,
            to=to,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            group_by=group_by,
            limit=limit,
        )
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/usage",
                query=query,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Usage,
        )

    async def sessions(
        self,
        session_ids: Sequence[str],
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionUsageList:
        """Fetch usage totals for up to 100 Sessions.

        Args:
            session_ids: Unique Session identifiers, 1 to 100.
            from_: First UTC day (YYYY-MM-DD) of the usage interval.
            to: Last UTC day (YYYY-MM-DD) of the usage interval.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Usage totals for each requested Session.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body: dict[str, object] = {"sessionIds": list(session_ids)}
        body |= drop_omitted(("from", from_), ("to", to))
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/usage/sessions",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SessionUsageList,
        )

    async def get_for_agent(
        self,
        agent_id: str,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        group_by: UsageGroupBy | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Usage:
        """Fetch usage for one Agent.

        Args:
            agent_id: Agent identifier.
            from_: Start of the usage interval.
            to: End of the usage interval.
            session_id: Session identifier.
            user_id: Caller-defined user identifier.
            group_by: Dimension used to group usage totals.
            limit: Maximum number of grouped results returned.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Usage totals grouped as requested.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        query = _usage_query(
            from_=from_,
            to=to,
            agent_id=OMITTED,
            session_id=session_id,
            user_id=user_id,
            group_by=group_by,
            limit=limit,
        )
        return await self._transport.request(
            _Request(
                "GET",
                f"/v1/agents/{path_segment('agent_id', agent_id)}/usage",
                query=query,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Usage,
        )


class AsyncUsageResource(AsyncUserUsageResource):
    async def overview(
        self,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> UsageOverview:
        """Fetch the usage overview.

        Args:
            from_: Start of the usage interval.
            to: End of the usage interval.
            limit: Maximum number of overview entries returned.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Usage overview for the requested interval.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/usage/overview",
                query=_usage_overview_query(from_=from_, to=to, limit=limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            UsageOverview,
        )
