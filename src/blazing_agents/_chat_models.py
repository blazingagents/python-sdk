from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import (
    Field,
    StringConstraints,
)

from ._models import AgentId, ResponseModel, TenantId


class ChatHealthCheck(ResponseModel):
    code: str
    status: Literal["pass", "fail", "unknown"]
    subject: str | None = None


class ChatHealth(ResponseModel):
    checked_at: str = Field(alias="checkedAt")
    token_valid: bool = Field(alias="tokenValid")
    identity_verified: bool = Field(alias="identityVerified")
    checks: list[ChatHealthCheck]


class ChatIdentity(ResponseModel):
    bot_id: str = Field(alias="botId")
    bot_user_id: str = Field(alias="botUserId")
    team_id: str | None = Field(alias="teamId")
    app_id: str | None = Field(alias="appId")


class SlackChatConfiguration(ResponseModel):
    platform: Literal["slack"]
    channel_ids: list[str] = Field(alias="channelIds")


class TelegramChatConfiguration(ResponseModel):
    platform: Literal["telegram"]
    business_mode: bool = Field(alias="businessMode")
    chat_ids: list[str] = Field(alias="chatIds")


ChatConfiguration: TypeAlias = Annotated[
    SlackChatConfiguration | TelegramChatConfiguration, Field(discriminator="platform")
]


class ChatConnection(ResponseModel):
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


class ChatConnections(ResponseModel):
    chat_connections: list[ChatConnection] = Field(alias="chatConnections")
