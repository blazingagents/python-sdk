from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Annotated, assert_type

from pydantic import BaseModel

from blazing_agents import (
    Agent,
    AgentCreate,
    AgentUpdate,
    Artifact,
    ArtifactDownloadUrl,
    ArtifactsListOptions,
    AsyncBlazingAgents,
    AsyncChatStream,
    AsyncCompletionStream,
    AsyncObjectStream,
    BlazingAgents,
    ChatMessageInput,
    ChatStream,
    Completion,
    CompletionLiteralInput,
    CompletionStream,
    JsonValue,
    MemoryCreate,
    MemoryResponse,
    ObjectStream,
    Session,
    Skill,
    SkillDetail,
    SkillsPage,
    TaskCreateResponse,
    TaskRunMessagesPage,
    TaskRunsPage,
    TaskRunStatus,
    TaskRunSubmission,
    TasksPage,
    ToolApprovalDecisionInput,
)


class Person(BaseModel):
    name: str


SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
}


def output_type_inference_examples(client: BlazingAgents) -> None:
    assert_type(
        client.object(
            agent_id="ag_0123456789abcdef",
            prompt="Optional number",
            output_type=int | None,
        ),
        int | None,
    )
    assert_type(
        client.object(
            agent_id="ag_0123456789abcdef",
            prompt="Positive number",
            output_type=Annotated[int, "positive"],
        ),
        int,
    )


def sync_examples(client: BlazingAgents) -> None:
    artifact_options: ArtifactsListOptions = {
        "agent_id": "ag_0123456789abcdef",
        "session_id": "ss_0123456789abcdef",
        "cursor": "next-page-token",
    }
    client.artifacts.list(**artifact_options)
    agent_request: AgentCreate = {
        "name": "Release agent",
        "tools": ["workspace"],
        "metadata": {"OpaqueKey": True},
    }
    assert_type(client.agents.create(**agent_request), Agent)
    configured_agent_request: AgentCreate = {
        "name": "Configured agent",
        "model": "openai/gpt-5",
        "provider_id": "prv_0123456789abcdef",
    }
    assert_type(client.agents.create(**configured_agent_request), Agent)
    clear_agent_request: AgentUpdate = {"model": None, "provider_id": None}
    assert_type(
        client.agents.update(
            "ag_0123456789abcdef",
            **clear_agent_request,
        ),
        Agent,
    )
    model_update: AgentUpdate = {"model": "openai/gpt-5-mini"}
    assert_type(
        client.agents.update("ag_0123456789abcdef", **model_update),
        Agent,
    )
    memory_request: MemoryCreate = {"text": "Prefer concise release notes"}
    assert_type(
        client.memories.create(
            agent_id="ag_0123456789abcdef",
            **memory_request,
        ),
        MemoryResponse,
    )
    chat_request: ChatMessageInput = {
        "agent_id": "ag_0123456789abcdef",
        "message": {"id": "message-1", "role": "user", "parts": []},
    }
    assert_type(client.chat(**chat_request), ChatStream)
    regenerate_request: ChatMessageInput = {
        "agent_id": "ag_0123456789abcdef",
        "message": {"id": "message-1", "role": "user", "parts": []},
        "session_id": "ss_0123456789abcdef",
        "trigger": "regenerate-message",
    }
    assert_type(client.chat(**regenerate_request), ChatStream)
    regenerate_from_message_request: ChatMessageInput = {
        "agent_id": "ag_0123456789abcdef",
        "message": {"id": "message-1", "role": "user", "parts": []},
        "session_id": "ss_0123456789abcdef",
        "trigger": "regenerate-message",
        "message_id": "message-1",
    }
    assert_type(client.chat(**regenerate_from_message_request), ChatStream)
    completion_request: CompletionLiteralInput = {
        "agent_id": "ag_0123456789abcdef",
        "prompt": "Summarize",
    }
    assert_type(client.completion(**completion_request), Completion)
    decision: ToolApprovalDecisionInput = {
        "agent_id": "ag_0123456789abcdef",
        "session_id": "ss_0123456789abcdef",
        "approval_id": "approval-1",
        "approved": True,
    }
    client.sessions.decide_tool_approval(**decision)
    assert_type(
        client.tasks.create(
            agent_id="ag_0123456789abcdef",
            name="Nightly report",
            prompt="Produce the report.",
            schedule={
                "kind": "cron",
                "config": {"expression": "0 2 * * *", "timezone": "UTC"},
            },
        ),
        TaskCreateResponse,
    )
    assert_type(client.tasks.list(limit=25), TasksPage)
    assert_type(
        client.tasks.submit(
            "tk_0123456789abcdef",
            idempotency_key="stable-key",
        ),
        TaskRunSubmission,
    )
    assert_type(
        client.tasks.list_runs("tk_0123456789abcdef"),
        TaskRunsPage,
    )
    assert_type(
        client.tasks.run_messages(
            "tk_0123456789abcdef",
            "tr_0123456789abcdef",
        ),
        TaskRunMessagesPage,
    )
    task_messages = client.tasks.run_messages(
        "tk_0123456789abcdef", "tr_0123456789abcdef"
    )
    assert_type(task_messages.status, TaskRunStatus)
    assert_type(task_messages.error, str | None)
    assert_type(task_messages.finished_at, datetime | None)
    assert_type(
        client.object(
            agent_id="ag_0123456789abcdef",
            prompt="Person",
            output_type=Person,
        ),
        Person,
    )
    assert_type(
        client.object(
            agent_id="ag_0123456789abcdef",
            prompt="People",
            output_type=list[Person],
        ),
        list[Person],
    )
    assert_type(
        client.object(
            agent_id="ag_0123456789abcdef",
            prompt="Raw",
            json_schema=SCHEMA,
        ),
        JsonValue,
    )
    assert_type(
        client.object_stream(
            agent_id="ag_0123456789abcdef",
            prompt="Stream",
            output_type=Person,
        ),
        ObjectStream[Person],
    )
    assert_type(
        client.sessions.iter(agent_id="ag_0123456789abcdef", limit=25),
        Iterator[Session],
    )
    skills = client.agent("ag_0123456789abcdef").skills
    assert_type(skills.list(limit=25), SkillsPage)
    assert_type(skills.iter(limit=25), Iterator[Skill])
    assert_type(
        skills.create(
            path="SKILL.md",
            content="---\nname: test\ndescription: Test.\n---\n",
        ),
        SkillDetail,
    )
    assert_type(
        client.artifacts.get(
            artifact_id="at_0123456789abcdef",
        ),
        Artifact,
    )
    assert_type(
        client.artifacts.create_download_url(
            artifact_id="at_0123456789abcdef",
        ),
        ArtifactDownloadUrl,
    )
    completion_stream = client.completion_stream(**completion_request)
    assert_type(completion_stream, CompletionStream)
    with completion_stream as deltas:
        assert_type(deltas, CompletionStream)
        assert_type(iter(deltas), Iterator[str])
        assert_type(deltas.get_final_text(), Completion)
    chat_stream = client.chat(**chat_request)
    with chat_stream as chunks:
        assert_type(chunks, ChatStream)
        assert_type(iter(chunks), Iterator[bytes])
    with client as entered:
        assert_type(entered, BlazingAgents)


async def async_examples(client: AsyncBlazingAgents) -> None:
    agent_request: AgentCreate = {"name": "Release agent"}
    assert_type(await client.agents.create(**agent_request), Agent)
    chat_request: ChatMessageInput = {
        "agent_id": "ag_0123456789abcdef",
        "message": {"id": "message-1", "role": "user", "parts": []},
    }
    assert_type(await client.chat(**chat_request), AsyncChatStream)
    regenerate_request: ChatMessageInput = {
        "agent_id": "ag_0123456789abcdef",
        "message": {"id": "message-1", "role": "user", "parts": []},
        "session_id": "ss_0123456789abcdef",
        "trigger": "regenerate-message",
    }
    assert_type(await client.chat(**regenerate_request), AsyncChatStream)
    regenerate_from_message_request: ChatMessageInput = {
        "agent_id": "ag_0123456789abcdef",
        "message": {"id": "message-1", "role": "user", "parts": []},
        "session_id": "ss_0123456789abcdef",
        "trigger": "regenerate-message",
        "message_id": "message-1",
    }
    assert_type(await client.chat(**regenerate_from_message_request), AsyncChatStream)
    completion_request: CompletionLiteralInput = {
        "agent_id": "ag_0123456789abcdef",
        "prompt": "Summarize",
    }
    assert_type(await client.completion(**completion_request), Completion)
    assert_type(
        await client.tasks.create(
            agent_id="ag_0123456789abcdef",
            name="Nightly report",
            prompt="Produce the report.",
        ),
        TaskCreateResponse,
    )
    assert_type(await client.tasks.list(limit=25), TasksPage)
    assert_type(
        await client.tasks.submit("tk_0123456789abcdef"),
        TaskRunSubmission,
    )
    assert_type(
        await client.tasks.list_runs("tk_0123456789abcdef"),
        TaskRunsPage,
    )
    assert_type(
        await client.tasks.run_messages(
            "tk_0123456789abcdef",
            "tr_0123456789abcdef",
        ),
        TaskRunMessagesPage,
    )
    assert_type(
        await client.object(
            agent_id="ag_0123456789abcdef",
            prompt="Person",
            output_type=Person,
        ),
        Person,
    )
    assert_type(
        await client.object_stream(
            agent_id="ag_0123456789abcdef",
            prompt="Raw stream",
            json_schema=SCHEMA,
        ),
        AsyncObjectStream[JsonValue],
    )
    assert_type(
        client.sessions.iter(agent_id="ag_0123456789abcdef", limit=25),
        AsyncIterator[Session],
    )
    skills = client.agent("ag_0123456789abcdef").skills
    assert_type(await skills.list(limit=25), SkillsPage)
    assert_type(skills.iter(limit=25), AsyncIterator[Skill])
    assert_type(
        await client.artifacts.get(
            artifact_id="at_0123456789abcdef",
        ),
        Artifact,
    )
    assert_type(
        await client.artifacts.create_download_url(
            artifact_id="at_0123456789abcdef",
        ),
        ArtifactDownloadUrl,
    )
    completion_stream = await client.completion_stream(**completion_request)
    assert_type(completion_stream, AsyncCompletionStream)
    async with completion_stream as deltas:
        assert_type(deltas, AsyncCompletionStream)
        assert_type(deltas.__aiter__(), AsyncIterator[str])
        assert_type(await deltas.get_final_text(), Completion)
    chat_stream = await client.chat(**chat_request)
    async with chat_stream as chunks:
        assert_type(chunks, AsyncChatStream)
        assert_type(chunks.__aiter__(), AsyncIterator[bytes])
    async with client as entered:
        assert_type(entered, AsyncBlazingAgents)
