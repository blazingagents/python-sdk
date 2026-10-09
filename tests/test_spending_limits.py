from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError
from test_clients import Response, loopback

from blazing_agents import (
    APIStatusError,
    AsyncBlazingAgents,
    BlazingAgents,
    SpendingLimit,
    SpendingLimitStopDetails,
    SpendingLimitStopEvent,
)

AGENT_ID = "ag_0123456789abcdef"
CONFIG: dict[str, Any] = {
    "amountUsd": 25.123456,
    "resetStartDate": "2026-10-09",
    "resetInterval": "monthly",
}
STATUS: dict[str, Any] = {
    "spendingLimit": CONFIG,
    "period": {
        "startsAt": "2026-10-09T00:00:00Z",
        "endsAt": "2026-11-09T00:00:00Z",
        "spentUsd": 5,
        "reservedUsd": 2,
        "availableUsd": 18.123456,
    },
    "nextResetAt": "2026-11-09T00:00:00Z",
    "scheduleChangeAt": "2026-11-09T00:00:00Z",
}
DISABLED: dict[str, Any] = {
    "spendingLimit": None,
    "period": None,
    "nextResetAt": None,
    "scheduleChangeAt": None,
}
STOP_DETAILS: dict[str, Any] = {
    "scope": "both",
    "reason": "reserved",
    "spentUsd": 5,
    "reservedUsd": 20,
    "availableUsd": 0,
    "nextResetAt": "2026-11-09T00:00:00Z",
}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_spending_limit_requests_and_statuses(asynchronous: bool) -> None:
    with loopback(
        *[Response(body=body) for body in [STATUS, STATUS, DISABLED] * 2]
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=base_url) as c:
                agent = await c.agents.get_spending_limit(AGENT_ID)
                assert agent.spending_limit is not None
                assert agent.spending_limit.amount_usd == 25.123456
                assert agent.spending_limit.reset_start_date == date(2026, 10, 9)
                assert agent.period is not None
                assert agent.period.reserved_usd == 2
                assert agent.next_reset_at is not None
                assert agent.schedule_change_at == agent.next_reset_at
                await c.agents.update_spending_limit(
                    AGENT_ID,
                    spending_limit={
                        "amount_usd": 25.123456,
                        "reset_start_date": "2026-10-09",
                        "reset_interval": "monthly",
                    },
                    extra_headers={"X-Test": "agent"},
                    timeout=2.0,
                )
                disabled = await c.agents.update_spending_limit(
                    AGENT_ID, spending_limit=None
                )
                assert disabled.spending_limit is None
                assert disabled.period is None
                assert disabled.next_reset_at is None
                tenant = await c.tenant.get_spending_limit()
                assert tenant.spending_limit is not None
                assert tenant.spending_limit.reset_interval == "monthly"
                await c.tenant.update_spending_limit(
                    spending_limit={
                        "amount_usd": 25.123456,
                        "reset_start_date": "2026-10-09",
                        "reset_interval": "monthly",
                    }
                )
                assert (
                    await c.tenant.update_spending_limit(spending_limit=None)
                ).period is None

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as c:
                agent = c.agents.get_spending_limit(AGENT_ID)
                assert agent.spending_limit is not None
                assert agent.spending_limit.amount_usd == 25.123456
                assert agent.spending_limit.reset_start_date == date(2026, 10, 9)
                assert agent.period is not None
                assert agent.period.reserved_usd == 2
                assert agent.next_reset_at is not None
                assert agent.schedule_change_at == agent.next_reset_at
                c.agents.update_spending_limit(
                    AGENT_ID,
                    spending_limit={
                        "amount_usd": 25.123456,
                        "reset_start_date": "2026-10-09",
                        "reset_interval": "monthly",
                    },
                    extra_headers={"X-Test": "agent"},
                    timeout=2.0,
                )
                disabled = c.agents.update_spending_limit(AGENT_ID, spending_limit=None)
                assert disabled.spending_limit is None
                assert disabled.period is None
                assert disabled.next_reset_at is None
                tenant = c.tenant.get_spending_limit()
                assert tenant.spending_limit is not None
                assert tenant.spending_limit.reset_interval == "monthly"
                c.tenant.update_spending_limit(
                    spending_limit={
                        "amount_usd": 25.123456,
                        "reset_start_date": "2026-10-09",
                        "reset_interval": "monthly",
                    }
                )
                assert (
                    c.tenant.update_spending_limit(spending_limit=None).period is None
                )

    assert [(r.method, r.target) for r in state.requests] == [
        ("GET", f"/v1/agents/{AGENT_ID}/spending-limit"),
        ("PUT", f"/v1/agents/{AGENT_ID}/spending-limit"),
        ("PUT", f"/v1/agents/{AGENT_ID}/spending-limit"),
        ("GET", "/v1/tenant/spending-limit"),
        ("PUT", "/v1/tenant/spending-limit"),
        ("PUT", "/v1/tenant/spending-limit"),
    ]
    assert state.requests[0].body == b""
    assert state.requests[3].body == b""
    for index in [1, 4]:
        assert json.loads(state.requests[index].body) == {"spendingLimit": CONFIG}
    for index in [2, 5]:
        assert json.loads(state.requests[index].body) == {"spendingLimit": None}
    assert state.requests[1].headers["X-Test"] == "agent"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_spending_limit_errors_preserve_details(asynchronous: bool) -> None:
    with loopback(
        Response(
            status=429,
            body={
                "error": {
                    "code": "model_spending_limit_exceeded",
                    "message": "Model spending is paused.",
                    "details": STOP_DETAILS,
                }
            },
        )
    ) as (base_url, _):

        async def run_async() -> None:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=base_url) as c:
                with pytest.raises(APIStatusError) as raised:
                    await c.completion(agent_id=AGENT_ID, prompt="Hello")
                assert raised.value.status_code == 429
                assert raised.value.code == "model_spending_limit_exceeded"
                assert raised.value.details == STOP_DETAILS

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as c:
                with pytest.raises(APIStatusError) as raised:
                    c.completion(agent_id=AGENT_ID, prompt="Hello")
                assert raised.value.status_code == 429
                assert raised.value.code == "model_spending_limit_exceeded"
                assert raised.value.details == STOP_DETAILS


@pytest.mark.parametrize("asynchronous", [False, True])
def test_invalid_spending_limit_response_is_rejected(asynchronous: bool) -> None:
    invalid = {**STATUS, "period": {**STATUS["period"], "availableUsd": -1}}
    with loopback(Response(body=invalid)) as (base_url, _):

        async def run_async() -> None:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=base_url) as c:
                with pytest.raises(ValidationError):
                    await c.tenant.get_spending_limit()

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as c:
                with pytest.raises(ValidationError):
                    c.tenant.get_spending_limit()


@pytest.mark.parametrize(
    "amount", [0, -1, 0.0000001, 1_000_000_001, float("nan"), float("inf")]
)
def test_invalid_amounts_are_rejected(amount: float) -> None:
    with pytest.raises(ValidationError):
        SpendingLimit.model_validate_json(json.dumps({**CONFIG, "amountUsd": amount}))


@pytest.mark.parametrize("value", ["2026-02-30", "2026-1-1", "2026-01-31T00:00:00Z"])
def test_invalid_reset_dates_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        SpendingLimit.model_validate_json(
            json.dumps({**CONFIG, "resetStartDate": value})
        )


def test_typed_stop_details_decode() -> None:
    details = SpendingLimitStopDetails.model_validate_json(json.dumps(STOP_DETAILS))
    assert details.scope == "both"
    assert details.reason == "reserved"
    assert details.spent_usd == 5
    assert details.next_reset_at is not None


@pytest.mark.parametrize("asynchronous", [False, True])
def test_spending_limit_update_requires_explicit_value(asynchronous: bool) -> None:
    async def run_async() -> None:
        async with AsyncBlazingAgents(api_key="ba_test") as client:
            with pytest.raises(TypeError):
                await client.tenant.update_spending_limit()  # type: ignore[call-arg]

    if asynchronous:
        asyncio.run(run_async())
    else:
        with BlazingAgents(api_key="ba_test") as client:
            with pytest.raises(TypeError):
                client.tenant.update_spending_limit()  # type: ignore[call-arg]


def test_typed_stop_event_decode() -> None:
    event = SpendingLimitStopEvent.model_validate_json(
        json.dumps(
            {
                "type": "data-model-spending-limit",
                "data": {"code": "model_spending_limit_exceeded", **STOP_DETAILS},
                "transient": True,
            }
        )
    )
    assert event.type == "data-model-spending-limit"
    assert event.transient is True
    assert event.data.code == "model_spending_limit_exceeded"
    assert event.data.scope == "both"
    assert event.data.reason == "reserved"
    assert event.data.next_reset_at is not None


@pytest.mark.parametrize("transient", [True, 1, 1.0, False])
@pytest.mark.parametrize("json_input", [False, True])
def test_stop_event_transient_requires_true_boolean(
    transient: object, json_input: bool
) -> None:
    payload = {
        "type": "data-model-spending-limit",
        "data": {
            "code": "model_spending_limit_exceeded",
            **STOP_DETAILS,
            "nextResetAt": None,
        },
        "transient": transient,
    }

    if transient is True:
        event = (
            SpendingLimitStopEvent.model_validate_json(json.dumps(payload))
            if json_input
            else SpendingLimitStopEvent.model_validate(payload)
        )
        assert event.transient is True
    else:
        with pytest.raises(ValidationError):
            if json_input:
                SpendingLimitStopEvent.model_validate_json(json.dumps(payload))
            else:
                SpendingLimitStopEvent.model_validate(payload)


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "data-other"},
        {"transient": False},
        {"data": {"code": "other", **STOP_DETAILS}},
        {"data": {"code": "model_spending_limit_exceeded"}},
        {"extra": True},
        {
            "data": {
                "code": "model_spending_limit_exceeded",
                **STOP_DETAILS,
                "extra": True,
            }
        },
    ],
)
def test_invalid_stop_events_are_rejected(patch: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SpendingLimitStopEvent.model_validate_json(
            json.dumps(
                {
                    "type": "data-model-spending-limit",
                    "data": {"code": "model_spending_limit_exceeded", **STOP_DETAILS},
                    "transient": True,
                    **patch,
                }
            )
        )


@pytest.mark.parametrize("asynchronous", [False, True])
def test_chat_preserves_spending_stop_event_bytes(asynchronous: bool) -> None:
    payload = (
        "data: "
        + json.dumps(
            {
                "type": "data-model-spending-limit",
                "data": {"code": "model_spending_limit_exceeded", **STOP_DETAILS},
                "transient": True,
            }
        )
        + "\n\ndata: [DONE]\n\n"
    ).encode()
    with loopback(
        Response(
            chunks=(payload[:40], payload[40:]),
            headers={
                "content-type": "text/event-stream",
                "location": f"/v1/agents/{AGENT_ID}/sessions/ss_0123456789abcdef",
            },
        )
    ) as (base_url, _):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                stream = await client.chat(
                    agent_id=AGENT_ID,
                    message={
                        "role": "user",
                        "parts": [{"type": "text", "text": "Hello"}],
                    },
                )
                assert b"".join([chunk async for chunk in stream]) == payload

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                stream = client.chat(
                    agent_id=AGENT_ID,
                    message={
                        "role": "user",
                        "parts": [{"type": "text", "text": "Hello"}],
                    },
                )
                assert b"".join(stream) == payload
