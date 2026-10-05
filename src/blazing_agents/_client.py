from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast, overload

import httpx

from ._chat import (
    AsyncChatStream,
    ChatStream,
    chat_request,
    continue_request,
)
from ._chat_connections import AsyncChatConnectionsResource, ChatConnectionsResource
from ._chat_deliveries import AsyncChatDeliveriesResource, ChatDeliveriesResource
from ._completion import AsyncCompletionStream, CompletionStream, generation_request
from ._functions import (
    AsyncFunctionRunner,
    ChatFunction,
    SyncFunctionRunner,
    _CallScope,
    function_definitions,
)
from ._object import (
    AsyncObjectStream,
    ObjectStream,
    decode_object,
    resolve_output,
)
from ._resources import (
    AgentSkillsResource,
    AgentsResource,
    ArtifactsResource,
    AsyncAgentSkillsResource,
    AsyncAgentsResource,
    AsyncArtifactsResource,
    AsyncMcpConnectionsResource,
    AsyncMemoriesResource,
    AsyncPromptsResource,
    AsyncProvidersResource,
    AsyncSessionsResource,
    AsyncTasksResource,
    AsyncTenantResource,
    AsyncUsageResource,
    AsyncWorkspacesResource,
    McpConnectionsResource,
    MemoriesResource,
    PromptsResource,
    ProvidersResource,
    SessionsResource,
    TasksResource,
    TenantResource,
    UsageResource,
    WorkspacesResource,
)
from ._responses import Completion
from ._transport import (
    OMITTED,
    RESPONSE_OBJECT_TEXT,
    RESPONSE_TEXT,
    AsyncTransport,
    ResponseObservation,
    SyncTransport,
    _Omitted,
    _TransportConfig,
)
from ._types import (
    ChatTrigger,
    JsonSchema,
    JsonValue,
    Timeout,
    ToolApprovalDecisionInput,
)
from ._version import __version__

if TYPE_CHECKING:
    from typing_extensions import TypeForm
else:
    TypeForm = type

_DEFAULT_BASE_URL = "https://api.blazingagents.com"
_ObjectT = TypeVar("_ObjectT")
_Opaque = object


def _api_key(explicit: str | None) -> str:
    value = (
        explicit if explicit is not None else os.environ.get("BLAZING_AGENTS_API_KEY")
    )
    if not value:
        msg = "An API key is required. Pass api_key or set BLAZING_AGENTS_API_KEY."
        raise ValueError(msg)
    return value


class AgentClient:
    def __init__(self, transport: SyncTransport, agent_id: str) -> None:
        self.skills = AgentSkillsResource(transport, agent_id)


class AsyncAgentClient:
    def __init__(self, transport: AsyncTransport, agent_id: str) -> None:
        self.skills = AsyncAgentSkillsResource(transport, agent_id)


class BlazingAgents:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: Timeout = 60.0,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
        on_response: Callable[[ResponseObservation], None] | None = None,
    ) -> None:
        if http_client is not None and not isinstance(http_client, httpx.Client):
            msg = "http_client must be an httpx.Client"
            raise TypeError(msg)
        if http_client is not None and "x-request-id" in http_client.headers:
            msg = (
                "http_client default headers must not contain X-Request-Id; "
                "it is server-owned"
            )
            raise ValueError(msg)
        config = _TransportConfig(
            api_key=_api_key(api_key),
            base_url=base_url,
            default_headers=default_headers,
            timeout=timeout,
            user_agent=f"blazing_agents/{__version__}",
            on_response=on_response,
            client_request_id=None,
        )
        self._bind_transport(SyncTransport(config, http_client))

    def _bind_transport(self, transport: SyncTransport) -> None:
        self._transport = transport
        self.agents = AgentsResource(transport)
        self.artifacts = ArtifactsResource(transport)
        self.providers = ProvidersResource(transport)
        self.chat_connections = ChatConnectionsResource(transport)
        self.chat_deliveries = ChatDeliveriesResource(transport)
        self.mcp_connections = McpConnectionsResource(transport)
        self.memories = MemoriesResource(transport)
        self.prompts = PromptsResource(transport)
        self.sessions = SessionsResource(transport)
        self.tasks = TasksResource(transport)
        self.workspaces = WorkspacesResource(transport)
        self.tenant = TenantResource(transport)
        self.usage = UsageResource(transport)

    def agent(self, agent_id: str) -> AgentClient:
        return AgentClient(self._transport, agent_id)

    def with_options(self, *, client_request_id: str) -> BlazingAgents:
        scoped = self.__class__.__new__(self.__class__)
        scoped._bind_transport(
            self._transport.with_client_request_id(client_request_id)
        )
        return scoped

    def close(self) -> None:
        self._transport.close()

    @overload
    def chat(
        self,
        *,
        agent_id: str,
        message: dict[str, _Opaque] | _Omitted = OMITTED,
        messages: list[dict[str, _Opaque]] | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        trigger: Literal["submit-message"] | _Omitted = OMITTED,
        message_id: str | _Omitted = OMITTED,
        session_id: _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatStream: ...

    @overload
    def chat(
        self,
        *,
        agent_id: str,
        session_id: str,
        message: dict[str, _Opaque] | _Omitted = OMITTED,
        messages: list[dict[str, _Opaque]] | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        trigger: ChatTrigger | _Omitted = OMITTED,
        message_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatStream: ...

    def chat(
        self,
        *,
        agent_id: str,
        message: dict[str, _Opaque] | _Omitted = OMITTED,
        messages: list[dict[str, _Opaque]] | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        trigger: ChatTrigger | _Omitted = OMITTED,
        message_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatStream:
        request, resolved_session_id = chat_request(
            agent_id=agent_id,
            message=message,
            messages=messages,
            prompt_id=prompt_id,
            variables=variables,
            trigger=trigger,
            message_id=message_id,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata,
            functions=(
                OMITTED
                if isinstance(functions, _Omitted)
                else function_definitions(functions, asynchronous=False) or OMITTED
            ),
            client_request_id=client_request_id,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return self._transport.stream(
            request,
            lambda response: ChatStream(
                response,
                resolved_session_id,
                self._function_runner(agent_id, functions, extra_headers),
            ),
        )

    def continue_chat(
        self,
        *,
        agent_id: str,
        session_id: str,
        decisions: Sequence[ToolApprovalDecisionInput],
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatStream:
        """Decide a complete approval round and stream the continuing Turn."""
        return self._transport.stream(
            continue_request(
                agent_id=agent_id,
                session_id=session_id,
                decisions=decisions,
                functions=(
                    OMITTED
                    if isinstance(functions, _Omitted)
                    else function_definitions(functions, asynchronous=False)
                ),
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            lambda response: ChatStream(
                response,
                session_id,
                self._function_runner(agent_id, functions, extra_headers),
            ),
        )

    def _function_runner(
        self,
        agent_id: str,
        functions: Mapping[str, ChatFunction] | _Omitted,
        extra_headers: Mapping[str, str] | None,
    ) -> Callable[[str], SyncFunctionRunner] | None:
        if isinstance(functions, _Omitted):
            return None
        return lambda session_id: SyncFunctionRunner(
            self._transport,
            _CallScope(agent_id, session_id, extra_headers),
            functions,
        )

    def completion(
        self,
        *,
        agent_id: str,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Completion:
        return self._transport.request(
            generation_request(
                agent_id=agent_id,
                output={"type": "text"},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_TEXT,
        )

    def completion_stream(
        self,
        *,
        agent_id: str,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> CompletionStream:
        return self._transport.stream(
            generation_request(
                agent_id=agent_id,
                output={"type": "text"},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            CompletionStream,
        )

    @overload
    def object(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[_ObjectT],
        json_schema: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> _ObjectT: ...

    @overload
    def object(
        self,
        *,
        agent_id: str,
        json_schema: JsonSchema,
        output_type: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> JsonValue: ...

    def object(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[Any] | None | _Omitted = OMITTED,
        json_schema: JsonSchema | None | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Any:
        adapter, schema = resolve_output(
            cast(type[Any] | None | _Omitted, output_type),
            json_schema,
        )
        response = self._transport.request(
            generation_request(
                agent_id=agent_id,
                output={"type": "object", "schema": schema},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_OBJECT_TEXT,
        )
        return decode_object(response, response._response, adapter)

    @overload
    def object_stream(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[_ObjectT],
        json_schema: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ObjectStream[_ObjectT]: ...

    @overload
    def object_stream(
        self,
        *,
        agent_id: str,
        json_schema: JsonSchema,
        output_type: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ObjectStream[JsonValue]: ...

    def object_stream(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[Any] | None | _Omitted = OMITTED,
        json_schema: JsonSchema | None | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ObjectStream[Any]:
        adapter, schema = resolve_output(
            cast(type[Any] | None | _Omitted, output_type),
            json_schema,
        )
        return self._transport.stream(
            generation_request(
                agent_id=agent_id,
                output={"type": "object", "schema": schema},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            lambda response: ObjectStream(response, adapter),
        )

    def __enter__(self) -> BlazingAgents:
        return self

    def __exit__(self, *_: _Opaque) -> None:
        self.close()


class AsyncBlazingAgents:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: Timeout = 60.0,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
        on_response: Callable[[ResponseObservation], None] | None = None,
    ) -> None:
        if http_client is not None and not isinstance(http_client, httpx.AsyncClient):
            msg = "http_client must be an httpx.AsyncClient"
            raise TypeError(msg)
        if http_client is not None and "x-request-id" in http_client.headers:
            msg = (
                "http_client default headers must not contain X-Request-Id; "
                "it is server-owned"
            )
            raise ValueError(msg)
        config = _TransportConfig(
            api_key=_api_key(api_key),
            base_url=base_url,
            default_headers=default_headers,
            timeout=timeout,
            user_agent=f"blazing_agents/{__version__}",
            on_response=on_response,
            client_request_id=None,
        )
        self._bind_transport(AsyncTransport(config, http_client))

    def _bind_transport(self, transport: AsyncTransport) -> None:
        self._transport = transport
        self.agents = AsyncAgentsResource(transport)
        self.artifacts = AsyncArtifactsResource(transport)
        self.providers = AsyncProvidersResource(transport)
        self.chat_connections = AsyncChatConnectionsResource(transport)
        self.chat_deliveries = AsyncChatDeliveriesResource(transport)
        self.mcp_connections = AsyncMcpConnectionsResource(transport)
        self.memories = AsyncMemoriesResource(transport)
        self.prompts = AsyncPromptsResource(transport)
        self.sessions = AsyncSessionsResource(transport)
        self.tasks = AsyncTasksResource(transport)
        self.workspaces = AsyncWorkspacesResource(transport)
        self.tenant = AsyncTenantResource(transport)
        self.usage = AsyncUsageResource(transport)

    def agent(self, agent_id: str) -> AsyncAgentClient:
        return AsyncAgentClient(self._transport, agent_id)

    def with_options(self, *, client_request_id: str) -> AsyncBlazingAgents:
        scoped = self.__class__.__new__(self.__class__)
        scoped._bind_transport(
            self._transport.with_client_request_id(client_request_id)
        )
        return scoped

    async def aclose(self) -> None:
        await self._transport.close()

    @overload
    async def chat(
        self,
        *,
        agent_id: str,
        message: dict[str, _Opaque] | _Omitted = OMITTED,
        messages: list[dict[str, _Opaque]] | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        trigger: Literal["submit-message"] | _Omitted = OMITTED,
        message_id: str | _Omitted = OMITTED,
        session_id: _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncChatStream: ...

    @overload
    async def chat(
        self,
        *,
        agent_id: str,
        session_id: str,
        message: dict[str, _Opaque] | _Omitted = OMITTED,
        messages: list[dict[str, _Opaque]] | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        trigger: ChatTrigger | _Omitted = OMITTED,
        message_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncChatStream: ...

    async def chat(
        self,
        *,
        agent_id: str,
        message: dict[str, _Opaque] | _Omitted = OMITTED,
        messages: list[dict[str, _Opaque]] | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        trigger: ChatTrigger | _Omitted = OMITTED,
        message_id: str | _Omitted = OMITTED,
        session_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncChatStream:
        request, resolved_session_id = chat_request(
            agent_id=agent_id,
            message=message,
            messages=messages,
            prompt_id=prompt_id,
            variables=variables,
            trigger=trigger,
            message_id=message_id,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata,
            functions=(
                OMITTED
                if isinstance(functions, _Omitted)
                else function_definitions(functions, asynchronous=True) or OMITTED
            ),
            client_request_id=client_request_id,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return await self._transport.stream(
            request,
            lambda response: AsyncChatStream(
                response,
                resolved_session_id,
                self._function_runner(agent_id, functions, extra_headers),
            ),
        )

    async def continue_chat(
        self,
        *,
        agent_id: str,
        session_id: str,
        decisions: Sequence[ToolApprovalDecisionInput],
        functions: Mapping[str, ChatFunction] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncChatStream:
        """Decide a complete approval round and stream the continuing Turn."""
        return await self._transport.stream(
            continue_request(
                agent_id=agent_id,
                session_id=session_id,
                decisions=decisions,
                functions=(
                    OMITTED
                    if isinstance(functions, _Omitted)
                    else function_definitions(functions, asynchronous=True)
                ),
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            lambda response: AsyncChatStream(
                response,
                session_id,
                self._function_runner(agent_id, functions, extra_headers),
            ),
        )

    def _function_runner(
        self,
        agent_id: str,
        functions: Mapping[str, ChatFunction] | _Omitted,
        extra_headers: Mapping[str, str] | None,
    ) -> Callable[[str], AsyncFunctionRunner] | None:
        if isinstance(functions, _Omitted):
            return None
        return lambda session_id: AsyncFunctionRunner(
            self._transport,
            _CallScope(agent_id, session_id, extra_headers),
            functions,
        )

    async def completion(
        self,
        *,
        agent_id: str,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Completion:
        return await self._transport.request(
            generation_request(
                agent_id=agent_id,
                output={"type": "text"},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_TEXT,
        )

    async def completion_stream(
        self,
        *,
        agent_id: str,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncCompletionStream:
        return await self._transport.stream(
            generation_request(
                agent_id=agent_id,
                output={"type": "text"},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            AsyncCompletionStream,
        )

    @overload
    async def object(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[_ObjectT],
        json_schema: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> _ObjectT: ...

    @overload
    async def object(
        self,
        *,
        agent_id: str,
        json_schema: JsonSchema,
        output_type: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> JsonValue: ...

    async def object(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[Any] | None | _Omitted = OMITTED,
        json_schema: JsonSchema | None | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Any:
        adapter, schema = resolve_output(
            cast(type[Any] | None | _Omitted, output_type),
            json_schema,
        )
        response = await self._transport.request(
            generation_request(
                agent_id=agent_id,
                output={"type": "object", "schema": schema},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            RESPONSE_OBJECT_TEXT,
        )
        return decode_object(response, response._response, adapter)

    @overload
    async def object_stream(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[_ObjectT],
        json_schema: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncObjectStream[_ObjectT]: ...

    @overload
    async def object_stream(
        self,
        *,
        agent_id: str,
        json_schema: JsonSchema,
        output_type: None = None,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncObjectStream[JsonValue]: ...

    async def object_stream(
        self,
        *,
        agent_id: str,
        output_type: TypeForm[Any] | None | _Omitted = OMITTED,
        json_schema: JsonSchema | None | _Omitted = OMITTED,
        prompt: str | _Omitted = OMITTED,
        prompt_id: str | _Omitted = OMITTED,
        variables: dict[str, str] | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, _Opaque] | _Omitted = OMITTED,
        client_request_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncObjectStream[Any]:
        adapter, schema = resolve_output(
            cast(type[Any] | None | _Omitted, output_type),
            json_schema,
        )
        return await self._transport.stream(
            generation_request(
                agent_id=agent_id,
                output={"type": "object", "schema": schema},
                prompt=prompt,
                prompt_id=prompt_id,
                variables=variables,
                user_id=user_id,
                metadata=metadata,
                client_request_id=client_request_id,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            lambda response: AsyncObjectStream(response, adapter),
        )

    async def __aenter__(self) -> AsyncBlazingAgents:
        return self

    async def __aexit__(self, *_: _Opaque) -> None:
        await self.aclose()
