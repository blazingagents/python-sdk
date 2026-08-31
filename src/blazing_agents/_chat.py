from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import quote

import httpx

from ._downloads import AsyncByteStream, ByteStream
from ._errors import StreamError
from ._transport import OMITTED, _Omitted, _Request
from ._types import ChatTrigger, Timeout

_SESSION_ID = re.compile(r"ss_[0-9A-Za-z]{16}\Z")


class ChatStream(ByteStream):
    """A single-consumer raw chat response with its resolved Session ID."""

    def __init__(self, response: httpx.Response, session_id: str | None) -> None:
        super().__init__(response)
        self.session_id = _session_id(response) if session_id is None else session_id


class AsyncChatStream(AsyncByteStream):
    """An asynchronous single-consumer raw chat response."""

    def __init__(self, response: httpx.Response, session_id: str | None) -> None:
        super().__init__(response)
        self.session_id = _session_id(response) if session_id is None else session_id


def _session_id(response: httpx.Response) -> str:
    location: str | None = response.headers.get("location")
    if location is None:
        raise StreamError(
            "The server did not return a Session ID in the Location header.",
            response=response,
        )
    candidate = location.rsplit("/", 1)[-1]
    if _SESSION_ID.fullmatch(candidate) is None:
        raise StreamError(
            "The server returned a malformed Session Location header.",
            response=response,
        )
    return candidate


def _chat_body(
    *,
    message: dict[str, object] | _Omitted,
    prompt_id: str | _Omitted,
    variables: dict[str, str] | _Omitted,
    trigger: ChatTrigger | _Omitted,
    message_id: str | _Omitted,
    version: int | _Omitted,
    user_id: str | _Omitted,
    metadata: dict[str, object] | _Omitted,
) -> dict[str, object]:
    has_message = not isinstance(message, _Omitted)
    has_prompt = not isinstance(prompt_id, _Omitted)
    if has_message == has_prompt:
        raise ValueError("Provide exactly one of message or prompt_id.")
    if not isinstance(variables, _Omitted) and not has_prompt:
        raise ValueError("variables can only be used with prompt_id.")
    if not isinstance(trigger, _Omitted) and trigger not in {
        "submit-message",
        "regenerate-message",
    }:
        raise ValueError("trigger must be submit-message or regenerate-message.")
    if not isinstance(message_id, _Omitted) and not message_id:
        raise ValueError("message_id must not be empty.")

    body: dict[str, object] = {}
    if has_message:
        body["message"] = message
    else:
        body["promptId"] = prompt_id
        if not isinstance(variables, _Omitted):
            body["variables"] = variables
    for wire_name, value in (
        ("trigger", trigger),
        ("messageId", message_id),
        ("version", version),
        ("userId", user_id),
        ("metadata", metadata),
    ):
        if not isinstance(value, _Omitted):
            body[wire_name] = value
    return body


def chat_request(
    *,
    agent_id: str,
    message: dict[str, object] | _Omitted = OMITTED,
    prompt_id: str | _Omitted = OMITTED,
    variables: dict[str, str] | _Omitted = OMITTED,
    trigger: ChatTrigger | _Omitted = OMITTED,
    message_id: str | _Omitted = OMITTED,
    session_id: str | _Omitted = OMITTED,
    version: int | _Omitted = OMITTED,
    user_id: str | _Omitted = OMITTED,
    metadata: dict[str, object] | _Omitted = OMITTED,
    client_request_id: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
    timeout: Timeout | _Omitted = OMITTED,
) -> tuple[_Request, str | None]:
    path = f"/v1/agents/{quote(agent_id, safe='')}/sessions"
    if isinstance(session_id, _Omitted):
        resolved_session_id = None
        if trigger == "regenerate-message":
            raise ValueError("regenerate-message can only resume an existing Session.")
    else:
        if not isinstance(version, _Omitted):
            raise ValueError("A Version Pin can only be set when creating a Session.")
        resolved_session_id = session_id
        path = f"{path}/{quote(resolved_session_id, safe='')}"
    return (
        _Request(
            "POST",
            path,
            client_request_id=client_request_id,
            json_body=_chat_body(
                message=message,
                prompt_id=prompt_id,
                variables=variables,
                trigger=trigger,
                message_id=message_id,
                version=version,
                user_id=user_id,
                metadata=metadata,
            ),
            extra_headers=extra_headers,
            timeout=timeout,
        ),
        resolved_session_id,
    )
