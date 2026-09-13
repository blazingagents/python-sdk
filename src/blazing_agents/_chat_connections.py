from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, overload
from urllib.parse import quote

from ._models import ChatConnection, ChatConnections
from ._transport import OMITTED, AsyncTransport, SyncTransport, _Omitted, _Request
from ._types import (
    SlackChatConfigurationInput,
    SlackChatCredentialsInput,
    TelegramChatConfigurationInput,
    TelegramChatCredentialsInput,
    Timeout,
)


def _wire(values: Mapping[str, object]) -> dict[str, object]:
    return {
        key.split("_")[0] + "".join(part.title() for part in key.split("_")[1:]): value
        for key, value in values.items()
    }


def _path(chat_connection_id: str) -> str:
    return f"/v1/chat-connections/{quote(chat_connection_id, safe='')}"


class ChatConnectionsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnections:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/chat-connections",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnections,
        )

    def get(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return self._transport.request(
            _Request(
                "GET",
                _path(chat_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    def check_health(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/health",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    def enable(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/enable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    def disable(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/disable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    def delete(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _path(chat_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    def update(
        self,
        chat_connection_id: str,
        *,
        name: str | _Omitted = OMITTED,
        webhook_url: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        body: dict[str, object] = {}
        if not isinstance(name, _Omitted):
            body["name"] = name
        if not isinstance(webhook_url, _Omitted):
            body["webhookUrl"] = webhook_url
        if not body:
            raise ValueError("Provide a name or webhook URL")
        return self._transport.request(
            _Request(
                "PATCH",
                _path(chat_connection_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    @overload
    def create(
        self,
        *,
        name: str,
        agent_id: str,
        platform: Literal["slack"],
        configuration: SlackChatConfigurationInput,
        credentials: SlackChatCredentialsInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    @overload
    def create(
        self,
        *,
        name: str,
        agent_id: str,
        platform: Literal["telegram"],
        configuration: TelegramChatConfigurationInput,
        credentials: TelegramChatCredentialsInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    def create(
        self,
        *,
        platform: Literal["slack", "telegram"],
        credentials: SlackChatCredentialsInput | TelegramChatCredentialsInput,
        name: str,
        agent_id: str,
        configuration: SlackChatConfigurationInput | TelegramChatConfigurationInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        credentials_body = _wire(credentials)
        required = (
            {"botToken", "signingSecret"}
            if platform == "slack"
            else {"botToken", "webhookSecret"}
        )
        if platform not in {"slack", "telegram"} or set(credentials_body) != required:
            raise ValueError("Credentials must match the selected platform")
        configuration_body = _wire(configuration)
        required_configuration = (
            {"teamId", "appId", "webhookUrl"}
            if platform == "slack"
            else {"botId", "webhookUrl"}
        )
        optional_configuration = {"channelIds"} if platform == "slack" else {"chatIds"}
        if (
            not required_configuration <= configuration_body.keys()
            or configuration_body.keys()
            - required_configuration
            - optional_configuration
        ):
            raise ValueError("Configuration must match the selected platform")
        body: dict[str, object] = {
            "name": name,
            "agentId": agent_id,
            "platform": platform,
            "configuration": configuration_body,
            "credentials": credentials_body,
        }
        if not isinstance(enabled, _Omitted):
            body["enabled"] = enabled
        return self._transport.request(
            _Request(
                "POST",
                "/v1/chat-connections",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=tuple(
                    value
                    for value in credentials_body.values()
                    if isinstance(value, str) and value
                ),
            ),
            ChatConnection,
        )

    @overload
    def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["slack"],
        credentials: SlackChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    @overload
    def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["telegram"],
        credentials: TelegramChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["slack", "telegram"],
        credentials: SlackChatCredentialsInput | TelegramChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        credentials_body = _wire(credentials)
        required = (
            {"botToken", "signingSecret"}
            if platform == "slack"
            else {"botToken", "webhookSecret"}
        )
        if platform not in {"slack", "telegram"} or set(credentials_body) != required:
            raise ValueError("Credentials must match the selected platform")
        body: dict[str, object] = {"platform": platform, **credentials_body}
        return self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/credentials",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=tuple(
                    value
                    for value in credentials_body.values()
                    if isinstance(value, str) and value
                ),
            ),
            ChatConnection,
        )


class AsyncChatConnectionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnections:
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/chat-connections",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnections,
        )

    async def get(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return await self._transport.request(
            _Request(
                "GET",
                _path(chat_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    async def check_health(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/health",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    async def enable(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/enable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    async def disable(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/disable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    async def delete(
        self,
        chat_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _path(chat_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    async def update(
        self,
        chat_connection_id: str,
        *,
        name: str | _Omitted = OMITTED,
        webhook_url: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        body: dict[str, object] = {}
        if not isinstance(name, _Omitted):
            body["name"] = name
        if not isinstance(webhook_url, _Omitted):
            body["webhookUrl"] = webhook_url
        if not body:
            raise ValueError("Provide a name or webhook URL")
        return await self._transport.request(
            _Request(
                "PATCH",
                _path(chat_connection_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatConnection,
        )

    @overload
    async def create(
        self,
        *,
        name: str,
        agent_id: str,
        platform: Literal["slack"],
        configuration: SlackChatConfigurationInput,
        credentials: SlackChatCredentialsInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    @overload
    async def create(
        self,
        *,
        name: str,
        agent_id: str,
        platform: Literal["telegram"],
        configuration: TelegramChatConfigurationInput,
        credentials: TelegramChatCredentialsInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    async def create(
        self,
        *,
        platform: Literal["slack", "telegram"],
        credentials: SlackChatCredentialsInput | TelegramChatCredentialsInput,
        name: str,
        agent_id: str,
        configuration: SlackChatConfigurationInput | TelegramChatConfigurationInput,
        enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        credentials_body = _wire(credentials)
        required = (
            {"botToken", "signingSecret"}
            if platform == "slack"
            else {"botToken", "webhookSecret"}
        )
        if platform not in {"slack", "telegram"} or set(credentials_body) != required:
            raise ValueError("Credentials must match the selected platform")
        configuration_body = _wire(configuration)
        required_configuration = (
            {"teamId", "appId", "webhookUrl"}
            if platform == "slack"
            else {"botId", "webhookUrl"}
        )
        optional_configuration = {"channelIds"} if platform == "slack" else {"chatIds"}
        if (
            not required_configuration <= configuration_body.keys()
            or configuration_body.keys()
            - required_configuration
            - optional_configuration
        ):
            raise ValueError("Configuration must match the selected platform")
        body: dict[str, object] = {
            "name": name,
            "agentId": agent_id,
            "platform": platform,
            "configuration": configuration_body,
            "credentials": credentials_body,
        }
        if not isinstance(enabled, _Omitted):
            body["enabled"] = enabled
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/chat-connections",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=tuple(
                    value
                    for value in credentials_body.values()
                    if isinstance(value, str) and value
                ),
            ),
            ChatConnection,
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
    ) -> ChatConnection: ...

    @overload
    async def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["telegram"],
        credentials: TelegramChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection: ...

    async def rotate_credentials(
        self,
        chat_connection_id: str,
        *,
        platform: Literal["slack", "telegram"],
        credentials: SlackChatCredentialsInput | TelegramChatCredentialsInput,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatConnection:
        credentials_body = _wire(credentials)
        required = (
            {"botToken", "signingSecret"}
            if platform == "slack"
            else {"botToken", "webhookSecret"}
        )
        if platform not in {"slack", "telegram"} or set(credentials_body) != required:
            raise ValueError("Credentials must match the selected platform")
        body: dict[str, object] = {"platform": platform, **credentials_body}
        return await self._transport.request(
            _Request(
                "POST",
                _path(chat_connection_id) + "/credentials",
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=tuple(
                    value
                    for value in credentials_body.values()
                    if isinstance(value, str) and value
                ),
            ),
            ChatConnection,
        )
