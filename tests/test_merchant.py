from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from test_clients import Response, ServerState, loopback

from blazing_agents import AsyncBlazingAgents, BlazingAgents

GUARD: dict[str, Any] = {"enabled": True, "productIds": ["prod_1"], "meterId": None}
CONNECTION: dict[str, Any] = {
    "id": "mch_0123456789abcdef",
    "provider": "polar",
    "environment": "sandbox",
    "status": "active",
    "merchantAccountId": "org_1",
    "keyFragment": "abcd",
    "guard": GUARD,
    "configVersion": 2,
    "createdAt": "2026-10-01T00:00:00.000Z",
    "updatedAt": "2026-10-02T00:00:00.000Z",
}
BINDING: dict[str, Any] = {
    "userId": "user/1",
    "customerId": "cus_1",
    "createdAt": "2026-10-01T00:00:00.000Z",
    "updatedAt": "2026-10-01T00:00:00.000Z",
}
EVENT: dict[str, Any] = {
    "id": "mev_0123456789abcdef",
    "turnId": "turn_0123456789abcdef",
    "connectionId": "mch_0123456789abcdef",
    "provider": "polar",
    "userId": "user/1",
    "customerId": None,
    "agentId": "ag_0123456789abcdef",
    "sessionId": "ss_0123456789abcdef",
    "model": "gpt-5",
    "modelProvider": "openai",
    "inputTokens": 10,
    "outputTokens": 5,
    "totalTokens": 15,
    "turnStatus": "succeeded",
    "startedAt": "2026-10-01T00:00:00.000Z",
    "occurredAt": "2026-10-01T00:00:01.000Z",
    "status": "unmapped",
    "payload": None,
    "attemptCount": 1,
    "attemptGeneration": 0,
    "lastAttemptAt": None,
    "lastErrorCode": "customer_unmapped",
    "acceptedAt": None,
    "workflowIssue": None,
    "nextAction": "bind_and_release",
}
SUMMARY: dict[str, Any] = {
    "counts": {
        "pending": 1,
        "accepted": 2,
        "uncertain": 0,
        "failed": 0,
        "unmapped": 1,
        "incomplete": 0,
        "expired": 0,
        "discarded": 0,
    },
    "lastAcceptedAt": "2026-10-01T00:00:00.000Z",
    "oldestPendingOccurredAt": None,
    "daily": [
        {
            "day": "2026-10-01",
            "acceptedEvents": 2,
            "acceptedTokens": 30,
            "pendingEvents": 1,
        }
    ],
}


def _run(asynchronous: bool, base_url: str, action: Callable[[Any], Any]) -> Any:
    """Run one client call with the sync or async client."""
    if asynchronous:

        async def run_async() -> Any:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                return await action(client)

        return asyncio.run(run_async())
    with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
        return action(client)


def _sent(state: ServerState) -> list[tuple[str, str, Any]]:
    return [
        (
            request.method,
            request.target,
            json.loads(request.body) if request.body else None,
        )
        for request in state.requests
    ]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_connection_lifecycle(asynchronous: bool) -> None:
    with loopback(
        Response(body={"connection": None}),
        Response(body={"connection": CONNECTION}),
        Response(body={"connection": CONNECTION}),
        Response(body={"connection": CONNECTION}),
        Response(body={"connection": CONNECTION}),
        Response(status=204),
    ) as (base_url, state):
        assert (
            _run(asynchronous, base_url, lambda c: c.merchant_connection.get())
        ).connection is None
        created = _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_connection.create(
                provider="polar",
                environment="sandbox",
                credential="polar_secret",
                guard={"enabled": True, "product_ids": ["prod_1"], "meter_id": None},
            ),
        )
        _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_connection.create(
                provider="dodo", environment="live", credential="dodo_secret"
            ),
        )
        _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_connection.update(
                status="disconnected",
                guard={"enabled": False, "product_ids": [], "meter_id": "m_1"},
            ),
        )
        _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_connection.update(credential="rotated"),
        )
        _run(asynchronous, base_url, lambda c: c.merchant_connection.retire())

    connection = created.connection
    assert connection is not None
    assert connection.key_fragment == "abcd"
    assert connection.guard.product_ids == ["prod_1"]
    assert connection.config_version == 2
    assert _sent(state) == [
        ("GET", "/v1/merchant-connection", None),
        (
            "POST",
            "/v1/merchant-connection",
            {
                "provider": "polar",
                "environment": "sandbox",
                "credential": "polar_secret",
                "guard": GUARD,
            },
        ),
        (
            "POST",
            "/v1/merchant-connection",
            {"provider": "dodo", "environment": "live", "credential": "dodo_secret"},
        ),
        (
            "PATCH",
            "/v1/merchant-connection",
            {
                "status": "disconnected",
                "guard": {"enabled": False, "productIds": [], "meterId": "m_1"},
            },
        ),
        ("PATCH", "/v1/merchant-connection", {"credential": "rotated"}),
        ("DELETE", "/v1/merchant-connection", None),
    ]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_bindings(asynchronous: bool) -> None:
    async def collect_async(client: Any) -> list[Any]:
        return [b async for b in client.merchant_bindings.iter(user_id="u", limit=1)]

    with loopback(
        Response(body={"bindings": [BINDING], "nextCursor": "next"}),
        Response(body={"bindings": [], "nextCursor": None}),
        Response(body={"bindings": [BINDING], "nextCursor": "next"}),
        Response(body={"bindings": [BINDING], "nextCursor": None}),
        Response(body={"binding": BINDING}),
        Response(status=204),
    ) as (base_url, state):
        page = _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_bindings.list(user_id="user/1", cursor="c", limit=5),
        )
        _run(asynchronous, base_url, lambda c: c.merchant_bindings.list())
        bindings = _run(
            asynchronous,
            base_url,
            collect_async
            if asynchronous
            else lambda c: list(c.merchant_bindings.iter(user_id="u", limit=1)),
        )
        saved = _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_bindings.put("user/1", customer_id="cus_1"),
        )
        _run(asynchronous, base_url, lambda c: c.merchant_bindings.delete("user/1"))

    assert page.bindings[0].customer_id == "cus_1"
    assert page.next_cursor == "next"
    assert [binding.user_id for binding in bindings] == ["user/1", "user/1"]
    assert saved.binding.user_id == "user/1"
    assert _sent(state) == [
        (
            "GET",
            "/v1/merchant-connection/bindings?userId=user%2F1&cursor=c&limit=5",
            None,
        ),
        ("GET", "/v1/merchant-connection/bindings", None),
        ("GET", "/v1/merchant-connection/bindings?userId=u&limit=1", None),
        ("GET", "/v1/merchant-connection/bindings?userId=u&cursor=next&limit=1", None),
        ("PUT", "/v1/merchant-connection/bindings/user%2F1", {"customerId": "cus_1"}),
        ("DELETE", "/v1/merchant-connection/bindings/user%2F1", None),
    ]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_usage_events(asynchronous: bool) -> None:
    async def collect_async(client: Any) -> list[Any]:
        return [
            e
            async for e in client.merchant_usage_events.iter(status="unmapped", limit=1)
        ]

    event_id = EVENT["id"]
    with loopback(
        Response(body={"events": [EVENT], "nextCursor": None}),
        Response(body={"events": [EVENT], "nextCursor": "next"}),
        Response(body={"events": [], "nextCursor": None}),
        Response(body={"event": EVENT}),
        Response(body={"summary": SUMMARY}),
        Response(body={"summary": SUMMARY}),
        Response(body={"event": EVENT}),
        Response(body={"event": EVENT}),
        Response(body={"event": EVENT}),
    ) as (base_url, state):
        page = _run(
            asynchronous,
            base_url,
            lambda c: c.merchant_usage_events.list(
                status="failed", cursor="c", limit=2
            ),
        )
        events = _run(
            asynchronous,
            base_url,
            collect_async
            if asynchronous
            else lambda c: list(
                c.merchant_usage_events.iter(status="unmapped", limit=1)
            ),
        )
        fetched = _run(
            asynchronous, base_url, lambda c: c.merchant_usage_events.get(event_id)
        )
        summary = _run(
            asynchronous, base_url, lambda c: c.merchant_usage_events.summary(days=7)
        )
        _run(asynchronous, base_url, lambda c: c.merchant_usage_events.summary())
        _run(asynchronous, base_url, lambda c: c.merchant_usage_events.retry(event_id))
        _run(
            asynchronous, base_url, lambda c: c.merchant_usage_events.release(event_id)
        )
        _run(
            asynchronous, base_url, lambda c: c.merchant_usage_events.discard(event_id)
        )

    assert page.events[0].next_action == "bind_and_release"
    assert [event.id for event in events] == [event_id]
    assert fetched.event.total_tokens == 15
    assert summary.summary.counts.accepted == 2
    assert summary.summary.daily[0].accepted_tokens == 30
    assert _sent(state) == [
        ("GET", "/v1/merchant-usage-events?status=failed&cursor=c&limit=2", None),
        ("GET", "/v1/merchant-usage-events?status=unmapped&limit=1", None),
        ("GET", "/v1/merchant-usage-events?status=unmapped&cursor=next&limit=1", None),
        ("GET", f"/v1/merchant-usage-events/{event_id}", None),
        ("GET", "/v1/merchant-usage-events/summary?days=7", None),
        ("GET", "/v1/merchant-usage-events/summary", None),
        ("POST", f"/v1/merchant-usage-events/{event_id}/retry", None),
        ("POST", f"/v1/merchant-usage-events/{event_id}/release", None),
        ("POST", f"/v1/merchant-usage-events/{event_id}/discard", None),
    ]
