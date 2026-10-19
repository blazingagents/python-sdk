from __future__ import annotations

from collections.abc import Mapping
from typing import get_args

from ._models import (
    McpConnection,
    McpConnectionReconnectResult,
    McpConnections,
    McpConnectionTestResult,
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
    McpConnectionAuthType,
    Timeout,
)


def _mcp_connection_path(mcp_connection_id: str) -> str:
    """Build the encoded mcp connection endpoint path."""
    return f"/v1/mcp-connections/{path_segment('mcp_connection_id', mcp_connection_id)}"


def _mcp_connection_body(
    *,
    auth_type: McpConnectionAuthType,
    url: str,
    name: str | _Omitted,
    bearer_token: str | _Omitted,
    client_id: str | _Omitted,
    client_secret: str | _Omitted,
    scope: str | _Omitted,
) -> dict[str, object]:
    """Build the mcp connection request body, omitting unspecified fields."""
    if auth_type not in get_args(McpConnectionAuthType):
        msg = "auth_type must be a supported MCP Connection authentication type"
        raise ValueError(msg)

    supplied = {
        "bearer": not isinstance(bearer_token, _Omitted),
        "client_id": not isinstance(client_id, _Omitted),
        "client_secret": not isinstance(client_secret, _Omitted),
        "scope": not isinstance(scope, _Omitted),
    }
    if auth_type == "none" and any(supplied.values()):
        msg = "none authentication accepts exactly no credential fields"
        raise ValueError(msg)
    if auth_type == "bearer" and (
        not supplied["bearer"]
        or supplied["client_id"]
        or supplied["client_secret"]
        or supplied["scope"]
    ):
        msg = "bearer authentication accepts exactly bearer_token"
        raise ValueError(msg)
    if auth_type == "oauth_authorization_code":
        if supplied["bearer"]:
            msg = "Authorization Code does not accept bearer_token"
            raise ValueError(msg)
        if supplied["client_id"] != supplied["client_secret"]:
            msg = "client_id and client_secret must be provided together"
            raise ValueError(msg)
    if auth_type == "oauth_client_credentials" and (
        supplied["bearer"] or not supplied["client_id"] or not supplied["client_secret"]
    ):
        msg = "OAuth Client Credentials requires exactly client_id and client_secret"
        raise ValueError(msg)

    body: dict[str, object] = {"authType": auth_type, "url": url}
    body |= drop_omitted(
        ("name", name),
        ("bearerToken", bearer_token),
        ("clientId", client_id),
        ("clientSecret", client_secret),
        ("scope", scope),
    )
    return body


def _credential_values(*values: str | _Omitted) -> tuple[str, ...]:
    """Collect credential values for response redaction."""
    return tuple(value for value in values if isinstance(value, str) and value)


class AsyncMcpConnectionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind MCP Connection operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        url: str,
        auth_type: McpConnectionAuthType,
        bearer_token: str | _Omitted = OMITTED,
        client_id: str | _Omitted = OMITTED,
        client_secret: str | _Omitted = OMITTED,
        scope: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnection:
        """Create a MCP Connection.

        Bearer authentication accepts only bearer_token. OAuth client credentials
        require client_id and client_secret. Authorization code credentials must be
        paired.

        Args:
            name: MCP Connection display name, unique within the tenant.
            url: Service endpoint URL.
            auth_type: Connection authentication type.
            bearer_token: Bearer token for bearer authentication.
            client_id: OAuth client identifier.
            client_secret: OAuth client secret.
            scope: OAuth scopes requested from the MCP service.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested MCP Connection details.

        Raises:
            ValueError: The authentication type and supplied credential fields do not
                match.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body = _mcp_connection_body(
            auth_type=auth_type,
            url=url,
            name=name,
            bearer_token=bearer_token,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/mcp-connections",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=_credential_values(
                    bearer_token,
                    client_secret,
                ),
            ),
            McpConnection,
        )

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnections:
        """Fetch one page of MCP Connection records.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Available MCP Connections.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/mcp-connections",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnections,
        )

    async def get(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnection:
        """Fetch the requested MCP Connection.

        Args:
            mcp_connection_id: MCP Connection identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested MCP Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _mcp_connection_path(mcp_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnection,
        )

    async def update(
        self,
        mcp_connection_id: str,
        *,
        name: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnection:
        """Update the provided MCP Connection fields.

        Args:
            mcp_connection_id: MCP Connection identifier.
            name: MCP Connection display name, unique within the tenant.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested MCP Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        if isinstance(name, _Omitted):
            msg = "At least one MCP Connection field must be provided."
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "PATCH",
                _mcp_connection_path(mcp_connection_id),
                json_body={"name": name},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnection,
        )

    async def delete(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested MCP Connection.

        Args:
            mcp_connection_id: MCP Connection identifier.
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
                _mcp_connection_path(mcp_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    async def test(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnectionTestResult:
        """Test an MCP Connection.

        Args:
            mcp_connection_id: MCP Connection identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Connectivity test result.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_mcp_connection_path(mcp_connection_id)}/test",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnectionTestResult,
        )

    async def reconnect(
        self,
        mcp_connection_id: str,
        *,
        url: str,
        auth_type: McpConnectionAuthType,
        bearer_token: str | _Omitted = OMITTED,
        client_id: str | _Omitted = OMITTED,
        client_secret: str | _Omitted = OMITTED,
        scope: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnectionReconnectResult:
        """Reconnect an MCP Connection.

        Bearer authentication accepts only bearer_token. OAuth client credentials
        require client_id and client_secret. Authorization code credentials must be
        paired.

        Args:
            mcp_connection_id: MCP Connection identifier.
            url: Service endpoint URL.
            auth_type: Connection authentication type.
            bearer_token: Bearer token for bearer authentication.
            client_id: OAuth client identifier.
            client_secret: OAuth client secret.
            scope: OAuth scopes requested from the MCP service.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Result of the reconnect request.

        Raises:
            ValueError: The authentication type and supplied credential fields do not
                match.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body = _mcp_connection_body(
            auth_type=auth_type,
            url=url,
            name=OMITTED,
            bearer_token=bearer_token,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
        return await self._transport.request(
            _Request(
                "POST",
                f"{_mcp_connection_path(mcp_connection_id)}/reconnect",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=_credential_values(
                    bearer_token,
                    client_secret,
                ),
            ),
            McpConnectionReconnectResult,
        )
