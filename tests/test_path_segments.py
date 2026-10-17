from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from support import loopback

import blazing_agents as ba

CALLS: dict[str, Callable[[ba.BlazingAgents, str], Any]] = {
    "agents.get": lambda c, v: c.agents.get(v),
    "agents.update_mcp_attachment": lambda c, v: c.agents.update_mcp_attachment(
        "ag_1", v, forward_user_id=True
    ),
    "sessions.get": lambda c, v: c.sessions.get("ag_1", v),
    "tasks.get": lambda c, v: c.tasks.get(v),
    "tasks.get_run": lambda c, v: c.tasks.get_run("tk_1", v),
    "workspaces.get": lambda c, v: c.workspaces.get(workspace_id=v),
    "providers.get": lambda c, v: c.providers.get(v),
    "mcp_connections.get": lambda c, v: c.mcp_connections.get(v),
    "prompts.get": lambda c, v: c.prompts.get(prompt_id=v),
    "memories.get": lambda c, v: c.memories.get(agent_id="ag_1", memory_id=v),
    "agent().skills.get": lambda c, v: c.agent("ag_1").skills.get(skill_id=v),
    "artifacts.get": lambda c, v: c.artifacts.get(artifact_id=v),
    "chat_connections.get": lambda c, v: c.chat_connections.get(v),
    "usage.get_for_agent": lambda c, v: c.usage.get_for_agent(v),
    "completion": lambda c, v: c.completion(agent_id=v, prompt="hi"),
    "chat": lambda c, v: c.chat(
        agent_id="ag_1", session_id=v, message={"role": "user", "parts": []}
    ),
    "continue_chat": lambda c, v: c.continue_chat(
        agent_id="ag_1", session_id=v, decisions=[]
    ),
}


@pytest.mark.parametrize("value", ["", ".", ".."])
@pytest.mark.parametrize("call", CALLS.values(), ids=CALLS.keys())
def test_identifiers_that_would_change_the_path_are_rejected_before_sending(
    call: Callable[[ba.BlazingAgents, str], Any], value: str
) -> None:
    with loopback() as (base_url, state):
        client = ba.BlazingAgents(api_key="ba_sk_test", base_url=base_url)
        with pytest.raises(ValueError, match="must not be empty, '.' or '..'"):
            call(client, value)
    assert state.requests == []
