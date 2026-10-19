from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from blazing_agents import (
    APIStatusError,
    AsyncBlazingAgents,
    AsyncUserClient,
    BlazingAgents,
    CredentialEchoError,
    UserClient,
)

SPEC = Path(__file__).resolve().parents[1] / "spec" / "openapi.json"
BASE_URL = "https://api.test"

AG = "ag_0123456789abcdef"
SS = "ss_0123456789abcdef"
ID = "id_0123456789abcdef"

User = UserClient | AsyncUserClient
Tenant = BlazingAgents | AsyncBlazingAgents
Client = User | Tenant

# Every public request-sending method of the user clients, keyed by its path from
# the client, with one call per request shape the method can send. The tenant
# clients have each of these methods too. The test records what each call puts on
# the wire and resolves it against the contract, so these entries name no
# operationIds.
CALLS: dict[str, tuple[Callable[[Client], object], ...]] = {
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

# Every public request-sending method of the tenant clients: CALLS plus the
# methods only a tenant client has.
TENANT_CALLS: dict[str, tuple[Callable[[Tenant], object], ...]] = {
    **CALLS,
    "agents.get_spending_limit": (lambda c: c.agents.get_spending_limit(AG),),
    "agents.update_spending_limit": (
        lambda c: c.agents.update_spending_limit(AG, spending_limit=None),
    ),
    "chat_connections.check_health": (lambda c: c.chat_connections.check_health(ID),),
    "chat_connections.create": (
        lambda c: c.chat_connections.create(
            platform="telegram",
            credentials={"bot_token": "123:secret"},
            name="Chat",
            agent_id=AG,
        ),
    ),
    "chat_connections.delete": (lambda c: c.chat_connections.delete(ID),),
    "chat_connections.disable": (lambda c: c.chat_connections.disable(ID),),
    "chat_connections.enable": (lambda c: c.chat_connections.enable(ID),),
    "chat_connections.get": (lambda c: c.chat_connections.get(ID),),
    "chat_connections.iter_deliveries": (
        lambda c: c.chat_connections.iter_deliveries(ID),
    ),
    "chat_connections.list": (lambda c: c.chat_connections.list(),),
    "chat_connections.list_deliveries": (
        lambda c: c.chat_connections.list_deliveries(ID),
    ),
    "chat_connections.repair_delivery": (
        lambda c: c.chat_connections.repair_delivery(ID, ID, expected_attempt=1),
    ),
    "chat_connections.rotate_credentials": (
        lambda c: c.chat_connections.rotate_credentials(
            ID, platform="telegram", credentials={"bot_token": "123:secret"}
        ),
    ),
    "chat_connections.update": (lambda c: c.chat_connections.update(ID, name="Chat"),),
    "chat_deliveries.iter": (lambda c: c.chat_deliveries.iter(),),
    "chat_deliveries.list": (lambda c: c.chat_deliveries.list(),),
    "mcp_connections.create": (
        lambda c: c.mcp_connections.create(
            name="Tools", url="https://mcp.example.com/", auth_type="none"
        ),
    ),
    "mcp_connections.delete": (lambda c: c.mcp_connections.delete(ID),),
    "mcp_connections.get": (lambda c: c.mcp_connections.get(ID),),
    "mcp_connections.list": (lambda c: c.mcp_connections.list(),),
    "mcp_connections.reconnect": (
        lambda c: c.mcp_connections.reconnect(
            ID, url="https://mcp.example.com/", auth_type="none"
        ),
    ),
    "mcp_connections.test": (lambda c: c.mcp_connections.test(ID),),
    "mcp_connections.update": (lambda c: c.mcp_connections.update(ID, name="Tools"),),
    "merchant_bindings.delete": (lambda c: c.merchant_bindings.delete("user-1"),),
    "merchant_bindings.iter": (lambda c: c.merchant_bindings.iter(),),
    "merchant_bindings.list": (lambda c: c.merchant_bindings.list(),),
    "merchant_bindings.put": (
        lambda c: c.merchant_bindings.put("user-1", customer_id="cus_1"),
    ),
    "merchant_connection.create": (
        lambda c: c.merchant_connection.create(
            provider="polar", environment="sandbox", credential="polar_secret"
        ),
    ),
    "merchant_connection.get": (lambda c: c.merchant_connection.get(),),
    "merchant_connection.retire": (lambda c: c.merchant_connection.retire(),),
    "merchant_connection.update": (
        lambda c: c.merchant_connection.update(credential="polar_secret"),
    ),
    "merchant_usage_events.discard": (lambda c: c.merchant_usage_events.discard(ID),),
    "merchant_usage_events.get": (lambda c: c.merchant_usage_events.get(ID),),
    "merchant_usage_events.iter": (lambda c: c.merchant_usage_events.iter(),),
    "merchant_usage_events.list": (lambda c: c.merchant_usage_events.list(),),
    "merchant_usage_events.release": (lambda c: c.merchant_usage_events.release(ID),),
    "merchant_usage_events.retry": (lambda c: c.merchant_usage_events.retry(ID),),
    "merchant_usage_events.summary": (lambda c: c.merchant_usage_events.summary(),),
    "providers.create": (
        lambda c: c.providers.create(name="P", provider_type="openai", api_key="sk"),
    ),
    "providers.delete": (lambda c: c.providers.delete(ID),),
    "providers.get": (lambda c: c.providers.get(ID),),
    "providers.get_thinking_levels": (
        lambda c: c.providers.get_thinking_levels(ID, model="m"),
    ),
    "providers.list": (lambda c: c.providers.list(),),
    "providers.list_models": (lambda c: c.providers.list_models(ID),),
    "providers.update": (lambda c: c.providers.update(ID, name="P"),),
    "tenant.get": (lambda c: c.tenant.get(),),
    "tenant.get_spending_limit": (lambda c: c.tenant.get_spending_limit(),),
    "tenant.update": (lambda c: c.tenant.update(name="Tenant"),),
    "tenant.update_spending_limit": (
        lambda c: c.tenant.update_spending_limit(spending_limit=None),
    ),
    "usage.overview": (lambda c: c.usage.overview(),),
}

# Public methods that send no request. The test walks the view agent() returns as
# "agent().". with_options() returns a copy of the same client, so it adds no
# methods. for_user() returns a user client, which has its own Surface.
NO_REQUEST: dict[str, Callable[[Client], object] | None] = {
    "agent": lambda c: c.agent(AG),
    "with_options": None,
    "for_user": None,
    "close": None,
    "aclose": None,
}

# Operations the SDK sends from inside a chat stream rather than from the call
# that opens it: function handlers passed to chat() and continue_chat() claim a
# backend function call and post its result while the stream is consumed.
INTERNAL = {"claimChatFunctionCall", "resolveChatFunctionCall"}


class Operation:
    def __init__(
        self, method: str, path: str, spec: dict[str, Any], security: list[Any]
    ) -> None:
        self.method = method.upper()
        self.path = path
        self.id: str | None = spec.get("operationId")
        self.scope: str | None = spec.get("x-scope")
        self.credential_bearing: bool = spec.get("x-credential-bearing", False)
        self.api_key = any("ApiKey" in way for way in spec.get("security", security))
        segments = path.split("/")
        self.literals = sum(not segment.startswith("{") for segment in segments)
        self.pattern = re.compile(
            "/".join(
                "[^/]+" if segment.startswith("{") else re.escape(segment)
                for segment in segments
            )
        )

    def __str__(self) -> str:
        access = "accepts" if self.api_key else "refuses"
        return (
            f"{self.id or 'operation without operationId'} ({self.method} "
            f"{self.path}, x-scope {self.scope}, {access} an API key)"
        )


@dataclass(frozen=True)
class Surface:
    """A client family and the contract operations it must send."""

    name: str
    calls: dict[str, tuple[Callable[[Any], object], ...]]
    open: Callable[[Tenant], Client]
    sends: Callable[[Operation], bool]
    user_id: str | None


SURFACES = {
    "user": Surface(
        name="user client",
        calls=CALLS,
        open=lambda tenant: tenant.for_user("user-1"),
        sends=lambda operation: operation.api_key and operation.scope == "end-user",
        user_id="user-1",
    ),
    "tenant": Surface(
        name="tenant client",
        calls=TENANT_CALLS,
        open=lambda tenant: tenant,
        sends=lambda operation: operation.api_key,
        user_id=None,
    ),
}


def contract() -> list[Operation]:
    """Every operation in the contract, including those no API key may call."""
    document: dict[str, Any] = json.loads(SPEC.read_text())
    return [
        Operation(method, path, spec, document["security"])
        for path, methods in document["paths"].items()
        for method, spec in methods.items()
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
        if name in NO_REQUEST:
            if open_view := NO_REQUEST[name]:
                names |= public_methods(
                    open_view(cast(Client, view)), f"{prefix}{name}()."
                )
        elif inspect.ismethod(attribute):
            names.add(prefix + name)
        elif type(attribute).__module__.startswith("blazing_agents"):
            names |= public_methods(attribute, f"{prefix}{name}.")
    return names


@dataclass(frozen=True)
class Reply:
    """The response every request gets, and the call failures it may cause."""

    status: int
    body: object
    expected: tuple[type[Exception], ...]


NOT_FOUND = Reply(
    404, {"error": {"code": "not_found", "message": "Not found"}}, (APIStatusError,)
)
# A successful body carrying a credential key. A guarded operation raises
# CredentialEchoError; any other call fails to decode it, which is fine here.
CREDENTIAL_ECHO = Reply(200, {"apiKey": "sk-echoed"}, (Exception,))


def send_sync(call: Callable[[Client], object], client: Client, reply: Reply) -> bool:
    """Send the call's requests and report whether it rejected a credential echo."""
    try:
        result = call(client)
        if isinstance(result, Iterator):
            next(cast(Iterator[object], result), None)
    except CredentialEchoError:
        return True
    except reply.expected:
        pass
    return False


async def send_async(
    call: Callable[[Client], object], client: Client, reply: Reply
) -> bool:
    """Send the call's requests and report whether it rejected a credential echo."""
    try:
        result = call(client)
        if isinstance(result, AsyncIterator):
            await anext(cast(AsyncIterator[object], result), None)
        elif inspect.isawaitable(result):
            await result
    except CredentialEchoError:
        return True
    except reply.expected:
        pass
    return False


@dataclass(frozen=True)
class Observation:
    public: set[str]
    sent: dict[str, list[httpx.Request]]
    """The requests each method sent."""
    echo_rejected: list[httpx.Request]
    """The last request of each call that raised CredentialEchoError."""


def observe(surface: Surface, asynchronous: bool, reply: Reply) -> Observation:
    """Run the calls the surface's client has and record the requests each sends."""
    requests: list[httpx.Request] = []
    echo_rejected: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(reply.status, json=reply.body)

    sent: dict[str, list[httpx.Request]] = {}
    transport = httpx.MockTransport(record)

    async def run_async() -> set[str]:
        async with AsyncBlazingAgents(
            api_key="ba_test",
            base_url=BASE_URL,
            http_client=httpx.AsyncClient(transport=transport),
        ) as tenant:
            client = surface.open(tenant)
            public = public_methods(client)
            for method in sorted(surface.calls.keys() & public):
                for call in surface.calls[method]:
                    if await send_async(call, client, reply):
                        echo_rejected.append(requests[-1])
                sent[method] = requests.copy()
                requests.clear()
            return public

    if asynchronous:
        return Observation(asyncio.run(run_async()), sent, echo_rejected)
    with BlazingAgents(
        api_key="ba_test",
        base_url=BASE_URL,
        http_client=httpx.Client(transport=transport),
    ) as tenant:
        client = surface.open(tenant)
        public = public_methods(client)
        for method in sorted(surface.calls.keys() & public):
            for call in surface.calls[method]:
                if send_sync(call, client, reply):
                    echo_rejected.append(requests[-1])
            sent[method] = requests.copy()
            requests.clear()
        return Observation(public, sent, echo_rejected)


def test_every_api_key_operation_names_its_scope() -> None:
    unscoped = [
        str(operation)
        for operation in contract()
        if operation.api_key
        and (operation.id is None or operation.scope not in {"end-user", "tenant"})
    ]
    assert not unscoped, "API-key operations without an operationId and x-scope:\n" + (
        "\n".join(unscoped)
    )


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("surface", SURFACES.values(), ids=SURFACES.keys())
def test_client_matches_contract(surface: Surface, asynchronous: bool) -> None:
    operations = contract()
    by_id = {operation.id: operation for operation in operations}
    observation = observe(surface, asynchronous, NOT_FOUND)
    public, sent = observation.public, observation.sent
    problems: list[str] = []

    problems += [
        f"{method}: public {surface.name} method missing from its calls table"
        for method in sorted(public - surface.calls.keys())
    ]
    problems += [
        f"{method}: the calls table names a method the {surface.name} lacks"
        for method in sorted(surface.calls.keys() - public)
    ]

    covered: set[str | None] = set(INTERNAL)
    for method, requests in sent.items():
        if not requests:
            problems.append(f"{method}: sent no request")
        for request in requests:
            if request.headers.get("x-ba-user-id") != surface.user_id:
                problems.append(
                    f"{method}: sends X-BA-User-Id "
                    f"{request.headers.get('x-ba-user-id')!r}, "
                    f"expected {surface.user_id!r}"
                )
            operation = resolve(operations, request)
            if operation is None:
                problems.append(
                    f"{method}: sends {request.method} {request.url.raw_path.decode()}"
                    ", which is not in the contract"
                )
            elif surface.sends(operation):
                covered.add(operation.id)
            else:
                problems.append(f"{method}: sends {operation}")

    for operation_id in sorted(INTERNAL):
        operation = by_id.get(operation_id)
        if operation is None or not surface.sends(operation):
            problems.append(
                f"INTERNAL: {operation or operation_id} is not sent by the "
                f"{surface.name}"
            )

    problems += [
        f"{operation}: not sent by any {surface.name} method"
        for operation in operations
        if surface.sends(operation) and operation.id not in covered
    ]

    assert not problems, (
        f"{surface.name} drifted from spec/openapi.json:\n" + "\n".join(problems)
    )


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("surface", SURFACES.values(), ids=SURFACES.keys())
def test_client_guards_exactly_the_credential_bearing_operations(
    surface: Surface, asynchronous: bool
) -> None:
    operations = contract()
    observation = observe(surface, asynchronous, CREDENTIAL_ECHO)
    guarded = {
        str(resolve(operations, request)) for request in observation.echo_rejected
    }
    flagged = {
        str(operation)
        for operation in operations
        if operation.credential_bearing and surface.sends(operation)
    }
    assert guarded == flagged, (
        f"{surface.name} credential guard drifted from x-credential-bearing:\n"
        + "\n".join(
            [f"unguarded: {operation}" for operation in sorted(flagged - guarded)]
            + [f"guarded, not flagged: {op}" for op in sorted(guarded - flagged)]
        )
    )
