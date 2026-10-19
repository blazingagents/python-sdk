from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    Field,
    StringConstraints,
)

from ._models import AgentId, CredentialSafeResponseModel, ResponseModel, TenantId
from ._types import (
    ChatDeliveryStatus,
)


class ChatHealthCheck(CredentialSafeResponseModel):
    code: str
    status: Literal["pass", "fail", "unknown"]
    subject: str | None = None


class ChatHealth(CredentialSafeResponseModel):
    checked_at: str = Field(alias="checkedAt")
    token_valid: bool = Field(alias="tokenValid")
    identity_verified: bool = Field(alias="identityVerified")
    checks: list[ChatHealthCheck]


class ChatIdentity(CredentialSafeResponseModel):
    bot_id: str = Field(alias="botId")
    bot_user_id: str = Field(alias="botUserId")
    team_id: str | None = Field(alias="teamId")
    app_id: str | None = Field(alias="appId")


class SlackChatConfiguration(CredentialSafeResponseModel):
    platform: Literal["slack"]
    channel_ids: list[str] = Field(alias="channelIds")


class TelegramChatConfiguration(CredentialSafeResponseModel):
    platform: Literal["telegram"]
    business_mode: bool = Field(alias="businessMode")
    chat_ids: list[str] = Field(alias="chatIds")


ChatConfiguration: TypeAlias = Annotated[
    SlackChatConfiguration | TelegramChatConfiguration, Field(discriminator="platform")
]


class ChatConnection(CredentialSafeResponseModel):
    id: Annotated[str, StringConstraints(pattern=r"^cc_[0-9A-Za-z]{16}$")]
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    name: str
    platform: Literal["slack", "telegram"]
    enabled: bool
    configuration: ChatConfiguration
    webhook_url: str = Field(alias="webhookUrl")
    identity: ChatIdentity
    health: ChatHealth
    credential_fragment: str = Field(alias="credentialFragment", max_length=4)
    credential_version: int = Field(alias="credentialVersion", ge=0)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ChatConnections(CredentialSafeResponseModel):
    chat_connections: list[ChatConnection] = Field(alias="chatConnections")


class ChatDelivery(ResponseModel):
    id: Annotated[str, StringConstraints(pattern=r"^cd_[0-9A-Za-z]{16}$")]
    kind: Literal["reply", "card"]
    status: ChatDeliveryStatus
    attempt: int = Field(ge=0)
    credential_version: int = Field(alias="credentialVersion", ge=0)
    representation: str
    diagnostic: str | None
    receipts: object | None = None
    session_id: str = Field(alias="sessionId")
    message_id: str | None = Field(alias="messageId")
    approval_id: str | None = Field(alias="approvalId")
    thread_id: str = Field(alias="threadId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class TenantChatDelivery(ChatDelivery):
    connection_id: Annotated[
        str, StringConstraints(pattern=r"^cc_[0-9A-Za-z]{16}$")
    ] = Field(alias="connectionId")
    agent_id: AgentId = Field(alias="agentId")
    platform: Literal["slack", "telegram"]


class ChatDeliveriesPage(ResponseModel):
    data: list[TenantChatDelivery]
    next_cursor: str | None = Field(alias="nextCursor")


class ChatConnectionDeliveriesPage(ResponseModel):
    data: list[ChatDelivery]
    next_cursor: str | None = Field(alias="nextCursor")


class ChatDeliveryResult(ResponseModel):
    id: Annotated[str, StringConstraints(pattern=r"^cd_[0-9A-Za-z]{16}$")]
    session_id: str = Field(alias="sessionId")
    thread_id: str = Field(alias="threadId")
    connection_id: Annotated[
        str, StringConstraints(pattern=r"^cc_[0-9A-Za-z]{16}$")
    ] = Field(alias="connectionId")
    kind: Literal["reply", "card"]
    status: Literal["confirmed", "failed", "ambiguous"]
    attempt: int = Field(ge=0)
