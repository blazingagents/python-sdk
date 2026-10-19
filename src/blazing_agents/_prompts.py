from __future__ import annotations

from collections.abc import Mapping

from ._models import (
    Prompt,
    PromptsPage,
)
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    decode_none,
    drop_omitted,
    path_segment,
)
from ._types import (
    Timeout,
)
from ._wire import cursor_limit_query


def _prompt_path(prompt_id: str) -> str:
    """Build the encoded prompt endpoint path."""
    return f"/v1/prompts/{path_segment('prompt_id', prompt_id)}"


def _prompt_body(
    *,
    name: str | _Omitted,
    template: str | _Omitted,
    agent_id: str | None | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
) -> dict[str, object]:
    """Build the prompt request body, omitting unspecified fields."""
    return drop_omitted(
        ("name", name),
        ("template", template),
        ("agentId", agent_id),
        ("userId", user_id),
        ("metadata", metadata),
    )


class AsyncPromptsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Prompt operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        template: str,
        agent_id: str | None | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        """Create a Prompt.

        Args:
            name: Prompt display name, 1 to 80 characters.
            template: Prompt template text.
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            metadata: Caller-defined JSON metadata.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Prompt details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/prompts",
                json_body=_prompt_body(
                    name=name,
                    template=template,
                    agent_id=agent_id,
                    user_id=user_id,
                    metadata=metadata,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Prompt),
        )

    async def list(
        self,
        *,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        agent_id: str | _Omitted = OMITTED,
        user_id: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> PromptsPage:
        """Fetch one page of Prompt records.

        Args:
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
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
                "/v1/prompts",
                query=drop_omitted(("userId", user_id), ("agentId", agent_id))
                | cursor_limit_query(cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(PromptsPage),
        )

    async def get(
        self,
        *,
        prompt_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        """Fetch the requested Prompt.

        Args:
            prompt_id: Stored Prompt identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Prompt details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _prompt_path(prompt_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Prompt),
        )

    async def update(
        self,
        *,
        prompt_id: str,
        agent_id: str | None | _Omitted = OMITTED,
        name: str | _Omitted = OMITTED,
        template: str | _Omitted = OMITTED,
        metadata: dict[str, object] | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Prompt:
        """Update the provided Prompt fields.

        Args:
            prompt_id: Stored Prompt identifier.
            agent_id: Agent identifier.
            name: Prompt display name, 1 to 80 characters.
            template: Prompt template text.
            metadata: Caller-defined JSON metadata.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Prompt details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        body = _prompt_body(
            name=name,
            template=template,
            agent_id=agent_id,
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
            decode_model(Prompt),
        )

    async def delete(
        self,
        *,
        prompt_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Prompt.

        Args:
            prompt_id: Stored Prompt identifier.
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
                _prompt_path(prompt_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )
