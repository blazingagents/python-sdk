<div align="center">
  <a href="https://docs.blazingagents.com">
    <img src="https://raw.githubusercontent.com/blazingagents/docs/main/public/brand/icon.svg" alt="Blazing Agents logo" width="96">
  </a>
  <h1>Blazing Agents Python SDK</h1>
  <p>Build production agents in Python with a typed client for the Blazing Agents API.</p>
  <p>
    <a href="https://docs.blazingagents.com/sdk/python">Documentation</a> ·
    <a href="https://pypi.org/project/blazing-agents/">PyPI</a>
  </p>
</div>

The official Python SDK provides synchronous and asynchronous clients for the
Blazing Agents `/v1` API. It supports CPython 3.11 and newer.

## Features

- Typed Pydantic request and response models.
- Matching synchronous and asynchronous APIs.
- Agent, Workspace, Skill, Provider, Prompt, Memory, Session, Artifact, Task,
  usage, and Tenant management.
- Chat, text, and structured-object generation streams.
- Lazy pagination and binary transfers.
- Request correlation with configurable timeouts and observability.

## Installation

```console
pip install blazing-agents
```

## Quick start

Create a Tenant API key in the Blazing Agents dashboard, then pass it to the
client or set `BLAZING_AGENTS_API_KEY`.

```python
from blazing_agents import BlazingAgents


with BlazingAgents(api_key="ba_...") as client:
    result = client.completion(
        agent_id="ag_...",
        prompt="Write a friendly welcome message.",
    )
    print(str(result))
```

Use `AsyncBlazingAgents` for asynchronous applications; it exposes the same
resources and generation methods.

## Documentation

Read the [Python SDK documentation](https://docs.blazingagents.com/sdk/python)
for authentication, resource guides, generation and streaming, error handling,
and the complete API reference.

## Thinking levels

Configure `thinking_level` on Agent create or update. Omit it on update to
preserve the current selection; pass `None` for Provider default. Explicit
levels are strings, including custom values for Models with unknown capabilities.
Agent and Agent Version responses expose `thinking_level`, and restoring a
Version restores its level too. The async client provides the same methods.

```python
capabilities = client.providers.get_thinking_levels(provider_id, model="gpt-5")
# capabilities.known distinguishes unknown metadata from known choices.
agent = client.agents.create(
    name="Reasoner",
    provider_id=provider_id,
    model="openai/gpt-5",
    thinking_level="high",
)
client.agents.update(agent.id, thinking_level=None)
```

## Development

```console
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run python scripts/run_typechecks.py
uv run python scripts/run_tests.py
```

## License

[MIT](LICENSE)

## Interactive resend

Successful interactive exchanges are saved together. Failed or canceled execution
leaves saved history unchanged, including the previous answer during regeneration;
executed usage and Tool effects remain. Retain submitted text/images until success
and resend edited or unchanged input through ordinary chat with a fresh message ID.
Stop requests cancellation; a lost response can hide a saved exchange. Reuse the
returned Session ID and load history normally on return. No outcome polling or
automatic generation retry is needed. See the [chatbot guide](https://docs.blazingagents.com/getting-started/chatbot)
and [working examples](https://github.com/blazingagents/examples).

## Automatic context compaction

Agents enable automatic compaction by default with a 16,384-token reserve.
A larger reserve compacts earlier. Settings are included in Agent Versions.
Compaction summarizes older history for the model while retaining the full
Session transcript; summarization calls contribute to token usage.

```python
client.agents.update(
    "ag_...",
    auto_compaction=True,
    compaction_reserve_tokens=32768,
)
```

### Tool approval policies (0.5.0)

Both `BlazingAgents` and `AsyncBlazingAgents` accept separate `approval_in_chat`
and `approval_in_tasks` policies on `agents.create()` and `agents.update()`:

```python
from blazing_agents import ApprovalPolicyInput, BlazingAgents

client = BlazingAgents()
policy: ApprovalPolicyInput = {
    "default": "full",
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
agent = client.agents.update(
    "ag_0123456789abcdef",
    approval_in_chat=policy,
    approval_in_tasks={"default": "deny", "overrides": []},
)
print(agent.approval_in_chat.default)
```

Exact tool overrides take precedence over `default`. Both accept `full`, `deny`,
`manual`, and `auto`. The initial policy is `full` with no overrides; `full` still
requires tool availability and access. `manual` requires human review. `auto`
uses the backend LLM reviewer and blocks on review failure or escalation without
an available human. The reviewer receives structured tool identity, runtime name,
arguments and conversation; tool descriptions are excluded.

Omitting either update argument preserves that policy. Supplying it replaces the
whole policy; omitted `overrides` or `overrides=[]` clears overrides. Python
`connection_id` is serialized as `connectionId`. Agent reads, version reads and
`restore_version()` include both policies.

Interactive Sessions use the existing `client.sessions.tool_approvals()`,
`decide_tool_approval()` and `join_tool_approval_continuation()` methods (await them
with the async client). Human review requires the backend Session reviewer path
and `TOOL_APPROVAL_SECRET`. Tasks and stateless generations have no human
continuation path and block manual or escalated calls. Stateless generations use
the chat policy; Tasks use the task policy.

`ToolApproval.tool` is a `BuiltinToolReference`, `McpToolReference`, or `None`
(admin approvals may have no ordinary tool reference). Approval records expose
`assistant_message_id`, `created_at`, and `decided_at` for correlation. These
metadata fields may be absent; only `tool` and `decided_at` also accept explicit
null. Use `model_fields_set` to distinguish absence from null. Persisted
`ToolApproval.decision` values are `pending`, `approved`, and `denied`; resolving
one still sends the existing `approved` boolean, with an optional `reason`.

## Slack and Telegram

Use the [connection example](https://github.com/blazingagents/python-sdk/blob/main/examples/chat-integrations.md) to connect an existing
Agent through REST. BA hosts the Chat SDK runtime, conversation history, and
approval cards; no additional SDK resource is required.
