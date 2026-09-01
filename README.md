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
