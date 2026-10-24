from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ._types import AgentTool

AgentToolGroupTag = Literal["files", "planning", "memory", "web"]
AgentToolFileAccessTag = Literal["file_read", "file_write", "execute"]
"""``file_read`` tools never change Workspace files, so an Agent limited to them
is read-only. ``execute`` runs arbitrary commands, which can change files and
more."""
AgentToolTag = Literal[AgentToolGroupTag, AgentToolFileAccessTag]


@dataclass(frozen=True)
class AgentToolGroup:
    tag: AgentToolGroupTag
    name: str
    description: str


@dataclass(frozen=True)
class AgentToolDefinition:
    """A built-in tool. Its first tag is its group; a file operation tool adds
    one file access tag. Tags describe a tool and never enable it."""

    name: AgentTool
    description: str
    requires_workspace: bool
    tags: tuple[AgentToolTag, ...]


AGENT_TOOL_GROUPS: tuple[AgentToolGroup, ...] = (
    AgentToolGroup(
        "files",
        "File operations",
        "Read, write, edit, search, and run shell commands in the attached Workspace.",
    ),
    AgentToolGroup(
        "planning",
        "Task planning",
        "Create and manage a structured todo list to plan and track multi-step work.",
    ),
    AgentToolGroup(
        "memory",
        "Memory",
        "Save, recall, search, update, and delete durable notes owned by this Agent.",
    ),
    AgentToolGroup("web", "Web", "Search the public web and read pages by URL."),
)

AGENT_TOOLS: tuple[AgentToolDefinition, ...] = (
    AgentToolDefinition(
        "read", "Read a file from the Workspace.", True, ("files", "file_read")
    ),
    AgentToolDefinition(
        "write",
        "Create or overwrite a file in the Workspace.",
        True,
        ("files", "file_write"),
    ),
    AgentToolDefinition(
        "edit",
        "Replace exact text in a Workspace file.",
        True,
        ("files", "file_write"),
    ),
    AgentToolDefinition(
        "grep",
        "Search Workspace file contents with a regular expression.",
        True,
        ("files", "file_read"),
    ),
    AgentToolDefinition(
        "glob",
        "Find Workspace files by path pattern.",
        True,
        ("files", "file_read"),
    ),
    AgentToolDefinition(
        "bash", "Run shell commands in the Workspace.", True, ("files", "execute")
    ),
    AgentToolDefinition(
        "publish_artifacts",
        "Publish Workspace files as downloadable Artifacts.",
        True,
        ("files",),
    ),
    AgentToolDefinition(
        "write_todos",
        "Plan and track multi-step work with a todo list.",
        False,
        ("planning",),
    ),
    AgentToolDefinition("save_memory", "Save a durable note.", False, ("memory",)),
    AgentToolDefinition("get_memory", "Read one saved note.", False, ("memory",)),
    AgentToolDefinition("search_memories", "Search saved notes.", False, ("memory",)),
    AgentToolDefinition("update_memory", "Update a saved note.", False, ("memory",)),
    AgentToolDefinition("delete_memory", "Delete a saved note.", False, ("memory",)),
    AgentToolDefinition(
        "web_search",
        "Search the public web for current results. Each search consumes Usage credit.",
        False,
        ("web",),
    ),
    AgentToolDefinition(
        "web_fetch",
        "Read a public web page or text document by URL, returned as markdown.",
        False,
        ("web",),
    ),
)
