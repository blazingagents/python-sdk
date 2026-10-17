from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from blazing_agents import (
    APIStatusError,
    AsyncBlazingAgents,
    AsyncUserClient,
    BlazingAgents,
    UserClient,
)

SPEC = Path(__file__).resolve().parents[1] / "spec" / "openapi.json"
BASE_URL = "https://api.test"

AG = "ag_0123456789abcdef"
SS = "ss_0123456789abcdef"
ID = "id_0123456789abcdef"

Client = UserClient | AsyncUserClient
Call = Callable[[Client], object]

# Every public request-sending method of the user clients, keyed by its path from
# the client, with one call per request shape the method can send. The test
# records what each call puts on the wire and resolves it against the contract, so
# these entries name no operationIds.
CALLS: dict[str, tuple[Call, ...]] = {
    "agents.create": (lambda c: c.agents.create(name="Agent"),),
    "agents.delete": (lambda c: c.agents.delete(AG, include_artifacts=False),),
    "agents.disable": (lambda c: c.agents.disable(AG),),
    "agents.enable": (lambda c: c.agents.enable(AG),),
    "agents.get": (lambda c: c.agents.get(AG),),
    "agents.list": (lambda c: c.agents.list(),),
    "agents.list_mcp_attachments": (lambda c: c.agents.list_mcp_attachments(AG),),
    "agents.remove_avatar": (lambda c: c.agents.remove_avatar(AG),),
    "agents.update": (lambda c: c.agents.update(AG, name="Agent"),),
    "agents.update_mcp_attachment": (
        lambda c: c.agents.update_mcp_attachment(AG, ID, forward_user_id=True),
    ),
    "agents.upload_avatar": (
        lambda c: c.agents.upload_avatar(AG, b"\x89PNG", filename="a.png"),
    ),
    "artifacts.create_download_url": (
        lambda c: c.artifacts.create_download_url(artifact_id=ID),
    ),
    "artifacts.delete": (lambda c: c.artifacts.delete(artifact_id=ID),),
    "artifacts.get": (lambda c: c.artifacts.get(artifact_id=ID),),
    "artifacts.iter": (lambda c: c.artifacts.iter(),),
    "artifacts.list": (lambda c: c.artifacts.list(),),
    "chat": (
        lambda c: c.chat(agent_id=AG, message={"role": "user", "content": "Hi"}),
        lambda c: c.chat(
            agent_id=AG, session_id=SS, message={"role": "user", "content": "Hi"}
        ),
    ),
    "completion": (lambda c: c.completion(agent_id=AG, prompt="Hi"),),
    "completion_stream": (lambda c: c.completion_stream(agent_id=AG, prompt="Hi"),),
    "continue_chat": (
        lambda c: c.continue_chat(
            agent_id=AG,
            session_id=SS,
            decisions=[{"approval_id": ID, "approved": True}],
        ),
    ),
    "memories.create": (lambda c: c.memories.create(agent_id=AG, text="Note"),),
    "memories.delete": (lambda c: c.memories.delete(agent_id=AG, memory_id=ID),),
    "memories.get": (lambda c: c.memories.get(agent_id=AG, memory_id=ID),),
    "memories.iter": (lambda c: c.memories.iter(agent_id=AG),),
    "memories.list": (lambda c: c.memories.list(agent_id=AG),),
    "memories.update": (
        lambda c: c.memories.update(agent_id=AG, memory_id=ID, text="Note"),
    ),
    "object": (lambda c: c.object(agent_id=AG, output_type=str, prompt="Hi"),),
    "object_stream": (
        lambda c: c.object_stream(agent_id=AG, output_type=str, prompt="Hi"),
    ),
    "prompts.create": (lambda c: c.prompts.create(name="P", template="Hi"),),
    "prompts.delete": (lambda c: c.prompts.delete(prompt_id=ID),),
    "prompts.get": (lambda c: c.prompts.get(prompt_id=ID),),
    "prompts.list": (lambda c: c.prompts.list(),),
    "prompts.update": (lambda c: c.prompts.update(prompt_id=ID, name="P"),),
    "sessions.delete": (
        lambda c: c.sessions.delete(agent_id=AG, session_id=SS, delete_artifacts=False),
    ),
    "sessions.fork": (
        lambda c: c.sessions.fork(AG, SS, message_id=ID, idempotency_key="fork-1"),
    ),
    "sessions.get": (lambda c: c.sessions.get(AG, SS),),
    "sessions.inputs": (lambda c: c.sessions.inputs(agent_id=AG, session_id=SS),),
    "sessions.iter": (lambda c: c.sessions.iter(agent_id=AG),),
    "sessions.list": (lambda c: c.sessions.list(agent_id=AG),),
    "sessions.list_latest": (lambda c: c.sessions.list_latest(),),
    "sessions.messages": (lambda c: c.sessions.messages(agent_id=AG, session_id=SS),),
    "sessions.stop": (
        lambda c: c.sessions.stop(agent_id=AG, session_id=SS, turn_id=ID),
    ),
    "sessions.submit_input": (
        lambda c: c.sessions.submit_input(
            agent_id=AG,
            session_id=SS,
            request_id=ID,
            message={"role": "user", "content": "Hi"},
        ),
    ),
    "sessions.tool_approvals": (
        lambda c: c.sessions.tool_approvals(agent_id=AG, session_id=SS),
    ),
    "tasks.cancel_run": (lambda c: c.tasks.cancel_run(ID, ID),),
    "tasks.create": (lambda c: c.tasks.create(agent_id=AG, name="Task", prompt="Hi"),),
    "tasks.delete": (lambda c: c.tasks.delete(ID),),
    "tasks.get": (lambda c: c.tasks.get(ID),),
    "tasks.get_run": (lambda c: c.tasks.get_run(ID, ID),),
    "tasks.iter": (lambda c: c.tasks.iter(),),
    "tasks.iter_runs": (lambda c: c.tasks.iter_runs(ID),),
    "tasks.list": (lambda c: c.tasks.list(),),
    "tasks.list_runs": (lambda c: c.tasks.list_runs(ID),),
    "tasks.run_messages": (lambda c: c.tasks.run_messages(ID, ID),),
    "tasks.submit": (lambda c: c.tasks.submit(ID),),
    "tasks.update": (lambda c: c.tasks.update(ID, name="Task"),),
    "usage.get": (lambda c: c.usage.get(),),
    "usage.get_for_agent": (lambda c: c.usage.get_for_agent(AG),),
    "usage.sessions": (lambda c: c.usage.sessions([SS]),),
    "workspaces.create": (lambda c: c.workspaces.create(),),
    "workspaces.delete": (lambda c: c.workspaces.delete(workspace_id=ID),),
    "workspaces.get": (lambda c: c.workspaces.get(workspace_id=ID),),
    "workspaces.iter": (lambda c: c.workspaces.iter(),),
    "workspaces.list": (lambda c: c.workspaces.list(),),
    "workspaces.update": (lambda c: c.workspaces.update(workspace_id=ID, name="W"),),
    "agent().skills.copy": (
        lambda c: c.agent(AG).skills.copy(skill_id=ID, destination_agent_ids=[AG]),
    ),
    "agent().skills.create": (
        lambda c: c.agent(AG).skills.create(path="SKILL.md", content="# Skill"),
    ),
    "agent().skills.delete": (lambda c: c.agent(AG).skills.delete(skill_id=ID),),
    "agent().skills.delete_file": (
        lambda c: c.agent(AG).skills.delete_file(skill_id=ID, path="a.md"),
    ),
    "agent().skills.get": (lambda c: c.agent(AG).skills.get(skill_id=ID),),
    "agent().skills.iter": (lambda c: c.agent(AG).skills.iter(),),
    "agent().skills.list": (lambda c: c.agent(AG).skills.list(),),
    "agent().skills.read_file": (
        lambda c: c.agent(AG).skills.read_file(skill_id=ID, path="a.md"),
    ),
    "agent().skills.replace_file": (
        lambda c: c.agent(AG).skills.replace_file(
            skill_id=ID, path="a.md", content=b"x"
        ),
    ),
    "agent().skills.upload": (
        lambda c: c.agent(AG).skills.upload(
            archive_type="zip", file=b"PK", filename="s.zip"
        ),
    ),
}

# Methods that return another view of the client instead of sending a request.
# The test walks the view agent() returns as "agent().". with_options() returns a
# copy of the same client, so it adds no methods.
VIEWS: dict[str, Callable[[Client], object] | None] = {
    "agent": lambda c: c.agent(AG),
    "with_options": None,
}

# Operations the SDK sends from inside a chat stream rather than from the call
# that opens it: function handlers passed to chat() and continue_chat() claim a
# backend function call and post its result while the stream is consumed.
INTERNAL = {"claimChatFunctionCall", "resolveChatFunctionCall"}


class Operation:
    def __init__(self, method: str, path: str, spec: dict[str, Any]) -> None:
        self.method = method.upper()
        self.path = path
        self.id: str = spec["operationId"]
        self.scope: str | None = spec.get("x-scope")
        segments = path.split("/")
        self.literals = sum(not segment.startswith("{") for segment in segments)
        self.pattern = re.compile(
            "/".join(
                "[^/]+" if segment.startswith("{") else re.escape(segment)
                for segment in segments
            )
        )

    def __str__(self) -> str:
        return f"{self.id} ({self.method} {self.path}, x-scope {self.scope})"


def contract() -> list[Operation]:
    paths: dict[str, dict[str, Any]] = json.loads(SPEC.read_text())["paths"]
    return [
        Operation(method, path, spec)
        for path, methods in paths.items()
        for method, spec in methods.items()
        if "operationId" in spec
    ]


def resolve(operations: list[Operation], request: httpx.Request) -> Operation | None:
    path = request.url.raw_path.decode().split("?")[0]
    matches = [
        operation
        for operation in operations
        if operation.method == request.method and operation.pattern.fullmatch(path)
    ]
    return max(matches, key=lambda operation: operation.literals, default=None)


def public_methods(view: object, prefix: str = "") -> set[str]:
    names: set[str] = set()
    for name in dir(view):
        if name.startswith("_"):
            continue
        attribute = getattr(view, name)
        if name in VIEWS:
            if open_view := VIEWS[name]:
                names |= public_methods(
                    open_view(cast(Client, view)), f"{prefix}{name}()."
                )
        elif inspect.ismethod(attribute):
            names.add(prefix + name)
        elif type(attribute).__module__.startswith("blazing_agents"):
            names |= public_methods(attribute, f"{prefix}{name}.")
    return names


def send_sync(call: Call, client: Client) -> None:
    with suppress(APIStatusError):
        result = call(client)
        if isinstance(result, Iterator):
            next(cast(Iterator[object], result), None)


async def send_async(call: Call, client: Client) -> None:
    with suppress(APIStatusError):
        result = call(client)
        if isinstance(result, AsyncIterator):
            await anext(cast(AsyncIterator[object], result), None)
        elif inspect.isawaitable(result):
            await result


def observe(asynchronous: bool) -> tuple[set[str], dict[str, list[httpx.Request]]]:
    """Run the CALLS the user client has and record the requests each sends."""
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            404, json={"error": {"code": "not_found", "message": "Not found"}}
        )

    sent: dict[str, list[httpx.Request]] = {}
    transport = httpx.MockTransport(record)

    async def run_async() -> set[str]:
        async with AsyncBlazingAgents(
            api_key="ba_test",
            base_url=BASE_URL,
            http_client=httpx.AsyncClient(transport=transport),
        ) as tenant:
            user = tenant.for_user("user-1")
            public = public_methods(user)
            for method in sorted(CALLS.keys() & public):
                for call in CALLS[method]:
                    await send_async(call, user)
                sent[method] = requests.copy()
                requests.clear()
            return public

    if asynchronous:
        return asyncio.run(run_async()), sent
    with BlazingAgents(
        api_key="ba_test",
        base_url=BASE_URL,
        http_client=httpx.Client(transport=transport),
    ) as tenant:
        user = tenant.for_user("user-1")
        public = public_methods(user)
        for method in sorted(CALLS.keys() & public):
            for call in CALLS[method]:
                send_sync(call, user)
            sent[method] = requests.copy()
            requests.clear()
        return public, sent


@pytest.mark.parametrize("asynchronous", [False, True])
def test_user_client_matches_contract_scope(asynchronous: bool) -> None:
    operations = contract()
    by_id = {operation.id: operation for operation in operations}
    public, sent = observe(asynchronous)
    problems: list[str] = []

    problems += [
        f"{method}: public user-client method missing from CALLS"
        for method in sorted(public - CALLS.keys())
    ]
    problems += [
        f"{method}: CALLS names a method the user client lacks"
        for method in sorted(CALLS.keys() - public)
    ]

    covered = set(INTERNAL)
    for method, requests in sent.items():
        if not requests:
            problems.append(f"{method}: sent no request")
        for request in requests:
            operation = resolve(operations, request)
            if operation is None:
                problems.append(
                    f"{method}: sends {request.method} {request.url.raw_path.decode()}"
                    ", which is not in the contract"
                )
            elif operation.scope != "end-user":
                problems.append(f"{method}: sends {operation}")
            else:
                covered.add(operation.id)

    for operation_id in sorted(INTERNAL):
        operation = by_id.get(operation_id)
        if operation is None or operation.scope != "end-user":
            problems.append(
                f"INTERNAL: {operation or operation_id} is not an end-user operation"
            )

    problems += [
        f"{operation}: not sent by any user-client method"
        for operation in operations
        if operation.scope == "end-user" and operation.id not in covered
    ]

    assert not problems, "User client drifted from spec/openapi.json:\n" + "\n".join(
        problems
    )
