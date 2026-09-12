from __future__ import annotations

import asyncio
import copy
import json
from typing import Any, get_args

import pytest
from pydantic import TypeAdapter, ValidationError
from test_clients import AGENT, AGENT_VERSION, Response, loopback

from blazing_agents import (
    Agent,
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalPolicyInput,
    AsyncBlazingAgents,
    BlazingAgents,
    BuiltinToolReference,
    McpToolReference,
    ToolApproval,
    ToolReference,
)
from blazing_agents._transport import OMITTED

POLICY: ApprovalPolicyInput = {
    "default": "deny",
    "overrides": [
        {"tool": {"type": "builtin", "name": "bash"}, "decision": "manual"},
        {
            "tool": {
                "type": "mcp",
                "connection_id": "mcp_0123456789abcdef",
                "name": "send_mail",
            },
            "decision": "auto",
        },
    ],
}
WIRE: dict[str, Any] = {
    "default": "deny",
    "overrides": [
        {"tool": {"type": "builtin", "name": "bash"}, "decision": "manual"},
        {
            "tool": {
                "type": "mcp",
                "connectionId": "mcp_0123456789abcdef",
                "name": "send_mail",
            },
            "decision": "auto",
        },
    ],
}
APPROVAL: dict[str, Any] = {
    "approvalId": "approval-1",
    "toolName": "runtime_mail",
    "toolCallId": "call-1",
    "input": {"recipient": "example"},
    "decision": "pending",
    "reason": None,
}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_policy_client_round_trip_and_restoration(asynchronous: bool) -> None:
    original = copy.deepcopy(POLICY)
    agent = {**AGENT, "approvalInChat": WIRE, "approvalInTasks": {"default": "auto"}}
    version: dict[str, Any] = {
        **AGENT_VERSION,
        "approvalInChat": WIRE,
        "approvalInTasks": {"default": "full", "overrides": []},
    }
    with loopback(
        Response(body=agent),
        Response(body=agent),
        Response(body=agent),
        Response(body=agent),
        Response(body=agent),
        Response(body={"agents": [agent]}),
        Response(body={"data": [version], "nextCursor": None}),
        Response(body=version),
        Response(body=version),
        Response(body=agent),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                created = await client.agents.create(
                    name="test",
                    approval_in_chat=POLICY,
                    approval_in_tasks={"default": "auto"},
                )
                assert created.approval_in_chat.default == "deny"
                await client.agents.update(
                    AGENT["id"],
                    name="renamed",
                    approval_in_chat=OMITTED,
                    approval_in_tasks=OMITTED,
                )
                await client.agents.update(
                    AGENT["id"], approval_in_chat={"default": "full"}
                )
                await client.agents.update(
                    AGENT["id"], approval_in_tasks={"default": "deny", "overrides": []}
                )
                assert (
                    await client.agents.get(AGENT["id"])
                ).approval_in_tasks.default == "auto"
                assert (await client.agents.list()).agents[
                    0
                ].approval_in_chat.default == "deny"
                assert (await client.agents.list_versions(AGENT["id"])).data[
                    0
                ].approval_in_chat.default == "deny"
                assert (
                    await client.agents.get_version(AGENT["id"], 3)
                ).approval_in_chat.default == "deny"
                await client.agents.restore_version(AGENT["id"], 3)

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                created = client.agents.create(
                    name="test",
                    approval_in_chat=POLICY,
                    approval_in_tasks={"default": "auto"},
                )
                assert created.approval_in_chat.default == "deny"
                client.agents.update(
                    AGENT["id"],
                    name="renamed",
                    approval_in_chat=OMITTED,
                    approval_in_tasks=OMITTED,
                )
                client.agents.update(AGENT["id"], approval_in_chat={"default": "full"})
                client.agents.update(
                    AGENT["id"], approval_in_tasks={"default": "deny", "overrides": []}
                )
                assert (
                    client.agents.get(AGENT["id"]).approval_in_tasks.default == "auto"
                )
                assert client.agents.list().agents[0].approval_in_chat.default == "deny"
                assert (
                    client.agents.list_versions(AGENT["id"])
                    .data[0]
                    .approval_in_chat.default
                    == "deny"
                )
                assert (
                    client.agents.get_version(AGENT["id"], 3).approval_in_chat.default
                    == "deny"
                )
                client.agents.restore_version(AGENT["id"], 3)
    bodies = [
        json.loads(request.body) if request.body else None for request in state.requests
    ]
    assert bodies[0] == {
        "name": "test",
        "approvalInChat": WIRE,
        "approvalInTasks": {"default": "auto"},
    }
    assert bodies[1] == {"name": "renamed"}
    assert bodies[2] == {"approvalInChat": {"default": "full"}}
    assert bodies[3] == {"approvalInTasks": {"default": "deny", "overrides": []}}
    assert bodies[9] is not None
    assert bodies[9]["approvalInChat"] == WIRE
    assert bodies[9]["approvalInTasks"] == {"default": "full", "overrides": []}
    assert original == POLICY


@pytest.mark.parametrize("mode", get_args(ApprovalDecision))
def test_policy_modes(mode: str) -> None:
    policy = ApprovalPolicy.model_validate(
        {
            "default": mode,
            "overrides": [
                {
                    "tool": {"type": "builtin", "name": "activate_skill"},
                    "decision": mode,
                }
            ],
        }
    )
    assert policy.default == mode
    assert policy.overrides[0].decision == mode


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"default": None},
        {"default": "approved"},
        {"default": "full", "overrides": None},
        {
            "default": "full",
            "overrides": [
                {"tool": {"type": "builtin", "name": "bash"}, "decision": "pending"}
            ],
        },
    ],
)
def test_invalid_policy(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ApprovalPolicy.model_validate(payload)


def test_default_policies_and_structured_references() -> None:
    agent = Agent.model_validate_json(json.dumps(AGENT))
    assert agent.approval_in_chat.model_dump() == {"default": "full", "overrides": []}
    assert agent.approval_in_chat is not agent.approval_in_tasks
    parsed = ApprovalPolicy.model_validate(WIRE)
    assert isinstance(parsed.overrides[0].tool, BuiltinToolReference)
    assert isinstance(parsed.overrides[1].tool, McpToolReference)
    assert parsed.overrides[1].tool.connection_id == "mcp_0123456789abcdef"
    assert parsed.model_dump(by_alias=True) == WIRE
    for bad in [
        {"type": "builtin", "name": "workspace"},
        {"type": "unknown", "name": "bash"},
        {"type": "mcp", "name": "send_mail"},
        {"type": "mcp", "connectionId": "invalid", "name": "send_mail"},
        {"type": "mcp", "connectionId": "mcp_0123456789abcdef", "name": ""},
    ]:
        with pytest.raises(ValidationError):
            TypeAdapter(ToolReference).validate_python(bad)


def test_approval_metadata_optional_and_null() -> None:
    old = ToolApproval.model_validate(APPROVAL)
    assert old.tool is None
    assert "tool" not in old.model_fields_set
    for tool in [
        None,
        {"type": "builtin", "name": "bash"},
        {"type": "mcp", "connectionId": "mcp_0123456789abcdef", "name": "send_mail"},
    ]:
        for decision in ["pending", "approved", "denied"]:
            data = {
                **APPROVAL,
                "tool": tool,
                "decision": decision,
                "assistantMessageId": "message-1",
                "createdAt": "2026-09-12T10:00:00Z",
                "decidedAt": None,
            }
            parsed = ToolApproval.model_validate_json(json.dumps(data))
            assert parsed.assistant_message_id == "message-1"
            assert parsed.created_at is not None
            assert parsed.decided_at is None
            assert "decided_at" in parsed.model_fields_set
    decided = ToolApproval.model_validate_json(
        json.dumps({**APPROVAL, "decidedAt": "2026-09-12T10:01:00+01:00"})
    )
    assert decided.decided_at is not None
    for field, value in [
        ("assistantMessageId", None),
        ("createdAt", None),
        ("assistantMessageId", ""),
        ("createdAt", "2026-09-12"),
        ("decidedAt", "invalid"),
        ("decision", "auto"),
    ]:
        with pytest.raises(ValidationError):
            ToolApproval.model_validate_json(json.dumps({**APPROVAL, field: value}))


@pytest.mark.parametrize("asynchronous", [False, True])
def test_existing_approval_lifecycle_with_metadata(asynchronous: bool) -> None:
    approval = {
        **APPROVAL,
        "tool": WIRE["overrides"][1]["tool"],
        "assistantMessageId": "message-1",
        "createdAt": "2026-09-12T10:00:00Z",
        "decidedAt": None,
    }
    with loopback(
        Response(body={"data": [approval], "continuation": None}),
        Response(body={"continuationId": "continuation-1", "state": "queued"}),
        Response(raw_body=b"continued"),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                result = await client.sessions.tool_approvals(
                    agent_id=AGENT["id"], session_id="session-1"
                )
                assert isinstance(result.data[0].tool, McpToolReference)
                assert result.data[0].assistant_message_id == "message-1"
                decision = await client.sessions.decide_tool_approval(
                    agent_id=AGENT["id"],
                    session_id="session-1",
                    approval_id="approval-1",
                    approved=True,
                )
                stream = await client.sessions.join_tool_approval_continuation(
                    agent_id=AGENT["id"],
                    session_id="session-1",
                    continuation_id=decision.continuation_id,
                )
                async with stream:
                    assert b"".join([chunk async for chunk in stream]) == b"continued"

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                result = client.sessions.tool_approvals(
                    agent_id=AGENT["id"], session_id="session-1"
                )
                assert isinstance(result.data[0].tool, McpToolReference)
                assert result.data[0].assistant_message_id == "message-1"
                decision = client.sessions.decide_tool_approval(
                    agent_id=AGENT["id"],
                    session_id="session-1",
                    approval_id="approval-1",
                    approved=True,
                )
                with client.sessions.join_tool_approval_continuation(
                    agent_id=AGENT["id"],
                    session_id="session-1",
                    continuation_id=decision.continuation_id,
                ) as stream:
                    assert b"".join(stream) == b"continued"
    assert json.loads(state.requests[1].body) == {"approved": True}
    assert state.requests[2].target.endswith(
        "/tool-approval-continuations/continuation-1"
    )
