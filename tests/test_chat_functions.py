from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, field_validator

import blazing_agents._functions as functions_module
from blazing_agents import (
    APIStatusError,
    AsyncBlazingAgents,
    BlazingAgents,
    ChatFunction,
    FunctionContext,
    StreamError,
    define_function,
)

AGENT_ID = "ag_0123456789abcdef"
SESSION_ID = "ss_0123456789abcdef"
CALL_ID = "fc_0123456789abcdef"
OTHER_CALL_ID = "fc_1123456789abcdef"
THIRD_CALL_ID = "fc_2123456789abcdef"
FOURTH_CALL_ID = "fc_3123456789abcdef"
CONTINUATION_ID = "tac_1"
MESSAGE: dict[str, object] = {
    "id": "m1",
    "role": "user",
    "parts": [{"type": "text", "text": "hi"}],
}
TEXT = b'data: {"type":"text-delta","id":"t","delta":"done"}\n\n'
HEARTBEAT = b'data: {"type":"start-step"}\n\n'
DONE = b"data: [DONE]\n\n"


class Order(BaseModel):
    order_id: str


def ready(
    call_id: str = CALL_ID,
    name: str = "getOrder",
    payload: object | None = None,
    *,
    seconds: float = 5,
) -> bytes:
    deadline = datetime.now(UTC) + timedelta(seconds=seconds)
    event = {
        "type": "data-ba-function-call",
        "data": {
            "id": call_id,
            "name": name,
            "input": {"order_id": "o1"} if payload is None else payload,
            "deadlineAt": deadline.isoformat(),
        },
        "transient": True,
    }
    return f"data: {json.dumps(event)}\n\n".encode()


@dataclass
class Wait:
    """Pause the chat stream until a result for ``call_id`` is accepted."""

    call_id: str


@dataclass
class Until:
    """Pause the chat stream until ``event`` is set."""

    event: threading.Event


@dataclass
class Claims:
    """Pause the chat stream until ``count`` claim requests arrived."""

    count: int


@dataclass
class Pause:
    seconds: float


@dataclass
class Later:
    """A ready event whose deadline is computed when the stream emits it."""

    seconds: float

    def frame(self) -> bytes:
        return ready(seconds=self.seconds)


Step = bytes | Wait | Until | Claims | Pause | Later


Failure = int | str | Callable[[], None]
"""A status, "drop"/"slow", or a hook run before answering 500."""


@dataclass
class Call:
    state: str = "pending"
    claim_request_id: str | None = None
    outcome: object = None
    resolved: threading.Event = field(default_factory=threading.Event)


@dataclass
class Recorded:
    method: str
    path: str
    body: Any
    headers: httpx.Headers


@dataclass
class FakePlatform:
    """BA claim/result state machine behind a scripted native SSE response."""

    script: list[Step]
    approvals: object = None
    failures: dict[str, list[Failure]] = field(
        default_factory=lambda: dict[str, list[Failure]]()
    )
    calls: dict[str, Call] = field(default_factory=lambda: dict[str, Call]())
    requests: list[Recorded] = field(default_factory=lambda: list[Recorded]())
    receipt_replayed: threading.Event = field(default_factory=threading.Event)

    def call(self, call_id: str) -> Call:
        return self.calls.setdefault(call_id, Call())

    def wait_for_claims(self, count: int) -> None:
        wait_for(lambda: len(self.bodies("/claim")) >= count)

    def bodies(self, suffix: str) -> list[Any]:
        return [r.body for r in self.requests if r.path.endswith(suffix)]

    def handle(self, request: httpx.Request) -> httpx.Response | None:
        body = json.loads(request.content) if request.content else None
        self.requests.append(
            Recorded(request.method, request.url.path, body, request.headers)
        )
        path = request.url.path
        if request.method == "GET" and path.endswith("/tool-approvals"):
            return httpx.Response(200, json=self.approvals)
        if request.method == "GET":
            return None
        action = path.rsplit("/", 1)[-1]
        if action not in {"claim", "result"}:
            return None
        call_id = path.split("/")[-2]
        scripted = self.failures.get(f"{call_id}/{action}")
        if scripted:
            failure = scripted.pop(0)
            if failure == "drop":
                raise httpx.ConnectError("dropped", request=request)
            if failure == "slow":
                time.sleep(0.3)
            if callable(failure):
                failure()
                failure = 500
            if isinstance(failure, int):
                return httpx.Response(
                    failure,
                    headers={"retry-after": "0"} if failure >= 429 else {},
                    json={"error": {"code": "scripted", "message": "scripted"}},
                )
        response = self._claim(call_id, body) if action == "claim" else None
        if response is None and action == "result":
            response = self._result(call_id, body)
        if failure_after := self.failures.get(f"{call_id}/{action}-ack"):
            failure_after.pop(0)
            raise httpx.ConnectError("lost ack", request=request)
        return response

    def _claim(self, call_id: str, body: Any) -> httpx.Response:
        call = self.call(call_id)
        nonce = body["claimRequestId"]
        if call.state == "pending":
            call.state, call.claim_request_id = "running", nonce
        if call.state == "running" and call.claim_request_id == nonce:
            return httpx.Response(200, json={"claimed": True})
        return conflict()

    def _result(self, call_id: str, body: Any) -> httpx.Response:
        call = self.call(call_id)
        if call.claim_request_id != body["claimRequestId"]:
            return conflict()
        if call.state == "resolved" and call.outcome == body["outcome"]:
            self.receipt_replayed.set()
            return httpx.Response(200, json={"accepted": True})
        if call.state != "running":
            return conflict()
        call.state, call.outcome = "resolved", body["outcome"]
        call.resolved.set()
        return httpx.Response(200, json={"accepted": True})

    def sync_stream(self) -> Iterator[bytes]:
        for step in self.script:
            if isinstance(step, Wait):
                self.call(step.call_id).resolved.wait(5)
            elif isinstance(step, Until):
                step.event.wait(5)
            elif isinstance(step, Claims):
                self.wait_for_claims(step.count)
            elif isinstance(step, Pause):
                time.sleep(step.seconds)
            elif isinstance(step, Later):
                yield step.frame()
            else:
                yield step

    async def async_stream(self) -> AsyncIterator[bytes]:
        for step in self.script:
            if isinstance(step, Wait):
                await asyncio.to_thread(self.call(step.call_id).resolved.wait, 5)
            elif isinstance(step, Until):
                await asyncio.to_thread(step.event.wait, 5)
            elif isinstance(step, Claims):
                await asyncio.to_thread(self.wait_for_claims, step.count)
            elif isinstance(step, Pause):
                await asyncio.sleep(step.seconds)
            elif isinstance(step, Later):
                yield step.frame()
            else:
                yield step

    def chat_response(self, request: httpx.Request, stream: Any) -> httpx.Response:
        headers = {"content-type": "text/event-stream"}
        status = 200
        if request.url.path == f"/v1/agents/{AGENT_ID}/sessions":
            status = 201
            headers["location"] = f"/v1/agents/{AGENT_ID}/sessions/{SESSION_ID}"
        return httpx.Response(status, headers=headers, content=stream)

    def sync_client(self) -> BlazingAgents:
        def handler(request: httpx.Request) -> httpx.Response:
            return self.handle(request) or self.chat_response(
                request, self.sync_stream()
            )

        return BlazingAgents(
            api_key="ba_test",
            base_url="https://api.test",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    def async_client(self) -> AsyncBlazingAgents:
        async def handler(request: httpx.Request) -> httpx.Response:
            await request.aread()
            return self.handle(request) or self.chat_response(
                request, self.async_stream()
            )

        return AsyncBlazingAgents(
            api_key="ba_test",
            base_url="https://api.test",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )


def conflict() -> httpx.Response:
    return httpx.Response(
        409,
        json={"error": {"code": "function_call_conflict", "message": "conflict"}},
    )


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(functions_module, "_FIRST_RETRY_DELAY", 0.001)
    monkeypatch.setattr(functions_module, "_MAX_RETRY_DELAY", 0.002)


def get_order(executions: list[tuple[Order, FunctionContext]]) -> ChatFunction:
    def execute(order: Order, context: FunctionContext) -> dict[str, str]:
        executions.append((order, context))
        return {"status": f"shipped {order.order_id}"}

    return define_function(
        description="Get one order",
        input_schema=Order,
        execute=execute,
    )


def wait_for(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline
        time.sleep(0.005)


def test_sync_chat_executes_function_in_live_stream_and_strips_ready_event() -> None:
    platform = FakePlatform([HEARTBEAT, ready(), Wait(CALL_ID), TEXT, DONE])
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            message=MESSAGE,
            user_id="end-user",
            functions={"getOrder": get_order(executions)},
            extra_headers={
                "x-client-request-id": "attempt",
                "X-BA-User-Id": "end-user",
            },
        )
        assert stream.session_id == SESSION_ID
        assert b"".join(stream) == HEARTBEAT + TEXT + DONE

    chat = platform.requests[0]
    assert chat.body["functions"] == {
        "getOrder": {
            "description": "Get one order",
            "inputSchema": Order.model_json_schema(),
        }
    }
    assert chat.body["userId"] == "end-user"
    [(order, context)] = executions
    assert order == Order(order_id="o1")
    assert context.idempotency_key == CALL_ID
    assert not context.cancelled.is_set()
    [claim] = platform.bodies("/claim")
    assert uuid.UUID(claim["claimRequestId"]).version == 4
    assert platform.bodies("/result") == [
        {
            "claimRequestId": claim["claimRequestId"],
            "outcome": {"kind": "output", "value": {"status": "shipped o1"}},
        }
    ]
    claim_request = next(r for r in platform.requests if r.path.endswith("/claim"))
    assert claim_request.path == (
        f"/v1/agents/{AGENT_ID}/sessions/{SESSION_ID}/function-calls/{CALL_ID}/claim"
    )
    assert claim_request.headers["x-ba-user-id"] == "end-user"
    assert claim_request.headers["x-client-request-id"] == "attempt"


def test_sync_stream_keeps_draining_while_handler_runs() -> None:
    started, release = threading.Event(), threading.Event()
    platform = FakePlatform([ready(), HEARTBEAT, Wait(CALL_ID), TEXT])

    def execute(order: Order, context: FunctionContext) -> str:
        started.set()
        release.wait(5)
        return order.order_id

    function = define_function(description="d", input_schema=Order, execute=execute)
    with platform.sync_client() as client:
        stream = iter(
            client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
        )
        assert next(stream) == HEARTBEAT
        assert started.wait(5)
        assert not release.is_set()
        release.set()
        assert list(stream) == [TEXT]
    assert platform.calls[CALL_ID].outcome == {"kind": "output", "value": "o1"}


def test_sync_replayed_ready_event_dispatches_once_and_lost_claim_skips() -> None:
    platform = FakePlatform(
        [ready(), ready(), ready(OTHER_CALL_ID), Wait(CALL_ID), Claims(2), TEXT]
    )
    platform.call(OTHER_CALL_ID).state = "running"
    platform.call(OTHER_CALL_ID).claim_request_id = str(uuid.uuid4())
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order(executions)},
        )
        assert b"".join(stream) == TEXT
    assert [context.idempotency_key for _, context in executions] == [CALL_ID]
    assert len(platform.bodies("/result")) == 1


def test_sync_claim_and_result_retry_with_stable_nonce_and_outcome() -> None:
    platform = FakePlatform(
        [],
        failures={
            f"{CALL_ID}/claim": [503, "drop", 429],
            f"{CALL_ID}/result": [500],
            f"{CALL_ID}/result-ack": ["drop"],
        },
    )
    platform.script = [ready(), Until(platform.receipt_replayed), TEXT]
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order(executions)},
        )
        assert b"".join(stream) == TEXT
    claims = platform.bodies("/claim")
    results = platform.bodies("/result")
    assert len(claims) == 4
    assert len({claim["claimRequestId"] for claim in claims}) == 1
    assert all(result == results[0] for result in results)
    assert len(executions) == 1
    assert platform.receipt_replayed.is_set()


def raises_secret(order: Order, context: FunctionContext) -> object:
    raise RuntimeError("secret-x")


def returns_object(order: Order, context: FunctionContext) -> object:
    return object()


def returns_oversized(order: Order, context: FunctionContext) -> object:
    return "x" * (256 * 1024)


def returns_nan(order: Order, context: FunctionContext) -> object:
    return float("nan")


def returns_nested_infinity(order: Order, context: FunctionContext) -> object:
    return {"total": [1.0, float("inf")]}


@pytest.mark.parametrize(
    ("name", "payload", "execute", "message"),
    [
        ("missing", None, None, "Function missing is not available."),
        ("getOrder", {"order_id": 1}, None, "Invalid function input."),
        (
            "getOrder",
            None,
            raises_secret,
            "Function execution failed.",
        ),
        (
            "getOrder",
            None,
            returns_object,
            "Function returned an invalid result.",
        ),
        (
            "getOrder",
            None,
            returns_oversized,
            "Function returned an invalid result.",
        ),
        ("getOrder", None, returns_nan, "Function returned an invalid result."),
        (
            "getOrder",
            None,
            returns_nested_infinity,
            "Function returned an invalid result.",
        ),
    ],
)
def test_sync_failures_become_sanitized_error_outcomes(
    name: str,
    payload: object,
    execute: Callable[[Order, FunctionContext], object] | None,
    message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    platform = FakePlatform([ready(name=name, payload=payload), Wait(CALL_ID), TEXT])
    executions: list[tuple[Order, FunctionContext]] = []
    function = (
        get_order(executions)
        if execute is None
        else define_function(description="d", input_schema=Order, execute=execute)
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert executions == []
    assert platform.calls[CALL_ID].outcome == {"kind": "error", "message": message}
    assert "secret-x" not in caplog.text
    assert "secret-x" not in json.dumps(platform.bodies("/result"))


def test_sync_none_result_is_json_null_output() -> None:
    platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
    function = define_function(
        description="d", input_schema=Order, execute=lambda order, context: None
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert platform.calls[CALL_ID].outcome == {"kind": "output", "value": None}


def test_sync_claim_granted_after_deadline_does_not_invoke_handler() -> None:
    platform = FakePlatform(
        [Later(0.2), Claims(1), Pause(0.4), TEXT],
        failures={f"{CALL_ID}/claim": ["slow"]},
    )
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order(executions)},
        )
        assert b"".join(stream) == TEXT
    assert platform.calls[CALL_ID].state == "running"
    assert executions == []
    assert platform.bodies("/result") == []


def test_sync_claim_granted_after_stream_close_does_not_invoke_handler() -> None:
    platform = FakePlatform(
        [ready(), HEARTBEAT, Until(threading.Event())],
        failures={f"{CALL_ID}/claim": ["slow"]},
    )
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order(executions)},
        )
        body = iter(stream)
        assert next(body) == HEARTBEAT
        platform.wait_for_claims(1)
        stream.close()
        wait_for(lambda: platform.calls.get(CALL_ID, Call()).state == "running")
        time.sleep(0.05)
    assert executions == []
    assert platform.bodies("/result") == []


@pytest.mark.parametrize("resume", [False, True])
def test_sync_empty_registry_claims_and_reports_missing_handler(resume: bool) -> None:
    platform = FakePlatform(
        [HEARTBEAT, ready(), Wait(CALL_ID), TEXT], approvals=approvals("queued")
    )
    with platform.sync_client() as client:
        stream = (
            client.resume_chat(agent_id=AGENT_ID, session_id=SESSION_ID, functions={})
            if resume
            else client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={},
            )
        )
        assert b"".join(stream) == HEARTBEAT + TEXT
    assert len(platform.bodies("/claim")) == 1
    assert platform.calls[CALL_ID].outcome == {
        "kind": "error",
        "message": "Function getOrder is not available.",
    }
    if not resume:
        assert "functions" not in platform.requests[0].body


def test_sync_handler_returning_awaitable_fails_without_awaiting() -> None:
    async def later() -> str:
        return "never"

    platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
    function = define_function(
        description="d",
        input_schema=Order,
        execute=lambda order, context: later(),
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert platform.calls[CALL_ID].outcome == {
        "kind": "error",
        "message": "Function execution failed.",
    }


def test_sync_deadline_cancels_handler_and_skips_result() -> None:
    finished = threading.Event()
    seen: list[bool] = []

    def execute(order: Order, context: FunctionContext) -> str:
        seen.append(context.cancelled.wait(5))
        finished.set()
        return "late"

    platform = FakePlatform([Later(0.1), Until(finished), TEXT])
    function = define_function(description="d", input_schema=Order, execute=execute)
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert seen == [True]
    assert platform.bodies("/result") == []


def test_sync_stream_close_cancels_running_handler() -> None:
    started, observed = threading.Event(), threading.Event()
    hold = threading.Event()

    def execute(order: Order, context: FunctionContext) -> str:
        started.set()
        if context.cancelled.wait(5):
            observed.set()
        return "late"

    platform = FakePlatform([ready(), HEARTBEAT, Until(hold), TEXT])
    function = define_function(description="d", input_schema=Order, execute=execute)
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        body = iter(stream)
        assert next(body) == HEARTBEAT
        assert started.wait(5)
        hold.set()
        stream.close()
        assert observed.wait(5)
    assert platform.bodies("/result") == []


def test_sync_permanent_claim_failure_fails_stream_visibly() -> None:
    platform = FakePlatform(
        [ready(), Claims(1), Pause(0.05), TEXT, Until(threading.Event())],
        failures={f"{CALL_ID}/claim": [400]},
    )
    executions: list[tuple[Order, FunctionContext]] = []
    received: list[bytes] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order(executions)},
        )
        with pytest.raises(APIStatusError) as failure:
            received.extend(stream)
    assert failure.value.status_code == 400
    assert received == []
    assert executions == []


def test_sync_stream_close_stops_claim_retries() -> None:
    platform = FakePlatform(
        [ready(), HEARTBEAT, Until(threading.Event())],
        failures={f"{CALL_ID}/claim": [503] * 100_000},
    )
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order(executions)},
        )
        body = iter(stream)
        assert next(body) == HEARTBEAT
        platform.wait_for_claims(3)
        stream.close()
        claims = len(platform.bodies("/claim"))
        time.sleep(0.05)
        assert len(platform.bodies("/claim")) <= claims + 1
    assert executions == []


def test_runner_skips_calls_started_after_close_and_parses_retry_after() -> None:
    platform = FakePlatform([])
    with platform.sync_client() as client:
        runner = functions_module.SyncFunctionRunner(
            client._transport,
            functions_module._CallScope(AGENT_ID, SESSION_ID, None),
            {},
        )
        runner.close()
        call = functions_module._FunctionCall.model_validate(
            json.loads(ready()[6:])["data"]
        )
        runner._run(call)
        runner.dispatch(call)
    assert platform.requests == []
    response = httpx.Response(503, headers={"retry-after": "Wed, 21 Oct 2026"})
    error = APIStatusError(
        "busy",
        status_code=503,
        headers=response.headers,
        code="busy",
        details=None,
        param=None,
        request_id=None,
        response_body="",
    )
    assert functions_module._retry_delay(error, 10) == 0.002
    for retry_after, expected in (
        (format_datetime(datetime.now(UTC) + timedelta(seconds=30)), 25.0),
        (format_datetime(datetime.now(UTC) - timedelta(seconds=30)), 0.0),
    ):
        error.retry_after = retry_after
        delay = functions_module._retry_delay(error, 0)
        assert delay is not None
        assert expected <= delay <= expected + 5.5


class Shape(BaseModel):
    value: int


def returns_datetime(order: Order, context: FunctionContext) -> object:
    return datetime.now(UTC)


def returns_model(order: Order, context: FunctionContext) -> object:
    return Shape(value=1)


def returns_tuple(order: Order, context: FunctionContext) -> object:
    return {"pair": (1, 2)}


def returns_int_keys(order: Order, context: FunctionContext) -> object:
    return {1: "one"}


def returns_cycle(order: Order, context: FunctionContext) -> object:
    cycle: list[object] = []
    cycle.append(cycle)
    return cycle


@pytest.mark.parametrize(
    "execute",
    [returns_datetime, returns_model, returns_tuple, returns_int_keys, returns_cycle],
)
def test_sync_results_must_already_be_plain_json(
    execute: Callable[[Order, FunctionContext], object],
) -> None:
    platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
    function = define_function(description="d", input_schema=Order, execute=execute)
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert platform.calls[CALL_ID].outcome == {
        "kind": "error",
        "message": "Function returned an invalid result.",
    }


def test_sync_expired_result_retries_end_without_failing_stream(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(functions_module, "_RESULT_GRACE_SECONDS", 0)
    exhausted = threading.Event()
    platform = FakePlatform(
        [Later(0.2), Until(exhausted)],
        failures={f"{CALL_ID}/result": ["drop"] * 100_000},
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order([])},
        )
        threading.Timer(0.5, exhausted.set).start()
        assert b"".join(stream) == b""
    assert platform.call(CALL_ID).state == "running"
    assert len(platform.bodies("/result")) > 1
    assert "result failed" in caplog.text


@pytest.mark.parametrize(
    "malformed",
    [
        ready().replace(b'"transient": true', b'"transient": false'),
        ready(name="bash"),
        ready("fc_short"),
        b"data: data-ba-function-call\n\n",
        b'data: {"type":"data-ba-function-call",\n\n',
    ],
)
def test_malformed_ready_event_is_stripped_and_raises(malformed: bytes) -> None:
    platform = FakePlatform([HEARTBEAT, malformed, TEXT])
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order([])},
        )
        received: list[bytes] = []
        with pytest.raises(StreamError, match="malformed function call"):
            received.extend(stream)
    assert received == [HEARTBEAT]


def test_frames_preserve_unrelated_events_crlf_and_trailing_bytes() -> None:
    lookalike = b'data: {"type":"text-delta","delta":"data-ba-function-call"}\n\n'
    not_data = b"event: data-ba-function-call\ndata: {}\n\n"
    array = b'data: ["data-ba-function-call"]\n\n'
    crlf = ready().replace(b"\n\n", b"\r\n\r\n")
    platform = FakePlatform(
        [lookalike[:10], lookalike[10:] + not_data, array, crlf, Wait(CALL_ID), b"tail"]
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order([])},
        )
        assert b"".join(stream) == lookalike + not_data + array + b"tail"


def test_function_definitions_are_validated_locally() -> None:
    function = get_order([])

    async def async_execute(order: Order, context: FunctionContext) -> str:
        return ""

    async_function = define_function(
        description="d", input_schema=Order, execute=async_execute
    )
    platform = FakePlatform([])
    big = define_function(
        description="x" * (64 * 1024),
        input_schema=Order,
        execute=lambda order, context: None,
    )
    with platform.sync_client() as client:
        for functions, error in [
            ({f"f{i}": function for i in range(33)}, "At most 32"),
            ({"1bad": function}, "Invalid or reserved"),
            ({"_bad": function}, "Invalid or reserved"),
            ({"bash": function}, "Invalid or reserved"),
            ({"activate_skill": function}, "Invalid or reserved"),
            ({"mcp__tool": function}, "Invalid or reserved"),
            ({"a" * 65: function}, "Invalid or reserved"),
            ({"slow": async_function}, "AsyncBlazingAgents"),
            ({"big": big}, "exceed"),
        ]:
            with pytest.raises(ValueError, match=error):
                client.chat(agent_id=AGENT_ID, message=MESSAGE, functions=functions)
        with pytest.raises(TypeError, match="define_function"):
            client.chat(
                agent_id=AGENT_ID,
                message=MESSAGE,
                functions={"getOrder": object()},  # type: ignore[dict-item]
            )
    assert platform.requests == []
    with pytest.raises(ValueError, match="description"):
        define_function(description=" ", input_schema=Order, execute=lambda o, c: o)
    with pytest.raises(ValueError, match="JSON object"):
        define_function(description="d", input_schema=int, execute=lambda o, c: o)


def test_reserved_names_match_builtin_tools() -> None:
    assert {
        "read",
        "write",
        "edit",
        "grep",
        "glob",
        "bash",
        "publish_artifacts",
        "write_todos",
        "save_memory",
        "get_memory",
        "search_memories",
        "update_memory",
        "delete_memory",
        "activate_skill",
    } == functions_module._RESERVED_NAMES


def approvals(state: str | None) -> object:
    continuation = None if state is None else {"id": CONTINUATION_ID, "state": state}
    return {"data": [], "continuation": continuation}


def test_sync_resume_chat_joins_queued_continuation_with_functions() -> None:
    platform = FakePlatform(
        [ready(), Wait(CALL_ID), TEXT], approvals=approvals("queued")
    )
    executions: list[tuple[Order, FunctionContext]] = []
    with platform.sync_client() as client:
        stream = client.resume_chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            functions={"getOrder": get_order(executions)},
            extra_headers={"X-BA-User-Id": "end-user"},
        )
        assert stream.session_id == SESSION_ID
        assert b"".join(stream) == TEXT
    get, resume = platform.requests[:2]
    assert get.method == "GET"
    assert get.path.endswith(f"/sessions/{SESSION_ID}/tool-approvals")
    assert resume.path == (
        f"/v1/agents/{AGENT_ID}/sessions/{SESSION_ID}"
        f"/tool-approval-continuations/{CONTINUATION_ID}/resume"
    )
    assert resume.body == {}
    assert resume.headers["x-ba-user-id"] == "end-user"
    assert len(executions) == 1


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (None, "no tool approval continuation"),
        ("waiting", "waiting"),
        ("failed", "failed"),
    ],
)
def test_resume_chat_rejects_inactive_continuations(
    state: str | None, message: str
) -> None:
    platform = FakePlatform([], approvals=approvals(state))
    with platform.sync_client() as client:
        with pytest.raises(ValueError, match=message):
            client.resume_chat(agent_id=AGENT_ID, session_id=SESSION_ID, functions={})
    assert len(platform.requests) == 1


async def drain(stream: Any) -> list[bytes]:
    return [chunk async for chunk in stream]


def test_async_chat_runs_concurrent_handlers_and_dedupes_replays() -> None:
    async def exercise() -> None:
        both = asyncio.Event()
        started: list[str] = []

        async def execute(order: Order, context: FunctionContext) -> str:
            started.append(context.idempotency_key)
            if len(started) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), 5)
            return "async"

        platform = FakePlatform(
            [
                ready(name="first"),
                ready(OTHER_CALL_ID, name="second"),
                ready(OTHER_CALL_ID, name="second"),
                ready(THIRD_CALL_ID, name="first"),
                ready(FOURTH_CALL_ID, name="missing"),
                HEARTBEAT,
                Wait(CALL_ID),
                Wait(OTHER_CALL_ID),
                Wait(FOURTH_CALL_ID),
                Claims(5),
                TEXT,
                b"tail",
            ],
            failures={f"{CALL_ID}/claim": ["drop"]},
        )
        platform.call(THIRD_CALL_ID).state = "closed"
        function = define_function(description="d", input_schema=Order, execute=execute)
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                message=MESSAGE,
                functions={"first": function, "second": function},
                extra_headers={"X-BA-User-Id": "end-user"},
            )
            assert stream.session_id == SESSION_ID
            assert await drain(stream) == [HEARTBEAT, TEXT, b"tail"]
        assert sorted(started) == [CALL_ID, OTHER_CALL_ID]
        assert len(platform.bodies("/claim")) == 5
        assert platform.calls[FOURTH_CALL_ID].outcome == {
            "kind": "error",
            "message": "Function missing is not available.",
        }
        assert platform.calls[CALL_ID].outcome == {"kind": "output", "value": "async"}
        claim = next(r for r in platform.requests if r.path.endswith("/claim"))
        assert claim.headers["x-ba-user-id"] == "end-user"

    asyncio.run(exercise())


def test_async_sync_handler_runs_off_event_loop() -> None:
    async def exercise() -> None:
        loop_thread = threading.current_thread()
        threads: list[threading.Thread] = []

        def execute(order: Order, context: FunctionContext) -> str:
            threads.append(threading.current_thread())
            return "sync"

        platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
        function = define_function(description="d", input_schema=Order, execute=execute)
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
            assert await drain(stream) == [TEXT]
        assert threads and threads[0] is not loop_thread
        assert platform.calls[CALL_ID].outcome == {"kind": "output", "value": "sync"}

    asyncio.run(exercise())


async def awaited() -> str:
    return "awaited"


async def raises_timeout(order: Order, context: FunctionContext) -> str:
    raise TimeoutError("secret-timeout")


def returns_awaitable(order: Order, context: FunctionContext) -> object:
    return awaited()


def raises_value(order: Order, context: FunctionContext) -> str:
    raise ValueError("secret-value")


@pytest.mark.parametrize(
    ("execute", "outcome"),
    [
        (returns_awaitable, {"kind": "output", "value": "awaited"}),
        (raises_timeout, {"kind": "error", "message": "Function execution failed."}),
        (raises_value, {"kind": "error", "message": "Function execution failed."}),
    ],
)
def test_async_handler_outcomes(
    execute: Callable[..., object],
    outcome: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def exercise() -> None:
        platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
        function = define_function(description="d", input_schema=Order, execute=execute)
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
            assert await drain(stream) == [TEXT]
        assert platform.calls[CALL_ID].outcome == outcome

    asyncio.run(exercise())
    assert "secret" not in caplog.text


def test_async_deadline_cancels_handler_and_skips_result() -> None:
    async def exercise() -> None:
        finished = threading.Event()
        contexts: list[FunctionContext] = []

        async def slow(order: Order, context: FunctionContext) -> str:
            contexts.append(context)
            await asyncio.sleep(5)
            return "late"

        platform = FakePlatform([Later(0.1), Until(finished), TEXT])
        function = define_function(description="d", input_schema=Order, execute=slow)
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
            asyncio.get_running_loop().call_later(0.4, finished.set)
            assert await drain(stream) == [TEXT]
        assert contexts[0].cancelled.is_set()
        assert platform.bodies("/result") == []

    asyncio.run(exercise())


def test_async_stream_close_cancels_running_handler() -> None:
    async def exercise() -> None:
        started = asyncio.Event()
        cancelled: list[bool] = []

        async def execute(order: Order, context: FunctionContext) -> str:
            started.set()
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                cancelled.append(context.cancelled.is_set())
                raise
            return "late"

        platform = FakePlatform([ready(), HEARTBEAT, Until(threading.Event()), TEXT])
        function = define_function(description="d", input_schema=Order, execute=execute)
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
            body = aiter(stream)
            assert await anext(body) == HEARTBEAT
            await asyncio.wait_for(started.wait(), 5)
            await stream.aclose()
        assert cancelled == [False] or cancelled == [True]
        assert platform.bodies("/result") == []

    asyncio.run(exercise())


def test_async_permanent_result_failure_fails_stream() -> None:
    async def exercise() -> None:
        platform = FakePlatform(
            [ready(), Until(threading.Event()), TEXT, Until(threading.Event())],
            failures={f"{CALL_ID}/result": [404]},
        )
        hold = platform.script[1]
        assert isinstance(hold, Until)
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": get_order([])},
            )
            asyncio.get_running_loop().call_later(0.2, hold.event.set)
            with pytest.raises(APIStatusError) as failure:
                await drain(stream)
        assert failure.value.status_code == 404

    asyncio.run(exercise())


def test_async_permanent_claim_failure_fails_stream_at_end() -> None:
    async def exercise() -> None:
        platform = FakePlatform(
            [ready(), Claims(1), Pause(0.05)],
            failures={f"{CALL_ID}/claim": [403]},
        )
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": get_order([])},
            )
            with pytest.raises(APIStatusError) as failure:
                await drain(stream)
        assert failure.value.status_code == 403

    asyncio.run(exercise())


def test_async_claim_after_deadline_and_empty_resume_registry() -> None:
    async def exercise() -> None:
        late = FakePlatform(
            [Later(0.2), Claims(1), Pause(0.4), TEXT],
            failures={f"{CALL_ID}/claim": ["slow"]},
        )
        executions: list[tuple[Order, FunctionContext]] = []
        async with late.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": get_order(executions)},
            )
            assert await drain(stream) == [TEXT]
        assert executions == []
        assert late.bodies("/result") == []

        empty = FakePlatform(
            [ready(), Wait(CALL_ID), TEXT], approvals=approvals("queued")
        )
        async with empty.async_client() as client:
            stream = await client.resume_chat(
                agent_id=AGENT_ID, session_id=SESSION_ID, functions={}
            )
            assert await drain(stream) == [TEXT]
        assert empty.calls[CALL_ID].outcome == {
            "kind": "error",
            "message": "Function getOrder is not available.",
        }

    asyncio.run(exercise())


def test_async_resume_chat_and_local_validation() -> None:
    async def exercise() -> None:
        async def execute(order: Order, context: FunctionContext) -> str:
            return "resumed"

        function = define_function(description="d", input_schema=Order, execute=execute)
        platform = FakePlatform(
            [ready(), Wait(CALL_ID), TEXT], approvals=approvals("running")
        )
        async with platform.async_client() as client:
            stream = await client.resume_chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                functions={"getOrder": function},
            )
            assert await drain(stream) == [TEXT]
            with pytest.raises(ValueError, match="Invalid or reserved"):
                await client.resume_chat(
                    agent_id=AGENT_ID,
                    session_id=SESSION_ID,
                    functions={"bash": function},
                )
        assert platform.requests[1].path.endswith(f"/{CONTINUATION_ID}/resume")
        assert platform.calls[CALL_ID].outcome == {
            "kind": "output",
            "value": "resumed",
        }

    asyncio.run(exercise())


class Exploding(float):
    def __eq__(self, other: object) -> bool:
        raise RuntimeError("secret-eq")

    __hash__ = float.__hash__


def returns_exploding(order: Order, context: FunctionContext) -> object:
    return Exploding(1.5)


def test_sync_result_serializer_exceptions_become_invalid_result() -> None:
    platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
    function = define_function(
        description="d", input_schema=Order, execute=returns_exploding
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert platform.calls[CALL_ID].outcome == {
        "kind": "error",
        "message": "Function returned an invalid result.",
    }


class Exploded(BaseModel):
    order_id: str

    @field_validator("order_id")
    @classmethod
    def explode(cls, value: str) -> str:
        raise RuntimeError("secret-validator")


def test_validator_exceptions_become_invalid_input_without_running_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    executions: list[object] = []

    def execute(order: Exploded, context: FunctionContext) -> str:
        executions.append(order)
        return "never"

    async def async_execute(order: Exploded, context: FunctionContext) -> str:
        executions.append(order)
        return "never"

    invalid = {"kind": "error", "message": "Invalid function input."}
    platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
    function = define_function(description="d", input_schema=Exploded, execute=execute)
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert platform.calls[CALL_ID].outcome == invalid

    async def exercise() -> None:
        platform = FakePlatform([ready(), Wait(CALL_ID), TEXT])
        function = define_function(
            description="d", input_schema=Exploded, execute=async_execute
        )
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
            assert await drain(stream) == [TEXT]
        assert platform.calls[CALL_ID].outcome == invalid

    asyncio.run(exercise())
    assert executions == []
    assert "secret-validator" not in caplog.text


def test_observer_join_strips_private_events_without_claiming() -> None:
    script: list[Step] = [HEARTBEAT, ready(), TEXT, b"tail"]
    platform = FakePlatform(list(script))
    with platform.sync_client() as client:
        joined = client.sessions.join_tool_approval_continuation(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            continuation_id=CONTINUATION_ID,
        )
        assert b"".join(joined) == HEARTBEAT + TEXT + b"tail"
        malformed = FakePlatform([HEARTBEAT, ready("fc_short"), TEXT])
    assert platform.bodies("/claim") == []

    async def exercise() -> None:
        platform = FakePlatform(list(script))
        async with platform.async_client() as client:
            joined = await client.sessions.join_tool_approval_continuation(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                continuation_id=CONTINUATION_ID,
            )
            assert await drain(joined) == [HEARTBEAT, TEXT, b"tail"]
        assert platform.bodies("/claim") == []

    asyncio.run(exercise())
    with malformed.sync_client() as client:
        joined = client.sessions.join_tool_approval_continuation(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            continuation_id=CONTINUATION_ID,
        )
        with pytest.raises(StreamError, match="malformed function call"):
            b"".join(joined)
    assert malformed.requests[0].path.endswith(
        f"/tool-approval-continuations/{CONTINUATION_ID}"
    )


def test_sync_permanent_claim_failure_fails_stream_at_end() -> None:
    platform = FakePlatform(
        [ready(), Claims(1), Pause(0.05)],
        failures={f"{CALL_ID}/claim": [403]},
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": get_order([])},
        )
        with pytest.raises(APIStatusError) as failure:
            b"".join(stream)
    assert failure.value.status_code == 403


def test_sync_handler_does_not_start_after_slow_validation_crosses_deadline() -> None:
    executions: list[object] = []

    class SlowOrder(BaseModel):
        order_id: str

        @field_validator("order_id")
        @classmethod
        def slow(cls, value: str) -> str:
            time.sleep(0.3)
            return value

    def execute(order: SlowOrder, context: FunctionContext) -> str:
        executions.append(order)
        return "late"

    platform = FakePlatform([Later(0.2), Claims(1), Pause(0.5), TEXT])
    function = define_function(description="d", input_schema=SlowOrder, execute=execute)
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        assert b"".join(stream) == TEXT
    assert executions == []
    assert platform.bodies("/result") == []


def test_sync_handler_does_not_start_when_stream_closes_during_validation() -> None:
    executions: list[object] = []
    validating, closed = threading.Event(), threading.Event()

    class GatedOrder(BaseModel):
        order_id: str

        @field_validator("order_id")
        @classmethod
        def gated(cls, value: str) -> str:
            validating.set()
            closed.wait(5)
            return value

    def execute(order: GatedOrder, context: FunctionContext) -> str:
        executions.append(order)
        return "late"

    platform = FakePlatform([ready(), HEARTBEAT, Until(threading.Event())])
    function = define_function(
        description="d", input_schema=GatedOrder, execute=execute
    )
    with platform.sync_client() as client:
        stream = client.chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            message=MESSAGE,
            functions={"getOrder": function},
        )
        body = iter(stream)
        assert next(body) == HEARTBEAT
        assert validating.wait(5)
        stream.close()
        closed.set()
        time.sleep(0.1)
    assert executions == []
    assert platform.bodies("/result") == []


def test_async_handler_does_not_start_after_slow_validation_crosses_deadline() -> None:
    executions: list[object] = []

    class SlowOrder(BaseModel):
        order_id: str

        @field_validator("order_id")
        @classmethod
        def slow(cls, value: str) -> str:
            time.sleep(0.3)
            return value

    async def execute(order: SlowOrder, context: FunctionContext) -> str:
        executions.append(order)
        return "late"

    async def exercise() -> None:
        platform = FakePlatform([Later(0.2), Claims(1), Pause(0.5), TEXT])
        function = define_function(
            description="d", input_schema=SlowOrder, execute=execute
        )
        async with platform.async_client() as client:
            stream = await client.chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                message=MESSAGE,
                functions={"getOrder": function},
            )
            assert await drain(stream) == [TEXT]
        assert platform.bodies("/result") == []

    asyncio.run(exercise())
    assert executions == []


def test_result_retries_send_a_snapshot_not_the_mutable_return_value() -> None:
    shared: dict[str, object] = {"status": "first"}

    def execute(order: Order, context: FunctionContext) -> object:
        return shared

    def mutate() -> None:
        shared["status"] = "mutated"

    async def async_execute(order: Order, context: FunctionContext) -> object:
        return shared

    for sync in (True, False):
        shared["status"] = "first"
        platform = FakePlatform(
            [ready(), Wait(CALL_ID), TEXT],
            failures={f"{CALL_ID}/result": [mutate]},
        )
        if sync:
            function = define_function(
                description="d", input_schema=Order, execute=execute
            )
            with platform.sync_client() as client:
                stream = client.chat(
                    agent_id=AGENT_ID,
                    session_id=SESSION_ID,
                    message=MESSAGE,
                    functions={"getOrder": function},
                )
                assert b"".join(stream) == TEXT
        else:
            function = define_function(
                description="d", input_schema=Order, execute=async_execute
            )

            async def exercise(platform: FakePlatform, function: ChatFunction) -> None:
                async with platform.async_client() as client:
                    stream = await client.chat(
                        agent_id=AGENT_ID,
                        session_id=SESSION_ID,
                        message=MESSAGE,
                        functions={"getOrder": function},
                    )
                    assert await drain(stream) == [TEXT]

            asyncio.run(exercise(platform, function))
        first, retry = platform.bodies("/result")
        assert shared["status"] == "mutated"
        assert first == retry
        assert retry["outcome"] == {"kind": "output", "value": {"status": "first"}}


FUNCTION_APPROVALS = {
    "data": [
        {
            "approvalId": "apr_1",
            "toolName": "getOrder",
            "toolCallId": "call_1",
            "input": {"order_id": "o1"},
            "decision": "approved",
            "reason": None,
            "tool": {"type": "function", "name": "getOrder"},
            "assistantMessageId": "message-1",
            "createdAt": "2026-10-02T02:59:31Z",
            "decidedAt": "2026-10-02T02:59:32Z",
        }
    ],
    "continuation": {"id": CONTINUATION_ID, "state": "queued"},
}


def test_resume_chat_after_a_function_approval() -> None:
    """The approval list carries the function reference the platform reports."""
    executions: list[tuple[Order, FunctionContext]] = []
    platform = FakePlatform(
        [ready(), Wait(CALL_ID), TEXT], approvals=FUNCTION_APPROVALS
    )
    with platform.sync_client() as client:
        stream = client.resume_chat(
            agent_id=AGENT_ID,
            session_id=SESSION_ID,
            functions={"getOrder": get_order(executions)},
        )
        assert b"".join(stream) == TEXT
    assert platform.requests[1].path.endswith(f"/{CONTINUATION_ID}/resume")
    assert platform.calls[CALL_ID].outcome == {
        "kind": "output",
        "value": {"status": "shipped o1"},
    }

    async def exercise() -> None:
        platform = FakePlatform(
            [ready(), Wait(CALL_ID), TEXT], approvals=FUNCTION_APPROVALS
        )
        async with platform.async_client() as client:
            stream = await client.resume_chat(
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                functions={"getOrder": get_order(executions)},
            )
            assert await drain(stream) == [TEXT]
        assert platform.requests[1].path.endswith(f"/{CONTINUATION_ID}/resume")

    asyncio.run(exercise())
    assert len(executions) == 2
