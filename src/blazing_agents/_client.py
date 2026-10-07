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
    """Resolve an explicit API key or BLAZING_AGENTS_API_KEY."""
    value = (
        explicit if explicit is not None else os.environ.get("BLAZING_AGENTS_API_KEY")
    )
    if not value:
        msg = "An API key is required. Pass api_key or set BLAZING_AGENTS_API_KEY."
        raise ValueError(msg)
    return value


class AgentClient:
    def __init__(self, transport: SyncTransport, agent_id: str) -> None:
        """Initialize AgentClient.

        Args:
            transport: Transport used for requests.
            agent_id: Agent identifier.
        """
        self.skills = AgentSkillsResource(transport, agent_id)


class AsyncAgentClient:
    def __init__(self, transport: AsyncTransport, agent_id: str) -> None:
        """Initialize AsyncAgentClient.

        Args:
            transport: Transport used for requests.
            agent_id: Agent identifier.
        """
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
        """Initialize BlazingAgents.

        Args:
            api_key: API key. Defaults to BLAZING_AGENTS_API_KEY.
            base_url: API base URL. Trailing slashes are removed.
            timeout: Default HTTP timeout in seconds, an HTTPX timeout, or None.
            default_headers: Headers applied to every request.
            http_client: HTTPX client to reuse. The SDK closes only clients it
                creates.
            on_response: Response observer. Callback exceptions are ignored.

        Raises:
            ValueError: The API key is missing, base_url is empty, or the supplied
                HTTP client has X-Request-Id defaults.
            TypeError: http_client is not the matching sync or async HTTPX client.
        """
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
        """Attach the transport and resource clients."""
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
        """Create a view of Skills attached to one Agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Skill operations scoped to the Agent.
        """
        return AgentClient(self._transport, agent_id)

    def with_options(self, *, client_request_id: str) -> BlazingAgents:
        """Create a client view with a default caller correlation ID.

        The view shares the HTTP client and resource configuration.

        Args:
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.

        Returns:
            Client view sharing the underlying HTTP client.
        """
        scoped = self.__class__.__new__(self.__class__)
        scoped._bind_transport(
            self._transport.with_client_request_id(client_request_id)
        )
        return scoped

    def close(self) -> None:
        """Close resources owned by this client."""
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
    ) -> ChatStream:
        """Submit a message to a new Session and return its byte stream.

        Consume or close the stream to release its HTTP connection. Function handlers
        run only while the stream is consumed.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            message: One message. Provide exactly one of message, messages, or
                prompt_id.
            messages: Nonempty message batch.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            trigger: Submit-message trigger for the new Session.
            message_id: Message identifier for the chat trigger.
            session_id: Session identifier. Omit to create a new Session.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer SSE byte stream with the resolved session_id.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
    ) -> ChatStream:
        """Start or resume a chat Turn and return its byte stream.

        Consume or close the stream to release its HTTP connection. Function handlers
        run only while the stream is consumed.

        Regeneration requires an existing Session. Its message batch contains one
        message.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            session_id: Existing Session identifier.
            message: One message. Provide exactly one of message, messages, or
                prompt_id.
            messages: Nonempty message batch. Regeneration accepts one message.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            trigger: Submit a message or regenerate an existing Session message.
            message_id: Message identifier for the chat trigger.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer SSE byte stream with the resolved session_id.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
        """Start or resume a chat Turn and return its byte stream.

        Consume or close the stream to release its HTTP connection. Function handlers
        run only while the stream is consumed.

        Regeneration requires an existing Session. Its message batch contains one
        message.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            message: One message. Provide exactly one of message, messages, or
                prompt_id.
            messages: Nonempty message batch. Regeneration accepts one message.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            trigger: Submit a message or regenerate an existing Session message.
            message_id: Message identifier for the chat trigger.
            session_id: Session identifier. Omit to create a new Session.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer SSE byte stream with the resolved session_id.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails while opening the stream.
            APITimeoutError: Opening the stream times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
        """Decide a complete approval round and stream the continuing Turn.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            decisions: Decisions for the complete pending approval round.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer SSE byte stream with the resolved session_id.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
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
        """Create a Session-scoped runner factory for supplied functions."""
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
        """Generate completion text with response metadata.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Generated text with its server request_id.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
        """Generate completion text as a single-consumer delta stream.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or close the stream, or use its context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer text delta stream. get_final_text drains
                remaining deltas.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails while opening the stream.
            APITimeoutError: Opening the stream times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
    ) -> _ObjectT:
        """Generate JSON and validate the requested output type.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Validated output_type value, or decoded JSON when json_schema is
                supplied.

        Raises:
            StreamError: The response body read fails after headers arrive.
            ValueError: Prompt, input, or output options conflict or are invalid.
            ObjectJSONDecodeError: The generated text is invalid JSON.
            ObjectTruncationError: The generated JSON is incomplete.
            ObjectValidationError: The JSON does not match output_type.
        """
        ...

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
    ) -> JsonValue:
        """Generate JSON and validate the requested output type.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Validated output_type value, or decoded JSON when json_schema is
                supplied.

        Raises:
            StreamError: The response body read fails after headers arrive.
            ValueError: Prompt, input, or output options conflict or are invalid.
            ObjectJSONDecodeError: The generated text is invalid JSON.
            ObjectTruncationError: The generated JSON is incomplete.
            ObjectValidationError: The JSON does not match output_type.
        """
        ...

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
        """Generate JSON and validate the requested output type.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Validated output_type value, or decoded JSON when json_schema is
                supplied.

        Raises:
            StreamError: The response body read fails after headers arrive.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
            ObjectJSONDecodeError: The generated text is invalid JSON.
            ObjectTruncationError: The generated JSON is incomplete.
            ObjectValidationError: The JSON does not match output_type.
        """
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
    ) -> ObjectStream[_ObjectT]:
        """Generate JSON as raw text deltas with final-object validation.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or close the stream, or use its context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer JSON text stream. get_final_object validates the
                final value.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
    ) -> ObjectStream[JsonValue]:
        """Generate JSON as raw text deltas with final-object validation.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or close the stream, or use its context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer JSON text stream. get_final_object validates the
                final value.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
        """Generate JSON as raw text deltas with final-object validation.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or close the stream, or use its context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer JSON text stream. get_final_object validates the
                final value.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails while opening the stream.
            APITimeoutError: Opening the stream times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
        """Return this object for use in a context manager.

        Returns:
            This object.
        """
        return self

    def __exit__(self, *_: _Opaque) -> None:
        """Close resources when the context manager exits."""
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
        """Initialize AsyncBlazingAgents.

        Args:
            api_key: API key. Defaults to BLAZING_AGENTS_API_KEY.
            base_url: API base URL. Trailing slashes are removed.
            timeout: Default HTTP timeout in seconds, an HTTPX timeout, or None.
            default_headers: Headers applied to every request.
            http_client: HTTPX client to reuse. The SDK closes only clients it
                creates.
            on_response: Response observer. Callback exceptions are ignored.

        Raises:
            ValueError: The API key is missing, base_url is empty, or the supplied
                HTTP client has X-Request-Id defaults.
            TypeError: http_client is not the matching sync or async HTTPX client.
        """
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
        """Attach the transport and resource clients."""
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
        """Create a view of Skills attached to one Agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Async Skill operations scoped to the Agent.
        """
        return AsyncAgentClient(self._transport, agent_id)

    def with_options(self, *, client_request_id: str) -> AsyncBlazingAgents:
        """Create a client view with a default caller correlation ID.

        The view shares the HTTP client and resource configuration.

        Args:
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.

        Returns:
            Async client view sharing the underlying HTTP client.
        """
        scoped = self.__class__.__new__(self.__class__)
        scoped._bind_transport(
            self._transport.with_client_request_id(client_request_id)
        )
        return scoped

    async def aclose(self) -> None:
        """Close resources owned by this client."""
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
    ) -> AsyncChatStream:
        """Submit a message to a new Session and return its byte stream.

        Consume or close the stream to release its HTTP connection. Function handlers
        run only while the stream is consumed.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            message: One message. Provide exactly one of message, messages, or
                prompt_id.
            messages: Nonempty message batch.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            trigger: Submit-message trigger for the new Session.
            message_id: Message identifier for the chat trigger.
            session_id: Session identifier. Omit to create a new Session.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Async single-consumer SSE byte stream with the resolved
                session_id.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
    ) -> AsyncChatStream:
        """Start or resume a chat Turn and return its byte stream.

        Consume or close the stream to release its HTTP connection. Function handlers
        run only while the stream is consumed.

        Regeneration requires an existing Session. Its message batch contains one
        message.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            session_id: Existing Session identifier.
            message: One message. Provide exactly one of message, messages, or
                prompt_id.
            messages: Nonempty message batch. Regeneration accepts one message.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            trigger: Submit a message or regenerate an existing Session message.
            message_id: Message identifier for the chat trigger.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Async single-consumer SSE byte stream with the resolved
                session_id.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
        """Start or resume a chat Turn and return its byte stream.

        Consume or close the stream to release its HTTP connection. Function handlers
        run only while the stream is consumed.

        Regeneration requires an existing Session. Its message batch contains one
        message.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            message: One message. Provide exactly one of message, messages, or
                prompt_id.
            messages: Nonempty message batch. Regeneration accepts one message.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            trigger: Submit a message or regenerate an existing Session message.
            message_id: Message identifier for the chat trigger.
            session_id: Session identifier. Omit to create a new Session.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Async single-consumer SSE byte stream with the resolved
                session_id.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails while opening the stream.
            APITimeoutError: Opening the stream times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
        """Decide a complete approval round and stream the continuing Turn.

        Args:
            agent_id: Agent identifier.
            session_id: Session identifier.
            decisions: Decisions for the complete pending approval round.
            functions: Named functions available for this invocation.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Async single-consumer SSE byte stream with the resolved
                session_id.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
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
        """Create a Session-scoped runner factory for supplied functions."""
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
        """Generate completion text with response metadata.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Generated text with its server request_id.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
        """Generate completion text as a single-consumer delta stream.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or aclose the stream, or use its async context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Async text delta stream. get_final_text drains remaining deltas.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails while opening the stream.
            APITimeoutError: Opening the stream times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
    ) -> _ObjectT:
        """Generate JSON and validate the requested output type.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Validated output_type value, or decoded JSON when json_schema is
                supplied.

        Raises:
            StreamError: The response body read fails after headers arrive.
            ValueError: Prompt, input, or output options conflict or are invalid.
            ObjectJSONDecodeError: The generated text is invalid JSON.
            ObjectTruncationError: The generated JSON is incomplete.
            ObjectValidationError: The JSON does not match output_type.
        """
        ...

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
    ) -> JsonValue:
        """Generate JSON and validate the requested output type.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Validated output_type value, or decoded JSON when json_schema is
                supplied.

        Raises:
            StreamError: The response body read fails after headers arrive.
            ValueError: Prompt, input, or output options conflict or are invalid.
            ObjectJSONDecodeError: The generated text is invalid JSON.
            ObjectTruncationError: The generated JSON is incomplete.
            ObjectValidationError: The JSON does not match output_type.
        """
        ...

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
        """Generate JSON and validate the requested output type.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Validated output_type value, or decoded JSON when json_schema is
                supplied.

        Raises:
            StreamError: The response body read fails after headers arrive.
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
            ObjectJSONDecodeError: The generated text is invalid JSON.
            ObjectTruncationError: The generated JSON is incomplete.
            ObjectValidationError: The JSON does not match output_type.
        """
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
    ) -> AsyncObjectStream[_ObjectT]:
        """Generate JSON as raw text deltas with final-object validation.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or aclose the stream, or use its async context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer JSON text stream. get_final_object validates the
                final value.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
    ) -> AsyncObjectStream[JsonValue]:
        """Generate JSON as raw text deltas with final-object validation.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or aclose the stream, or use its async context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer JSON text stream. get_final_object validates the
                final value.

        Raises:
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
        ...

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
        """Generate JSON as raw text deltas with final-object validation.

        Provide exactly one of prompt or prompt_id. variables requires prompt_id.

        Consume or aclose the stream, or use its async context manager, to release
        the HTTP connection.

        Request errors occur while opening the stream. Iteration or finalization
        can raise StreamError.

        Args:
            agent_id: Agent identifier.
            output_type: Python output type for Pydantic validation. Mutually
                exclusive with json_schema.
            json_schema: Output JSON Schema. Mutually exclusive with output_type.
            prompt: Literal prompt. Provide exactly one of prompt or prompt_id.
            prompt_id: Stored Prompt identifier.
            variables: Template substitutions. Requires prompt_id.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Single-consumer JSON text stream. get_final_object validates the
                final value.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails while opening the stream.
            APITimeoutError: Opening the stream times out.
            ValueError: Prompt, input, or output options conflict or are invalid.
        """
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
        """Return this object for use in a context manager.

        Returns:
            This object.
        """
        return self

    async def __aexit__(self, *_: _Opaque) -> None:
        """Close resources when the context manager exits."""
        await self.aclose()
