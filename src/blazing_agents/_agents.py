from __future__ import annotations

from collections.abc import Mapping, Sequence

from ._models import (
    Agent,
    AgentsPage,
    McpAttachment,
    McpAttachments,
    SpendingLimitResponse,
)
from ._transport import (
    OMITTED,
    AsyncTransport,
    SyncTransport,
    _Omitted,
    _Request,
    camel_case_keys,
    drop_omitted,
    path_segment,
)
from ._types import (
    AgentTool,
    ApprovalPolicyInput,
    SpendingLimitInput,
    Timeout,
    UploadFile,
    WorkspaceTier,
)
from ._wire import agent_path, cursor_limit_query, spending_limit_body, upload_part


def _agent_body(
    *,
    name: str | _Omitted,
    model: str | None | _Omitted,
    provider_id: str | None | _Omitted,
    thinking_level: str | None | _Omitted,
    workspace_id: str | _Omitted,
    workspace_tier: WorkspaceTier | _Omitted = OMITTED,
    auto_compaction: bool | _Omitted,
    compaction_reserve_tokens: int | _Omitted,
    memory_injection_enabled: bool | _Omitted,
    tools: Sequence[AgentTool] | _Omitted,
    approval_in_chat: ApprovalPolicyInput | _Omitted,
    approval_in_tasks: ApprovalPolicyInput | _Omitted,
    instructions: str | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
    mcp_connection_ids: Sequence[str] | _Omitted,
) -> dict[str, object]:
    """Build the agent request body, omitting unspecified fields."""
    if not isinstance(workspace_id, _Omitted) and not isinstance(
        workspace_tier, _Omitted
    ):
        raise ValueError("workspace_id and workspace_tier are mutually exclusive")
    body: dict[str, object] = drop_omitted(
        ("name", name),
        ("model", model),
        ("providerId", provider_id),
        ("thinkingLevel", thinking_level),
        ("workspaceId", workspace_id),
        ("workspaceTier", workspace_tier),
        ("autoCompaction", auto_compaction),
        ("compactionReserveTokens", compaction_reserve_tokens),
        ("memoryInjectionEnabled", memory_injection_enabled),
        ("tools", tools),
        ("instructions", instructions),
        ("userId", user_id),
        ("metadata", metadata),
        ("mcpConnectionIds", mcp_connection_ids),
    )
    for wire_name, policy in drop_omitted(
        ("approvalInChat", approval_in_chat),
        ("approvalInTasks", approval_in_tasks),
    ).items():
        body[wire_name] = _approval_policy_body(policy)
    return body


def _approval_policy_body(policy: ApprovalPolicyInput) -> dict[str, object]:
    """Build the approval policy request body, omitting unspecified fields."""
    body: dict[str, object] = {"default": policy["default"]}
    if "overrides" in policy:
        body["overrides"] = [
            {"tool": camel_case_keys(rule["tool"]), "decision": rule["decision"]}
            for rule in policy["overrides"]
        ]
    return body


def _validate_agent_create_configuration(
    model: object,
    provider_id: str | None | _Omitted,
) -> None:
    """Require provider_id and model together when configuring an Agent."""
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
    """Validate provider changes and paired null configuration values."""
    if not isinstance(provider_id, _Omitted) and isinstance(model, _Omitted):
        msg = "Changing provider_id requires model"
        raise ValueError(msg)
    if not isinstance(model, _Omitted) and (
        (model is None and provider_id is not None)
        or (model is not None and provider_id is None)
    ):
        msg = "provider_id and model must both be null when clearing"
        raise ValueError(msg)


def _agents_query(
    user_id: str | _Omitted,
    workspace_id: str | _Omitted,
) -> dict[str, str]:
    """Build the agents query, omitting unspecified filters."""
    return drop_omitted(
        ("userId", user_id),
        ("workspaceId", workspace_id),
    )


def _mcp_attachment_body(
    forward_user_id: bool | _Omitted,
    forwarded_metadata_keys: Sequence[str] | _Omitted,
) -> dict[str, object]:
    """Build the mcp attachment request body, omitting unspecified fields."""
    body: dict[str, object] = drop_omitted(
        ("forwardUserId", forward_user_id),
        ("forwardedMetadataKeys", forwarded_metadata_keys),
    )
    if not body:
        msg = "At least one MCP Attachment field must be provided."
        raise ValueError(msg)
    return body


class UserAgentsResource:
    def __init__(self, transport: SyncTransport) -> None:
        """Bind Agent operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        model: str | _Omitted = OMITTED,
        provider_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        workspace_tier: WorkspaceTier | _Omitted = OMITTED,
        thinking_level: str | None | _Omitted = OMITTED,
        auto_compaction: bool | _Omitted = OMITTED,
        compaction_reserve_tokens: int | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: list[AgentTool] | _Omitted = OMITTED,
        approval_in_chat: ApprovalPolicyInput | _Omitted = OMITTED,
        approval_in_tasks: ApprovalPolicyInput | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: list[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Create an Agent.

        Omitted fields retain server defaults or existing values.

        Args:
            name: Agent display name, 1 to 80 characters.
            model: Provider model identifier.
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            workspace_id: Workspace identifier.
            workspace_tier: Tier for an automatic Workspace; defaults to Core.
                Mutually exclusive with workspace_id.
            thinking_level: Provider-supported reasoning level.
            auto_compaction: Whether the Agent compacts its context automatically.
            compaction_reserve_tokens: Tokens reserved for context compaction.
            memory_injection_enabled: Whether the Agent injects matching Memories.
            tools: Built-in tools available to the Agent.
            approval_in_chat: Tool approval policy for chat Turns.
            approval_in_tasks: Tool approval policy for Task Turns.
            instructions: Agent instructions.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            mcp_connection_ids: MCP Connections attached to the Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            ValueError: provider_id and model are not both supplied when configuring
                an Agent.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
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
                    workspace_tier=workspace_tier,
                    thinking_level=thinking_level,
                    auto_compaction=auto_compaction,
                    compaction_reserve_tokens=compaction_reserve_tokens,
                    memory_injection_enabled=memory_injection_enabled,
                    tools=tools,
                    approval_in_chat=approval_in_chat,
                    approval_in_tasks=approval_in_tasks,
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
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AgentsPage:
        """Fetch one page of Agent records.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            user_id: Caller-defined user identifier.
            workspace_id: Workspace identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                "/v1/agents",
                query={
                    **_agents_query(user_id, workspace_id),
                    **cursor_limit_query(cursor, limit),
                },
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AgentsPage,
        )

    def get(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Fetch the requested Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                agent_path(agent_id),
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
        """Fetch MCP attachments for an Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            MCP attachments for the Agent.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                f"{agent_path(agent_id)}/mcp-attachments",
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
        """Update an Agent MCP attachment.

        Args:
            agent_id: Agent identifier.
            mcp_connection_id: MCP Connection identifier.
            forward_user_id: Whether to forward the user identifier to this MCP
                Connection.
            forwarded_metadata_keys: Metadata keys to forward to this MCP Connection.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Updated MCP attachment settings.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "PATCH",
                (
                    f"{agent_path(agent_id)}/mcp-attachments/"
                    f"{path_segment('mcp_connection_id', mcp_connection_id)}"
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
        thinking_level: str | None | _Omitted = OMITTED,
        auto_compaction: bool | _Omitted = OMITTED,
        compaction_reserve_tokens: int | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: Sequence[AgentTool] | _Omitted = OMITTED,
        approval_in_chat: ApprovalPolicyInput | _Omitted = OMITTED,
        approval_in_tasks: ApprovalPolicyInput | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: Sequence[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Update the provided Agent fields.

        Omitted fields retain server defaults or existing values. Changing
        provider_id requires model. Set both to None to clear them.

        Args:
            agent_id: Agent identifier.
            name: Agent display name, 1 to 80 characters.
            model: Provider model identifier.
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            workspace_id: Workspace identifier.
            thinking_level: Provider-supported reasoning level. None clears the
                setting. Omission retains the current value.
            auto_compaction: Whether the Agent compacts its context automatically.
            compaction_reserve_tokens: Tokens reserved for context compaction.
            memory_injection_enabled: Whether the Agent injects matching Memories.
            tools: Built-in tools available to the Agent.
            approval_in_chat: Tool approval policy for chat Turns.
            approval_in_tasks: Tool approval policy for Task Turns.
            instructions: Agent instructions.
            metadata: Caller-defined JSON metadata.
            mcp_connection_ids: MCP Connections attached to the Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            ValueError: Provider and model changes are inconsistent.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        _validate_agent_update_configuration(model, provider_id)
        body = _agent_body(
            name=name,
            model=model,
            provider_id=provider_id,
            workspace_id=workspace_id,
            thinking_level=thinking_level,
            auto_compaction=auto_compaction,
            compaction_reserve_tokens=compaction_reserve_tokens,
            memory_injection_enabled=memory_injection_enabled,
            tools=tools,
            approval_in_chat=approval_in_chat,
            approval_in_tasks=approval_in_tasks,
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
                agent_path(agent_id),
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
        """Disable the Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                f"{agent_path(agent_id)}/disable",
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
        """Enable the Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                f"{agent_path(agent_id)}/enable",
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
        """Delete the requested Agent.

        Args:
            agent_id: Agent identifier.
            include_artifacts: Whether to include the Agent Artifacts in deletion.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "DELETE",
                agent_path(agent_id),
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
        """Upload an Agent avatar.

        Paths are opened and closed by the SDK. Caller-owned file objects remain
        open.

        Args:
            agent_id: Agent identifier.
            file: File upload input.
            filename: Filename supplied for the upload.
            content_type: Media type for the upload.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            ValueError: No filename is available for bytes or an unnamed file object.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        with upload_part(
            file,
            filename=filename,
            content_type=content_type,
        ) as files:
            return self._transport.request(
                _Request(
                    "POST",
                    f"{agent_path(agent_id)}/avatar",
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
        """Remove an Agent avatar.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "DELETE",
                f"{agent_path(agent_id)}/avatar",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )


class AgentsResource(UserAgentsResource):
    def get_spending_limit(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SpendingLimitResponse:
        """Fetch the Agent model spending limit using tenant authority."""
        return self._transport.request(
            _Request(
                "GET",
                agent_path(agent_id) + "/spending-limit",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SpendingLimitResponse,
        )

    def update_spending_limit(
        self,
        agent_id: str,
        *,
        spending_limit: SpendingLimitInput | None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SpendingLimitResponse:
        """Set or disable the Agent model spending limit using tenant authority."""
        return self._transport.request(
            _Request(
                "PUT",
                agent_path(agent_id) + "/spending-limit",
                json_body=spending_limit_body(spending_limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SpendingLimitResponse,
        )


class AsyncUserAgentsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Agent operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        model: str | _Omitted = OMITTED,
        provider_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        workspace_tier: WorkspaceTier | _Omitted = OMITTED,
        thinking_level: str | None | _Omitted = OMITTED,
        auto_compaction: bool | _Omitted = OMITTED,
        compaction_reserve_tokens: int | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: list[AgentTool] | _Omitted = OMITTED,
        approval_in_chat: ApprovalPolicyInput | _Omitted = OMITTED,
        approval_in_tasks: ApprovalPolicyInput | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: list[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Create an Agent.

        Omitted fields retain server defaults or existing values.

        Args:
            name: Agent display name, 1 to 80 characters.
            model: Provider model identifier.
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            workspace_id: Workspace identifier.
            workspace_tier: Tier for an automatic Workspace; defaults to Core.
                Mutually exclusive with workspace_id.
            thinking_level: Provider-supported reasoning level.
            auto_compaction: Whether the Agent compacts its context automatically.
            compaction_reserve_tokens: Tokens reserved for context compaction.
            memory_injection_enabled: Whether the Agent injects matching Memories.
            tools: Built-in tools available to the Agent.
            approval_in_chat: Tool approval policy for chat Turns.
            approval_in_tasks: Tool approval policy for Task Turns.
            instructions: Agent instructions.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            mcp_connection_ids: MCP Connections attached to the Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            ValueError: provider_id and model are not both supplied when configuring
                an Agent.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
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
                    workspace_tier=workspace_tier,
                    thinking_level=thinking_level,
                    auto_compaction=auto_compaction,
                    compaction_reserve_tokens=compaction_reserve_tokens,
                    memory_injection_enabled=memory_injection_enabled,
                    tools=tools,
                    approval_in_chat=approval_in_chat,
                    approval_in_tasks=approval_in_tasks,
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
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        workspace_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AgentsPage:
        """Fetch one page of Agent records.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            user_id: Caller-defined user identifier.
            workspace_id: Workspace identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of matching records and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/agents",
                query={
                    **_agents_query(user_id, workspace_id),
                    **cursor_limit_query(cursor, limit),
                },
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AgentsPage,
        )

    async def get(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Fetch the requested Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                agent_path(agent_id),
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
        """Fetch MCP attachments for an Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            MCP attachments for the Agent.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{agent_path(agent_id)}/mcp-attachments",
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
        """Update an Agent MCP attachment.

        Args:
            agent_id: Agent identifier.
            mcp_connection_id: MCP Connection identifier.
            forward_user_id: Whether to forward the user identifier to this MCP
                Connection.
            forwarded_metadata_keys: Metadata keys to forward to this MCP Connection.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Updated MCP attachment settings.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "PATCH",
                (
                    f"{agent_path(agent_id)}/mcp-attachments/"
                    f"{path_segment('mcp_connection_id', mcp_connection_id)}"
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
        thinking_level: str | None | _Omitted = OMITTED,
        auto_compaction: bool | _Omitted = OMITTED,
        compaction_reserve_tokens: int | _Omitted = OMITTED,
        memory_injection_enabled: bool | _Omitted = OMITTED,
        tools: Sequence[AgentTool] | _Omitted = OMITTED,
        approval_in_chat: ApprovalPolicyInput | _Omitted = OMITTED,
        approval_in_tasks: ApprovalPolicyInput | _Omitted = OMITTED,
        instructions: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        mcp_connection_ids: Sequence[str] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Agent:
        """Update the provided Agent fields.

        Omitted fields retain server defaults or existing values. Changing
        provider_id requires model. Set both to None to clear them.

        Args:
            agent_id: Agent identifier.
            name: Agent display name, 1 to 80 characters.
            model: Provider model identifier.
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            workspace_id: Workspace identifier.
            thinking_level: Provider-supported reasoning level. None clears the
                setting. Omission retains the current value.
            auto_compaction: Whether the Agent compacts its context automatically.
            compaction_reserve_tokens: Tokens reserved for context compaction.
            memory_injection_enabled: Whether the Agent injects matching Memories.
            tools: Built-in tools available to the Agent.
            approval_in_chat: Tool approval policy for chat Turns.
            approval_in_tasks: Tool approval policy for Task Turns.
            instructions: Agent instructions.
            metadata: Caller-defined JSON metadata.
            mcp_connection_ids: MCP Connections attached to the Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            ValueError: Provider and model changes are inconsistent.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        _validate_agent_update_configuration(model, provider_id)
        body = _agent_body(
            name=name,
            model=model,
            provider_id=provider_id,
            workspace_id=workspace_id,
            thinking_level=thinking_level,
            auto_compaction=auto_compaction,
            compaction_reserve_tokens=compaction_reserve_tokens,
            memory_injection_enabled=memory_injection_enabled,
            tools=tools,
            approval_in_chat=approval_in_chat,
            approval_in_tasks=approval_in_tasks,
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
                agent_path(agent_id),
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
        """Disable the Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{agent_path(agent_id)}/disable",
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
        """Enable the Agent.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{agent_path(agent_id)}/enable",
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
        """Delete the requested Agent.

        Args:
            agent_id: Agent identifier.
            include_artifacts: Whether to include the Agent Artifacts in deletion.
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
                agent_path(agent_id),
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
        """Upload an Agent avatar.

        Paths are opened and closed by the SDK. Caller-owned file objects remain
        open.

        Args:
            agent_id: Agent identifier.
            file: File upload input.
            filename: Filename supplied for the upload.
            content_type: Media type for the upload.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            ValueError: No filename is available for bytes or an unnamed file object.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        with upload_part(
            file,
            filename=filename,
            content_type=content_type,
        ) as files:
            return await self._transport.request(
                _Request(
                    "POST",
                    f"{agent_path(agent_id)}/avatar",
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
        """Remove an Agent avatar.

        Args:
            agent_id: Agent identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Agent details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "DELETE",
                f"{agent_path(agent_id)}/avatar",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            Agent,
        )


class AsyncAgentsResource(AsyncUserAgentsResource):
    async def get_spending_limit(
        self,
        agent_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SpendingLimitResponse:
        """Fetch the Agent model spending limit using tenant authority."""
        return await self._transport.request(
            _Request(
                "GET",
                agent_path(agent_id) + "/spending-limit",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SpendingLimitResponse,
        )

    async def update_spending_limit(
        self,
        agent_id: str,
        *,
        spending_limit: SpendingLimitInput | None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SpendingLimitResponse:
        """Set or disable the Agent model spending limit using tenant authority."""
        return await self._transport.request(
            _Request(
                "PUT",
                agent_path(agent_id) + "/spending-limit",
                json_body=spending_limit_body(spending_limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            SpendingLimitResponse,
        )
