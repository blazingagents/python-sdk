from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence

from ._models import ChatDeliveriesPage, TenantChatDelivery
from ._transport import OMITTED, AsyncTransport, SyncTransport, _Omitted, _Request
from ._types import ChatDeliveryListStatus, Timeout


def _chat_deliveries_query(
    status: Sequence[ChatDeliveryListStatus] | _Omitted,
    since: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
    """Build the chat deliveries query, omitting unspecified filters."""
    query: dict[str, str | int] = {}
    if not isinstance(status, _Omitted) and status:
        # One comma-separated parameter carries the multi-value filter.
        query["status"] = ",".join(status)
    for wire_name, value in (
        ("since", since),
        ("cursor", cursor),
        ("limit", limit),
    ):
        if not isinstance(value, _Omitted):
            query[wire_name] = value
    return query


class ChatDeliveriesResource:
    def __init__(self, transport: SyncTransport) -> None:
        """Bind Chat Delivery operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    def list(
        self,
        *,
        status: Sequence[ChatDeliveryListStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatDeliveriesPage:
        """Fetch one page of Chat Delivery records.

        Args:
            status: Status filter.
            since: Lower bound for the list query.
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
        return self._transport.request(
            _Request(
                "GET",
                "/v1/chat-deliveries",
                query=_chat_deliveries_query(status, since, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatDeliveriesPage,
        )

    def iter(
        self,
        *,
        status: Sequence[ChatDeliveryListStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[TenantChatDelivery]:
        """Iterate Chat Delivery records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            status: Status filter.
            since: Lower bound for the list query.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            TenantChatDelivery records in server order.
        """
        next_cursor = cursor
        while True:
            page = self.list(
                status=status,
                since=since,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor


class AsyncChatDeliveriesResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Chat Delivery operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def list(
        self,
        *,
        status: Sequence[ChatDeliveryListStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatDeliveriesPage:
        """Fetch one page of Chat Delivery records.

        Args:
            status: Status filter.
            since: Lower bound for the list query.
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
                "/v1/chat-deliveries",
                query=_chat_deliveries_query(status, since, cursor, limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            ChatDeliveriesPage,
        )

    async def iter(
        self,
        *,
        status: Sequence[ChatDeliveryListStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[TenantChatDelivery]:
        """Iterate Chat Delivery records across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            status: Status filter.
            since: Lower bound for the list query.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            TenantChatDelivery records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                status=status,
                since=since,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for delivery in page.data:
                yield delivery
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor
