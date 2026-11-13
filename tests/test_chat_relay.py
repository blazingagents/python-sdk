from __future__ import annotations

import asyncio
import json
import logging
import socket
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from threading import Event
from typing import Any

import pytest
from pydantic import BaseModel
from support import Response, loopback

from blazing_agents import (
    APIConnectionError,
    AsyncBlazingAgents,
    AsyncChatRelay,
    BlazingAgents,
    ChatRelay,
    RelayContext,
    StreamError,
    define_function,
)

AGENT = "ag_0123456789abcdef"
SESSION = "ss_0123456789abcdef"
TURN = "turn_0123456789abcdef"
SESSIONS = f"/v1/agents/{AGENT}/sessions"
THIS_SESSION = f"{SESSIONS}/{SESSION}"
SCOPE_HEADER = "x-ba-user-id"
SSE = b'data: {"type":"text-delta","id":"t","delta":"Hi"}\n\n'

MESSAGE: dict[str, Any] = {
    "id": "message-1",
    "role": "user",
    "parts": [{"type": "text", "text": "Hello"}],
}
ASSISTANT_TEXT: dict[str, Any] = {
    "id": "assistant-1",
    "role": "assistant",
    "parts": [{"type": "text", "text": "Hi"}],
}
APPROVAL_MESSAGE: dict[str, Any] = {
    "id": "assistant-1",
    "role": "assistant",
    "parts": [
        {
            "type": "dynamic-tool",
            "toolName": "getOrder",
            "toolCallId": "call-0",
            "state": "approval-responded",
            "input": {"orderId": "stale"},
            "approval": {"id": "approval-0", "approved": True},
        },
        {"type": "step-start"},
        {
            "type": "dynamic-tool",
            "toolName": "getOrder",
            "toolCallId": "call-1",
            "state": "approval-responded",
            "input": {"orderId": "o1"},
            "approval": {"id": "approval-1", "approved": True},
        },
        {
            "type": "tool-bash",
            "toolCallId": "call-2",
            "state": "approval-responded",
            "input": {"command": "rm"},
            "approval": {"id": "approval-2", "approved": False, "reason": "No"},
        },
        {
            "type": "tool-bash",
            "toolCallId": "call-3",
            "state": "output-available",
            "input": {},
            "output": {},
        },
    ],
}
DECISIONS = [
    {"approvalId": "approval-1", "approved": True},
    {"approvalId": "approval-2", "approved": False, "reason": "No"},
]
STORED = [
    {**MESSAGE, "branchable": True},
    {**ASSISTANT_TEXT, "branchable": False, "metadata": {"model": "m"}},
]
RECEIPT = {
    "data": {
        "requestId": "steer-1",
        "sequence": 1,
        "message": MESSAGE,
        "state": "accepted",
        "turnId": TURN,
        "createdAt": "2026-11-01T10:00:00Z",
        "updatedAt": "2026-11-01T10:00:00Z",
        "reason": None,
    },
    "activity": {"state": "running", "turnId": TURN},
}
STREAM_HEADERS = {"content-type": "text/event-stream", "x-ba-turn-id": TURN}

Req = dict[str, str]
USER_A: Req = {"user": "user-a"}
ASYNC = pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])


class OrderInput(BaseModel):
    order_id: str


FUNCTIONS = {
    "getOrder": define_function(
        description="Get an order",
        input_schema=OrderInput,
        execute=lambda value, context: None,
    )
}


def resolve(request: Req) -> RelayContext | None:
    user = request.get("user")
    if user is None:
        return None
    return RelayContext(agent_id=AGENT, user_id=user, metadata={"plan": "demo"})


def chat_reply(**headers: str) -> Response:
    return Response(
        status=201,
        chunks=(SSE,),
        headers={
            **STREAM_HEADERS,
            "location": THIS_SESSION,
            "x-request-id": "req-chat",
            **headers,
        },
    )


def continue_reply(**headers: str) -> Response:
    return Response(chunks=(SSE,), headers={**STREAM_HEADERS, **headers})


def api_error(status: int, code: str, request_id: str) -> Response:
    return Response(
        status=status,
        body={"error": {"code": code, "message": f"{code} message."}},
        headers={"x-request-id": request_id},
    )


@dataclass
class Opened:
    status: int
    headers: dict[str, str]
    read: Callable[[], bytes | None]
    close: Callable[[], None]

    def drain(self) -> bytes:
        chunks: list[bytes] = []
        while (chunk := self.read()) is not None:
            chunks.append(chunk)
        return b"".join(chunks)


@contextmanager
def _opened_sync(
    url: str,
    raw: bytes,
    request: Req,
    resolve_context: Callable[[Req], RelayContext | None],
) -> Generator[Opened]:
    with BlazingAgents(api_key="ba_test", base_url=url) as client:
        relay = ChatRelay(client=client, resolve_context=resolve_context)
        response = relay.handle(request, raw)
        chunks = iter(response)
        try:
            yield Opened(
                response.status_code,
                response.headers,
                lambda: next(chunks, None),
                response.close,
            )
        finally:
            response.close()


@contextmanager
def _opened_async(
    url: str,
    raw: bytes,
    request: Req,
    resolve_context: Callable[[Req], RelayContext | None],
) -> Generator[Opened]:
    async def resolver(request: Req, /) -> RelayContext | None:
        return resolve_context(request)

    loop = asyncio.new_event_loop()
    try:
        client = AsyncBlazingAgents(api_key="ba_test", base_url=url)
        relay = AsyncChatRelay(client=client, resolve_context=resolver)
        response = loop.run_until_complete(relay.handle(request, raw))
        chunks = aiter(response)

        async def read() -> bytes | None:
            return await anext(chunks, None)

        try:
            yield Opened(
                response.status_code,
                response.headers,
                lambda: loop.run_until_complete(read()),
                lambda: loop.run_until_complete(response.aclose()),
            )
        finally:
            loop.run_until_complete(response.aclose())
            loop.run_until_complete(client.aclose())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def opened(
    url: str,
    body: object,
    *,
    asynchronous: bool,
    request: Req = USER_A,
    resolve_context: Callable[[Req], RelayContext | None] = resolve,
) -> AbstractContextManager[Opened]:
    """Send one body through the sync or async relay and read its answer by chunk."""
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    open_answer = _opened_async if asynchronous else _opened_sync
    return open_answer(url, raw, request, resolve_context)


@dataclass
class Answer:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


def ask(url: str, body: object, *, asynchronous: bool, **options: Any) -> Answer:
    with opened(url, body, asynchronous=asynchronous, **options) as answer:
        return Answer(answer.status, answer.headers, answer.drain())


def chat(**fields: object) -> dict[str, object]:
    return {"op": "chat", "message": MESSAGE, **fields}


@ASYNC
def test_chat_starts_a_session_as_the_user_and_relays_the_api_headers(
    asynchronous: bool,
) -> None:
    with loopback(chat_reply()) as (url, state):
        answer = ask(
            url,
            chat(agentId="ag_attackeragent0000", userId="attacker"),
            asynchronous=asynchronous,
        )
    (call,) = state.requests
    assert (call.method, call.target) == ("POST", SESSIONS)
    assert call.headers[SCOPE_HEADER] == "user-a"
    assert call.headers["authorization"] == "Bearer ba_test"
    assert json.loads(call.body) == {
        "messages": [MESSAGE],
        "metadata": {"plan": "demo"},
        "trigger": "submit-message",
    }
    assert answer.status == 201
    assert answer.body == SSE
    assert answer.headers == {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        "x-accel-buffering": "no",
        "x-vercel-ai-ui-message-stream": "v1",
        "location": THIS_SESSION,
        "x-ba-turn-id": TURN,
        "x-request-id": "req-chat",
    }


@ASYNC
def test_chat_forwards_a_user_message_unchanged_and_omits_absent_headers(
    asynchronous: bool,
) -> None:
    message = {
        **MESSAGE,
        "metadata": {"clientTime": 1},
        "parts": [
            *MESSAGE["parts"],
            {"type": "file", "mediaType": "image/png", "url": "https://x/y.png"},
        ],
    }
    reply = Response(status=201, chunks=(SSE,), headers=STREAM_HEADERS)
    with loopback(reply) as (url, state):
        answer = ask(url, chat(message=message), asynchronous=asynchronous)
    assert json.loads(state.requests[0].body)["messages"] == [message]
    assert "x-request-id" not in answer.headers
    assert "location" not in answer.headers


@ASYNC
def test_chat_resumes_and_regenerates_inside_the_users_scope(
    asynchronous: bool,
) -> None:
    with loopback(chat_reply(), chat_reply(), chat_reply()) as (url, state):
        for fields in (
            {"sessionId": SESSION},
            {
                "sessionId": SESSION,
                "messageId": "assistant-1",
                "trigger": "regenerate-message",
            },
            {"messageId": "assistant-1", "trigger": "regenerate-message"},
        ):
            ask(url, chat(**fields), asynchronous=asynchronous)
    assert [(call.method, call.target) for call in state.requests] == [
        ("POST", THIS_SESSION),
        ("POST", THIS_SESSION),
        ("POST", SESSIONS),
    ]
    assert {call.headers[SCOPE_HEADER] for call in state.requests} == {"user-a"}
    bodies = [json.loads(call.body) for call in state.requests]
    assert bodies[0]["trigger"] == "submit-message"
    assert "messageId" not in bodies[0]
    assert bodies[1]["trigger"] == "regenerate-message"
    assert bodies[1]["messageId"] == "assistant-1"
    assert bodies[2]["trigger"] == "submit-message"


@ASYNC
def test_chat_registers_the_contexts_functions_with_the_api(
    asynchronous: bool,
) -> None:
    def with_functions(request: Req) -> RelayContext:
        return RelayContext(agent_id=AGENT, user_id="user-a", functions=FUNCTIONS)

    with loopback(chat_reply()) as (url, state):
        ask(url, chat(), asynchronous=asynchronous, resolve_context=with_functions)
    body = json.loads(state.requests[0].body)
    assert body["functions"]["getOrder"]["description"] == "Get an order"
    assert "metadata" not in body


@ASYNC
def test_history_returns_one_page_as_the_user_newest_page_first(
    asynchronous: bool,
) -> None:
    page = {"data": STORED, "nextCursor": "cursor-older", "latestCursor": "cursor-x"}
    with loopback(Response(body=page), Response(body=page)) as (url, state):
        newest = ask(
            url,
            {"op": "history", "sessionId": SESSION, "userId": "attacker"},
            asynchronous=asynchronous,
        )
        older = ask(
            url,
            {"op": "history", "sessionId": SESSION, "cursor": "cursor-older"},
            asynchronous=asynchronous,
        )
    assert [(call.method, call.target) for call in state.requests] == [
        ("GET", f"{THIS_SESSION}/messages?limit=200"),
        ("GET", f"{THIS_SESSION}/messages?cursor=cursor-older&limit=200"),
    ]
    assert {call.headers[SCOPE_HEADER] for call in state.requests} == {"user-a"}
    assert newest.status == older.status == 200
    assert newest.headers == {"content-type": "application/json"}
    assert newest.json() == {"data": STORED, "nextCursor": "cursor-older"}


@ASYNC
def test_history_of_the_last_page_answers_a_null_cursor(asynchronous: bool) -> None:
    page = {"data": STORED[:1], "nextCursor": None, "latestCursor": None}
    with loopback(Response(body=page)) as (url, _):
        answer = ask(
            url, {"op": "history", "sessionId": SESSION}, asynchronous=asynchronous
        )
    assert answer.json() == {"data": STORED[:1], "nextCursor": None}


@ASYNC
def test_history_that_the_api_answers_malformed_is_a_500_not_a_400(
    asynchronous: bool, caplog: pytest.LogCaptureFixture
) -> None:
    with loopback(Response(body={"data": "nope"})) as (url, _):
        with caplog.at_level(logging.ERROR, logger="blazing_agents"):
            answer = ask(
                url,
                {"op": "history", "sessionId": SESSION},
                asynchronous=asynchronous,
            )
    assert answer.status == 500
    assert answer.json() == {
        "error": {"code": "internal_error", "message": "Request failed."}
    }


@ASYNC
def test_steer_submits_to_the_running_turn_and_answers_the_receipt_state(
    asynchronous: bool,
) -> None:
    with loopback(Response(status=202, body=RECEIPT)) as (url, state):
        answer = ask(
            url,
            {
                "op": "steer",
                "sessionId": SESSION,
                "requestId": "steer-1",
                "message": MESSAGE,
                "userId": "attacker",
            },
            asynchronous=asynchronous,
        )
    (call,) = state.requests
    assert (call.method, call.target) == ("POST", f"{THIS_SESSION}/inputs")
    assert call.headers[SCOPE_HEADER] == "user-a"
    assert json.loads(call.body) == {"requestId": "steer-1", "message": MESSAGE}
    assert answer.status == 202
    assert answer.json() == {"state": "accepted"}


@ASYNC
def test_steer_passes_the_apis_409_steer_not_available_through(
    asynchronous: bool,
) -> None:
    with loopback(api_error(409, "steer_not_available", "req-409")) as (url, _):
        answer = ask(
            url,
            {
                "op": "steer",
                "sessionId": SESSION,
                "requestId": "steer-1",
                "message": MESSAGE,
            },
            asynchronous=asynchronous,
        )
    assert answer.status == 409
    assert answer.headers["x-request-id"] == "req-409"
    assert answer.json() == {
        "error": {
            "code": "steer_not_available",
            "message": "steer_not_available message.",
        }
    }


@ASYNC
def test_chat_continues_an_approval_round_with_the_last_steps_decisions(
    asynchronous: bool,
) -> None:
    def with_functions(request: Req) -> RelayContext:
        return RelayContext(agent_id=AGENT, user_id="user-a", functions=FUNCTIONS)

    with loopback(continue_reply(), continue_reply()) as (url, state):
        continued = ask(
            url,
            chat(message=APPROVAL_MESSAGE, sessionId=SESSION),
            asynchronous=asynchronous,
            resolve_context=with_functions,
        )
        executor = ask(
            url,
            chat(message=APPROVAL_MESSAGE, sessionId=SESSION),
            asynchronous=asynchronous,
        )
    path = f"{THIS_SESSION}/tool-approvals/continue"
    assert [(call.method, call.target) for call in state.requests] == [
        ("POST", path),
        ("POST", path),
    ]
    assert {call.headers[SCOPE_HEADER] for call in state.requests} == {"user-a"}
    first, second = (json.loads(call.body) for call in state.requests)
    assert first["decisions"] == DECISIONS
    assert first["functions"]["getOrder"]["description"] == "Get an order"
    assert second == {"decisions": DECISIONS, "functions": {}}
    assert continued.status == executor.status == 200
    assert continued.body == executor.body == SSE
    assert continued.headers["x-ba-turn-id"] == TURN
    assert "location" not in continued.headers


@ASYNC
@pytest.mark.parametrize("code", ["not_found", "workspace_not_found"])
def test_a_foreign_session_is_the_apis_404_on_every_operation(
    asynchronous: bool, code: str
) -> None:
    bodies = [
        chat(sessionId=SESSION),
        chat(message=APPROVAL_MESSAGE, sessionId=SESSION),
        {"op": "history", "sessionId": SESSION},
        {
            "op": "steer",
            "sessionId": SESSION,
            "requestId": "steer-1",
            "message": MESSAGE,
        },
    ]
    with loopback(*(api_error(404, code, "req-404") for _ in bodies)) as (url, state):
        answers = [ask(url, body, asynchronous=asynchronous) for body in bodies]
    for answer in answers:
        assert answer.status == 404
        assert answer.headers["x-request-id"] == "req-404"
        assert answer.json() == {"error": {"code": code, "message": f"{code} message."}}
    assert [call.headers[SCOPE_HEADER] for call in state.requests] == ["user-a"] * 4


@ASYNC
def test_each_request_acts_for_its_own_resolved_user(asynchronous: bool) -> None:
    with loopback(*(chat_reply() for _ in range(3))) as (url, state):
        for user in ("user-a", "user-b", "user-a"):
            ask(url, chat(), asynchronous=asynchronous, request={"user": user})
    assert [call.headers[SCOPE_HEADER] for call in state.requests] == [
        "user-a",
        "user-b",
        "user-a",
    ]


BAD_MESSAGES: dict[str, object] = {
    "malformed": {"nope": True},
    "absent": None,
    "without an id": {"role": "user", "parts": MESSAGE["parts"]},
    "with an empty id": {**MESSAGE, "id": ""},
    "without parts": {**MESSAGE, "parts": []},
    "with parts that are no list": {**MESSAGE, "parts": "Hello"},
    "with a part that has no type": {**MESSAGE, "parts": [{"text": "Hello"}]},
    "with a text part that has no text": {**MESSAGE, "parts": [{"type": "text"}]},
    "from the system": {**MESSAGE, "role": "system"},
}
BAD_APPROVALS: dict[str, dict[str, Any]] = {
    "has no tool call ID": {"toolCallId": None},
    "has no input": {"input": None},
    "names no dynamic tool": {"type": "dynamic-tool", "toolName": None},
    "has an approval that is no object": {"approval": "yes"},
    "has an approval without an id": {"approval": {"id": "", "approved": True}},
    "has an approval that is not a boolean": {"approval": {"id": "a", "approved": 1}},
    "has a null reason": {"approval": {"id": "a", "approved": True, "reason": None}},
}


def approval_part(**overrides: object) -> dict[str, Any]:
    part: dict[str, Any] = {
        "type": "tool-bash",
        "toolCallId": "call-1",
        "state": "approval-responded",
        "input": {},
        "approval": {"id": "approval-1", "approved": True},
    }
    for key, value in overrides.items():
        if value is None:
            part.pop(key, None)
        else:
            part[key] = value
    return part


INVALID_BODIES: dict[str, object] = {
    "an unknown op": {"op": "stop", "sessionId": SESSION},
    "an op that is no string": {"op": 3},
    "no op": {"message": MESSAGE, "sessionId": SESSION},
    "a body that is no JSON": b"{",
    "an empty body": b"",
    "a body that is no object": b"[]",
    "chat with a malformed Session ID": chat(sessionId="ss_short"),
    "chat with a null Session ID": chat(sessionId=None),
    "chat with an unknown trigger": chat(sessionId=SESSION, trigger="resend"),
    "chat with a null trigger": chat(trigger=None),
    "chat with an empty message ID": chat(messageId=""),
    "history without a Session": {"op": "history"},
    "history with a malformed Session ID": {"op": "history", "sessionId": "x"},
    "history with an empty cursor": {
        "op": "history",
        "sessionId": SESSION,
        "cursor": "",
    },
    "history with a null cursor": {
        "op": "history",
        "sessionId": SESSION,
        "cursor": None,
    },
    "a steer without a Session": {"op": "steer", "requestId": "s", "message": MESSAGE},
    "a steer without a request ID": {
        "op": "steer",
        "sessionId": SESSION,
        "message": MESSAGE,
    },
    **{
        f"a steer with the request ID {request_id!r}": {
            "op": "steer",
            "sessionId": SESSION,
            "requestId": request_id,
            "message": MESSAGE,
        }
        for request_id in (".", "..", "", "x" * 129, 7)
    },
    "a steer from the assistant": {
        "op": "steer",
        "sessionId": SESSION,
        "requestId": "s",
        "message": ASSISTANT_TEXT,
    },
    **{
        f"a steer with a {name} message": {
            "op": "steer",
            "sessionId": SESSION,
            "requestId": "s",
            "message": message,
        }
        for name, message in BAD_MESSAGES.items()
    },
    **{
        f"chat with a {name} message": chat(message=message)
        for name, message in BAD_MESSAGES.items()
    },
    "a tool approval without a Session": chat(message=APPROVAL_MESSAGE),
    "a tool approval without decisions": chat(
        message=ASSISTANT_TEXT, sessionId=SESSION
    ),
    "a tool approval whose decisions all precede the last step": chat(
        message={
            **APPROVAL_MESSAGE,
            "parts": [*APPROVAL_MESSAGE["parts"][:2], {"type": "step-start"}],
        },
        sessionId=SESSION,
    ),
    **{
        f"a tool approval that {name}": chat(
            message={
                **APPROVAL_MESSAGE,
                "parts": [approval_part(**changes)],
            },
            sessionId=SESSION,
        )
        for name, changes in BAD_APPROVALS.items()
    },
}


@ASYNC
def test_an_invalid_request_is_a_400_before_any_api_request(
    asynchronous: bool,
) -> None:
    with loopback() as (url, state):
        answers = {
            description: ask(url, body, asynchronous=asynchronous)
            for description, body in INVALID_BODIES.items()
        }
    assert {description: answer.status for description, answer in answers.items()} == {
        description: 400 for description in INVALID_BODIES
    }
    for answer in answers.values():
        assert answer.headers == {"content-type": "application/json"}
        assert answer.json()["error"]["code"] == "invalid_request"
    assert state.requests == []


@ASYNC
def test_a_400_names_what_was_wrong_without_echoing_the_request(
    asynchronous: bool,
) -> None:
    with loopback() as (url, _):
        messages = {
            description: ask(url, body, asynchronous=asynchronous).json()
            for description, body in {
                "body": {"op": "stop"},
                "chat": chat(message={"nope": True}),
                "role": chat(message={**MESSAGE, "role": "system"}),
                "session": chat(message=APPROVAL_MESSAGE),
                "decisions": chat(message=ASSISTANT_TEXT, sessionId=SESSION),
                "steer": {
                    "op": "steer",
                    "sessionId": SESSION,
                    "requestId": "s",
                    "message": ASSISTANT_TEXT,
                },
            }.items()
        }
    assert messages == {
        "body": {
            "error": {"code": "invalid_request", "message": "Invalid request body."}
        },
        "chat": {
            "error": {"code": "invalid_request", "message": "Invalid chat message."}
        },
        "role": {
            "error": {
                "code": "invalid_request",
                "message": "Chat submission requires a user message.",
            }
        },
        "session": {
            "error": {
                "code": "invalid_request",
                "message": "Tool approval requires an existing Session.",
            }
        },
        "decisions": {
            "error": {
                "code": "invalid_request",
                "message": "The message has no tool approval responses.",
            }
        },
        "steer": {
            "error": {
                "code": "invalid_request",
                "message": "Steering requires a user message.",
            }
        },
    }


@ASYNC
@pytest.mark.parametrize(
    "body",
    [
        chat(),
        {"op": "history", "sessionId": SESSION},
        {"op": "steer", "sessionId": SESSION, "requestId": "s", "message": MESSAGE},
        b"{",
    ],
    ids=["chat", "history", "steer", "invalid body"],
)
def test_a_request_without_a_signed_in_user_is_a_401_before_any_api_request(
    asynchronous: bool, body: object
) -> None:
    with loopback() as (url, state):
        answer = ask(url, body, asynchronous=asynchronous, request={})
    assert answer.status == 401
    assert answer.json() == {
        "error": {"code": "unauthorized", "message": "Authentication required."}
    }
    assert state.requests == []


@ASYNC
def test_an_invalid_user_id_is_a_500_without_a_leak_and_sends_nothing(
    asynchronous: bool, caplog: pytest.LogCaptureFixture
) -> None:
    def padded(request: Req) -> RelayContext:
        return RelayContext(agent_id=AGENT, user_id=" padded ")

    with loopback() as (url, state):
        with caplog.at_level(logging.ERROR, logger="blazing_agents"):
            answer = ask(url, chat(), asynchronous=asynchronous, resolve_context=padded)
    assert answer.status == 500
    assert answer.json() == {
        "error": {"code": "internal_error", "message": "Request failed."}
    }
    assert b"padded" not in answer.body
    assert state.requests == []
    (record,) = caplog.records
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], ValueError)


@ASYNC
def test_a_resolver_that_raises_is_a_500_without_a_leak(asynchronous: bool) -> None:
    def broken(request: Req) -> RelayContext:
        raise RuntimeError("secret")

    with loopback() as (url, state):
        answer = ask(url, chat(), asynchronous=asynchronous, resolve_context=broken)
    assert answer.status == 500
    assert b"secret" not in answer.body
    assert state.requests == []


@ASYNC
def test_an_api_error_keeps_its_status_code_message_and_request_id(
    asynchronous: bool,
) -> None:
    with loopback(api_error(429, "rate_limited", "req-429")) as (url, _):
        answer = ask(url, chat(), asynchronous=asynchronous)
    assert answer.status == 429
    assert answer.headers == {
        "content-type": "application/json",
        "x-request-id": "req-429",
    }
    assert answer.json() == {
        "error": {"code": "rate_limited", "message": "rate_limited message."}
    }


@ASYNC
def test_an_unreachable_api_is_a_502_network_error_with_a_fixed_message(
    asynchronous: bool, caplog: pytest.LogCaptureFixture
) -> None:
    with socket.socket() as closed:
        closed.bind(("localhost", 0))
        port = closed.getsockname()[1]
    with caplog.at_level(logging.ERROR, logger="blazing_agents"):
        answer = ask(f"http://localhost:{port}", chat(), asynchronous=asynchronous)
    assert answer.status == 502
    assert answer.json() == {
        "error": {
            "code": "network_error",
            "message": "Unable to reach Blazing Agents.",
        }
    }
    assert b"localhost" not in answer.body
    assert str(port).encode() not in answer.body
    (record,) = caplog.records
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], APIConnectionError)


@ASYNC
def test_a_created_session_without_a_location_is_a_502_stream_error(
    asynchronous: bool, caplog: pytest.LogCaptureFixture
) -> None:
    def with_functions(request: Req) -> RelayContext:
        return RelayContext(agent_id=AGENT, user_id="user-a", functions=FUNCTIONS)

    call = b'data: {"type":"data-ba-function-call","transient":true}\n\n'
    reply = Response(
        status=201,
        chunks=(call, SSE),
        headers={**STREAM_HEADERS, "x-request-id": "req-chat"},
    )
    with loopback(reply) as (url, _):
        with caplog.at_level(logging.ERROR, logger="blazing_agents"):
            answer = ask(
                url,
                chat(),
                asynchronous=asynchronous,
                resolve_context=with_functions,
            )
    assert answer.status == 502
    assert answer.headers["x-request-id"] == "req-chat"
    assert answer.json() == {
        "error": {"code": "stream_error", "message": "The stream failed."}
    }
    assert b"data-ba-function-call" not in answer.body
    (record,) = caplog.records
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], StreamError)


@ASYNC
def test_a_stream_that_breaks_after_it_started_fails_the_iteration(
    asynchronous: bool,
) -> None:
    reply = chat_reply()
    reply.chunks = (b"partial",)
    reply.complete_chunks = False
    with loopback(reply) as (url, _):
        with opened(url, chat(), asynchronous=asynchronous) as answer:
            assert answer.status == 201
            assert answer.read() == b"partial"
            with pytest.raises(StreamError, match="read failed"):
                answer.read()


@ASYNC
@pytest.mark.parametrize("read_first_chunk", [True, False])
def test_closing_the_answer_closes_the_api_request_and_cancels_the_turn(
    asynchronous: bool, read_first_chunk: bool
) -> None:
    gate, cancelled = Event(), Event()
    reply = chat_reply()
    reply.chunks = (b"first", b"server-still-working")
    reply.chunk_gate = gate
    reply.cancelled = cancelled
    with loopback(reply) as (url, _):
        with opened(url, chat(), asynchronous=asynchronous) as answer:
            if read_first_chunk:
                assert answer.read() == b"first"
            answer.close()
            gate.set()
            assert cancelled.wait(timeout=2)


def test_cancelling_the_task_that_streams_an_answer_closes_the_api_request() -> None:
    gate, cancelled = Event(), Event()
    reply = chat_reply()
    reply.chunks = (b"first", b"server-still-working")
    reply.chunk_gate = gate
    reply.cancelled = cancelled

    async def run(url: str) -> None:
        async def resolver(request: Req, /) -> RelayContext | None:
            return resolve(request)

        async with AsyncBlazingAgents(api_key="ba_test", base_url=url) as client:
            relay = AsyncChatRelay(client=client, resolve_context=resolver)
            response = await relay.handle(USER_A, json.dumps(chat()).encode())
            received: list[bytes] = []

            async def stream() -> None:
                async for chunk in response:
                    received.append(chunk)

            task = asyncio.create_task(stream())
            while not received:
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            gate.set()
            assert await asyncio.to_thread(cancelled.wait, 2)

    with loopback(reply) as (url, _):
        asyncio.run(run(url))


@ASYNC
def test_a_json_answer_has_nothing_to_close(asynchronous: bool) -> None:
    with loopback() as (url, _):
        with opened(url, {"op": "stop"}, asynchronous=asynchronous) as answer:
            answer.close()
            answer.close()
            assert json.loads(answer.drain())["error"]["code"] == "invalid_request"
