# Blazing Agents Python SDK

The official backend SDK for the Blazing Agents `/v1` API. It provides native
synchronous and asynchronous clients, typed Pydantic responses, lazy
pagination, binary transfers, and one-owner generation streams.

## Installation

Blazing Agents supports CPython 3.11 and newer.

```console
pip install blazing_agents
```

Create a Tenant API key in the Blazing Agents dashboard. Pass it explicitly or
set `BLAZING_AGENTS_API_KEY`; an explicit key takes precedence.

```python
from blazing_agents import BlazingAgents

with BlazingAgents(api_key="ba_...") as client:
    tenant = client.tenant.get()
    print(tenant.name)
```

The production API origin is `https://api.blazingagents.com`. Use `base_url`
only for an intentional alternative deployment:

```python
client = BlazingAgents(
    api_key="ba_...",
    base_url="http://127.0.0.1:8787",
    timeout=30.0,
    on_response=lambda response: print(response.request_id, response.status),
)
```

Generation methods accept `client_request_id` for caller-owned correlation
without raw headers. Use `client.with_options(client_request_id=...)` to
correlate any resource or generation request through a scoped client view.
`on_response` receives method, path without query,
status, duration, server request ID, and the optional client request ID once
for every received response, including errors and streaming handshakes.
Callback failures are ignored, and failures with no HTTP response do not
invoke it. Retain the server-owned `request_id` when contacting support; each
retry receives a different value.

Tenant API-key creation, rotation, and revocation are dashboard-only and are
not exposed by this backend SDK.

## Sync and async clients

`BlazingAgents` and `AsyncBlazingAgents` expose the same resources and
generation behavior. The async client uses HTTPX asynchronously throughout; it
does not run synchronous calls through an event loop bridge.

```python
from blazing_agents import AsyncBlazingAgents


async def show_tenant() -> None:
    async with AsyncBlazingAgents(api_key="ba_...") as client:
        tenant = await client.tenant.get()
        print(tenant.name)
```

Context managers close transports created by the SDK. When injecting an
`httpx.Client` or `httpx.AsyncClient`, the caller retains ownership and must
close it.

## Resources

Both clients expose these resource groups:

| Resource | Operations |
| --- | --- |
| `agents` | Create, list, get, update, disable, enable, delete, versions, restore, MCP attachments, avatar upload/removal |
| `workspaces` | Create, list, iterate, get, update, delete |
| `agent(agent_id).skills` | Create/upload, list, iterate, get, delete, read/replace/delete files, copy |
| `providers` | Create, list, get, update, delete, and discover models |
| `mcp_connections` | Connect, create, list, get, update, delete, test, reconnect |
| `prompts` | Create, list, get, update, delete |
| `memories` | Create, list, iterate, get, update, delete |
| `sessions` | List, iterate, messages, Tool approvals and continuations, delete |
| `artifacts` | List, iterate, download URL, buffered/streaming download, delete |
| `tasks` | Create, list, iterate, get, update, delete, submit, runs, messages, cancel |
| `usage` | Tenant or Agent usage |
| `tenant` | Get and update Tenant settings |

Writes use keyword-only snake-case parameters. SDK-owned names are translated
to camel case on the wire; keys inside metadata, message parts, variables, and
JSON Schema remain unchanged. Omitted values are not sent, while explicit
`None` is sent as JSON null.

Returned objects are strict Pydantic v2 models for documented fields and retain
unknown server fields in `model_extra`. Successful models expose the
non-serialized `_request_id` correlation attribute.

Every Agent has a Workspace. Omitting `workspace_id` when creating an Agent
creates its default Workspace; passing an existing ID shares that Workspace.
Updates accept another concrete Workspace ID, and deleting an Agent preserves
its Workspace for explicit deletion or reuse.

An Agent may be created without a Provider configuration. To configure one,
pass both `provider_id` and `model`. Updates may replace only the model, replace
both values, or clear the configuration by passing `None` for both values.

## Pagination

Cursor resources provide a page-level `list()` and a lazy `iter()`. Iteration
requests another page only when it is needed.

```python
with BlazingAgents(api_key="ba_...") as client:
    page = client.sessions.list(agent_id="ag_...", limit=25)
    print(page.data, page.next_cursor)

    for session in client.sessions.iter(agent_id="ag_...", limit=25):
        print(session.id)
```

Async resource iterators are consumed with `async for`:

```python
async with AsyncBlazingAgents(api_key="ba_...") as client:
    sessions = client.sessions.iter(agent_id="ag_...", limit=25)
    async for session in sessions:
        print(session.id)
```

Task pages support the same lazy pagination with `agent_id`, `cursor`, and
`limit` filters:

```python
with BlazingAgents(api_key="ba_...") as client:
    page = client.tasks.list(
        agent_id="ag_...",
        cursor="next-page-token",
        limit=25,
    )
    for task in client.tasks.iter(agent_id="ag_...", limit=25):
        print(task.id)
```

## Binary transfer

Uploads accept `bytes`, a path-like value, or a readable binary file. The SDK
closes a file it opens from a path and leaves caller-owned file objects open.

```python
with BlazingAgents(api_key="ba_...") as client:
    client.agents.upload_avatar("ag_...", file="avatar.png")
    client.agent("ag_...").skills.replace_file(
        skill_id="skill_...",
        path="assets/config.bin",
        content=b"\x00\x01",
    )
```

Artifact metadata and management are Tenant-level. Create a five-minute
presigned R2 URL, then fetch the immutable bytes directly:

```python
with BlazingAgents(api_key="ba_...") as client:
    artifact = client.artifacts.get(
        artifact_id="at_...",
    )
    download = client.artifacts.create_download_url(
        artifact_id=artifact.artifact_id,
    )
    print(download.url, download.expires_at)
```

Use `await async_client.artifacts.create_download_url(...)` with the async
client. Keep presigned URLs out of logs and referrers.

## Chat relay

`chat()` returns the server's exact SSE bytes. The SDK does not decode or
re-encode AI SDK `UIMessageChunk` values, so a backend can relay each byte
chunk unchanged.

```python
with BlazingAgents(api_key="ba_...") as client:
    with client.chat(
        agent_id="ag_...",
        message={"id": "message-1", "role": "user", "parts": []},
    ) as stream:
        print(stream.status_code, stream.session_id, stream.request_id)
        for chunk in stream:
            relay(chunk)
```

For a new Session, `session_id` is resolved from the response `Location`
header. Pass that ID to a later `chat(..., session_id=session_id)` call to
resume. Status, headers, request ID, and Session ID are available before body
consumption. `trigger="regenerate-message"` requires an existing `session_id`;
`message_id` is optional for that regeneration request.

## Completion

`completion()` buffers plain text. `completion_stream()` yields decoded text
deltas, and `get_final_text()` drains any unread remainder before returning the
complete correlated value.

```python
with BlazingAgents(api_key="ba_...") as client:
    result = client.completion(agent_id="ag_...", prompt="Summarize this")
    print(str(result), result.request_id)

    with client.completion_stream(
        agent_id="ag_...",
        prompt="Write a release note",
    ) as stream:
        for delta in stream:
            print(delta, end="")
        final = stream.get_final_text()
```

## Structured objects

Pass either a Pydantic-compatible `output_type` or a raw `json_schema`, but not
both. A typed result is inferred from `output_type`.

```python
from pydantic import BaseModel


class Summary(BaseModel):
    title: str
    risks: list[str]


with BlazingAgents(api_key="ba_...") as client:
    summary = client.object(
        agent_id="ag_...",
        prompt="Summarize the release",
        output_type=Summary,
    )
```

`object_stream()` yields raw JSON text deltas. It does not construct partial
models. `get_final_object()` drains the remainder and validates only after
successful terminal completion:

```python
with BlazingAgents(api_key="ba_...") as client:
    with client.object_stream(
        agent_id="ag_...",
        prompt="Summarize the release",
        output_type=Summary,
    ) as stream:
        for json_delta in stream:
            print(json_delta, end="")
        summary = stream.get_final_object()
```

## Errors, timeouts, and retries

```python
from blazing_agents import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    StreamError,
)

with BlazingAgents(api_key="ba_...") as client:
    try:
        client.agents.get("ag_...")
    except APIStatusError as error:
        print(error.status_code, error.code, error.request_id, error.retry_after)
    except APITimeoutError:
        ...
    except APIConnectionError:
        ...
    except StreamError:
        ...
```

`APIStatusError` retains response headers, the server error code, details,
parameter, request ID, retry information, and the safe response body.
Cancellation, `KeyboardInterrupt`, and `SystemExit` are not wrapped.

Ordinary operations default to 60 seconds. Set `timeout` on a client or an
individual operation; use `None` to disable it. Streaming responses retain
connect, write, and pool timeouts but deliberately have no SDK read deadline.
The SDK performs no automatic retries or implicit idempotency. Task submission
accepts an explicit `idempotency_key` because that operation defines one.

## Stream and security ownership

Every binary, chat, completion, and object stream has one consumer. Exhaustion
closes it automatically. Early exit requires `close()` or `aclose()`, normally
through a context manager. Closing an active chat or generation stream
propagates cancellation; closing an admitted durable Tool continuation only
detaches.

The SDK is silent by default, sends no telemetry or background analytics, and
starts no background tasks. If the host enables the `blazing_agents` logger at
debug level, records contain only HTTP method, path without query parameters,
status, elapsed time, and request ID. Credentials, headers, query values,
bodies, schemas, file data, and stream content are never logged.

## Verification commands

The package check is self-contained and does not require Supabase:

```console
npm --workspace @blazing-agents/python-sdk run check
```

It builds and tests the installed wheel, enforces the 99% line, branch,
function, and statement thresholds, runs Pyright and mypy, and checks Ruff.
Interpreter compatibility uses the same installed-wheel behavioral suite for
each supported Python version:

```console
npm --workspace @blazing-agents/python-sdk run test:compatibility
```

The local-platform suite is a separate command. Start the repository's local
Supabase stack, reset it with `npm run db:test:reset`, then run:

```console
npm --workspace @blazing-agents/python-sdk run test:integration
```

The complete `npm run test:integration` gate performs the guarded reset and
includes this command in its database integration chain.
