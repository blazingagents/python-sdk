from __future__ import annotations

from collections.abc import Mapping
from os import PathLike
from typing import Any, BinaryIO, Literal, Never, Required, TypeAlias, TypedDict

import httpx

Timeout = float | httpx.Timeout | None
JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
JsonSchema: TypeAlias = Mapping[str, Any]
ChatTrigger = Literal["submit-message", "regenerate-message"]
UsageGroupBy = Literal["day", "agent", "model", "session", "user"]
AgentTool = Literal["workspace", "write_todos", "memory"]
UploadFile = bytes | str | PathLike[str] | BinaryIO
SkillArchiveType = Literal["zip", "tar", "tar.gz"]
WorkspaceDeletionOutcome = Literal["completed", "pending"]
ProviderType = Literal[
    "openai",
    "anthropic",
    "openrouter",
    "google",
    "vercel_ai_gateway",
    "custom",
]
McpConnectionAuthType = Literal[
    "none",
    "bearer",
    "oauth_authorization_code",
    "oauth_client_credentials",
]
TaskScheduleKind = Literal["once", "interval", "cron"]


class WorkspaceUnrestrictedNetworkPolicy(TypedDict):
    mode: Literal["unrestricted"]


class WorkspaceAllowlistNetworkPolicy(TypedDict):
    mode: Literal["allowlist"]
    allowed_hosts: list[str]


class WorkspaceOfflineNetworkPolicy(TypedDict):
    mode: Literal["offline"]


WorkspaceNetworkPolicy: TypeAlias = (
    WorkspaceUnrestrictedNetworkPolicy
    | WorkspaceAllowlistNetworkPolicy
    | WorkspaceOfflineNetworkPolicy
)


class SkillCreate(TypedDict):
    path: Literal["SKILL.md"]
    content: str


class SkillArchiveUpload(TypedDict, total=False):
    archive_type: Required[SkillArchiveType]
    file: Required[UploadFile]
    filename: str


class SkillsListOptions(TypedDict, total=False):
    cursor: str
    limit: int


class ArtifactsListOptions(TypedDict, total=False):
    session_id: str
    agent_id: str
    cursor: str


class SessionsListOptions(TypedDict, total=False):
    user_id: str
    cursor: str
    limit: int


class SessionMessagesOptions(TypedDict, total=False):
    cursor: str
    after: str
    limit: int


class TaskOnceConfigInput(TypedDict):
    at: str


class TaskIntervalConfigInput(TypedDict):
    every_ms: int


class TaskCronConfigInput(TypedDict, total=False):
    expression: Required[str]
    timezone: str
    stagger_ms: int


class TaskOnceScheduleInput(TypedDict):
    kind: Literal["once"]
    config: TaskOnceConfigInput


class TaskIntervalScheduleInput(TypedDict):
    kind: Literal["interval"]
    config: TaskIntervalConfigInput


class TaskCronScheduleInput(TypedDict):
    kind: Literal["cron"]
    config: TaskCronConfigInput


TaskScheduleInput: TypeAlias = (
    TaskOnceScheduleInput | TaskIntervalScheduleInput | TaskCronScheduleInput
)


class TaskCreate(TypedDict, total=False):
    agent_id: Required[str]
    name: Required[str]
    prompt: Required[str]
    agent_version: int | None
    schedule: TaskScheduleInput | None
    enabled: bool
    submit: bool
    user_id: str
    metadata: dict[str, object]


class TaskUpdate(TypedDict, total=False):
    agent_version: int | None
    name: str
    prompt: str
    schedule: TaskScheduleInput | None
    enabled: bool
    metadata: dict[str, object]


class TasksListOptions(TypedDict, total=False):
    agent_id: str
    user_id: str
    cursor: str
    limit: int


class TaskRunCreate(TypedDict, total=False):
    idempotency_key: str


class TaskRunsListOptions(TypedDict, total=False):
    cursor: str
    limit: int


class TaskRunMessagesOptions(TypedDict, total=False):
    cursor: str
    after: str
    limit: int


class ToolApprovalDecisionInput(TypedDict, total=False):
    agent_id: Required[str]
    session_id: Required[str]
    approval_id: Required[str]
    approved: Required[bool]
    reason: str


class _ChatInput(TypedDict, total=False):
    agent_id: Required[str]
    user_id: str
    metadata: dict[str, object]
    message_id: str


class _ChatMessageInput(_ChatInput, total=False):
    message: Required[dict[str, object]]


class _ChatPromptInput(_ChatInput, total=False):
    prompt_id: Required[str]
    variables: dict[str, str]


class _NewChatInput(TypedDict, total=False):
    trigger: Literal["submit-message"]
    version: int


class _ExistingChatInput(TypedDict, total=False):
    session_id: Required[str]
    trigger: ChatTrigger
    version: Never


class _NewChatMessageInput(_ChatMessageInput, _NewChatInput):
    pass


class _ExistingChatMessageInput(_ChatMessageInput, _ExistingChatInput):
    pass


class _NewChatPromptInput(_ChatPromptInput, _NewChatInput):
    pass


class _ExistingChatPromptInput(_ChatPromptInput, _ExistingChatInput):
    pass


ChatMessageInput: TypeAlias = _NewChatMessageInput | _ExistingChatMessageInput
ChatPromptInput: TypeAlias = _NewChatPromptInput | _ExistingChatPromptInput


class _CompletionInput(TypedDict, total=False):
    agent_id: Required[str]
    version: int
    user_id: str
    metadata: dict[str, object]


class CompletionLiteralInput(_CompletionInput, total=False):
    prompt: Required[str]
    prompt_id: Never
    variables: Never


class CompletionPromptInput(_CompletionInput, total=False):
    prompt_id: Required[str]
    prompt: Never
    variables: dict[str, str]


class SkillCopy(TypedDict):
    destination_agent_ids: list[str]


class _AgentCreateBase(TypedDict, total=False):
    thinking_level: str | None
    name: Required[str]
    workspace_id: str
    memory_injection_enabled: bool
    tools: list[AgentTool]
    instructions: str
    user_id: str
    metadata: dict[str, object]
    mcp_connection_ids: list[str]


class _ConfiguredAgentCreate(_AgentCreateBase):
    model: Required[str]
    provider_id: Required[str]


class _UnconfiguredAgentCreate(_AgentCreateBase, total=False):
    model: Never
    provider_id: Never


AgentCreate: TypeAlias = _ConfiguredAgentCreate | _UnconfiguredAgentCreate


class _AgentUpdateBase(TypedDict, total=False):
    thinking_level: str | None
    name: str
    workspace_id: str
    memory_injection_enabled: bool
    tools: list[AgentTool]
    instructions: str
    metadata: dict[str, object]
    mcp_connection_ids: list[str]


class _AgentUpdateOther(_AgentUpdateBase, total=False):
    model: Never
    provider_id: Never


class _AgentUpdateModel(_AgentUpdateBase, total=False):
    model: Required[str]
    provider_id: Never


class _AgentUpdateConfigured(_AgentUpdateBase):
    model: Required[str]
    provider_id: Required[str]


class _AgentUpdateClear(_AgentUpdateBase):
    model: Required[None]
    provider_id: Required[None]


AgentUpdate: TypeAlias = (
    _AgentUpdateOther | _AgentUpdateModel | _AgentUpdateConfigured | _AgentUpdateClear
)


class AgentsListOptions(TypedDict, total=False):
    user_id: str
    workspace_id: str


class AgentVersionsListOptions(TypedDict, total=False):
    cursor: str
    limit: int


class McpAttachmentUpdate(TypedDict, total=False):
    forward_user_id: bool
    forwarded_metadata_keys: list[str]


class ProviderCreate(TypedDict, total=False):
    name: Required[str]
    provider_type: Required[ProviderType]
    api_key: Required[str]
    base_url: str | None


class ProviderUpdate(TypedDict, total=False):
    name: str


class McpConnectionCreateNone(TypedDict):
    name: str
    url: str
    auth_type: Literal["none"]


class McpConnectionCreateBearer(TypedDict):
    name: str
    url: str
    auth_type: Literal["bearer"]
    bearer_token: str


class McpConnectionCreateAuthorizationCode(TypedDict, total=False):
    name: Required[str]
    url: Required[str]
    auth_type: Required[Literal["oauth_authorization_code"]]
    client_id: str
    client_secret: str
    scope: str


class McpConnectionCreateClientCredentials(TypedDict, total=False):
    name: Required[str]
    url: Required[str]
    auth_type: Required[Literal["oauth_client_credentials"]]
    client_id: Required[str]
    client_secret: Required[str]
    scope: str


McpConnectionCreate: TypeAlias = (
    McpConnectionCreateNone
    | McpConnectionCreateBearer
    | McpConnectionCreateAuthorizationCode
    | McpConnectionCreateClientCredentials
)


class McpConnectionUpdate(TypedDict):
    name: str


class McpConnectionReconnectNone(TypedDict):
    url: str
    auth_type: Literal["none"]


class McpConnectionReconnectBearer(TypedDict):
    url: str
    auth_type: Literal["bearer"]
    bearer_token: str


class McpConnectionReconnectAuthorizationCode(TypedDict, total=False):
    url: Required[str]
    auth_type: Required[Literal["oauth_authorization_code"]]
    client_id: str
    client_secret: str
    scope: str


class McpConnectionReconnectClientCredentials(TypedDict, total=False):
    url: Required[str]
    auth_type: Required[Literal["oauth_client_credentials"]]
    client_id: Required[str]
    client_secret: Required[str]
    scope: str


McpConnectionReconnect: TypeAlias = (
    McpConnectionReconnectNone
    | McpConnectionReconnectBearer
    | McpConnectionReconnectAuthorizationCode
    | McpConnectionReconnectClientCredentials
)


class WorkspaceCreate(TypedDict, total=False):
    name: str
    user_id: str
    metadata: dict[str, object]
    network_policy: WorkspaceNetworkPolicy


class WorkspaceUpdate(TypedDict, total=False):
    name: str | None
    metadata: dict[str, object]
    network_policy: WorkspaceNetworkPolicy


class WorkspacesListOptions(TypedDict, total=False):
    cursor: str
    limit: int
    user_id: str


class PromptCreate(TypedDict, total=False):
    name: Required[str]
    template: Required[str]
    user_id: str
    metadata: dict[str, object]


class PromptUpdate(TypedDict, total=False):
    name: str
    template: str
    metadata: dict[str, object]


class PromptsListOptions(TypedDict, total=False):
    user_id: str


class MemoryCreate(TypedDict, total=False):
    text: Required[str]
    user_id: str


class MemoryUpdate(TypedDict):
    text: str


class MemoriesListOptions(TypedDict, total=False):
    user_id: str
    search: str
    cursor: str
    limit: int


class QuotaUpdate(TypedDict):
    monthly_token_limit: int | None
    monthly_request_limit: int | None
    reset_day: int


class TenantUpdate(TypedDict, total=False):
    name: str
    quota: QuotaUpdate | None


class UsageQuery(TypedDict, total=False):
    from_: str
    to: str
    agent_id: str
    session_id: str
    user_id: str
    group_by: UsageGroupBy
    limit: int
