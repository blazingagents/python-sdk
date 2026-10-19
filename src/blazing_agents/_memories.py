from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from ._models import (
    MemoriesPage,
    Memory,
    MemoryResponse,
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
from ._wire import agent_path


def _memory_path(agent_id: str, memory_id: str | None = None) -> str:
    """Build the encoded memory endpoint path."""
    path = f"{agent_path(agent_id)}/memories"
    if memory_id is None:
        return path
    return f"{path}/{path_segment('memory_id', memory_id)}"


def _memory_body(
    *,
    text: str,
    user_id: str | _Omitted,
) -> dict[str, object]:
    """Build the memory request body, omitting unspecified fields."""
    body: dict[str, object] = {"text": text}
    return body | drop_omitted(("userId", user_id))


def _memories_query(
    *,
    user_id: str | _Omitted,
    search: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    """Build the memories query, omitting unspecified filters."""
    return drop_omitted(
        ("userId", user_id),
        ("search", search),
        ("cursor", cursor),
        ("limit", limit),
    )


class AsyncMemoriesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Memory operations to the transport.

        Args:
            transport: Transport used for requests.
        """
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
        """Create a Memory.

        Args:
            agent_id: Agent identifier.
            text: Memory text to store.
            user_id: Caller-defined user identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Memory response details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                _memory_path(agent_id),
                json_body=_memory_body(text=text, user_id=user_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(MemoryResponse),
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
        """Fetch one page of Memory records.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            search: Search filter sent to the API.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
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
            decode_model(MemoriesPage),
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
        """Iterate Memory records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            agent_id: Agent identifier.
            user_id: Caller-defined user identifier.
            search: Search filter sent to the API.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            Memory records in server order.
        """
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
        """Fetch the requested Memory.

        Args:
            agent_id: Agent identifier.
            memory_id: Memory identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Memory response details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _memory_path(agent_id, memory_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(MemoryResponse),
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
        """Update the provided Memory fields.

        Args:
            agent_id: Agent identifier.
            memory_id: Memory identifier.
            text: Memory text to store.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Memory response details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "PATCH",
                _memory_path(agent_id, memory_id),
                json_body={"text": text},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(MemoryResponse),
        )

    async def delete(
        self,
        *,
        agent_id: str,
        memory_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Memory.

        Args:
            agent_id: Agent identifier.
            memory_id: Memory identifier.
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
                _memory_path(agent_id, memory_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )
