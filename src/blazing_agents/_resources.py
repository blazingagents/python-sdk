from __future__ import annotations

import mimetypes
import re
from collections.abc import AsyncIterator, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Literal, cast
from urllib.parse import quote

from ._downloads import AsyncByteStream, ByteStream
from ._models import (
    Agent,
    Agents,
    AgentVersion,
    AgentVersionsPage,
    Artifact,
    ArtifactDownloadUrl,
    ArtifactsPage,
    McpAttachment,
    McpAttachments,
    McpConnection,
    McpConnectionAuthorization,
    McpConnectionReconnectResult,
    McpConnections,
    McpConnectionTestResult,
    MemoriesPage,
    Memory,
    MemoryResponse,
    Prompt,
    Prompts,
    Provider,
    ProviderModels,
    Providers,
    Session,
    SessionMessagesPage,
    SessionsPage,
    Skill,
    SkillCopyResult,
    SkillCopyResults,
    SkillDetail,
    SkillsPage,
    Task,
    TaskCreateResponse,
    TaskListItem,
    TaskRun,
    TaskRunMessagesPage,
    TaskRunsPage,
    TaskRunSubmission,
    TasksPage,
    TenantSettings,
    ToolApprovalDecision,
    ToolApprovals,
    Usage,
    Workspace,
    WorkspacesPage,
    _validate_cron,
    _validate_timezone,
)
from ._transport import (
    OMITTED,
    RESPONSE_BYTES,
    RESPONSE_STATUS,
    AsyncTransport,
    SyncTransport,
    _Omitted,
    _Request,
)
from ._types import (
    AgentTool,
    McpConnectionAuthType,
    ProviderType,
    QuotaUpdate,
    SkillArchiveType,
    TaskScheduleInput,
    Timeout,
    UploadFile,
    UsageGroupBy,
    WorkspaceDeletionOutcome,
    WorkspaceNetworkPolicy,
)

_QUOTA_FIELDS = {
    "monthly_token_limit",
    "monthly_request_limit",
    "reset_day",
}
_PROVIDER_TYPES = {
    "openai",
    "anthropic",
    "openrouter",
    "google",
    "vercel_ai_gateway",
    "custom",
}
_MCP_CONNECTION_AUTH_TYPES = {
    "none",
    "bearer",
    "oauth_authorization_code",
    "oauth_client_credentials",
}
_SKILL_ARCHIVE_TYPES = {"zip", "tar", "tar.gz"}
_SkillCopyResultList = list[SkillCopyResult]
_ISO_OFFSET_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _agent_body(
    *,
    name: str | _Omitted,
    model: str | None | _Omitted,
    provider_id: str | None | _Omitted,
    workspace_id: str | _Omitted,
    memory_injection_enabled: bool | _Omitted,
    tools: Sequence[str] | _Omitted,
    instructions: str | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    mcp_connection_ids: Sequence[str] | _Omitted,
) -> dict[str, object]:
    body: dict[str, object] = {}
    for wire_name, value in (
        ("name", name),
        ("model", model),
        ("providerId", provider_id),
        ("workspaceId", workspace_id),
        ("memoryInjectionEnabled", memory_injection_enabled),
        ("tools", tools),
        ("instructions", instructions),
        ("userId", user_id),
        ("metadata", metadata),
        ("mcpConnectionIds", mcp_connection_ids),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value
    return body


def _validate_agent_create_configuration(
    model: object,
    provider_id: str | None | _Omitted,
) -> None:
    if isinstance(model, _Omitted) and isinstance(provider_id, _Omitted):
        return
    if (
        isinstance(model, _Omitted)
        or isinstance(provider_id, _Omitted)
        or model is None
        or provider_id is None
    ):
        msg = "provider_id and model must both be provided"
        raise ValueError(msg)


def _validate_agent_update_configuration(
    model: str | None | _Omitted,
    provider_id: str | None | _Omitted,
) -> None:
    if not isinstance(provider_id, _Omitted) and isinstance(model, _Omitted):
        msg = "Changing provider_id requires model"
        raise ValueError(msg)
    if not isinstance(model, _Omitted) and (
        (model is None and provider_id is not None)
        or (model is not None and provider_id is None)
    ):
        msg = "provider_id and model must both be null when clearing"
        raise ValueError(msg)


def _agent_path(agent_id: str) -> str:
    return f"/v1/agents/{quote(agent_id, safe='')}"


def _sessions_path(agent_id: str, session_id: str | None = None) -> str:
    path = f"/v1/agents/{quote(agent_id, safe='')}/sessions"
    if session_id is not None:
        return f"{path}/{quote(session_id, safe='')}"
    return path


def _sessions_query(
    user_id: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    query: dict[str, str | int] = {}
    for wire_name, value in (
        ("userId", user_id),
        ("cursor", cursor),
        ("limit", limit),
    ):
        if not isinstance(value, _Omitted):
            query[wire_name] = value
    return query


def _session_messages_query(
    cursor: str | _Omitted,
    after: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    query: dict[str, str | int] = {}
    for wire_name, value in (
        ("cursor", cursor),
        ("after", after),
        ("limit", limit),
    ):
        if not isinstance(value, _Omitted):
            query[wire_name] = value
    return query


def _task_path(task_id: str | None = None) -> str:
    path = "/v1/tasks"
    if task_id is None:
        return path
    return f"{path}/{quote(task_id, safe='')}"


def _task_run_path(task_id: str, run_id: str | None = None) -> str:
    path = f"{_task_path(task_id)}/runs"
    if run_id is None:
        return path
    return f"{path}/{quote(run_id, safe='')}"


def _validate_offset_datetime(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if (
        _ISO_OFFSET_DATETIME.fullmatch(value) is None
        or parsed is None
        or parsed.utcoffset() is None
    ):
        msg = "once schedule at must be an ISO datetime with an offset"
        raise ValueError(msg)


def _task_schedule(schedule: TaskScheduleInput) -> dict[str, object]:
    if not isinstance(schedule, dict) or set(schedule) != {"kind", "config"}:
        msg = "schedule must contain exactly kind and config"
        raise TypeError(msg)
    kind = schedule["kind"]
    config = cast(dict[str, object], schedule["config"])
    if not isinstance(config, dict):
        msg = "schedule config must be a dictionary"
        raise TypeError(msg)
    if kind == "once":
        if set(config) != {"at"} or not isinstance(config["at"], str):
            msg = "once schedule config must contain exactly string at"
            raise TypeError(msg)
        _validate_offset_datetime(config["at"])
        return {"kind": kind, "config": {"at": config["at"]}}
    if kind == "interval":
        every_ms = config.get("every_ms")
        if (
            set(config) != {"every_ms"}
            or not isinstance(every_ms, int)
            or isinstance(every_ms, bool)
            or every_ms < 60_000
        ):
            msg = "interval schedule config requires every_ms of at least 60000"
            raise ValueError(msg)
        return {"kind": kind, "config": {"everyMs": every_ms}}
    if kind == "cron":
        if "expression" not in config or not set(config) <= {
            "expression",
            "timezone",
            "stagger_ms",
        }:
            msg = "cron schedule config has invalid fields"
            raise TypeError(msg)
        expression = config["expression"]
        timezone = config.get("timezone")
        stagger_ms = config.get("stagger_ms")
        if not isinstance(expression, str):
            msg = "cron schedule expression must be a string"
            raise TypeError(msg)
        _validate_cron(expression)
        if timezone is not None and not isinstance(timezone, str):
            msg = "cron schedule timezone must be a string"
            raise TypeError(msg)
        if timezone is not None:
            timezone = _validate_timezone(timezone)
        if stagger_ms is not None and (
            not isinstance(stagger_ms, int)
            or isinstance(stagger_ms, bool)
            or stagger_ms < 0
        ):
            msg = "cron schedule stagger_ms must be a non-negative integer"
            raise ValueError(msg)
        wire_config: dict[str, object] = {"expression": expression}
        if timezone is not None:
            wire_config["timezone"] = timezone
        if stagger_ms is not None:
            wire_config["staggerMs"] = stagger_ms
        return {"kind": kind, "config": wire_config}
    msg = "schedule kind must be once, interval, or cron"
    raise ValueError(msg)


def _task_body(
    *,
    agent_id: str | _Omitted,
    agent_version: int | None | _Omitted,
    name: str | _Omitted,
    prompt: str | _Omitted,
    schedule: TaskScheduleInput | None | _Omitted,
    enabled: bool | _Omitted,
    submit: bool | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
) -> dict[str, object]:
    body: dict[str, object] = {}
    for wire_name, value in (
        ("agentId", agent_id),
        ("agentVersion", agent_version),
        ("name", name),
        ("prompt", prompt),
        ("enabled", enabled),
        ("submit", submit),
        ("userId", user_id),
        ("metadata", metadata),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value
    if not isinstance(schedule, _Omitted):
        body["schedule"] = None if schedule is None else _task_schedule(schedule)
    return body


def _tasks_query(
    agent_id: str | _Omitted,
    user_id: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    return {
        wire_name: value
        for wire_name, value in (
            ("agentId", agent_id),
            ("userId", user_id),
            ("cursor", cursor),
            ("limit", limit),
        )
        if not isinstance(value, _Omitted)
    }


def _task_run_body(
    idempotency_key: str | _Omitted,
) -> dict[str, object]:
    if isinstance(idempotency_key, _Omitted):
        return {}
    if not isinstance(idempotency_key, str):
        msg = "idempotency_key must be a string"
        raise TypeError(msg)
    if not idempotency_key.strip():
        msg = "idempotency_key must not be blank"
        raise ValueError(msg)
    return {"idempotencyKey": idempotency_key}


def _agents_query(
    user_id: str | _Omitted,
    workspace_id: str | _Omitted,
) -> dict[str, str]:
    return {
        wire_name: value
        for wire_name, value in (
            ("userId", user_id),
            ("workspaceId", workspace_id),
        )
        if not isinstance(value, _Omitted)
    }


def _cursor_limit_query(
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    return {
        wire_name: value
        for wire_name, value in (("cursor", cursor), ("limit", limit))
        if not isinstance(value, _Omitted)
    }


def _workspace_path(workspace_id: str) -> str:
    return f"/v1/workspaces/{quote(workspace_id, safe='')}"


def _workspace_body(
    *,
    name: str | None | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    network_policy: WorkspaceNetworkPolicy | _Omitted,
) -> dict[str, object]:
    return {
        wire_name: value
        for wire_name, value in (
            ("name", name),
            ("userId", user_id),
            ("metadata", metadata),
            (
                "networkPolicy",
                (
                    {
                        "allowedHosts": network_policy["allowed_hosts"],
                        "mode": "allowlist",
                    }
                    if not isinstance(network_policy, _Omitted)
                    and network_policy["mode"] == "allowlist"
                    else network_policy
                ),
            ),
        )
        if not isinstance(value, _Omitted)
    }


def _workspaces_query(
    cursor: str | _Omitted,
    limit: int | _Omitted,
    user_id: str | _Omitted,
) -> dict[str, str | int]:
    return {
        wire_name: value
        for wire_name, value in (
            ("cursor", cursor),
            ("limit", limit),
            ("userId", user_id),
        )
        if not isinstance(value, _Omitted)
    }


def _restored_agent_body(version: AgentVersion) -> dict[str, object]:
    return _agent_body(
        name=version.name,
        model=version.model,
        provider_id=version.provider_id,
        workspace_id=OMITTED,
        memory_injection_enabled=version.memory_injection_enabled,
        tools=version.tools,
        instructions=version.instructions,
        user_id=OMITTED,
        metadata=version.metadata,
        mcp_connection_ids=version.mcp_connection_ids,
    )


def _mcp_attachment_body(
    forward_user_id: bool | _Omitted,
    forwarded_metadata_keys: Sequence[str] | _Omitted,
) -> dict[str, object]:
    body: dict[str, object] = {
        wire_name: value
        for wire_name, value in (
            ("forwardUserId", forward_user_id),
            ("forwardedMetadataKeys", forwarded_metadata_keys),
        )
        if not isinstance(value, _Omitted)
    }
    if not body:
        msg = "At least one MCP Attachment field must be provided."
        raise ValueError(msg)
    return body


def _provider_body(
    *,
    provider_type: ProviderType,
    api_key: str,
    model: str | _Omitted,
    name: str | _Omitted,
    base_url: str | None | _Omitted,
) -> dict[str, object]:
    if provider_type not in _PROVIDER_TYPES:
        msg = "provider_type must be a supported Provider type"
        raise ValueError(msg)
    if provider_type == "custom" and (isinstance(base_url, _Omitted) or not base_url):
        msg = "base_url is required for custom Providers"
        raise ValueError(msg)
    if (
        provider_type == "vercel_ai_gateway"
        and not isinstance(base_url, _Omitted)
        and base_url is not None
    ):
        msg = "base_url is not accepted for Vercel AI Gateway Providers"
        raise ValueError(msg)
    body: dict[str, object] = {
        "providerType": provider_type,
        "apiKey": api_key,
    }
    for wire_name, value in (
        ("name", name),
        ("baseUrl", base_url),
        ("model", model),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value
    return body


def _provider_update_body(
    name: str | _Omitted,
) -> dict[str, object]:
    body: dict[str, object] = {} if isinstance(name, _Omitted) else {"name": name}
    if not body:
        msg = "At least one Provider field must be provided."
        raise ValueError(msg)
    return body


def _provider_path(provider_id: str) -> str:
    return f"/v1/providers/{quote(provider_id, safe='')}"


def _mcp_connection_path(mcp_connection_id: str) -> str:
    return f"/v1/mcp-connections/{quote(mcp_connection_id, safe='')}"


def _prompt_path(prompt_id: str) -> str:
    return f"/v1/prompts/{quote(prompt_id, safe='')}"


def _memory_path(agent_id: str, memory_id: str | None = None) -> str:
    path = f"{_agent_path(agent_id)}/memories"
    if memory_id is None:
        return path
    return f"{path}/{quote(memory_id, safe='')}"


def _skill_path(agent_id: str, skill_id: str | None = None) -> str:
    path = f"{_agent_path(agent_id)}/skills"
    if skill_id is None:
        return path
    return f"{path}/{quote(skill_id, safe='')}"


def _artifact_path(artifact_id: str) -> str:
    return f"/v1/artifacts/{quote(artifact_id, safe='')}"


def _artifacts_query(
    agent_id: str | _Omitted,
    session_id: str | _Omitted,
    cursor: str | _Omitted,
) -> dict[str, str]:
    return {
        wire_name: value
        for wire_name, value in (
            ("agentId", agent_id),
            ("sessionId", session_id),
            ("cursor", cursor),
        )
        if not isinstance(value, _Omitted)
    }


def _skill_file_path(agent_id: str, skill_id: str, path: str) -> str:
    encoded_path = "/".join(quote(segment, safe="") for segment in path.split("/"))
    return f"{_skill_path(agent_id, skill_id)}/files/{encoded_path}"


def _skills_query(
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    return {
        wire_name: value
        for wire_name, value in (("cursor", cursor), ("limit", limit))
        if not isinstance(value, _Omitted)
    }


def _memory_body(
    *,
    text: str,
    user_id: str | _Omitted,
) -> dict[str, object]:
    body: dict[str, object] = {"text": text}
    if not isinstance(user_id, _Omitted):
        body["userId"] = user_id
    return body


def _memories_query(
    *,
    user_id: str | _Omitted,
    search: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    return {
        wire_name: value
        for wire_name, value in (
            ("userId", user_id),
            ("search", search),
            ("cursor", cursor),
            ("limit", limit),
        )
        if not isinstance(value, _Omitted)
    }


def _prompt_body(
    *,
    name: str | _Omitted,
    template: str | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
) -> dict[str, object]:
    return {
        wire_name: value
        for wire_name, value in (
            ("name", name),
            ("template", template),
            ("userId", user_id),
            ("metadata", metadata),
        )
        if not isinstance(value, _Omitted)
    }


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
    if auth_type not in _MCP_CONNECTION_AUTH_TYPES:
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
    for wire_name, value in (
        ("name", name),
        ("bearerToken", bearer_token),
        ("clientId", client_id),
        ("clientSecret", client_secret),
        ("scope", scope),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value
    return body


def _credential_values(*values: str | _Omitted) -> tuple[str, ...]:
    return tuple(value for value in values if isinstance(value, str) and value)


@contextmanager
def _upload_part(
    file: UploadFile,
    *,
    filename: str | None,
    content_type: str | None,
    fallback_filename: str | None = None,
) -> Generator[dict[str, tuple[str, object, str]]]:
    opened = None
    source_name: str | None = None
    if isinstance(file, bytes):
        content: object = file
    elif isinstance(file, (str, PathLike)):
        path = Path(file)
        opened = path.open("rb")
        content = opened
        source_name = path.name
    else:
        content = file
        raw_name = getattr(file, "name", None)
        if isinstance(raw_name, str):
            source_name = Path(raw_name).name

    upload_name = filename or source_name or fallback_filename
    if not upload_name:
        msg = "filename is required for bytes and unnamed file objects"
        raise ValueError(msg)
    upload_type = content_type or mimetypes.guess_type(upload_name)[0]
    try:
        yield {
            "file": (
                upload_name,
                content,
                upload_type or "application/octet-stream",
            )
        }
    finally:
        if opened is not None:
            opened.close()


@contextmanager
def _skill_upload_request(
    *,
    agent_id: str,
    archive_type: SkillArchiveType,
    file: UploadFile,
    filename: str | None,
    extra_headers: Mapping[str, str] | None,
    timeout: Timeout | _Omitted,
) -> Generator[_Request]:
    if archive_type not in _SKILL_ARCHIVE_TYPES:
        msg = "archive_type must be zip, tar, or tar.gz"
        raise ValueError(msg)
    with _upload_part(
        file,
        filename=filename,
        content_type=None,
        fallback_filename=f"skill.{archive_type}",
    ) as file_part:
        multipart: dict[str, object] = {
            "type": (None, archive_type),
            **file_part,
        }
        yield _Request(
            "POST",
            f"{_skill_path(agent_id)}/upload",
            files=multipart,
            extra_headers=extra_headers,
            timeout=timeout,
        )


def _skill_copy_values(response: SkillCopyResults) -> _SkillCopyResultList:
    for result in response.root:
        result._request_id = response._request_id
    return response.root


class AgentsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        model: str | _Omitted = OMITTED,
        provider_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: list[AgentTool] | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: list[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        _validate_agent_create_configuration(model, provider_id)
        return self._transport.request(
            _Request(
                "POST",
                "/v1/agents",
                json_body=_agent_body(
                    name=name,
                    model=model,
                    provider_id=provider_id,
                    workspace_id=workspace_id,
                    memory_injection_enabled=memory_injection_enabled,
                    tools=tools,
                    instructions=instructions,
                    user_id=user_id,
                    metadata=metadata,
                    mcp_connection_ids=mcp_connection_ids,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    def list(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agents:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/agents",
                query=_agents_query(user_id, workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agents,
        )

    def get(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return self._transport.request(
            _Request(
                "GET",
                _agent_path(agent_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    def list_versions(
        self,
        agent_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AgentVersionsPage:
        return self._transport.request(
            _Request(
                "GET",
                f"{_agent_path(agent_id)}/versions",
                query=_cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AgentVersionsPage,
        )

    def iter_versions(
        self,
        agent_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[AgentVersion]:
        next_cursor = cursor
        while True:
            page = self.list_versions(
                agent_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get_version(
        self,
        agent_id: str,
        version: int,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AgentVersion:
        return self._transport.request(
            _Request(
                "GET",
                f"{_agent_path(agent_id)}/versions/{version}",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AgentVersion,
        )

    def restore_version(
        self,
        agent_id: str,
        version: int,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Copy an immutable Version into a new latest Agent Version."""
        historical = self.get_version(
            agent_id,
            version,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return self._transport.request(
            _Request(
                "PUT",
                _agent_path(agent_id),
                json_body=_restored_agent_body(historical),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    def list_mcp_attachments(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpAttachments:
        return self._transport.request(
            _Request(
                "GET",
                f"{_agent_path(agent_id)}/mcp-attachments",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpAttachments,
        )

    def update_mcp_attachment(
        self,
        agent_id: str,
        mcp_connection_id: str,
        *,
        forward_user_id: bool | _Omitted = OMITTED,
        forwarded_metadata_keys: Sequence[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpAttachment:
        return self._transport.request(
            _Request(
                "PATCH",
                (
                    f"{_agent_path(agent_id)}/mcp-attachments/"
                    f"{quote(mcp_connection_id, safe='')}"
                ),
                json_body=_mcp_attachment_body(
                    forward_user_id,
                    forwarded_metadata_keys,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpAttachment,
        )

    def update(
        self,
        agent_id: str,
        *,
        name: str | _Omitted = OMITTED,
        model: str | None | _Omitted = OMITTED,
        provider_id: str | None | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: Sequence[AgentTool] | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: Sequence[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        _validate_agent_update_configuration(model, provider_id)
        body = _agent_body(
            name=name,
            model=model,
            provider_id=provider_id,
            workspace_id=workspace_id,
            memory_injection_enabled=memory_injection_enabled,
            tools=tools,
            instructions=instructions,
            user_id=OMITTED,
            metadata=metadata,
            mcp_connection_ids=mcp_connection_ids,
        )
        if not body:
            msg = "At least one agent field must be provided."
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "PUT",
                _agent_path(agent_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    def disable(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return self._transport.request(
            _Request(
                "POST",
                f"{_agent_path(agent_id)}/disable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    def enable(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return self._transport.request(
            _Request(
                "POST",
                f"{_agent_path(agent_id)}/enable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    def delete(
        self,
        agent_id: str,
        *,
        include_artifacts: bool,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _agent_path(agent_id),
                query={"includeArtifacts": str(include_artifacts).lower()},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    def upload_avatar(
        self,
        agent_id: str,
        file: UploadFile,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        with _upload_part(
            file,
            filename=filename,
            content_type=content_type,
        ) as files:
            return self._transport.request(
                _Request(
                    "POST",
                    f"{_agent_path(agent_id)}/avatar",
                    files=files,
                    extra_headers=extra_headers,
                    timeout=timeout,
                ),
                Agent,
            )

    def remove_avatar(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return self._transport.request(
            _Request(
                "DELETE",
                f"{_agent_path(agent_id)}/avatar",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )


class AsyncAgentsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        model: str | _Omitted = OMITTED,
        provider_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: list[AgentTool] | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: list[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        _validate_agent_create_configuration(model, provider_id)
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/agents",
                json_body=_agent_body(
                    name=name,
                    model=model,
                    provider_id=provider_id,
                    workspace_id=workspace_id,
                    memory_injection_enabled=memory_injection_enabled,
                    tools=tools,
                    instructions=instructions,
                    user_id=user_id,
                    metadata=metadata,
                    mcp_connection_ids=mcp_connection_ids,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    async def list(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agents:
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/agents",
                query=_agents_query(user_id, workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agents,
        )

    async def get(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return await self._transport.request(
            _Request(
                "GET",
                _agent_path(agent_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    async def list_versions(
        self,
        agent_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AgentVersionsPage:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_agent_path(agent_id)}/versions",
                query=_cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AgentVersionsPage,
        )

    async def iter_versions(
        self,
        agent_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[AgentVersion]:
        next_cursor = cursor
        while True:
            page = await self.list_versions(
                agent_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for version in page.data:
                yield version
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get_version(
        self,
        agent_id: str,
        version: int,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AgentVersion:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_agent_path(agent_id)}/versions/{version}",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AgentVersion,
        )

    async def restore_version(
        self,
        agent_id: str,
        version: int,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Copy an immutable Version into a new latest Agent Version."""
        historical = await self.get_version(
            agent_id,
            version,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return await self._transport.request(
            _Request(
                "PUT",
                _agent_path(agent_id),
                json_body=_restored_agent_body(historical),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    async def list_mcp_attachments(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpAttachments:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_agent_path(agent_id)}/mcp-attachments",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpAttachments,
        )

    async def update_mcp_attachment(
        self,
        agent_id: str,
        mcp_connection_id: str,
        *,
        forward_user_id: bool | _Omitted = OMITTED,
        forwarded_metadata_keys: Sequence[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpAttachment:
        return await self._transport.request(
            _Request(
                "PATCH",
                (
                    f"{_agent_path(agent_id)}/mcp-attachments/"
                    f"{quote(mcp_connection_id, safe='')}"
                ),
                json_body=_mcp_attachment_body(
                    forward_user_id,
                    forwarded_metadata_keys,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpAttachment,
        )

    async def update(
        self,
        agent_id: str,
        *,
        name: str | _Omitted = OMITTED,
        model: str | None | _Omitted = OMITTED,
        provider_id: str | None | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: Sequence[AgentTool] | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: Sequence[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        _validate_agent_update_configuration(model, provider_id)
        body = _agent_body(
            name=name,
            model=model,
            provider_id=provider_id,
            workspace_id=workspace_id,
            memory_injection_enabled=memory_injection_enabled,
            tools=tools,
            instructions=instructions,
            user_id=OMITTED,
            metadata=metadata,
            mcp_connection_ids=mcp_connection_ids,
        )
        if not body:
            msg = "At least one agent field must be provided."
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "PUT",
                _agent_path(agent_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    async def disable(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return await self._transport.request(
            _Request(
                "POST",
                f"{_agent_path(agent_id)}/disable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    async def enable(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return await self._transport.request(
            _Request(
                "POST",
                f"{_agent_path(agent_id)}/enable",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )

    async def delete(
        self,
        agent_id: str,
        *,
        include_artifacts: bool,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _agent_path(agent_id),
                query={"includeArtifacts": str(include_artifacts).lower()},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    async def upload_avatar(
        self,
        agent_id: str,
        file: UploadFile,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        with _upload_part(
            file,
            filename=filename,
            content_type=content_type,
        ) as files:
            return await self._transport.request(
                _Request(
                    "POST",
                    f"{_agent_path(agent_id)}/avatar",
                    files=files,
                    extra_headers=extra_headers,
                    timeout=timeout,
                ),
                Agent,
            )

    async def remove_avatar(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        return await self._transport.request(
            _Request(
                "DELETE",
                f"{_agent_path(agent_id)}/avatar",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )


class ProvidersResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        provider_type: ProviderType,
        api_key: str,
        base_url: str | None | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        return self._transport.request(
            _Request(
                "POST",
                "/v1/providers",
                json_body=_provider_body(
                    provider_type=provider_type,
                    api_key=api_key,
                    model=OMITTED,
                    name=name,
                    base_url=base_url,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=(api_key,),
            ),
            Provider,
        )

    def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Providers:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/providers",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Providers,
        )

    def get(
        self,
        provider_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        return self._transport.request(
            _Request(
                "GET",
                _provider_path(provider_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Provider,
        )

    def list_models(
        self,
        provider_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ProviderModels:
        return self._transport.request(
            _Request(
                "GET",
                f"{_provider_path(provider_id)}/models",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ProviderModels,
        )

    def update(
        self,
        provider_id: str,
        *,
        name: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        return self._transport.request(
            _Request(
                "PATCH",
                _provider_path(provider_id),
                json_body=_provider_update_body(name),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Provider,
        )

    def delete(
        self,
        provider_id: str,
        *,
        confirm_version_invalidation: bool = False,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _provider_path(provider_id),
                query=(
                    {"confirmVersionInvalidation": "true"}
                    if confirm_version_invalidation
                    else {}
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncProvidersResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        provider_type: ProviderType,
        api_key: str,
        base_url: str | None | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/providers",
                json_body=_provider_body(
                    provider_type=provider_type,
                    api_key=api_key,
                    model=OMITTED,
                    name=name,
                    base_url=base_url,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=(api_key,),
            ),
            Provider,
        )

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Providers:
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/providers",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Providers,
        )

    async def get(
        self,
        provider_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        return await self._transport.request(
            _Request(
                "GET",
                _provider_path(provider_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Provider,
        )

    async def list_models(
        self,
        provider_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ProviderModels:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_provider_path(provider_id)}/models",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ProviderModels,
        )

    async def update(
        self,
        provider_id: str,
        *,
        name: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        return await self._transport.request(
            _Request(
                "PATCH",
                _provider_path(provider_id),
                json_body=_provider_update_body(name),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Provider,
        )

    async def delete(
        self,
        provider_id: str,
        *,
        confirm_version_invalidation: bool = False,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _provider_path(provider_id),
                query=(
                    {"confirmVersionInvalidation": "true"}
                    if confirm_version_invalidation
                    else {}
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class McpConnectionsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def connect(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnectionAuthorization:
        return self._transport.request(
            _Request(
                "POST",
                f"{_mcp_connection_path(mcp_connection_id)}/connect",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnectionAuthorization,
        )

    def create(
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
        body = _mcp_connection_body(
            auth_type=auth_type,
            url=url,
            name=name,
            bearer_token=bearer_token,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
        return self._transport.request(
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

    def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnections:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/mcp-connections",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnections,
        )

    def get(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnection:
        return self._transport.request(
            _Request(
                "GET",
                _mcp_connection_path(mcp_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnection,
        )

    def update(
        self,
        mcp_connection_id: str,
        *,
        name: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnection:
        if isinstance(name, _Omitted):
            msg = "At least one MCP Connection field must be provided."
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "PATCH",
                _mcp_connection_path(mcp_connection_id),
                json_body={"name": name},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnection,
        )

    def delete(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _mcp_connection_path(mcp_connection_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    def test(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnectionTestResult:
        return self._transport.request(
            _Request(
                "POST",
                f"{_mcp_connection_path(mcp_connection_id)}/test",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnectionTestResult,
        )

    def reconnect(
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
        body = _mcp_connection_body(
            auth_type=auth_type,
            url=url,
            name=OMITTED,
            bearer_token=bearer_token,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
        return self._transport.request(
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


class AsyncMcpConnectionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def connect(
        self,
        mcp_connection_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> McpConnectionAuthorization:
        return await self._transport.request(
            _Request(
                "POST",
                f"{_mcp_connection_path(mcp_connection_id)}/connect",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            McpConnectionAuthorization,
        )

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


class MemoriesResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        agent_id: str,
        text: str,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoryResponse:
        return self._transport.request(
            _Request(
                "POST",
                _memory_path(agent_id),
                json_body=_memory_body(text=text, user_id=user_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoryResponse,
        )

    def list(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        search: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoriesPage:
        return self._transport.request(
            _Request(
                "GET",
                _memory_path(agent_id),
                query=_memories_query(
                    user_id=user_id,
                    search=search,
                    cursor=cursor,
                    limit=limit,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoriesPage,
        )

    def iter(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        search: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[Memory]:
        next_cursor = cursor
        while True:
            page = self.list(
                agent_id=agent_id,
                user_id=user_id,
                search=search,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get(
        self,
        *,
        agent_id: str,
        memory_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoryResponse:
        return self._transport.request(
            _Request(
                "GET",
                _memory_path(agent_id, memory_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoryResponse,
        )

    def update(
        self,
        *,
        agent_id: str,
        memory_id: str,
        text: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoryResponse:
        return self._transport.request(
            _Request(
                "PATCH",
                _memory_path(agent_id, memory_id),
                json_body={"text": text},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoryResponse,
        )

    def delete(
        self,
        *,
        agent_id: str,
        memory_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _memory_path(agent_id, memory_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncMemoriesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        agent_id: str,
        text: str,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoryResponse:
        return await self._transport.request(
            _Request(
                "POST",
                _memory_path(agent_id),
                json_body=_memory_body(text=text, user_id=user_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoryResponse,
        )

    async def list(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        search: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoriesPage:
        return await self._transport.request(
            _Request(
                "GET",
                _memory_path(agent_id),
                query=_memories_query(
                    user_id=user_id,
                    search=search,
                    cursor=cursor,
                    limit=limit,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoriesPage,
        )

    async def iter(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        search: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Memory]:
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                user_id=user_id,
                search=search,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for memory in page.data:
                yield memory
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        *,
        agent_id: str,
        memory_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoryResponse:
        return await self._transport.request(
            _Request(
                "GET",
                _memory_path(agent_id, memory_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoryResponse,
        )

    async def update(
        self,
        *,
        agent_id: str,
        memory_id: str,
        text: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MemoryResponse:
        return await self._transport.request(
            _Request(
                "PATCH",
                _memory_path(agent_id, memory_id),
                json_body={"text": text},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MemoryResponse,
        )

    async def delete(
        self,
        *,
        agent_id: str,
        memory_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _memory_path(agent_id, memory_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class PromptsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        template: str,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        return self._transport.request(
            _Request(
                "POST",
                "/v1/prompts",
                json_body=_prompt_body(
                    name=name,
                    template=template,
                    user_id=user_id,
                    metadata=metadata,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompt,
        )

    def list(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompts:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/prompts",
                query=({} if isinstance(user_id, _Omitted) else {"userId": user_id}),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompts,
        )

    def get(
        self,
        *,
        prompt_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        return self._transport.request(
            _Request(
                "GET",
                _prompt_path(prompt_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompt,
        )

    def update(
        self,
        *,
        prompt_id: str,
        name: str | _Omitted = OMITTED,
        template: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        body = _prompt_body(
            name=name,
            template=template,
            user_id=OMITTED,
            metadata=metadata,
        )
        if not body:
            msg = "At least one Prompt field must be provided."
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "PATCH",
                _prompt_path(prompt_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompt,
        )

    def delete(
        self,
        *,
        prompt_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _prompt_path(prompt_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncPromptsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        template: str,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/prompts",
                json_body=_prompt_body(
                    name=name,
                    template=template,
                    user_id=user_id,
                    metadata=metadata,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompt,
        )

    async def list(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompts:
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/prompts",
                query=({} if isinstance(user_id, _Omitted) else {"userId": user_id}),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompts,
        )

    async def get(
        self,
        *,
        prompt_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        return await self._transport.request(
            _Request(
                "GET",
                _prompt_path(prompt_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompt,
        )

    async def update(
        self,
        *,
        prompt_id: str,
        name: str | _Omitted = OMITTED,
        template: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        body = _prompt_body(
            name=name,
            template=template,
            user_id=OMITTED,
            metadata=metadata,
        )
        if not body:
            msg = "At least one Prompt field must be provided."
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "PATCH",
                _prompt_path(prompt_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Prompt,
        )

    async def delete(
        self,
        *,
        prompt_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _prompt_path(prompt_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class WorkspacesResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        network_policy: WorkspaceNetworkPolicy | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        return self._transport.request(
            _Request(
                "POST",
                "/v1/workspaces",
                json_body=_workspace_body(
                    name=name,
                    user_id=user_id,
                    metadata=metadata,
                    network_policy=network_policy,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Workspace,
        )

    def list(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> WorkspacesPage:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/workspaces",
                query=_workspaces_query(cursor, limit, user_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            WorkspacesPage,
        )

    def iter(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[Workspace]:
        next_cursor = cursor
        while True:
            page = self.list(
                cursor=next_cursor,
                limit=limit,
                user_id=user_id,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get(
        self,
        *,
        workspace_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        return self._transport.request(
            _Request(
                "GET",
                _workspace_path(workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Workspace,
        )

    def update(
        self,
        *,
        workspace_id: str,
        name: str | None | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        network_policy: WorkspaceNetworkPolicy | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        body = _workspace_body(
            name=name,
            user_id=OMITTED,
            metadata=metadata,
            network_policy=network_policy,
        )
        if not body:
            msg = "At least one Workspace field must be provided."
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "PUT",
                _workspace_path(workspace_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Workspace,
        )

    def delete(
        self,
        *,
        workspace_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> WorkspaceDeletionOutcome:
        status = self._transport.request(
            _Request(
                "DELETE",
                _workspace_path(workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_STATUS,
        )
        return "pending" if status == 202 else "completed"


class AsyncWorkspacesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        name: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        network_policy: WorkspaceNetworkPolicy | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Workspace:
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/workspaces",
                json_body=_workspace_body(
                    name=name,
                    user_id=user_id,
                    metadata=metadata,
                    network_policy=network_policy,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Workspace,
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
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/workspaces",
                query=_workspaces_query(cursor, limit, user_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            WorkspacesPage,
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
        return await self._transport.request(
            _Request(
                "GET",
                _workspace_path(workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Workspace,
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
            Workspace,
        )

    async def delete(
        self,
        *,
        workspace_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> WorkspaceDeletionOutcome:
        status = await self._transport.request(
            _Request(
                "DELETE",
                _workspace_path(workspace_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_STATUS,
        )
        return "pending" if status == 202 else "completed"


def _tenant_body(
    name: str | _Omitted,
    quota: QuotaUpdate | None | _Omitted,
) -> dict[str, object]:
    body: dict[str, object] = {}
    if not isinstance(name, _Omitted):
        body["name"] = name
    if not isinstance(quota, _Omitted):
        if quota is None:
            body["quota"] = None
        else:
            if not isinstance(quota, dict) or set(quota) != _QUOTA_FIELDS:
                msg = "quota must contain exactly the documented fields"
                raise TypeError(msg)
            body["quota"] = {
                "monthlyTokenLimit": quota["monthly_token_limit"],
                "monthlyRequestLimit": quota["monthly_request_limit"],
                "resetDay": quota["reset_day"],
            }
    if not body:
        msg = "At least one tenant field must be provided."
        raise ValueError(msg)
    return body


def _usage_query(
    *,
    from_: str | _Omitted,
    to: str | _Omitted,
    agent_id: str | _Omitted,
    session_id: str | _Omitted,
    user_id: str | _Omitted,
    group_by: UsageGroupBy | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    query: dict[str, str | int] = {}
    for wire_name, value in (
        ("from", from_),
        ("to", to),
        ("agentId", agent_id),
        ("sessionId", session_id),
        ("userId", user_id),
        ("groupBy", group_by),
        ("limit", limit),
    ):
        if not isinstance(value, _Omitted):
            query[wire_name] = value
    return query


class TenantResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TenantSettings:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/tenant",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TenantSettings,
        )

    def update(
        self,
        *,
        name: str | _Omitted = OMITTED,
        quota: QuotaUpdate | _Omitted | None = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TenantSettings:
        return self._transport.request(
            _Request(
                "PATCH",
                "/v1/tenant",
                json_body=_tenant_body(name, quota),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TenantSettings,
        )


class AsyncTenantResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TenantSettings:
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/tenant",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TenantSettings,
        )

    async def update(
        self,
        *,
        name: str | _Omitted = OMITTED,
        quota: QuotaUpdate | _Omitted | None = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TenantSettings:
        return await self._transport.request(
            _Request(
                "PATCH",
                "/v1/tenant",
                json_body=_tenant_body(name, quota),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TenantSettings,
        )


class UsageResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(
        self,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        group_by: UsageGroupBy | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Usage:
        query = _usage_query(
            from_=from_,
            to=to,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            group_by=group_by,
            limit=limit,
        )
        return self._transport.request(
            _Request(
                "GET",
                "/v1/usage",
                query=query,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Usage,
        )

    def get_for_agent(
        self,
        agent_id: str,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        group_by: UsageGroupBy | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Usage:
        query = _usage_query(
            from_=from_,
            to=to,
            agent_id=OMITTED,
            session_id=session_id,
            user_id=user_id,
            group_by=group_by,
            limit=limit,
        )
        return self._transport.request(
            _Request(
                "GET",
                f"/v1/agents/{quote(agent_id, safe='')}/usage",
                query=query,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Usage,
        )


class AsyncUsageResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(
        self,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        group_by: UsageGroupBy | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Usage:
        query = _usage_query(
            from_=from_,
            to=to,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            group_by=group_by,
            limit=limit,
        )
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/usage",
                query=query,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Usage,
        )

    async def get_for_agent(
        self,
        agent_id: str,
        *,
        from_: str | _Omitted = OMITTED,
        to: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        group_by: UsageGroupBy | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Usage:
        query = _usage_query(
            from_=from_,
            to=to,
            agent_id=OMITTED,
            session_id=session_id,
            user_id=user_id,
            group_by=group_by,
            limit=limit,
        )
        return await self._transport.request(
            _Request(
                "GET",
                f"/v1/agents/{quote(agent_id, safe='')}/usage",
                query=query,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Usage,
        )


class ArtifactsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ArtifactsPage:
        return self._transport.request(
            _Request(
                "GET",
                "/v1/artifacts",
                query=_artifacts_query(agent_id, session_id, cursor),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ArtifactsPage,
        )

    def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[Artifact]:
        next_cursor = cursor
        while True:
            page = self.list(
                agent_id=agent_id,
                session_id=session_id,
                cursor=next_cursor,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def create_download_url(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ArtifactDownloadUrl:
        return self._transport.request(
            _Request(
                "POST",
                f"{_artifact_path(artifact_id)}/download-url",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ArtifactDownloadUrl,
        )

    def get(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Artifact:
        return self._transport.request(
            _Request(
                "GET",
                _artifact_path(artifact_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Artifact,
        )

    def delete(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _artifact_path(artifact_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class TasksResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        agent_id: str,
        name: str,
        prompt: str,
        agent_version: int | None | _Omitted = OMITTED,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        submit: bool | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskCreateResponse:
        return self._transport.request(
            _Request(
                "POST",
                _task_path(),
                json_body=_task_body(
                    agent_id=agent_id,
                    agent_version=agent_version,
                    name=name,
                    prompt=prompt,
                    schedule=schedule,
                    enabled=enabled,
                    submit=submit,
                    user_id=user_id,
                    metadata=metadata,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskCreateResponse,
        )

    def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TasksPage:
        return self._transport.request(
            _Request(
                "GET",
                _task_path(),
                query=_tasks_query(agent_id, user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TasksPage,
        )

    def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[TaskListItem]:
        next_cursor = cursor
        while True:
            page = self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        return self._transport.request(
            _Request(
                "GET",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    def update(
        self,
        task_id: str,
        *,
        agent_version: int | None | _Omitted = OMITTED,
        name: str | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        body = _task_body(
            agent_id=OMITTED,
            agent_version=agent_version,
            name=name,
            prompt=prompt,
            schedule=schedule,
            enabled=enabled,
            submit=OMITTED,
            user_id=OMITTED,
            metadata=metadata,
        )
        if not body:
            msg = "At least one Task field must be provided."
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "PATCH",
                _task_path(task_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    def delete(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    def submit(
        self,
        task_id: str,
        *,
        idempotency_key: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunSubmission:
        return self._transport.request(
            _Request(
                "POST",
                _task_run_path(task_id),
                json_body=_task_run_body(idempotency_key),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunSubmission,
        )

    def list_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunsPage:
        return self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id),
                query=_cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunsPage,
        )

    def iter_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[TaskRun]:
        next_cursor = cursor
        while True:
            page = self.list_runs(
                task_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRun:
        return self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id, run_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRun,
        )

    def run_messages(
        self,
        task_id: str,
        run_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunMessagesPage:
        return self._transport.request(
            _Request(
                "GET",
                f"{_task_run_path(task_id, run_id)}/messages",
                query=_session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunMessagesPage,
        )

    def cancel_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "POST",
                f"{_task_run_path(task_id, run_id)}/cancel",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncTasksResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        agent_id: str,
        name: str,
        prompt: str,
        agent_version: int | None | _Omitted = OMITTED,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        submit: bool | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskCreateResponse:
        return await self._transport.request(
            _Request(
                "POST",
                _task_path(),
                json_body=_task_body(
                    agent_id=agent_id,
                    agent_version=agent_version,
                    name=name,
                    prompt=prompt,
                    schedule=schedule,
                    enabled=enabled,
                    submit=submit,
                    user_id=user_id,
                    metadata=metadata,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskCreateResponse,
        )

    async def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TasksPage:
        return await self._transport.request(
            _Request(
                "GET",
                _task_path(),
                query=_tasks_query(agent_id, user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TasksPage,
        )

    async def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[TaskListItem]:
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for task in page.data:
                yield task
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        return await self._transport.request(
            _Request(
                "GET",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    async def update(
        self,
        task_id: str,
        *,
        agent_version: int | None | _Omitted = OMITTED,
        name: str | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        schedule: TaskScheduleInput | None | _Omitted = OMITTED,
        enabled: bool | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Task:
        body = _task_body(
            agent_id=OMITTED,
            agent_version=agent_version,
            name=name,
            prompt=prompt,
            schedule=schedule,
            enabled=enabled,
            submit=OMITTED,
            user_id=OMITTED,
            metadata=metadata,
        )
        if not body:
            msg = "At least one Task field must be provided."
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "PATCH",
                _task_path(task_id),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Task,
        )

    async def delete(
        self,
        task_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _task_path(task_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    async def submit(
        self,
        task_id: str,
        *,
        idempotency_key: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunSubmission:
        return await self._transport.request(
            _Request(
                "POST",
                _task_run_path(task_id),
                json_body=_task_run_body(idempotency_key),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunSubmission,
        )

    async def list_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunsPage:
        return await self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id),
                query=_cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunsPage,
        )

    async def iter_runs(
        self,
        task_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[TaskRun]:
        next_cursor = cursor
        while True:
            page = await self.list_runs(
                task_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for run in page.data:
                yield run
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRun:
        return await self._transport.request(
            _Request(
                "GET",
                _task_run_path(task_id, run_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRun,
        )

    async def run_messages(
        self,
        task_id: str,
        run_id: str,
        *,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TaskRunMessagesPage:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_task_run_path(task_id, run_id)}/messages",
                query=_session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            TaskRunMessagesPage,
        )

    async def cancel_run(
        self,
        task_id: str,
        run_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "POST",
                f"{_task_run_path(task_id, run_id)}/cancel",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class SessionsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def list(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionsPage:
        return self._transport.request(
            _Request(
                "GET",
                _sessions_path(agent_id),
                query=_sessions_query(user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SessionsPage,
        )

    def iter(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[Session]:
        next_cursor = cursor
        while True:
            page = self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def messages(
        self,
        *,
        agent_id: str,
        session_id: str,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionMessagesPage:
        return self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/messages",
                query=_session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SessionMessagesPage,
        )

    def tool_approvals(
        self,
        *,
        agent_id: str,
        session_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ToolApprovals:
        return self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/tool-approvals",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ToolApprovals,
        )

    def decide_tool_approval(
        self,
        *,
        agent_id: str,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ToolApprovalDecision:
        body: dict[str, object] = {"approved": approved}
        if not isinstance(reason, _Omitted):
            body["reason"] = reason
        return self._transport.request(
            _Request(
                "POST",
                (
                    f"{_sessions_path(agent_id, session_id)}/tool-approvals/"
                    f"{quote(approval_id, safe='')}"
                ),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ToolApprovalDecision,
        )

    def join_tool_approval_continuation(
        self,
        *,
        agent_id: str,
        session_id: str,
        continuation_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ByteStream:
        return self._transport.stream(
            _Request(
                "GET",
                (
                    f"{_sessions_path(agent_id, session_id)}"
                    "/tool-approval-continuations/"
                    f"{quote(continuation_id, safe='')}"
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            )
        )

    def delete(
        self,
        *,
        agent_id: str,
        session_id: str,
        delete_artifacts: bool,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _sessions_path(agent_id, session_id),
                query={"deleteArtifacts": str(delete_artifacts).lower()},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncSessionsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def list(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionsPage:
        return await self._transport.request(
            _Request(
                "GET",
                _sessions_path(agent_id),
                query=_sessions_query(user_id, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SessionsPage,
        )

    async def iter(
        self,
        *,
        agent_id: str,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Session]:
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for session in page.data:
                yield session
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def messages(
        self,
        *,
        agent_id: str,
        session_id: str,
        cursor: str | _Omitted = OMITTED,
        after: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SessionMessagesPage:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/messages",
                query=_session_messages_query(cursor, after, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SessionMessagesPage,
        )

    async def tool_approvals(
        self,
        *,
        agent_id: str,
        session_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ToolApprovals:
        return await self._transport.request(
            _Request(
                "GET",
                f"{_sessions_path(agent_id, session_id)}/tool-approvals",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ToolApprovals,
        )

    async def decide_tool_approval(
        self,
        *,
        agent_id: str,
        session_id: str,
        approval_id: str,
        approved: bool,
        reason: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ToolApprovalDecision:
        body: dict[str, object] = {"approved": approved}
        if not isinstance(reason, _Omitted):
            body["reason"] = reason
        return await self._transport.request(
            _Request(
                "POST",
                (
                    f"{_sessions_path(agent_id, session_id)}/tool-approvals/"
                    f"{quote(approval_id, safe='')}"
                ),
                json_body=body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ToolApprovalDecision,
        )

    async def join_tool_approval_continuation(
        self,
        *,
        agent_id: str,
        session_id: str,
        continuation_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncByteStream:
        return await self._transport.stream(
            _Request(
                "GET",
                (
                    f"{_sessions_path(agent_id, session_id)}"
                    "/tool-approval-continuations/"
                    f"{quote(continuation_id, safe='')}"
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            )
        )

    async def delete(
        self,
        *,
        agent_id: str,
        session_id: str,
        delete_artifacts: bool,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _sessions_path(agent_id, session_id),
                query={"deleteArtifacts": str(delete_artifacts).lower()},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncArtifactsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def list(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ArtifactsPage:
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/artifacts",
                query=_artifacts_query(agent_id, session_id, cursor),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ArtifactsPage,
        )

    async def iter(
        self,
        *,
        agent_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Artifact]:
        next_cursor = cursor
        while True:
            page = await self.list(
                agent_id=agent_id,
                session_id=session_id,
                cursor=next_cursor,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for artifact in page.data:
                yield artifact
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def create_download_url(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ArtifactDownloadUrl:
        return await self._transport.request(
            _Request(
                "POST",
                f"{_artifact_path(artifact_id)}/download-url",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ArtifactDownloadUrl,
        )

    async def get(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Artifact:
        return await self._transport.request(
            _Request(
                "GET",
                _artifact_path(artifact_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Artifact,
        )

    async def delete(
        self,
        *,
        artifact_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _artifact_path(artifact_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AgentSkillsResource:
    def __init__(self, transport: SyncTransport, agent_id: str) -> None:
        self._transport = transport
        self._agent_id = agent_id

    def create(
        self,
        *,
        path: Literal["SKILL.md"],
        content: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        if path != "SKILL.md":
            msg = "path must be SKILL.md"
            raise ValueError(msg)
        return self._transport.request(
            _Request(
                "POST",
                _skill_path(self._agent_id),
                json_body={"path": path, "content": content},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    def upload(
        self,
        *,
        archive_type: SkillArchiveType,
        file: UploadFile,
        filename: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        with _skill_upload_request(
            agent_id=self._agent_id,
            archive_type=archive_type,
            file=file,
            filename=filename,
            extra_headers=extra_headers,
            timeout=timeout,
        ) as request:
            return self._transport.request(request, SkillDetail)

    def list(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillsPage:
        return self._transport.request(
            _Request(
                "GET",
                _skill_path(self._agent_id),
                query=_skills_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillsPage,
        )

    def iter(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[Skill]:
        next_cursor = cursor
        while True:
            page = self.list(
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get(
        self,
        *,
        skill_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        return self._transport.request(
            _Request(
                "GET",
                _skill_path(self._agent_id, skill_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    def delete(
        self,
        *,
        skill_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return self._transport.request(
            _Request(
                "DELETE",
                _skill_path(self._agent_id, skill_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    def read_file(
        self,
        *,
        skill_id: str,
        path: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> bytes:
        return self._transport.request(
            _Request(
                "GET",
                _skill_file_path(self._agent_id, skill_id, path),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_BYTES,
        )

    def replace_file(
        self,
        *,
        skill_id: str,
        path: str,
        content: bytes,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        return self._transport.request(
            _Request(
                "PUT",
                _skill_file_path(self._agent_id, skill_id, path),
                content=content,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    def delete_file(
        self,
        *,
        skill_id: str,
        path: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        return self._transport.request(
            _Request(
                "DELETE",
                _skill_file_path(self._agent_id, skill_id, path),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    def copy(
        self,
        *,
        skill_id: str,
        destination_agent_ids: Sequence[str],
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> _SkillCopyResultList:
        response = self._transport.request(
            _Request(
                "POST",
                f"{_skill_path(self._agent_id, skill_id)}/copies",
                json_body={"agentIds": list(destination_agent_ids)},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillCopyResults,
        )
        return _skill_copy_values(response)


class AsyncAgentSkillsResource:
    def __init__(self, transport: AsyncTransport, agent_id: str) -> None:
        self._transport = transport
        self._agent_id = agent_id

    async def create(
        self,
        *,
        path: Literal["SKILL.md"],
        content: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        if path != "SKILL.md":
            msg = "path must be SKILL.md"
            raise ValueError(msg)
        return await self._transport.request(
            _Request(
                "POST",
                _skill_path(self._agent_id),
                json_body={"path": path, "content": content},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    async def upload(
        self,
        *,
        archive_type: SkillArchiveType,
        file: UploadFile,
        filename: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        with _skill_upload_request(
            agent_id=self._agent_id,
            archive_type=archive_type,
            file=file,
            filename=filename,
            extra_headers=extra_headers,
            timeout=timeout,
        ) as request:
            return await self._transport.request(request, SkillDetail)

    async def list(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillsPage:
        return await self._transport.request(
            _Request(
                "GET",
                _skill_path(self._agent_id),
                query=_skills_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillsPage,
        )

    async def iter(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[Skill]:
        next_cursor = cursor
        while True:
            page = await self.list(
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for skill in page.data:
                yield skill
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        *,
        skill_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        return await self._transport.request(
            _Request(
                "GET",
                _skill_path(self._agent_id, skill_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    async def delete(
        self,
        *,
        skill_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        return await self._transport.request(
            _Request(
                "DELETE",
                _skill_path(self._agent_id, skill_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )

    async def read_file(
        self,
        *,
        skill_id: str,
        path: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> bytes:
        return await self._transport.request(
            _Request(
                "GET",
                _skill_file_path(self._agent_id, skill_id, path),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_BYTES,
        )

    async def replace_file(
        self,
        *,
        skill_id: str,
        path: str,
        content: bytes,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        return await self._transport.request(
            _Request(
                "PUT",
                _skill_file_path(self._agent_id, skill_id, path),
                content=content,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    async def delete_file(
        self,
        *,
        skill_id: str,
        path: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SkillDetail:
        return await self._transport.request(
            _Request(
                "DELETE",
                _skill_file_path(self._agent_id, skill_id, path),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillDetail,
        )

    async def copy(
        self,
        *,
        skill_id: str,
        destination_agent_ids: Sequence[str],
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> _SkillCopyResultList:
        response = await self._transport.request(
            _Request(
                "POST",
                f"{_skill_path(self._agent_id, skill_id)}/copies",
                json_body={"agentIds": list(destination_agent_ids)},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SkillCopyResults,
        )
        return _skill_copy_values(response)
