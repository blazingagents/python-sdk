from __future__ import annotations

import re
from calendar import monthrange
from typing import Annotated, ClassVar, Literal, TypeAlias, cast
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    if len(values) != len(set(values)):
        msg = "values must be unique"
        raise ValueError(msg)
    return values


def _memory_text(value: str) -> str:
    if len(value.encode()) > 10_240:
        msg = "Memory text must be at most 10240 bytes"
        raise ValueError(msg)
    return value


def _skill_name(value: str) -> str:
    if value in {"anthropic", "claude"}:
        msg = "Skill name is reserved"
        raise ValueError(msg)
    return value


def _skill_file_path(value: str) -> str:
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
    list[NonEmptyString],
    AfterValidator(_unique_strings),
]
McpConnectionIds: TypeAlias = Annotated[
    list[McpConnectionId],
    Field(max_length=10),
    AfterValidator(_unique_strings),
]

_NUMERIC_CRON = re.compile(r"^[0-9*,/\-\s]+$")
_IANA_TIMEZONE = re.compile(
    r"^(?:UTC|[A-Za-z_]+/[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)?)$"
)
_CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
_CRON_STEP_MAXIMA = (60, 24, 31, 12, 7)


def _cron_values(
    value: str,
    minimum: int,
    maximum: int,
    step_maximum: int,
) -> set[int] | None:
    values: set[int] = set()
    for item in value.split(","):
        base, separator, step = item.partition("/")
        if separator and (not step.isdigit() or int(step) < 1):
            return None
        stride = int(step) if separator else 1
        endpoints = base.split("-")
        if base == "*":
            lower, upper = minimum, maximum
        elif len(endpoints) > 2 or not all(part.isdigit() for part in endpoints):
            return None
        else:
            numbers = [int(part) for part in endpoints]
            if any(number < minimum or number > maximum for number in numbers):
                return None
            if len(numbers) == 2 and numbers[0] > numbers[1]:
                return None
            if separator and len(numbers) == 1:
                return None
            lower = upper = numbers[0]
            if len(numbers) == 2:
                upper = numbers[1]
        if separator and stride > step_maximum:
            return None
        values.update(range(lower, upper + 1, stride))
    return values


def _validate_cron(expression: str) -> None:
    fields = expression.split()
    invalid = (
        not expression.strip()
        or len(expression) > 120
        or _NUMERIC_CRON.fullmatch(expression) is None
        or len(fields) != 5
    )
    parsed_fields = (
        []
        if invalid
        else [
            _cron_values(field, *bounds, step_maximum)
            for field, bounds, step_maximum in zip(
                fields, _CRON_RANGES, _CRON_STEP_MAXIMA, strict=True
            )
        ]
    )
    if not invalid and all(values is not None for values in parsed_fields):
        days = cast(set[int], parsed_fields[2])
        months = cast(set[int], parsed_fields[3])
        invalid = fields[4] == "*" and not any(
            day <= monthrange(2024, month)[1] for month in months for day in days
        )
    else:
        invalid = True
    if invalid:
        msg = "cron schedule expression must be a valid five-field numeric cron"
        raise ValueError(msg)


def _validate_timezone(timezone: str) -> str:
    timezone = timezone.strip()
    if len(timezone) > 64 or _IANA_TIMEZONE.fullmatch(timezone) is None:
        msg = "cron schedule timezone must be a canonical IANA timezone"
        raise ValueError(msg)
    try:
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError) as error:
        msg = "cron schedule timezone is unknown"
        raise ValueError(msg) from error
    return timezone


_MCP_OAUTH_SETUP_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
ForwardedMetadataKeys: TypeAlias = Annotated[
    list[MetadataKey],
    Field(max_length=32),
    AfterValidator(_unique_strings),
]


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    _request_id: str | None = PrivateAttr(default=None)


class CredentialSafeResponseModel(ResponseModel):
    _credential_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "apiKey",
            "api_key",
            "bearerToken",
            "bearer_token",
            "clientSecret",
            "client_secret",
        }
    )


class Quota(ResponseModel):
    monthly_token_limit: int | None = Field(alias="monthlyTokenLimit")
    monthly_request_limit: int | None = Field(alias="monthlyRequestLimit")
    reset_day: int = Field(alias="resetDay")


class TenantSettings(ResponseModel):
    name: str
    quota: Quota | None


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


class Provider(CredentialSafeResponseModel):
    id: ProviderId
    name: NonEmptyString
    provider_type: str = Field(alias="providerType")
    base_url: str | None = Field(alias="baseUrl")
    key_fragment: str = Field(alias="keyFragment", min_length=1, max_length=4)
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class Providers(CredentialSafeResponseModel):
    providers: list[Provider]


class ProviderModel(CredentialSafeResponseModel):
    id: NonEmptyString


class ProviderModels(CredentialSafeResponseModel):
    models: list[ProviderModel]


class McpConnection(CredentialSafeResponseModel):
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


class McpConnections(CredentialSafeResponseModel):
    mcp_connections: list[McpConnection] = Field(alias="mcpConnections")


class McpConnectionAuthorization(CredentialSafeResponseModel):
    authorization_url: AnyUrl = Field(alias="authorizationUrl")

    @field_validator("authorization_url")
    @classmethod
    def _validate_authorization_url(cls, value: AnyUrl) -> AnyUrl:
        parsed = urlsplit(str(value))
        query = parse_qsl(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/app/mcp-connections"
            or parsed.fragment
            or len(query) != 1
            or query[0][0] != "mcpOAuthSetup"
            or _MCP_OAUTH_SETUP_TOKEN.fullmatch(query[0][1]) is None
        ):
            msg = "authorizationUrl must be the Blazing MCP OAuth setup URL"
            raise ValueError(msg)
        return value


class McpConnectionTestError(CredentialSafeResponseModel):
    code: str
    message: NonEmptyString


class McpServer(CredentialSafeResponseModel):
    name: NonEmptyString
    version: NonEmptyString


class McpConnectionTestResult(CredentialSafeResponseModel):
    ok: bool
    latency_ms: int | None = Field(default=None, alias="latencyMs", ge=0)
    server: McpServer | None = None
    tool_count: int | None = Field(default=None, alias="toolCount", ge=0)
    tool_names: list[NonEmptyString] | None = Field(default=None, alias="toolNames")
    error: McpConnectionTestError | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> McpConnectionTestResult:
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


class McpConnectionReconnectResult(CredentialSafeResponseModel):
    status: str
    connection: McpConnection


class Agent(ResponseModel):
    id: AgentId
    tenant_id: TenantId = Field(alias="tenantId")
    name: AgentName
    model: AgentModelId | None
    provider_id: ProviderId | None = Field(alias="providerId")
    workspace_id: WorkspaceId = Field(alias="workspaceId")
    memory_injection_enabled: bool = Field(alias="memoryInjectionEnabled")
    tools: AgentTools
    instructions: AgentInstructions
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    mcp_connection_ids: McpConnectionIds = Field(alias="mcpConnectionIds")
    avatar_url: AnyUrl | None = Field(alias="avatarUrl")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")
    version: int = Field(ge=1, le=2_147_483_647)
    status: NonEmptyString

    @model_validator(mode="after")
    def _validate_provider_model(self) -> Agent:
        if (self.provider_id is None) != (self.model is None):
            msg = "providerId and model must both be present or both be null"
            raise ValueError(msg)
        return self


class Agents(ResponseModel):
    agents: list[Agent]


class AgentVersion(ResponseModel):
    agent_id: AgentId = Field(alias="agentId")
    tenant_id: TenantId = Field(alias="tenantId")
    version: int = Field(ge=1, le=2_147_483_647)
    name: AgentName
    model: AgentModelId | None
    provider_id: ProviderId | None = Field(alias="providerId")
    memory_injection_enabled: bool = Field(alias="memoryInjectionEnabled")
    tools: AgentTools
    instructions: AgentInstructions
    metadata: dict[str, object]
    mcp_connection_ids: McpConnectionIds = Field(alias="mcpConnectionIds")
    created_at: AwareDatetime = Field(alias="createdAt")

    @model_validator(mode="after")
    def _validate_provider_model(self) -> AgentVersion:
        if (self.provider_id is None) != (self.model is None):
            msg = "providerId and model must both be present or both be null"
            raise ValueError(msg)
        return self


class AgentVersionsPage(ResponseModel):
    data: list[AgentVersion]
    next_cursor: str | None = Field(alias="nextCursor")


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


class Prompts(ResponseModel):
    prompts: list[Prompt]


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
    _request_id: str | None = PrivateAttr(default=None)


class Artifact(ResponseModel):
    artifact_id: ArtifactId = Field(alias="artifactId")
    agent_id: AgentId = Field(alias="agentId")
    tenant_id: TenantId = Field(alias="tenantId")
    session_id: SessionId = Field(alias="sessionId")
    filename: ArtifactFilename
    media_type: MediaType = Field(alias="mediaType")
    size_bytes: int = Field(alias="sizeBytes", ge=0, le=10 * 1024 * 1024)
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class ArtifactsPage(ResponseModel):
    data: list[Artifact]
    next_cursor: str | None = Field(alias="nextCursor")


class Session(ResponseModel):
    id: SessionId
    agent_version: int | None = Field(
        alias="agentVersion",
        ge=1,
        le=2_147_483_647,
    )
    message_count: int = Field(alias="messageCount", ge=0)
    last_message_preview: str | None = Field(alias="lastMessagePreview")
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class SessionsPage(ResponseModel):
    data: list[Session]
    next_cursor: str | None = Field(alias="nextCursor")


class SessionMessagePart(ResponseModel):
    type: NonEmptyString


class SessionMessage(ResponseModel):
    id: NonEmptyString
    role: Literal["system", "user", "assistant"]
    parts: list[SessionMessagePart] = Field(min_length=1)
    metadata: object | None = None


class SessionMessagesPage(ResponseModel):
    data: list[SessionMessage]
    next_cursor: str | None = Field(alias="nextCursor")
    latest_cursor: str | None = Field(alias="latestCursor")


class TaskOnceConfig(ResponseModel):
    at: AwareDatetime


class TaskIntervalConfig(ResponseModel):
    every_ms: int = Field(alias="everyMs", ge=60_000)


class TaskCronConfig(ResponseModel):
    expression: NonEmptyString
    stagger_ms: int | None = Field(default=None, alias="staggerMs", ge=0)
    timezone: NonEmptyString

    @field_validator("expression")
    @classmethod
    def _validate_expression(cls, value: str) -> str:
        _validate_cron(value)
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        return _validate_timezone(value)


class TaskOnceSchedule(ResponseModel):
    kind: Literal["once"]
    config: TaskOnceConfig


class TaskIntervalSchedule(ResponseModel):
    kind: Literal["interval"]
    config: TaskIntervalConfig


class TaskCronSchedule(ResponseModel):
    kind: Literal["cron"]
    config: TaskCronConfig


TaskSchedule: TypeAlias = Annotated[
    TaskOnceSchedule | TaskIntervalSchedule | TaskCronSchedule,
    Field(discriminator="kind"),
]


class Task(ResponseModel):
    id: TaskId
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    agent_version: int | None = Field(
        alias="agentVersion",
        ge=1,
        le=2_147_483_647,
    )
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    ]
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=6_000),
    ]
    schedule: TaskSchedule | None
    enabled: bool
    active_run_id: TaskRunId | None = Field(alias="activeRunId")
    latest_run_id: TaskRunId | None = Field(alias="latestRunId")
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    deleted_at: AwareDatetime | None = Field(alias="deletedAt")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class TaskLatestRun(ResponseModel):
    id: TaskRunId
    status: NonEmptyString
    finished_at: AwareDatetime | None = Field(alias="finishedAt")


class TaskListItem(Task):
    latest_run: TaskLatestRun | None = Field(alias="latestRun")


class TasksPage(ResponseModel):
    data: list[TaskListItem]
    next_cursor: str | None = Field(alias="nextCursor")


class TaskCreateResponse(ResponseModel):
    task: Task
    run_id: TaskRunId | None = Field(alias="runId")


class TaskRunSubmission(ResponseModel):
    run_id: TaskRunId = Field(alias="runId")


class TaskRun(ResponseModel):
    id: TaskRunId
    task_id: TaskId = Field(alias="taskId")
    tenant_id: TenantId = Field(alias="tenantId")
    agent_id: AgentId = Field(alias="agentId")
    agent_version: int = Field(alias="agentVersion", ge=1, le=2_147_483_647)
    session_id: SessionId | None = Field(alias="sessionId")
    turn_id: TurnId | None = Field(alias="turnId")
    status: NonEmptyString
    error: str | None
    user_id: str = Field(alias="userId")
    metadata: dict[str, object]
    started_at: AwareDatetime | None = Field(alias="startedAt")
    finished_at: AwareDatetime | None = Field(alias="finishedAt")
    cancel_requested_at: AwareDatetime | None = Field(alias="cancelRequestedAt")
    canceled_at: AwareDatetime | None = Field(alias="canceledAt")
    created_at: AwareDatetime = Field(alias="createdAt")
    updated_at: AwareDatetime = Field(alias="updatedAt")


class TaskRunsPage(ResponseModel):
    data: list[TaskRun]
    next_cursor: str | None = Field(alias="nextCursor")


TaskRunMessagesPage: TypeAlias = SessionMessagesPage


class ToolApproval(ResponseModel):
    approval_id: NonEmptyString = Field(alias="approvalId")
    tool_name: NonEmptyString = Field(alias="toolName")
    tool_call_id: NonEmptyString = Field(alias="toolCallId")
    input: object
    decision: str
    reason: str | None


class ToolApprovalContinuation(ResponseModel):
    id: NonEmptyString
    state: str


class ToolApprovals(ResponseModel):
    data: list[ToolApproval]
    continuation: ToolApprovalContinuation | None


class ToolApprovalDecision(ResponseModel):
    continuation_id: NonEmptyString = Field(alias="continuationId")
    state: str


class ArtifactDownloadUrl(ResponseModel):
    url: AnyUrl
    expires_at: AwareDatetime = Field(alias="expiresAt")
