from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from test_chat_functions import (
    CALL_ID,
    DONE,
    HEARTBEAT,
    TEXT,
    FakePlatform,
    Order,
    Wait,
    drain,
    get_order,
    ready,
)
from test_clients import Response, loopback

from blazing_agents import (
    APIStatusError,
    AsyncBlazingAgents,
    BlazingAgents,
    FunctionContext,
    SessionActivityResponse,
    SessionInputResponse,
    SessionInputsPage,
    SessionStopResponse,
)
from blazing_agents._resources import SessionsResource

AGENT = "ag_0123456789abcdef"
SESSION = "ss_0123456789abcdef"
TURN = "turn_0123456789abcdef"
NEXT_TURN = "turn_fedcba9876543210"
BASE = f"/v1/agents/{AGENT}/sessions/{SESSION}"
MESSAGE: dict[str, Any] = {
    "id": "message-1",
    "role": "user",
    "parts": [{"type": "text", "text": "Please also compare costs"}],
}
Call = Callable[[SessionsResource], object]
RUNNING: dict[str, Any] = {"state": "running", "turnId": TURN, "reason": None}
IDLE: dict[str, Any] = {"state": "idle", "turnId": None, "reason": None}


def receipt(**overrides: Any) -> dict[str, Any]:
    return {
        "requestId": "draft/1 a",
        "sequence": 1,
        "message": MESSAGE,
        "mode": "queue",
        "state": "accepted",
        "turnId": None,
        "createdAt": "2026-10-04T12:00:00Z",
        "updatedAt": "2026-10-04T12:00:00Z",
        "consumedAt": None,
        "reason": None,
        **overrides,
    }


def error(code: str) -> Response:
    return Response(status=409, body={"error": {"code": code, "message": code}})


@pytest.mark.parametrize("asynchronous", [False, True])
def test_input_lifecycle_round_trips_contract(asynchronous: bool) -> None:
    accepted = {"data": receipt(), "activity": RUNNING}
    steer = receipt(mode="steer")
    deleted = receipt(state="cancelled", reason="deleted")
    with loopback(
        Response(status=202, body=accepted),
        Response(status=202, body=accepted),
        Response(body={"data": [receipt()], "nextCursor": "c2", "activity": RUNNING}),
        Response(body={"data": steer, "activity": RUNNING}),
        Response(body={"data": deleted, "activity": RUNNING}),
        Response(body={"stoppedTurnId": TURN, "activity": IDLE}),
        Response(body={"activity": IDLE}),
    ) as (base_url, state):
        request_id = "draft/1 a"

        async def run_async() -> list[object]:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                sessions = client.sessions
                return [
                    await sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id=request_id,
                        message=MESSAGE,
                    ),
                    await sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id=request_id,
                        message=MESSAGE,
                    ),
                    await sessions.inputs(
                        agent_id=AGENT,
                        session_id=SESSION,
                        include_completed=True,
                        cursor="c1",
                        limit=50,
                    ),
                    await sessions.promote_input(
                        agent_id=AGENT, session_id=SESSION, request_id=request_id
                    ),
                    await sessions.delete_input(
                        agent_id=AGENT, session_id=SESSION, request_id=request_id
                    ),
                    await sessions.stop(
                        agent_id=AGENT, session_id=SESSION, turn_id=TURN
                    ),
                    await sessions.resume_inputs(agent_id=AGENT, session_id=SESSION),
                ]

        if asynchronous:
            results = asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                sessions = client.sessions
                results = [
                    sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id=request_id,
                        message=MESSAGE,
                    ),
                    sessions.submit_input(
                        agent_id=AGENT,
                        session_id=SESSION,
                        request_id=request_id,
                        message=MESSAGE,
                    ),
                    sessions.inputs(
                        agent_id=AGENT,
                        session_id=SESSION,
                        include_completed=True,
                        cursor="c1",
                        limit=50,
                    ),
                    sessions.promote_input(
                        agent_id=AGENT, session_id=SESSION, request_id=request_id
                    ),
                    sessions.delete_input(
                        agent_id=AGENT, session_id=SESSION, request_id=request_id
                    ),
                    sessions.stop(agent_id=AGENT, session_id=SESSION, turn_id=TURN),
                    sessions.resume_inputs(agent_id=AGENT, session_id=SESSION),
                ]

    encoded = f"{BASE}/inputs/draft%2F1%20a"
    assert [(r.method, r.target) for r in state.requests] == [
        ("POST", f"{BASE}/inputs"),
        ("POST", f"{BASE}/inputs"),
        ("GET", f"{BASE}/inputs?includeCompleted=true&cursor=c1&limit=50"),
        ("POST", f"{encoded}/promote"),
        ("DELETE", encoded),
        ("POST", f"{BASE}/stop"),
        ("POST", f"{BASE}/inputs/resume"),
    ]
    submit = {"requestId": request_id, "message": MESSAGE}
    assert [json.loads(r.body) for r in state.requests[:2]] == [submit, submit]
    assert [r.body for r in (*state.requests[2:5], state.requests[6])] == [b""] * 4
    assert json.loads(state.requests[5].body) == {"turnId": TURN}

    first, retry, page, promoted, withdrawn, stopped, resumed = results
    assert isinstance(first, SessionInputResponse)
    assert isinstance(page, SessionInputsPage)
    assert isinstance(promoted, SessionInputResponse)
    assert isinstance(withdrawn, SessionInputResponse)
    assert isinstance(stopped, SessionStopResponse)
    assert isinstance(resumed, SessionActivityResponse)
    assert first == retry
    assert first.data.request_id == request_id
    assert first.data.sequence == 1
    assert first.data.message.id == "message-1"
    assert first.activity.state == "running"
    assert first.activity.turn_id == TURN
    assert page.data[0].state == "accepted"
    assert page.next_cursor == "c2"
    assert promoted.data.mode == "steer"
    assert promoted.data.sequence == 1
    assert withdrawn.data.state == "cancelled"
    assert withdrawn.data.reason == "deleted"
    assert stopped.stopped_turn_id == TURN
    assert stopped.activity.state == "idle"
    assert resumed.activity.state == "idle"


def test_steer_submission_and_default_listing_send_only_given_fields() -> None:
    delivered = receipt(
        mode="steer", state="consumed", turnId=TURN, consumedAt="2026-10-04T12:00:01Z"
    )
    with (
        loopback(
            Response(status=202, body={"data": delivered, "activity": RUNNING}),
            Response(body={"data": [], "nextCursor": None, "activity": IDLE}),
        ) as (base_url, state),
        BlazingAgents(api_key="ba_test", base_url=base_url) as client,
    ):
        submitted = client.sessions.submit_input(
            agent_id=AGENT,
            session_id=SESSION,
            request_id="steer-1",
            message=MESSAGE,
            when_busy="steer",
        )
        page = client.sessions.inputs(agent_id=AGENT, session_id=SESSION)

    assert json.loads(state.requests[0].body) == {
        "requestId": "steer-1",
        "message": MESSAGE,
        "whenBusy": "steer",
    }
    assert state.requests[1].target == f"{BASE}/inputs"
    assert submitted.data.turn_id == TURN
    assert submitted.data.consumed_at is not None
    assert page.data == []
    assert page.activity.state == "idle"


CONFLICTS: list[tuple[str, Call]] = [
    (
        "input_idempotency_conflict",
        lambda s: s.submit_input(
            agent_id=AGENT,
            session_id=SESSION,
            request_id="draft-1",
            message={**MESSAGE, "parts": [{"type": "text", "text": "changed"}]},
        ),
    ),
    (
        "input_not_pending",
        lambda s: s.delete_input(
            agent_id=AGENT, session_id=SESSION, request_id="draft-1"
        ),
    ),
    (
        "input_not_pending",
        lambda s: s.promote_input(
            agent_id=AGENT, session_id=SESSION, request_id="draft-1"
        ),
    ),
    (
        "session_busy",
        lambda s: s.stop(agent_id=AGENT, session_id=SESSION, turn_id=TURN),
    ),
    (
        "session_busy",
        lambda s: s.resume_inputs(agent_id=AGENT, session_id=SESSION),
    ),
]


@pytest.mark.parametrize(("code", "call"), CONFLICTS)
def test_conflicts_surface_contract_error_codes(code: str, call: Call) -> None:
    with (
        loopback(error(code)) as (base_url, state),
        BlazingAgents(api_key="ba_test", base_url=base_url) as client,
        pytest.raises(APIStatusError) as raised,
    ):
        call(client.sessions)
    assert raised.value.status_code == 409
    assert raised.value.code == code
    assert len(state.requests) == 1


EMPTY_REQUEST_IDS: list[Call] = [
    lambda s: s.submit_input(
        agent_id=AGENT, session_id=SESSION, request_id="", message=MESSAGE
    ),
    lambda s: s.promote_input(agent_id=AGENT, session_id=SESSION, request_id=""),
    lambda s: s.delete_input(agent_id=AGENT, session_id=SESSION, request_id=""),
]


@pytest.mark.parametrize("call", EMPTY_REQUEST_IDS)
def test_empty_request_id_is_rejected_before_any_request(call: Call) -> None:
    with (
        loopback() as (base_url, state),
        BlazingAgents(api_key="ba_test", base_url=base_url) as client,
        pytest.raises(ValueError, match="request_id"),
    ):
        call(client.sessions)
    assert state.requests == []


@pytest.mark.parametrize(
    "body",
    [
        {"data": receipt(state="queued"), "activity": RUNNING},
        {"data": receipt(sequence=0), "activity": RUNNING},
        {"data": receipt(), "activity": {**RUNNING, "turnId": "tr_0123456789abcdef"}},
        {"data": receipt(requestId="x" * 129), "activity": RUNNING},
    ],
)
def test_malformed_receipts_are_rejected(body: dict[str, Any]) -> None:
    with (
        loopback(Response(status=202, body=body)) as (base_url, _),
        BlazingAgents(api_key="ba_test", base_url=base_url) as client,
        pytest.raises(ValidationError),
    ):
        client.sessions.submit_input(
            agent_id=AGENT, session_id=SESSION, request_id="draft-1", message=MESSAGE
        )


def test_stop_response_may_report_the_next_drained_turn() -> None:
    running_next = {"state": "running", "turnId": NEXT_TURN, "reason": None}
    with (
        loopback(Response(body={"stoppedTurnId": TURN, "activity": running_next})) as (
            base_url,
            _,
        ),
        BlazingAgents(api_key="ba_test", base_url=base_url) as client,
    ):
        stopped = client.sessions.stop(agent_id=AGENT, session_id=SESSION, turn_id=TURN)
    assert stopped.stopped_turn_id == TURN
    assert stopped.activity.turn_id == NEXT_TURN


INPUT_TURN = f"{BASE}/input-turns/{TURN}"
GET_ORDER = {
    "getOrder": {
        "description": "Get one order",
        "inputSchema": Order.model_json_schema(),
    }
}


def test_run_inputs_admits_queue_with_functions_and_executes_them() -> None:
    platform = FakePlatform([HEARTBEAT, ready(), Wait(CALL_ID), TEXT, DONE])
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.run_inputs(
            agent_id=AGENT,
            session_id=SESSION,
            functions={"getOrder": get_order(executions)},
        )
        assert stream.session_id == SESSION
        assert b"".join(stream) == HEARTBEAT + TEXT + DONE

    run = platform.requests[0]
    assert (run.method, run.path) == ("POST", f"{BASE}/inputs/run")
    assert run.body == {"functions": GET_ORDER}
    assert [order for order, _ in executions] == [Order(order_id="o1")]
    assert len(platform.bodies("/claim")) == 1


def test_async_run_inputs_without_functions_sends_empty_body() -> None:
    async def exercise() -> None:
        platform = FakePlatform([HEARTBEAT, TEXT, DONE])
        async with platform.async_client() as client:
            stream = await client.run_inputs(agent_id=AGENT, session_id=SESSION)
            assert await drain(stream) == [HEARTBEAT, TEXT, DONE]
        assert platform.requests[0].body == {}
        assert platform.requests[0].path == f"{BASE}/inputs/run"

    asyncio.run(exercise())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_client_join_input_turn_executes_functions(asynchronous: bool) -> None:
    platform = FakePlatform([HEARTBEAT, ready(), Wait(CALL_ID), TEXT, DONE])
    executions: list[tuple[Order, FunctionContext]] = []
    functions = {"getOrder": get_order(executions)}

    async def exercise() -> list[bytes]:
        async with platform.async_client() as client:
            return await drain(
                await client.join_input_turn(
                    agent_id=AGENT,
                    session_id=SESSION,
                    turn_id=TURN,
                    functions=functions,
                )
            )

    if asynchronous:
        chunks = asyncio.run(exercise())
    else:
        with platform.sync_client() as client:
            chunks = list(
                client.join_input_turn(
                    agent_id=AGENT,
                    session_id=SESSION,
                    turn_id=TURN,
                    functions=functions,
                )
            )

    assert b"".join(chunks) == HEARTBEAT + TEXT + DONE
    assert (platform.requests[0].method, platform.requests[0].path) == (
        "GET",
        INPUT_TURN,
    )
    assert len(executions) == 1
    assert len(platform.bodies("/claim")) == 1


@pytest.mark.parametrize("asynchronous", [False, True])
def test_sessions_join_input_turn_observes_without_claiming(
    asynchronous: bool,
) -> None:
    platform = FakePlatform([HEARTBEAT, ready(), TEXT, DONE])

    async def exercise() -> list[bytes]:
        async with platform.async_client() as client:
            return await drain(
                await client.sessions.join_input_turn(
                    agent_id=AGENT, session_id=SESSION, turn_id=TURN
                )
            )

    if asynchronous:
        chunks = asyncio.run(exercise())
    else:
        with platform.sync_client() as client:
            chunks = list(
                client.sessions.join_input_turn(
                    agent_id=AGENT, session_id=SESSION, turn_id=TURN
                )
            )

    assert b"".join(chunks) == HEARTBEAT + TEXT + DONE
    assert platform.requests[0].path == INPUT_TURN
    assert platform.bodies("/claim") == []


def test_input_turn_streams_reject_empty_turn_and_surface_busy() -> None:
    with (
        loopback(error("session_busy")) as (base_url, state),
        BlazingAgents(api_key="ba_test", base_url=base_url) as client,
    ):
        with pytest.raises(ValueError, match="turn_id"):
            client.sessions.join_input_turn(
                agent_id=AGENT, session_id=SESSION, turn_id=""
            )
        with pytest.raises(APIStatusError) as raised:
            client.run_inputs(agent_id=AGENT, session_id=SESSION)
    assert raised.value.code == "session_busy"
    assert [(r.method, r.target) for r in state.requests] == [
        ("POST", f"{BASE}/inputs/run")
    ]
