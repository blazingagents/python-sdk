from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from pydantic import ValidationError
from test_clients import Response, loopback

from blazing_agents import (
    APIStatusError,
    AsyncBlazingAgents,
    BlazingAgents,
    TurnInterruptedEvent,
)

AGENT_ID = "ag_0123456789abcdef"
MESSAGE: Any = {"role": "user", "parts": [{"type": "text", "text": "Hello"}]}
EVENT: dict[str, Any] = {
    "type": "data-turn-interrupted",
    "data": {"code": "turn_interrupted"},
    "transient": True,
}
ERROR_TEXT = (
    "The turn was interrupted before it finished. Read the session's messages "
    "to see what was saved. The session may stay busy for up to a minute."
)


def test_typed_interruption_event_decode() -> None:
    event = TurnInterruptedEvent.model_validate_json(json.dumps(EVENT))
    assert event.type == "data-turn-interrupted"
    assert event.transient is True
    assert event.data.code == "turn_interrupted"


@pytest.mark.parametrize("transient", [1, 1.0, False, "true"])
def test_interruption_event_transient_requires_true_boolean(
    transient: object,
) -> None:
    with pytest.raises(ValidationError):
        TurnInterruptedEvent.model_validate({**EVENT, "transient": transient})


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "data-model-spending-limit"},
        {"transient": False},
        {"data": {"code": "internal"}},
        {"data": {"code": "turn_interrupted", "extra": True}},
        {"data": {}},
        {"extra": True},
    ],
)
def test_invalid_interruption_events_are_rejected(patch: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TurnInterruptedEvent.model_validate_json(json.dumps({**EVENT, **patch}))


@pytest.mark.parametrize("asynchronous", [False, True])
def test_chat_preserves_interrupted_stream_bytes(asynchronous: bool) -> None:
    payload = (
        "".join(
            f"data: {json.dumps(chunk)}\n\n"
            for chunk in (
                {"type": "start", "messageId": "answer"},
                {"type": "text-start", "id": "text"},
                {"type": "text-delta", "id": "text", "delta": "Half an answ"},
                EVENT,
                {"type": "error", "errorText": ERROR_TEXT},
            )
        )
        + "data: [DONE]\n\n"
    ).encode()
    with loopback(
        Response(
            chunks=(payload[:40], payload[40:]),
            headers={
                "content-type": "text/event-stream",
                "location": f"/v1/agents/{AGENT_ID}/sessions/ss_0123456789abcdef",
                "x-ba-turn-id": "turn_0123456789abcdef",
            },
        )
    ) as (base_url, _):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                stream = await client.chat(agent_id=AGENT_ID, message=MESSAGE)
                assert b"".join([chunk async for chunk in stream]) == payload

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                stream = client.chat(agent_id=AGENT_ID, message=MESSAGE)
                assert b"".join(stream) == payload


@pytest.mark.parametrize("asynchronous", [False, True])
def test_unresponsive_turn_error_carries_retry_after(asynchronous: bool) -> None:
    body = {
        "error": {
            "code": "session_turn_unresponsive",
            "message": "The previous turn in this session stopped responding.",
            "details": {"retryAfterSeconds": 23},
        }
    }
    with loopback(Response(status=409, body=body, headers={"retry-after": "23"})) as (
        base_url,
        _,
    ):

        async def run_async() -> APIStatusError:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                with pytest.raises(APIStatusError) as raised:
                    await client.chat(
                        agent_id=AGENT_ID,
                        session_id="ss_0123456789abcdef",
                        message=MESSAGE,
                    )
                return raised.value

        if asynchronous:
            error = asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                with pytest.raises(APIStatusError) as raised:
                    client.chat(
                        agent_id=AGENT_ID,
                        session_id="ss_0123456789abcdef",
                        message=MESSAGE,
                    )
                error = raised.value

    assert error.code == "session_turn_unresponsive"
    assert error.status_code == 409
    assert error.retry_after == "23"
    assert error.details == {"retryAfterSeconds": 23}
