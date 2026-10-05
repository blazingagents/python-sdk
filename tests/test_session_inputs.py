from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from pydantic import ValidationError
from test_clients import Response, loopback

from blazing_agents import (
    AsyncBlazingAgents,
    BlazingAgents,
    ChatSteerConsumedEvent,
    SessionActivity,
    SessionInput,
    SessionInputResponse,
    SessionInputsPage,
    SessionStopResponse,
)

AGENT = "ag_0123456789abcdef"
SESSION = "ss_0123456789abcdef"
TURN = "turn_0123456789abcdef"
BASE = f"/v1/agents/{AGENT}/sessions/{SESSION}"
MESSAGE: dict[str, Any] = {
    "id": "message-1",
    "role": "user",
    "parts": [{"type": "text", "text": "Compare costs"}],
}
ACTIVITY = {"state": "running", "turnId": TURN}


def receipt(**overrides: Any) -> dict[str, Any]:
    return {
        "requestId": "draft/1 a",
        "sequence": 1,
        "message": MESSAGE,
        "state": "accepted",
        "turnId": TURN,
        "createdAt": "2026-10-04T12:00:00Z",
        "updatedAt": "2026-10-04T12:00:00Z",
        "reason": None,
        **overrides,
    }


@pytest.mark.parametrize("asynchronous", [False, True])
def test_steer_receipts_and_immediate_stop(asynchronous: bool) -> None:
    with loopback(
        Response(status=202, body={"data": receipt(), "activity": ACTIVITY}),
        Response(
            body={
                "data": [receipt(state="not_placed", reason="turn_finished")],
                "activity": ACTIVITY,
                "nextCursor": None,
            }
        ),
        Response(
            body={
                "stoppedTurnId": TURN,
                "activity": {"state": "stopping", "turnId": TURN},
            }
        ),
    ) as (url, state):

        async def run() -> list[Any]:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=url) as client:
                return [
                    await client.sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id="draft/1 a",
                        message=MESSAGE,
                    ),
                    await client.sessions.inputs(
                        agent_id=AGENT,
                        session_id=SESSION,
                        include_completed=True,
                        cursor="c1",
                        limit=50,
                    ),
                    await client.sessions.stop(
                        agent_id=AGENT, session_id=SESSION, turn_id=TURN
                    ),
                ]

        if asynchronous:
            results = asyncio.run(run())
        else:
            with BlazingAgents(api_key="ba_test", base_url=url) as client:
                results = [
                    client.sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id="draft/1 a",
                        message=MESSAGE,
                    ),
                    client.sessions.inputs(
                        agent_id=AGENT,
                        session_id=SESSION,
                        include_completed=True,
                        cursor="c1",
                        limit=50,
                    ),
                    client.sessions.stop(
                        agent_id=AGENT, session_id=SESSION, turn_id=TURN
                    ),
                ]
    assert [(r.method, r.target) for r in state.requests] == [
        ("POST", f"{BASE}/inputs"),
        ("GET", f"{BASE}/inputs?includeCompleted=true&cursor=c1&limit=50"),
        ("POST", f"{BASE}/stop"),
    ]
    assert json.loads(state.requests[0].body) == {
        "requestId": "draft/1 a",
        "message": MESSAGE,
    }
    assert json.loads(state.requests[2].body) == {"turnId": TURN}
    assert isinstance(results[0], SessionInputResponse)
    assert isinstance(results[1], SessionInputsPage)
    assert isinstance(results[2], SessionStopResponse)
    assert results[0].data.turn_id == TURN
    assert results[1].data[0].state == "not_placed"
    assert results[2].activity.state == "stopping"


@pytest.mark.parametrize("value", ["", ".", ".."])
def test_invalid_request_identity(value: str) -> None:
    with BlazingAgents(api_key="ba_test") as client:
        with pytest.raises(ValueError):
            client.sessions.submit_input(
                agent_id=AGENT, session_id=SESSION, request_id=value, message=MESSAGE
            )


@pytest.mark.parametrize(
    "state", ["accepted", "delivered", "committed", "not_placed", "uncertain"]
)
def test_receipt_states_and_removed_fields(state: str) -> None:
    value = SessionInput.model_validate_json(
        json.dumps(receipt(state=state, mode="queue", consumedAt=None))
    )
    assert value.state == state
    assert not hasattr(value, "mode")
    assert not hasattr(value, "consumed_at")


@pytest.mark.parametrize(
    "overrides",
    [
        {"state": "consumed"},
        {"turnId": None},
        {"reason": "deleted"},
        {"message": {**MESSAGE, "role": "assistant"}},
    ],
)
def test_invalid_receipts(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SessionInput.model_validate_json(json.dumps(receipt(**overrides)))


def test_activity_and_consumed_event_contract() -> None:
    activity = SessionActivity.model_validate({**ACTIVITY, "reason": "failed"})
    assert not hasattr(activity, "reason")
    with pytest.raises(ValidationError):
        SessionActivity.model_validate({"state": "paused", "turnId": None})
    event = ChatSteerConsumedEvent.model_validate(
        {
            "type": "data-ba-steer-consumed",
            "transient": True,
            "data": {
                "requestId": "r1",
                "turnId": TURN,
                "sequence": 1,
                "message": MESSAGE,
            },
        }
    )
    assert event.data.message.id == "message-1"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_batches_and_steer_events_preserve_wire_order(asynchronous: bool) -> None:
    messages: list[dict[str, Any]] = [MESSAGE, {**MESSAGE, "id": "message-2"}]
    event = {
        "type": "data-ba-steer-consumed",
        "transient": True,
        "data": {"requestId": "r1", "turnId": TURN, "sequence": 1, "message": MESSAGE},
    }
    raw = b"data: " + json.dumps(event).encode() + b"\n\ndata: [DONE]\n\n"
    with loopback(Response(raw_body=raw)) as (url, state):

        async def run() -> bytes:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=url) as client:
                stream = await client.chat(
                    agent_id=AGENT, session_id=SESSION, messages=messages
                )
                return b"".join([chunk async for chunk in stream])

        if asynchronous:
            output = asyncio.run(run())
        else:
            with BlazingAgents(api_key="ba_test", base_url=url) as client:
                output = b"".join(
                    client.chat(agent_id=AGENT, session_id=SESSION, messages=messages)
                )
    assert output == raw
    assert json.loads(state.requests[0].body) == {"messages": messages}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"messages": []},
        {"message": MESSAGE, "messages": [MESSAGE]},
        {"messages": [MESSAGE], "prompt_id": "prompt_1"},
        {
            "messages": [MESSAGE, {**MESSAGE, "id": "m2"}],
            "trigger": "regenerate-message",
        },
    ],
)
def test_chat_rejects_ambiguous_or_empty_batches(kwargs: dict[str, Any]) -> None:
    with BlazingAgents(api_key="ba_test") as client:
        with pytest.raises(ValueError):
            client.chat(agent_id=AGENT, session_id=SESSION, **kwargs)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_continuation_omits_functions_and_preserves_correlation(
    asynchronous: bool,
) -> None:
    with loopback(Response(raw_body=b"data: [DONE]\n\n")) as (url, state):

        async def run() -> None:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=url) as client:
                stream = await client.continue_chat(
                    agent_id=AGENT,
                    session_id=SESSION,
                    decisions=[
                        {"approval_id": "a1", "approved": False, "reason": "No"}
                    ],
                    client_request_id="attempt",
                )
                assert (
                    b"".join([chunk async for chunk in stream]) == b"data: [DONE]\n\n"
                )

        if asynchronous:
            asyncio.run(run())
        else:
            with BlazingAgents(api_key="ba_test", base_url=url) as client:
                stream = client.continue_chat(
                    agent_id=AGENT,
                    session_id=SESSION,
                    decisions=[
                        {"approval_id": "a1", "approved": False, "reason": "No"}
                    ],
                    client_request_id="attempt",
                )
                assert b"".join(stream) == b"data: [DONE]\n\n"
    assert len(state.requests) == 1
    assert state.requests[0].target == f"{BASE}/tool-approvals/continue"
    assert state.requests[0].headers["x-client-request-id"] == "attempt"
    assert json.loads(state.requests[0].body) == {
        "decisions": [{"approvalId": "a1", "approved": False, "reason": "No"}]
    }


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("code", ["steer_not_available", "input_idempotency_conflict"])
def test_steer_refusal_is_visible_without_followup(
    code: str, asynchronous: bool
) -> None:
    from blazing_agents import APIStatusError

    with loopback(
        Response(status=409, body={"error": {"code": code, "message": code}})
    ) as (url, state):

        async def run() -> None:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=url) as client:
                with pytest.raises(APIStatusError) as failure:
                    await client.sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id="r1",
                        message=MESSAGE,
                    )
                assert failure.value.code == code

        if asynchronous:
            asyncio.run(run())
        else:
            with BlazingAgents(api_key="ba_test", base_url=url) as client:
                with pytest.raises(APIStatusError) as failure:
                    client.sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id="r1",
                        message=MESSAGE,
                    )
                assert failure.value.code == code
    assert len(state.requests) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
def test_default_receipt_listing_sends_no_options(asynchronous: bool) -> None:
    with loopback(
        Response(
            body={
                "data": [],
                "nextCursor": None,
                "activity": {"state": "idle", "turnId": None},
            }
        )
    ) as (url, state):

        async def run() -> None:
            async with AsyncBlazingAgents(api_key="ba_test", base_url=url) as client:
                assert (
                    await client.sessions.inputs(agent_id=AGENT, session_id=SESSION)
                ).data == []

        if asynchronous:
            asyncio.run(run())
        else:
            with BlazingAgents(api_key="ba_test", base_url=url) as client:
                assert (
                    client.sessions.inputs(agent_id=AGENT, session_id=SESSION).data
                    == []
                )
    assert state.requests[0].target == f"{BASE}/inputs"


@pytest.mark.parametrize("request_id", [".", "..", "", "x" * 129])
def test_receipt_and_event_reject_invalid_request_ids(request_id: str) -> None:
    with pytest.raises(ValidationError):
        SessionInput.model_validate_json(json.dumps(receipt(requestId=request_id)))
    with pytest.raises(ValidationError):
        ChatSteerConsumedEvent.model_validate(
            {
                "type": "data-ba-steer-consumed",
                "transient": True,
                "data": {
                    "requestId": request_id,
                    "turnId": TURN,
                    "sequence": 1,
                    "message": MESSAGE,
                },
            }
        )
