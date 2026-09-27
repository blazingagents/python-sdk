from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence

from ._models import ChatDeliveriesPage, TenantChatDelivery
from ._transport import OMITTED, AsyncTransport, SyncTransport, _Omitted, _Request
from ._types import ChatDeliveryStatus, Timeout


def _chat_deliveries_query(
    status: Sequence[ChatDeliveryStatus] | _Omitted,
    since: str | _Omitted,
    cursor: str | _Omitted,
    limit: int | _Omitted,
) -> dict[str, str | int]:
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
        self._transport = transport

    def list(
        self,
        *,
        status: Sequence[ChatDeliveryStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatDeliveriesPage:
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
        status: Sequence[ChatDeliveryStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[TenantChatDelivery]:
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
        self._transport = transport

    async def list(
        self,
        *,
        status: Sequence[ChatDeliveryStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ChatDeliveriesPage:
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
        status: Sequence[ChatDeliveryStatus] | _Omitted = OMITTED,
        since: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[TenantChatDelivery]:
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
