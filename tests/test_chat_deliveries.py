from __future__ import annotations

import asyncio
from typing import Any

import pytest
from test_clients import Response, loopback

from blazing_agents import AsyncBlazingAgents, BlazingAgents

DELIVERY: dict[str, Any] = {
    "id": "cd_0123456789abcdef",
    "kind": "reply",
    "status": "confirmed",
    "attempt": 1,
    "credentialVersion": 2,
    "representation": "text",
    "diagnostic": None,
    "receipts": [{"attempt": 1, "messageId": "412"}],
    "sessionId": "ss_0123456789abcdef",
    "messageId": "message-1",
    "approvalId": None,
    "threadId": "thread-1",
    "createdAt": "2026-09-13T12:00:00Z",
    "updatedAt": "2026-09-13T12:00:01Z",
    "connectionId": "cc_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "platform": "slack",
}

EMPTY_PAGE: dict[str, Any] = {"data": [], "nextCursor": None}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_list_serializes_filters_and_parses_page(asynchronous: bool) -> None:
    with loopback(
        Response(body={"data": [DELIVERY], "nextCursor": "next"}),
        Response(body=EMPTY_PAGE),
        Response(body=EMPTY_PAGE),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                page = await client.chat_deliveries.list(
                    status=["failed", "ambiguous"],
                    since="2026-09-01T00:00:00.000Z",
                    cursor="cursor-1",
                    limit=10,
                )
                delivery = page.data[0]
                assert delivery.id == DELIVERY["id"]
                assert delivery.connection_id == DELIVERY["connectionId"]
                assert delivery.agent_id == DELIVERY["agentId"]
                assert delivery.platform == "slack"
                assert delivery.receipts == DELIVERY["receipts"]
                assert page.next_cursor == "next"
                await client.chat_deliveries.list(status=[])
                await client.chat_deliveries.list()

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                page = client.chat_deliveries.list(
                    status=["failed", "ambiguous"],
                    since="2026-09-01T00:00:00.000Z",
                    cursor="cursor-1",
                    limit=10,
                )
                delivery = page.data[0]
                assert delivery.id == DELIVERY["id"]
                assert delivery.connection_id == DELIVERY["connectionId"]
                assert delivery.agent_id == DELIVERY["agentId"]
                assert delivery.platform == "slack"
                assert delivery.receipts == DELIVERY["receipts"]
                assert page.next_cursor == "next"
                client.chat_deliveries.list(status=[])
                client.chat_deliveries.list()

    assert [request.target for request in state.requests] == [
        "/v1/chat-deliveries?status=failed%2Cambiguous&since=2026-09-01T00%3A00%3A00.000Z&cursor=cursor-1&limit=10",
        "/v1/chat-deliveries",
        "/v1/chat-deliveries",
    ]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_iter_follows_cursors(asynchronous: bool) -> None:
    with loopback(
        Response(body={"data": [DELIVERY], "nextCursor": "next"}),
        Response(body={"data": [DELIVERY], "nextCursor": None}),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                deliveries = [
                    delivery
                    async for delivery in client.chat_deliveries.iter(
                        status=["failed"], limit=1
                    )
                ]
                assert [delivery.id for delivery in deliveries] == [
                    DELIVERY["id"],
                    DELIVERY["id"],
                ]

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                deliveries = list(
                    client.chat_deliveries.iter(status=["failed"], limit=1)
                )
                assert [delivery.id for delivery in deliveries] == [
                    DELIVERY["id"],
                    DELIVERY["id"],
                ]

    assert [request.target for request in state.requests] == [
        "/v1/chat-deliveries?status=failed&limit=1",
        "/v1/chat-deliveries?status=failed&cursor=next&limit=1",
    ]
