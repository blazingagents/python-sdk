from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Annotated, Literal, TypeAlias

import httpx
from pydantic import (
    AfterValidator,
    AnyUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)

from ._types import (
    AgentTool,
    ApprovalDecision,
    BuiltinToolName,
    SpendingLimitResetInterval,
    WorkspaceTier,
)

SkillId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^skill_[0-9A-Za-z]{16}$"),
]
AgentId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^ag_[0-9A-Za-z]{16}$"),
]
TenantId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^ten_[0-9A-Za-z]{16}$"),
]
ProviderId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^prv_[0-9A-Za-z]{16}$"),
]
WorkspaceId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^ws_[0-9A-Za-z]{16}$"),
]
McpConnectionId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^mcp_[0-9A-Za-z]{16}$"),
]
MemoryId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^mem_[0-9A-Za-z]{16}$"),
]
PromptId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^prompt_[0-9A-Za-z]{16}$"),
]
ArtifactId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^at_[0-9A-Za-z]{16}$"),
]
SessionId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^ss_[0-9A-Za-z]{16}$"),
]
TaskId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^tk_[0-9A-Za-z]{16}$"),
]
TaskRunId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^tr_[0-9A-Za-z]{16}$"),
]
TurnId: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^turn_[0-9A-Za-z]{16}$"),
]
AgentName: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
WorkspaceName: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
AgentModelId: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[^/]+/.+$",
    ),
]
AgentInstructions: TypeAlias = Annotated[
    str,
    StringConstraints(max_length=3_000),
]
NonEmptyString: TypeAlias = Annotated[str, StringConstraints(min_length=1)]
MetadataKey: TypeAlias = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
]


def _unique_strings(values: list[str]) -> list[str]:
    """Reject duplicate strings."""
    if len(values) != len(set(values)):
        msg = "values must be unique"
        raise ValueError(msg)
    return values


def _memory_text(value: str) -> str:
    """Reject blank or oversized Memory text."""
    if len(value.encode()) > 10_240:
        msg = "Memory text must be at most 10240 bytes"
        raise ValueError(msg)
    return value


def _skill_name(value: str) -> str:
    """Validate a Skill name."""
    if value in {"anthropic", "claude"}:
        msg = "Skill name is reserved"
        raise ValueError(msg)
    return value


def _skill_file_path(value: str) -> str:
    """Reject invalid or unsafe paths within a Skill."""
    segments = value.split("/")
    if (
        value.startswith("/")
        or "\0" in value
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        msg = "Skill file path must be a safe relative path"
        raise ValueError(msg)
    return value


def _artifact_filename(value: str) -> str:
    """Validate an Artifact filename."""
    if not value.strip() or value in {".", ".."} or "/" in value or "\\" in value:
        msg = "Artifact filename must be a non-blank flat filename"
        raise ValueError(msg)
    return value


MemoryText: TypeAlias = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_memory_text),
]
SkillName: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
    AfterValidator(_skill_name),
]
SkillDescription: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_024),
]
SkillFilePath: TypeAlias = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_skill_file_path),
]
ArtifactFilename: TypeAlias = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_artifact_filename),
]
MediaType: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


AgentTools: TypeAlias = Annotated[
    list[AgentTool],
    AfterValidator(_unique_strings),
]
McpConnectionIds: TypeAlias = Annotated[
    list[McpConnectionId],
    Field(max_length=10),
    AfterValidator(_unique_strings),
]


ForwardedMetadataKeys: TypeAlias = Annotated[
    list[MetadataKey],
    Field(max_length=32),
    AfterValidator(_unique_strings),
]


class _ReadOnlyHeaders(Mapping[str, str]):
    """Case-insensitive, read-only view of response headers."""

    def __init__(self, headers: httpx.Headers) -> None:
        self._headers = httpx.Headers(headers)

    def __getitem__(self, name: str) -> str:
        return self._headers[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._headers)

    def __len__(self) -> int:
        return len(self._headers.keys())

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._headers)!r})"


@dataclass(frozen=True)
class ResponseMeta:
    """HTTP metadata of the response a client method decoded into a model.

    Attributes:
        status: HTTP status code.
        request_id: Server request ID from X-Request-Id, if present.
        headers: Read-only, case-insensitive response headers. Header values
            that contain a credential the call sent are redacted.
    """

    status: int
    request_id: str | None
    headers: Mapping[str, str] = field(hash=False)

    @classmethod
    def _from_response(
        cls,
        response: httpx.Response,
        headers: httpx.Headers,
    ) -> ResponseMeta:
        return cls(
            status=response.status_code,
            request_id=headers.get("x-request-id"),
            headers=_ReadOnlyHeaders(headers),
        )


def response_meta(model: BaseModel) -> ResponseMeta:
    """Return the HTTP metadata of the response a client method returned.

    Args:
        model: A response model returned by a client method, such as an
            Agent, a page, or a Skill copy result.

    Returns:
        The response's status, server request ID, and headers.

    Raises:
        ValueError: The model was not returned by a client method. Models you
            construct and events read from a stream carry no response; use the
            stream's own ``request_id`` instead.
    """
    meta: ResponseMeta | None = getattr(model, "_response_meta", None)
    if meta is None:
        msg = (
            f"{type(model).__name__} was not returned by a Blazing Agents "
            "client method, so it has no response metadata."
        )
        raise ValueError(msg)
    return meta


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    _response_meta: ResponseMeta | None = PrivateAttr(default=None)

    def _attach_response_meta(self, meta: ResponseMeta) -> None:
        """Record the response this model was decoded from."""
        self._response_meta = meta


class Quota(ResponseModel):
    monthly_token_limit: int | None = Field(alias="monthlyTokenLimit")
    monthly_request_limit: int | None = Field(alias="monthlyRequestLimit")
    reset_day: int = Field(alias="resetDay")


class SpendingLimit(ResponseModel):
    amount_usd: float = Field(
        alias="amountUsd", gt=0, le=1_000_000_000, multiple_of=0.000001
    )
    reset_start_date: date = Field(alias="resetStartDate")
    reset_interval: SpendingLimitResetInterval = Field(alias="resetInterval")


class SpendingLimitPeriod(ResponseModel):
    starts_at: AwareDatetime = Field(alias="startsAt")
    ends_at: AwareDatetime = Field(alias="endsAt")
    spent_usd: float = Field(alias="spentUsd", ge=0)
    reserved_usd: float = Field(alias="reservedUsd", ge=0)
    available_usd: float = Field(alias="availableUsd", ge=0)


class SpendingLimitResponse(ResponseModel):
    spending_limit: SpendingLimit | None = Field(alias="spendingLimit")
    period: SpendingLimitPeriod | None
    next_reset_at: AwareDatetime | None = Field(alias="nextResetAt")


class SpendingLimitStopDetails(ResponseModel):
    scope: Literal["agent", "tenant", "both"]
    reason: Literal["exhausted", "reserved", "unpriced", "unknown_usage"]
    spent_usd: float = Field(alias="spentUsd", ge=0)
    reserved_usd: float = Field(alias="reservedUsd", ge=0)
    available_usd: float = Field(alias="availableUsd", ge=0)
    next_reset_at: AwareDatetime | None = Field(alias="nextResetAt")


class _TransientEvent(ResponseModel):
    """Base for stream events whose `transient` field must be the boolean true."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("transient", mode="before", check_fields=False)
    @classmethod
    def _validate_transient(cls, value: object) -> Literal[True]:
        if value is not True:
            msg = "transient must be the boolean true"
            raise ValueError(msg)
        return value


class TurnStreamError(ResponseModel):
    """The `error` of the HTTP error body the same failure would have returned.

    `code` is an API error code or `turn_interrupted`, which only a stream
    sends. It stays open to codes added later, as an HTTP error code does.
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, object] | None = Field(default=None, min_length=1)


class TurnStreamErrorEvent(_TransientEvent):
    """Transient event that precedes the `error` chunk of a failed Turn stream.

    A spending stop carries its numbers in `details`; parse them with
    `SpendingLimitStopDetails.model_validate(details, strict=False)`, which
    reads the ISO reset time from the decoded JSON. After `turn_interrupted`
    the Turn may have saved its work before the cut, so read the Session's
    messages.
    """

    type: Literal["data-ba-error"]
    data: TurnStreamError
    transient: Literal[True]


class TenantDeletion(ResponseModel):
    requested_at: AwareDatetime = Field(alias="requestedAt")
    deletes_at: AwareDatetime = Field(alias="deletesAt")


class TenantSettings(ResponseModel):
    name: str
    quota: Quota | None
    deletion: TenantDeletion | None
    monetization_enabled: bool = Field(alias="monetizationEnabled")


class UsageBucket(ResponseModel):
    day: str | None
    agent_id: str | None = Field(alias="agentId")
    session_id: str | None = Field(alias="sessionId")
    user_id: str | None = Field(alias="userId")
    provider: str | None
    model: str | None
    input_tokens: int = Field(alias="inputTokens", ge=0)
    output_tokens: int = Field(alias="outputTokens", ge=0)
    request_count: int = Field(alias="requestCount", ge=0)
    duration_ms: int = Field(alias="durationMs", ge=0)


class UsageTotals(ResponseModel):
    input_tokens: int = Field(alias="inputTokens", ge=0)
    output_tokens: int = Field(alias="outputTokens", ge=0)
    request_count: int = Field(alias="requestCount", ge=0)
    duration_ms: int = Field(alias="durationMs", ge=0)


class Usage(ResponseModel):
    buckets: list[UsageBucket]
    totals: UsageTotals


class SessionUsage(ResponseModel):
    session_id: SessionId = Field(alias="sessionId")
    totals: UsageTotals


class SessionUsageList(ResponseModel):
    data: list[SessionUsage]


class UsageOverview(ResponseModel):
    totals: UsageTotals
    daily: list[UsageBucket]
    by_agent: list[UsageBucket] = Field(alias="byAgent")
    by_user: list[UsageBucket] = Field(alias="byUser")
    by_model: list[UsageBucket] = Field(alias="byModel")
    active_agent_count: int = Field(alias="activeAgentCount", ge=0)


class Provider(ResponseModel):
    id: ProviderId
    name: NonEmptyString
    provider_type: str = Field(alias="providerType")
    base_url: str | None = Field(alias="baseUrl")
    key_fragment: str = Field(alias="keyFragment", min_length=1, max_length=4)
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class ProviderListItem(ResponseModel):
    id: ProviderId
    name: NonEmptyString
    provider_type: str = Field(alias="providerType")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class Providers(ResponseModel):
    providers: list[ProviderListItem]


class ProviderModel(ResponseModel):
    id: NonEmptyString


class ThinkingLevels(ResponseModel):
    known: bool
    levels: list[NonEmptyString]


class ProviderModels(ResponseModel):
    models: list[ProviderModel]


class McpConnection(ResponseModel):
    id: McpConnectionId
    name: NonEmptyString
    url: AnyUrl
    auth_type: str = Field(alias="authType")
    status: str
    credential_fragment: str | None = Field(
        alias="credentialFragment",
        max_length=4,
    )
    last_auth_error_code: str | None = Field(alias="lastAuthErrorCode")
    oauth_issuer: AnyUrl | None = Field(alias="oauthIssuer")
    oauth_resource: AnyUrl | None = Field(alias="oauthResource")
    token_expires_at: AwareDatetime | None = Field(alias="tokenExpiresAt")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class McpConnections(ResponseModel):
    mcp_connections: list[McpConnection] = Field(alias="mcpConnections")


class McpConnectionTestError(ResponseModel):
    code: str
    message: NonEmptyString


class McpServer(ResponseModel):
    name: NonEmptyString
    version: NonEmptyString


class McpConnectionTestResult(ResponseModel):
    ok: bool
    latency_ms: int | None = Field(default=None, alias="latencyMs", ge=0)
    server: McpServer | None = None
    tool_count: int | None = Field(default=None, alias="toolCount", ge=0)
    tool_names: list[NonEmptyString] | None = Field(default=None, alias="toolNames")
    error: McpConnectionTestError | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> McpConnectionTestResult:
        """Require consistent success or failure fields in the MCP test result."""
        successful = (
            self.latency_ms is not None
            and self.server is not None
            and self.tool_count is not None
            and self.tool_names is not None
            and self.tool_count == len(self.tool_names)
            and self.error is None
        )
        failed = (
            self.error is not None
            and self.latency_ms is None
            and self.server is None
            and self.tool_count is None
            and self.tool_names is None
        )
        if (self.ok and not successful) or (not self.ok and not failed):
            msg = "MCP Connection test result does not match ok"
            raise ValueError(msg)
        return self


class McpConnectionReconnectResult(ResponseModel):
    status: str
    connection: McpConnection


class BuiltinToolReference(ResponseModel):
    type: Literal["builtin"]
    name: BuiltinToolName


class McpToolReference(ResponseModel):
    type: Literal["mcp"]
    connection_id: McpConnectionId = Field(alias="connectionId")
    name: NonEmptyString


ToolReference: TypeAlias = Annotated[
    BuiltinToolReference | McpToolReference, Field(discriminator="type")
]
"""A tool an approval policy may configure: built-in or MCP only."""


class FunctionToolReference(ResponseModel):
    type: Literal["function"]
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


ToolExecutionReference: TypeAlias = Annotated[
    BuiltinToolReference | McpToolReference | FunctionToolReference,
    Field(discriminator="type"),
]
"""The tool behind one execution or approval record.

Backend functions appear here for display and audit only; approval policies
use ``ToolReference``, so function names never become Agent configuration.
"""


class ApprovalOverride(ResponseModel):
    tool: ToolReference
    decision: ApprovalDecision


class ApprovalPolicy(ResponseModel):
    default: ApprovalDecision
    overrides: list[ApprovalOverride] = Field(default_factory=list[ApprovalOverride])


class Agent(ResponseModel):
    id: AgentId
    tenant_id: TenantId = Field(alias="tenantId")
    name: AgentName
    model: AgentModelId | None
    thinking_level: NonEmptyString | None = Field(alias="thinkingLevel")
    provider_id: ProviderId | None = Field(alias="providerId")
    workspace_id: WorkspaceId = Field(alias="workspaceId")
    auto_compaction: bool = Field(alias="autoCompaction")
    compaction_reserve_tokens: int = Field(
        alias="compactionReserveTokens", ge=0, le=9007199254740991
    )
    memory_injection_enabled: bool = Field(alias="memoryInjectionEnabled")
    tools: AgentTools
    approval_in_chat: ApprovalPolicy = Field(
        default_factory=lambda: ApprovalPolicy(default="full"), alias="approvalInChat"
    )
    approval_in_tasks: ApprovalPolicy = Field(
        default_factory=lambda: ApprovalPolicy(default="full"), alias="approvalInTasks"
    )
    instructions: AgentInstructions
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    mcp_connection_ids: McpConnectionIds = Field(alias="mcpConnectionIds")
    avatar_url: AnyUrl | None = Field(alias="avatarUrl")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")
    status: NonEmptyString

    @model_validator(mode="after")
    def _validate_provider_model(self) -> Agent:
        """Require a consistent provider and model configuration."""
        if (self.provider_id is None) != (self.model is None):
            msg = "providerId and model must both be present or both be null"
            raise ValueError(msg)
        return self


class AgentsPage(ResponseModel):
    data: list[Agent]
    next_cursor: str | None = Field(alias="nextCursor")


class AgentConfig(ResponseModel):
    name: AgentName
    model: AgentModelId | None
    thinking_level: NonEmptyString | None = Field(alias="thinkingLevel")
    provider_id: ProviderId | None = Field(alias="providerId")
    auto_compaction: bool = Field(alias="autoCompaction")
    compaction_reserve_tokens: int = Field(
        alias="compactionReserveTokens", ge=0, le=9007199254740991
    )
    memory_injection_enabled: bool = Field(alias="memoryInjectionEnabled")
    tools: AgentTools
    approval_in_chat: ApprovalPolicy = Field(
        default_factory=lambda: ApprovalPolicy(default="full"), alias="approvalInChat"
    )
    approval_in_tasks: ApprovalPolicy = Field(
        default_factory=lambda: ApprovalPolicy(default="full"), alias="approvalInTasks"
    )
    instructions: AgentInstructions
    metadata: dict[str, object]
    mcp_connection_ids: McpConnectionIds = Field(alias="mcpConnectionIds")

    @model_validator(mode="after")
    def _validate_provider_model(self) -> AgentConfig:
        """Require a consistent provider and model configuration."""
        if (self.provider_id is None) != (self.model is None):
            msg = "providerId and model must both be present or both be null"
            raise ValueError(msg)
        return self


class McpAttachment(ResponseModel):
    mcp_connection_id: McpConnectionId = Field(alias="mcpConnectionId")
    forward_user_id: bool = Field(alias="forwardUserId")
    forwarded_metadata_keys: ForwardedMetadataKeys = Field(
        alias="forwardedMetadataKeys"
    )
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class McpAttachments(ResponseModel):
    mcp_attachments: list[McpAttachment] = Field(alias="mcpAttachments")


class WorkspaceUnrestrictedNetworkPolicy(ResponseModel):
    mode: Literal["unrestricted"]


class WorkspaceAllowlistNetworkPolicy(ResponseModel):
    mode: Literal["allowlist"]
    allowed_hosts: list[NonEmptyString] = Field(alias="allowedHosts")


class WorkspaceOfflineNetworkPolicy(ResponseModel):
    mode: Literal["offline"]


WorkspaceNetworkPolicy: TypeAlias = Annotated[
    WorkspaceUnrestrictedNetworkPolicy
    | WorkspaceAllowlistNetworkPolicy
    | WorkspaceOfflineNetworkPolicy,
    Field(discriminator="mode"),
]


class Workspace(ResponseModel):
    tier: WorkspaceTier
    id: WorkspaceId
    tenant_id: TenantId = Field(alias="tenantId")
    name: WorkspaceName | None
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    network_policy: WorkspaceNetworkPolicy = Field(alias="networkPolicy")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class WorkspacesPage(ResponseModel):
    data: list[Workspace]
    next_cursor: str | None = Field(alias="nextCursor")


class Prompt(ResponseModel):
    agent_id: AgentId | None = Field(alias="agentId")
    id: PromptId
    tenant_id: TenantId = Field(alias="tenantId")
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    ]
    template: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=10_240),
    ]
    variables: list[NonEmptyString]
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")

    @model_validator(mode="after")
    def _validate_variables(self) -> Prompt:
        """Check template variable names, count, and first-occurrence order."""
        inferred = list(
            dict.fromkeys(
                value.strip() for value in re.findall(r"{{([\s\S]*?)}}", self.template)
            )
        )
        if (
            not all(
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) for value in inferred
            )
            or len(inferred) > 10
            or self.variables != inferred
        ):
            msg = "Prompt variables do not match the inferred-variable contract"
            raise ValueError(msg)
        return self


class PromptsPage(ResponseModel):
    data: list[Prompt]
    next_cursor: str | None = Field(alias="nextCursor")


class Memory(ResponseModel):
    id: MemoryId
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    user_id: str = Field(alias="userId")
    text: MemoryText
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")
    last_accessed_at: AwareDatetime = Field(alias="lastAccessedAt")


class MemoryResponse(ResponseModel):
    memory: Memory


class MemoriesPage(ResponseModel):
    data: list[Memory]
    next_cursor: str | None = Field(alias="nextCursor")


class Skill(ResponseModel):
    id: SkillId
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    name: SkillName
    description: SkillDescription
    metadata: dict[str, str] | None = None
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")

    @field_validator("metadata", mode="before")
    @classmethod
    def _reject_null_metadata(cls, value: object) -> object:
        """Reject explicit null metadata."""
        if value is None:
            msg = "Skill metadata may be omitted but cannot be null"
            raise ValueError(msg)
        return value


class SkillFile(ResponseModel):
    path: SkillFilePath
    size_bytes: int = Field(alias="sizeBytes", ge=0)


class SkillDetail(Skill):
    files: list[SkillFile]


class SkillsPage(ResponseModel):
    data: list[Skill]
    next_cursor: str | None = Field(alias="nextCursor")


class SkillCopyError(ResponseModel):
    code: NonEmptyString
    message: NonEmptyString
    details: object | None = None


class SkillCopyCreated(ResponseModel):
    agent_id: AgentId = Field(alias="agentId")
    status: Literal["created"]
    skill: SkillDetail


class SkillCopyFailed(ResponseModel):
    agent_id: AgentId = Field(alias="agentId")
    status: Literal["failed"]
    error: SkillCopyError


SkillCopyResult: TypeAlias = SkillCopyCreated | SkillCopyFailed


class SkillCopyResults(RootModel[list[SkillCopyResult]]):
    def _attach_response_meta(self, meta: ResponseMeta) -> None:
        """Record the response on each copy result, which callers receive."""
        for result in self.root:
            result._attach_response_meta(meta)
