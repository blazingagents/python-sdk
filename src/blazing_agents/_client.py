from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, Self, TypeVar, cast, overload

import httpx

from ._agents import AsyncAgentsResource, AsyncUserAgentsResource
from ._artifacts import AsyncArtifactsResource
from ._chat import (
    AsyncChatStream,
    chat_request,
    continue_request,
)
from ._chat_connections import AsyncChatConnectionsResource
from ._chat_deliveries import AsyncChatDeliveriesResource
from ._completion import AsyncCompletionStream, generation_request
from ._functions import (
    AsyncFunctionRunner,
    ChatFunction,
    _CallScope,
    function_definitions,
)
from ._mcp_connections import AsyncMcpConnectionsResource
from ._memories import AsyncMemoriesResource
from ._merchant import (
    AsyncMerchantBindingsResource,
    AsyncMerchantConnectionResource,
    AsyncMerchantUsageEventsResource,
)
from ._object import (
    AsyncObjectStream,
    decode_object,
    resolve_output,
)
from ._prompts import AsyncPromptsResource
from ._providers import AsyncProvidersResource
from ._responses import Completion
from ._sessions import AsyncSessionsResource
from ._skills import AsyncAgentSkillsResource
from ._tasks import AsyncTasksResource
from ._tenant import AsyncTenantResource
from ._transport import (
    OMITTED,
    AsyncTransport,
    ResponseObservation,
    _Omitted,
    _TransportConfig,
    decode_completion,
)
from ._types import (
    ChatTrigger,
    JsonSchema,
    JsonValue,
    Timeout,
    ToolApprovalDecisionInput,
)
from ._usage import AsyncUsageResource, AsyncUserUsageResource
from ._version import __version__
from ._workspaces import AsyncWorkspacesResource

if TYPE_CHECKING:
    from typing_extensions import TypeForm
else:
    TypeForm = type

_DEFAULT_BASE_URL = "https://api.blazingagents.com"
_ObjectT = TypeVar("_ObjectT")
_Opaque = object


_SCOPED_USER_ID = re.compile(r"[\x21-\x7e](?:[\x20-\x7e]*[\x21-\x7e])?")


def _scoped_user_id(user_id: str) -> str:
    """Validate an end-user ID for X-BA-User-Id."""
    if len(user_id) > 256 or _SCOPED_USER_ID.fullmatch(user_id) is None:
        msg = (
            "user_id must be printable ASCII, at most 256 characters, with no "
            "leading or trailing spaces"
        )
        raise ValueError(msg)
    return user_id


def _api_key(explicit: str | None) -> str:
    """Resolve an explicit API key or BLAZING_AGENTS_API_KEY."""
    value = (
        explicit if explicit is not None else os.environ.get("BLAZING_AGENTS_API_KEY")
    )
    if not value:
        msg = "An API key is required. Pass api_key or set BLAZING_AGENTS_API_KEY."
        raise ValueError(msg)
    return value


class AsyncAgentClient:
    def __init__(self, transport: AsyncTransport, agent_id: str) -> None:
        """Scope Agent-level operations to one Agent.

        Args:
            transport: Transport used for requests.
            agent_id: Agent identifier.
        """
        self.skills = AsyncAgentSkillsResource(transport, agent_id)


class _AsyncClient(ABC):
    _transport: AsyncTransport

    @abstractmethod
    def _bind_transport(self, transport: AsyncTransport) -> None:
        """Attach the transport and resource clients."""

    def agent(self, agent_id: str) -> AsyncAgentClient:
        """Create a view of Skills attached to one Agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Skill operations scoped to the Agent.
        """
        return AsyncAgentClient(self._transport, agent_id)

    def with_options(self, *, client_request_id: str) -> Self:
        """Create a client view with a default caller correlation ID.

        The view shares the HTTP client and resource configuration.

        Args:
            client_request_id: Caller correlation ID sent as X-Client-Request-Id.

        Returns:
            Client view of the same kind sharing the underlying HTTP client.
        """
        scoped = self.__class__.__new__(self.__class__)
        scoped._bind_transport(
            self._transport.with_client_request_id(client_request_id)
        )
        return scoped

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
            Single-consumer SSE byte stream with the resolved session_id and
                running turn_id.

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
            Single-consumer SSE byte stream with the resolved session_id and
                running turn_id.

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
            Single-consumer SSE byte stream with the resolved session_id and
                running turn_id.

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
                else function_definitions(functions, AsyncFunctionRunner) or OMITTED
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
            Single-consumer SSE byte stream with the resolved session_id and
                running turn_id.

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
                    else function_definitions(functions, AsyncFunctionRunner)
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
            decode_completion,
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

        Consume or aclose the stream, or use its context manager, to release
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
            decode_completion,
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

        Consume or aclose the stream, or use its context manager, to release
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

        Consume or aclose the stream, or use its context manager, to release
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

        Consume or aclose the stream, or use its context manager, to release
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


class AsyncUserClient(_AsyncClient):
    """Client view whose requests act for one end user.

    Create it with AsyncBlazingAgents.for_user. Every request sends
    X-BA-User-Id, so the API limits reads and writes to resources that user owns.
    """

    def __init__(self, transport: AsyncTransport) -> None:
        """Scope every request to the end user the transport names.

        Args:
            transport: Transport scoped to the end user.
        """
        self._bind_transport(transport)

    def _bind_transport(self, transport: AsyncTransport) -> None:
        """Attach the transport and resource clients."""
        self._transport = transport
        self.agents = AsyncUserAgentsResource(transport)
        self.artifacts = AsyncArtifactsResource(transport)
        self.memories = AsyncMemoriesResource(transport)
        self.prompts = AsyncPromptsResource(transport)
        self.sessions = AsyncSessionsResource(transport)
        self.tasks = AsyncTasksResource(transport)
        self.workspaces = AsyncWorkspacesResource(transport)
        self.usage = AsyncUserUsageResource(transport)


class AsyncBlazingAgents(_AsyncClient):
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
        """Create a Blazing Agents API client.

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
            TypeError: http_client is not an httpx.AsyncClient.
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
        self.merchant_connection = AsyncMerchantConnectionResource(transport)
        self.merchant_bindings = AsyncMerchantBindingsResource(transport)
        self.merchant_usage_events = AsyncMerchantUsageEventsResource(transport)

    def for_user(self, user_id: str) -> AsyncUserClient:
        """Create a client view that acts for one end user.

        The view sends X-BA-User-Id on every request and shares the HTTP client.
        It exposes only the resources an end user can own.

        Args:
            user_id: End-user ID from your verified sign-in. Printable ASCII, at
                most 256 characters, with no leading or trailing spaces.

        Returns:
            End-user client view sharing the underlying HTTP client.

        Raises:
            ValueError: user_id is not a valid end-user ID.
        """
        return AsyncUserClient(
            self._transport.with_scope_user_id(_scoped_user_id(user_id))
        )

    async def aclose(self) -> None:
        """Close resources owned by this client."""
        await self._transport.close()

    async def __aenter__(self) -> AsyncBlazingAgents:
        """Return this object for use in a context manager.

        Returns:
            This object.
        """
        return self

    async def __aexit__(self, *_: _Opaque) -> None:
        """Close resources when the context manager exits."""
        await self.aclose()
