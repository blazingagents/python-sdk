from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AwareDatetime,
    Field,
    StringConstraints,
)

from ._models import AgentId, ResponseModel, SessionId, TurnId
from ._types import (
    MerchantEnvironment,
    MerchantProvider,
    MerchantUsageEventStatus,
    ProviderType,
)

MerchantConnectionId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^mch_[0-9A-Za-z]{16}$"),
]
MerchantUsageEventId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^mev_[0-9A-Za-z]{16}$"),
]


class MerchantGuard(ResponseModel):
    enabled: bool
    product_ids: list[str] = Field(alias="productIds")
    meter_id: str | None = Field(alias="meterId")


class MerchantConnection(ResponseModel):
    id: MerchantConnectionId
    provider: MerchantProvider
    environment: MerchantEnvironment
    merchant_account_id: str = Field(alias="merchantAccountId", min_length=1)
    key_fragment: str = Field(alias="keyFragment", min_length=1, max_length=4)
    guard: MerchantGuard
    config_version: int = Field(alias="configVersion", ge=1)
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class MerchantConnectionResponse(ResponseModel):
    connection: MerchantConnection | None


class MerchantCustomerBinding(ResponseModel):
    user_id: str = Field(alias="userId", min_length=1)
    customer_id: str = Field(alias="customerId", min_length=1)
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class MerchantBindingResponse(ResponseModel):
    binding: MerchantCustomerBinding


class MerchantBindingsPage(ResponseModel):
    bindings: list[MerchantCustomerBinding]
    next_cursor: str | None = Field(alias="nextCursor")


class MerchantUsageEvent(ResponseModel):
    id: MerchantUsageEventId
    turn_id: TurnId = Field(alias="turnId")
    connection_id: MerchantConnectionId = Field(alias="connectionId")
    provider: MerchantProvider
    user_id: str = Field(alias="userId")
    customer_id: str | None = Field(alias="customerId")
    agent_id: AgentId = Field(alias="agentId")
    session_id: SessionId | None = Field(alias="sessionId")
    model: str = Field(min_length=1)
    model_provider: ProviderType = Field(alias="modelProvider")
    input_tokens: int = Field(alias="inputTokens", ge=0)
    output_tokens: int = Field(alias="outputTokens", ge=0)
    total_tokens: int = Field(alias="totalTokens", ge=0)
    turn_status: Literal["succeeded", "cancelled", "failed"] = Field(alias="turnStatus")
    started_at: AwareDatetime = Field(alias="startedAt")
    occurred_at: AwareDatetime = Field(alias="occurredAt")
    status: MerchantUsageEventStatus
    payload: dict[str, object] | None
    attempt_count: int = Field(alias="attemptCount", ge=0)
    attempt_generation: int = Field(alias="attemptGeneration", ge=0)
    last_attempt_at: AwareDatetime | None = Field(alias="lastAttemptAt")
    last_error_code: str | None = Field(alias="lastErrorCode")
    accepted_at: AwareDatetime | None = Field(alias="acceptedAt")
    workflow_issue: Literal["error", "cancelled", "recovery_exhausted"] | None = Field(
        alias="workflowIssue"
    )
    next_action: Literal["none", "wait", "retry", "investigate", "discard"] = Field(
        alias="nextAction"
    )


class MerchantUsageEventResponse(ResponseModel):
    event: MerchantUsageEvent


class MerchantUsageEventsPage(ResponseModel):
    events: list[MerchantUsageEvent]
    next_cursor: str | None = Field(alias="nextCursor")


class MerchantUsageSummaryCounts(ResponseModel):
    pending: int = Field(ge=0)
    accepted: int = Field(ge=0)
    failed: int = Field(ge=0)
    incomplete: int = Field(ge=0)
    expired: int = Field(ge=0)
    discarded: int = Field(ge=0)


class MerchantUsageSummaryDay(ResponseModel):
    day: date
    accepted_events: int = Field(alias="acceptedEvents", ge=0)
    accepted_tokens: int = Field(alias="acceptedTokens", ge=0)
    pending_events: int = Field(alias="pendingEvents", ge=0)


class MerchantUsageSummary(ResponseModel):
    counts: MerchantUsageSummaryCounts
    last_accepted_at: AwareDatetime | None = Field(alias="lastAcceptedAt")
    oldest_pending_occurred_at: AwareDatetime | None = Field(
        alias="oldestPendingOccurredAt"
    )
    daily: list[MerchantUsageSummaryDay]


class MerchantUsageSummaryResponse(ResponseModel):
    summary: MerchantUsageSummary
