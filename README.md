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

The official Python SDK is a client for the Blazing Agents `/v1` API that
your backend uses to manage Agents and run them for your users. It supports
CPython 3.11 and newer.

## Features

- A typed method for every `/v1` operation an API key can call: Agents,
  Skills, Sessions, Memories, Prompts, Tasks, Workspaces, Artifacts,
  Providers, MCP Connections, Chat Connections, usage, spending limits, Tenant
  settings, and merchant monetization.
- Chat streams in the AI SDK UI message stream format, with steering, Tool
  approvals, and backend functions that run in your process.
- Text and structured-object generation.
- End-user scoped clients through `for_user`.
- Lazy pagination, uploads, and downloads.
- Request IDs and typed errors.
- Matching synchronous and asynchronous clients with Pydantic models.

## Installation

```console
pip install blazing-agents
```

## Quick start

Create a Full API key in the Blazing Agents dashboard and set
`BLAZING_AGENTS_API_KEY` in your server environment. The key acts for your
whole Tenant, so keep it on your backend and never send it to a browser.

```python
from blazing_agents import BlazingAgents

client = BlazingAgents()

answer = client.completion(
    agent_id="ag_...",
    prompt="Write a friendly welcome message.",
)
print(answer)
```

Replace `ag_...` with an Agent ID from the dashboard.

For requests from your users, scope the client to the user ID that your
backend verified at sign-in, never to an ID from the request body. A scoped
client reaches only that End-user's Agents, Sessions, and Workspace. An
unscoped Agent shares one Workspace across all your users, so give each user
an Agent of their own:

```python
from uuid import uuid4

from blazing_agents import ChatStream


def create_agent_for_user(user_id: str) -> str:
    agent = client.for_user(user_id).agents.create(
        name="Assistant",
        provider_id="prv_...",
        model="openai/gpt-6-luna",
    )
    return agent.id


def chat_as_user(user_id: str, agent_id: str, text: str) -> ChatStream:
    return client.for_user(user_id).chat(
        agent_id=agent_id,
        message={
            "id": str(uuid4()),
            "role": "user",
            "parts": [{"type": "text", "text": text}],
        },
    )
```

Call `create_agent_for_user` once per user and store the Agent ID with the
user. A scoped chat with an Agent created without the scope fails with `404`.
`chat_as_user` returns the chat as a stream of server-sent event bytes.
Send it to the browser as a `text/event-stream` response, and AI SDK
`useChat` reads it. For asyncio applications, `AsyncBlazingAgents` has the
same methods.

## Examples

The [examples repository](https://github.com/blazingagents/examples) has
complete TypeScript and Python apps built on the Blazing Agents SDKs.

## Documentation

Read the [Python SDK documentation](https://docs.blazingagents.com/sdk/python)
for client setup, End-user scoping, chat and generation, a guide to each
resource, and error handling.

## Development

```console
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run python scripts/run_typechecks.py
uv run python scripts/run_tests.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the changelog convention and
the release process.

## License

[MIT](LICENSE)
