from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import get_args

from blazing_agents import (
    AGENT_TOOL_GROUPS,
    AGENT_TOOLS,
    AgentTool,
    AgentToolFileAccessTag,
    AgentToolGroupTag,
)

SPEC = Path(__file__).resolve().parents[1] / "spec" / "openapi.json"


def test_catalog_matches_the_contract() -> None:
    catalog = json.loads(SPEC.read_text())["x-agent-tools"]
    assert [asdict(group) for group in AGENT_TOOL_GROUPS] == catalog["groups"]
    assert [
        {
            "name": tool.name,
            "description": tool.description,
            "requiresWorkspace": tool.requires_workspace,
            "tags": list(tool.tags),
        }
        for tool in AGENT_TOOLS
    ] == catalog["tools"]
    assert [*get_args(AgentToolGroupTag), *get_args(AgentToolFileAccessTag)] == (
        catalog["tags"]
    )


def test_catalog_lists_every_tool_name_once() -> None:
    assert [tool.name for tool in AGENT_TOOLS] == list(get_args(AgentTool))


def test_read_only_file_tools_are_the_file_read_tagged_ones() -> None:
    assert [tool.name for tool in AGENT_TOOLS if "file_read" in tool.tags] == [
        "read",
        "grep",
        "glob",
    ]


def test_web_tools_need_no_workspace() -> None:
    web = [tool for tool in AGENT_TOOLS if "web" in tool.tags]
    assert [tool.name for tool in web] == ["web_search", "web_fetch"]
    assert not any(tool.requires_workspace for tool in web)
