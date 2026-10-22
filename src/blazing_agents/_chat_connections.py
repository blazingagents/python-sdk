from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, overload

from ._chat_models import (
    ChatConnection,
    ChatConnections,
)
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    decode_none,
    path_segment,
    wire_fields,
)
from ._types import (
    SlackChatConfigurationInput,
    SlackChatCredentialsInput,
    TelegramChatConfigurationInput,
    TelegramChatCredentialsInput,
    Timeout,
)


def _path(chat_connection_id: str) -> str:
    """Build the encoded Chat Connection endpoint path."""
    return (
        f"/v1/chat-connections/{path_segment('chat_connection_id', chat_connection_id)}"
    )


class AsyncChatConnectionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Chat Connection operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnections:
        """Fetch the available Chat Connections.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Available Chat Connections.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/chat-connections",
                credential_bearing=True,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ChatConnections),
        )

    async def get(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Fetch the requested Chat Connection.

        Args:
            chat_connection_id: Chat Connection identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _path(chat_connection_id),
                credential_bearing=True,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ChatConnection),
        )

    async def check_health(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Check the Chat Connection health.

        Args:
            chat_connection_id: Chat Connection identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Chat Connection with refreshed health and status.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/health",
                credential_bearing=True,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ChatConnection),
        )

    async def enable(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Enable the Chat Connection.

        Args:
            chat_connection_id: Chat Connection identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/enable",
                credential_bearing=True,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ChatConnection),
        )

    async def disable(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Disable the Chat Connection.

        Args:
            chat_connection_id: Chat Connection identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/disable",
                credential_bearing=True,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ChatConnection),
        )

    async def delete(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Chat Connection.

        Args:
            chat_connection_id: Chat Connection identifier.
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
                _path(chat_connection_id),
                credential_bearing=True,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )

    async def update(
        self,
        chat_connection_id: str,
        *,
        name: str | _Omitted = OMITTED,
        configuration: SlackChatConfigurationInput
        | TelegramChatConfigurationInput
        | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Update the provided Chat Connection fields.

        Args:
            chat_connection_id: Chat Connection identifier.
            name: Name of the entity.
            configuration: Settings for the selected chat platform.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body: dict[str, object] = wire_fields(name=name)
        if not isinstance(configuration, _Omitted):
            body["configuration"] = wire_fields(**configuration)
        return await self._transport.request(
            _Request(
                "PATCH",
                _path(chat_connection_id),
                credential_bearing=True,
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ChatConnection),
        )

    @overload
    async def create(
        self,
        *,
        name: str,
        agent_id: str,
        platform: Literal["slack"],
        configuration: SlackChatConfigurationInput | _Omitted = OMITTED,
        credentials: SlackChatCredentialsInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Create a Chat Connection.

        Args:
            name: Name of the entity.
            agent_id: Agent identifier.
            platform: Chat platform. Must match the configuration and credentials.
            configuration: Settings for the selected chat platform.
            credentials: Credentials for the selected authentication type.
            enabled: Whether the connection is enabled.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.
        """
        ...

    @overload
    async def create(
        self,
        *,
        name: str,
        agent_id: str,
        platform: Literal["telegram"],
        configuration: TelegramChatConfigurationInput | _Omitted = OMITTED,
        credentials: TelegramChatCredentialsInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Create a Chat Connection.

        Args:
            name: Name of the entity.
            agent_id: Agent identifier.
            platform: Chat platform. Must match the configuration and credentials.
            configuration: Settings for the selected chat platform.
            credentials: Credentials for the selected authentication type.
            enabled: Whether the connection is enabled.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.
        """
        ...

    async def create(
        self,
        *,
        platform: Literal["slack", "telegram"],
        credentials: SlackChatCredentialsInput | TelegramChatCredentialsInput,
        name: str,
        agent_id: str,
        configuration: SlackChatConfigurationInput
        | TelegramChatConfigurationInput
        | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Create a Chat Connection.

        Args:
            platform: Chat platform. Must match the configuration and credentials.
            credentials: Credentials for the selected authentication type.
            name: Name of the entity.
            agent_id: Agent identifier.
            configuration: Settings for the selected chat platform.
            enabled: Whether the connection is enabled.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        credentials_body = wire_fields(**credentials)
        body: dict[str, object] = {
            "name": name,
            "agentId": agent_id,
            "platform": platform,
            "credentials": credentials_body,
        }
        if not isinstance(configuration, _Omitted):
            body["configuration"] = wire_fields(**configuration)
        if not isinstance(enabled, _Omitted):
            body["enabled"] = enabled
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/chat-connections",
                credential_bearing=True,
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=tuple(
                    value
                    for value in credentials_body.values()
                    if isinstance(value, str) and value
                ),
            ),
            decode_model(ChatConnection),
        )

    @overload
    async def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["slack"],
        credentials: SlackChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Replace the Chat Connection credentials.

        Args:
            chat_connection_id: Chat Connection identifier.
            platform: Chat platform. Must match the configuration and credentials.
            credentials: Credentials for the selected authentication type.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.
        """
        ...

    @overload
    async def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["telegram"],
        credentials: TelegramChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Replace the Chat Connection credentials.

        Args:
            chat_connection_id: Chat Connection identifier.
            platform: Chat platform. Must match the configuration and credentials.
            credentials: Credentials for the selected authentication type.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.
        """
        ...

    async def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["slack", "telegram"],
        credentials: SlackChatCredentialsInput | TelegramChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        """Replace the Chat Connection credentials.

        Args:
            chat_connection_id: Chat Connection identifier.
            platform: Chat platform. Must match the configuration and credentials.
            credentials: Credentials for the selected authentication type.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Chat Connection details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        credentials_body = wire_fields(**credentials)
        body: dict[str, object] = {"platform": platform, **credentials_body}
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/credentials",
                credential_bearing=True,
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=tuple(
                    value
                    for value in credentials_body.values()
                    if isinstance(value, str) and value
                ),
            ),
            decode_model(ChatConnection),
        )
