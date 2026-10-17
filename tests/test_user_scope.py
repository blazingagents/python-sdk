from __future__ import annotations

import asyncio
import json
import warnings
from typing import Any

import pytest
from test_clients import TASK, Response, loopback

from blazing_agents import (
    AsyncBlazingAgents,
    AsyncUserClient,
    BlazingAgents,
    UserClient,
)

TOTALS: dict[str, Any] = {
    "inputTokens": 3,
    "outputTokens": 2,
    "requestCount": 1,
    "durationMs": 40,
}
SESSION_USAGE: dict[str, Any] = {
    "data": [{"sessionId": "ss_0123456789abcdef", "totals": TOTALS}]
}
TENANT_ONLY = (
    "providers",
    "chat_connections",
    "chat_deliveries",
    "mcp_connections",
    "tenant",
    "merchant_connection",
    "merchant_bindings",
    "merchant_usage_events",
)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_for_user_scopes_every_request(asynchronous: bool) -> None:
    with loopback(
        Response(body=SESSION_USAGE),
        Response(body=SESSION_USAGE),
        Response(body={"buckets": [], "totals": TOTALS}),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                user = client.for_user("tenant/User 1")
                assert isinstance(user, AsyncUserClient)
                usage = await user.usage.sessions(
                    ["ss_0123456789abcdef"], from_="2026-10-01", to="2026-10-31"
                )
                assert usage.data[0].totals.input_tokens == 3
                await user.usage.sessions(
                    ["ss_0123456789abcdef"],
                    extra_headers={"X-BA-User-Id": "someone-else"},
                )
                traced = user.with_options(client_request_id="trace-1")
                assert isinstance(traced, AsyncUserClient)
                await traced.usage.get()
                for name in TENANT_ONLY:
                    assert not hasattr(user, name)

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                user = client.for_user("tenant/User 1")
                assert isinstance(user, UserClient)
                usage = user.usage.sessions(
                    ["ss_0123456789abcdef"], from_="2026-10-01", to="2026-10-31"
                )
                assert usage.data[0].totals.input_tokens == 3
                user.usage.sessions(
                    ["ss_0123456789abcdef"],
                    extra_headers={"X-BA-User-Id": "someone-else"},
                )
                traced = user.with_options(client_request_id="trace-1")
                assert isinstance(traced, UserClient)
                traced.usage.get()
                for name in TENANT_ONLY:
                    assert not hasattr(user, name)

    assert [request.headers["x-ba-user-id"] for request in state.requests] == [
        "tenant/User 1",
        "tenant/User 1",
        "tenant/User 1",
    ]
    assert state.requests[2].headers["x-client-request-id"] == "trace-1"
    assert [(r.method, r.target) for r in state.requests] == [
        ("POST", "/v1/usage/sessions"),
        ("POST", "/v1/usage/sessions"),
        ("GET", "/v1/usage"),
    ]
    assert json.loads(state.requests[0].body) == {
        "sessionIds": ["ss_0123456789abcdef"],
        "from": "2026-10-01",
        "to": "2026-10-31",
    }
    assert json.loads(state.requests[1].body) == {"sessionIds": ["ss_0123456789abcdef"]}


def test_tenant_client_sends_no_user_scope() -> None:
    with loopback(Response(body=SESSION_USAGE)) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            client.for_user("user-1")
            client.usage.sessions(["ss_0123456789abcdef"])

    assert "x-ba-user-id" not in state.requests[0].headers


@pytest.mark.parametrize("user_id", ["", " user", "user ", "user\n", "ü", "x" * 257])
def test_for_user_rejects_invalid_ids(user_id: str) -> None:
    client = BlazingAgents(api_key="ba_test")
    async_client = AsyncBlazingAgents(api_key="ba_test")
    with pytest.raises(ValueError, match="printable ASCII"):
        client.for_user(user_id)
    with pytest.raises(ValueError, match="printable ASCII"):
        async_client.for_user(user_id)
    client.close()
    asyncio.run(async_client.aclose())


def test_for_user_accepts_boundary_ids() -> None:
    with BlazingAgents(api_key="ba_test") as client:
        client.for_user("a")
        client.for_user("a b")
        client.for_user("x" * 256)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_task_create_sends_idempotency_key(asynchronous: bool) -> None:
    created = {"task": TASK, "runId": None}
    with loopback(Response(body=created), Response(body=created)) as (
        base_url,
        state,
    ):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                await client.tasks.create(
                    agent_id=TASK["agentId"],
                    name="Digest",
                    prompt="Summarize",
                    idempotency_key="create-1",
                )
                await client.tasks.create(
                    agent_id=TASK["agentId"], name="Digest", prompt="Summarize"
                )

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                client.tasks.create(
                    agent_id=TASK["agentId"],
                    name="Digest",
                    prompt="Summarize",
                    idempotency_key="create-1",
                )
                client.tasks.create(
                    agent_id=TASK["agentId"], name="Digest", prompt="Summarize"
                )

    bodies = [json.loads(request.body) for request in state.requests]
    assert bodies[0]["idempotencyKey"] == "create-1"
    assert "idempotencyKey" not in bodies[1]


def test_task_create_rejects_blank_idempotency_key() -> None:
    with BlazingAgents(api_key="ba_test") as client:
        with pytest.raises(ValueError, match="must not be blank"):
            client.tasks.create(
                agent_id=TASK["agentId"],
                name="Digest",
                prompt="Summarize",
                idempotency_key=" ",
            )


@pytest.mark.parametrize("asynchronous", [False, True])
def test_user_client_reads_one_agents_usage(asynchronous: bool) -> None:
    with loopback(Response(body={"buckets": [], "totals": TOTALS})) as (
        base_url,
        state,
    ):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                usage = await client.for_user("user-1").usage.get_for_agent(
                    "ag_0123456789abcdef", group_by="model"
                )
                assert usage.totals.input_tokens == 3

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                usage = client.for_user("user-1").usage.get_for_agent(
                    "ag_0123456789abcdef", group_by="model"
                )
                assert usage.totals.input_tokens == 3

    request = state.requests[0]
    assert (request.method, request.target) == (
        "GET",
        "/v1/agents/ag_0123456789abcdef/usage?groupBy=model",
    )
    assert request.headers["x-ba-user-id"] == "user-1"


DISABLED_LIMIT: dict[str, Any] = {
    "spendingLimit": None,
    "period": None,
    "nextResetAt": None,
}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_user_client_spending_limits_warn_deprecated(asynchronous: bool) -> None:
    with loopback(
        Response(body=DISABLED_LIMIT),
        Response(body=DISABLED_LIMIT),
        Response(body=DISABLED_LIMIT),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                user = client.for_user("user-1")
                with pytest.warns(DeprecationWarning, match="tenant client"):
                    await user.agents.get_spending_limit("ag_0123456789abcdef")
                with pytest.warns(DeprecationWarning, match="tenant client"):
                    await user.agents.update_spending_limit(
                        "ag_0123456789abcdef", spending_limit=None
                    )
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    await client.agents.get_spending_limit("ag_0123456789abcdef")

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                user = client.for_user("user-1")
                with pytest.warns(DeprecationWarning, match="tenant client"):
                    user.agents.get_spending_limit("ag_0123456789abcdef")
                with pytest.warns(DeprecationWarning, match="tenant client"):
                    user.agents.update_spending_limit(
                        "ag_0123456789abcdef", spending_limit=None
                    )
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    client.agents.get_spending_limit("ag_0123456789abcdef")

    assert [(r.method, r.target) for r in state.requests] == [
        ("GET", "/v1/agents/ag_0123456789abcdef/spending-limit"),
        ("PUT", "/v1/agents/ag_0123456789abcdef/spending-limit"),
        ("GET", "/v1/agents/ag_0123456789abcdef/spending-limit"),
    ]
