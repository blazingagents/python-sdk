from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from ._models import Workspace, WorkspacesPage
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    decode_status,
    path_segment,
    wire_fields,
)
from ._types import (
    Timeout,
    WorkspaceDeletionOutcome,
    WorkspaceNetworkPolicy,
    WorkspaceTier,
)


def _workspace_path(workspace_id: str) -> str:
    """Build the encoded workspace endpoint path."""
    return f"/v1/workspaces/{path_segment('workspace_id', workspace_id)}"


def _workspace_body(
    *,
    name: str | None | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    network_policy: WorkspaceNetworkPolicy | _Omitted,
    tier: WorkspaceTier | _Omitted = OMITTED,
) -> dict[str, object]:
    """Build the workspace request body, omitting unspecified fields."""
    return wire_fields(
        name=name,
        tier=tier,
        user_id=user_id,
        metadata=metadata,
        network_policy=network_policy
        if isinstance(network_policy, _Omitted)
        else wire_fields(**network_policy),
    )


class AsyncWorkspacesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Workspace operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def create(
        self,
        *,
        tier: WorkspaceTier | _Omitted = OMITTED,
        name: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        network_policy: WorkspaceNetworkPolicy | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        """Create a Workspace.

        Args:
            tier: Immutable Workspace tier; defaults to Core.
            name: Workspace display name, up to 80 characters.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            network_policy: Workspace network access policy.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Workspace details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/workspaces",
                json_body=_workspace_body(
                    tier=tier,
                    name=name,
                    user_id=user_id,
                    metadata=metadata,
                    network_policy=network_policy,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Workspace),
        )

    async def list(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> WorkspacesPage:
        """Fetch one page of Workspace records.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            user_id: Caller-defined user identifier.
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
                "/v1/workspaces",
                query=wire_fields(cursor=cursor, limit=limit, user_id=user_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(WorkspacesPage),
        )

    async def iter(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Workspace]:
        """Iterate Workspace records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            user_id: Caller-defined user identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            Workspace records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                cursor=next_cursor,
                limit=limit,
                user_id=user_id,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for workspace in page.data:
                yield workspace
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        *,
        workspace_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        """Fetch the requested Workspace.

        Args:
            workspace_id: Workspace identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Workspace details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _workspace_path(workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Workspace),
        )

    async def update(
        self,
        *,
        workspace_id: str,
        name: str | None | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        network_policy: WorkspaceNetworkPolicy | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        """Update the provided Workspace fields.

        Args:
            workspace_id: Workspace identifier.
            name: New Workspace display name, or None to clear it.
            metadata: Caller-defined JSON metadata.
            network_policy: Workspace network access policy.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Workspace details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body = _workspace_body(
            name=name,
            user_id=OMITTED,
            metadata=metadata,
            network_policy=network_policy,
        )
        if not body:
            msg = "At least one Workspace field must be provided."
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "PUT",
                _workspace_path(workspace_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Workspace),
        )

    async def delete(
        self,
        *,
        workspace_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> WorkspaceDeletionOutcome:
        """Delete the requested Workspace.

        Args:
            workspace_id: Workspace identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Outcome of the Workspace deletion.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        status = await self._transport.request(
            _Request(
                "DELETE",
                _workspace_path(workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_status,
        )
        return "pending" if status == 202 else "completed"
