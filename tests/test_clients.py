from __future__ import annotations

import asyncio
import io
import json
import logging
import socket
import time
from collections import deque
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path
from threading import Event, Thread
from typing import Annotated, Any, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from blazing_agents import (
    AgentVersion,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Artifact,
    ArtifactDownloadUrl,
    ArtifactsPage,
    AsyncBlazingAgents,
    AsyncByteStream,
    AsyncChatStream,
    AsyncCompletionStream,
    AsyncObjectStream,
    BlazingAgents,
    BlazingAgentsError,
    ByteStream,
    ChatMessageInput,
    ChatPromptInput,
    ChatStream,
    ChatTrigger,
    Completion,
    CompletionLiteralInput,
    CompletionPromptInput,
    CompletionStream,
    JsonValue,
    McpConnection,
    McpConnectionReconnectResult,
    McpConnectionTestResult,
    MemoriesListOptions,
    MemoriesPage,
    Memory,
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
    ObjectJSONDecodeError,
    ObjectStream,
    ObjectTruncationError,
    ObjectValidationError,
    Prompt,
    PromptCreate,
    Prompts,
    PromptsListOptions,
    PromptUpdate,
    Provider,
    ProviderModels,
    Session,
    SessionMessage,
    SessionMessagePart,
    SessionMessagesOptions,
    SessionMessagesPage,
    SessionsListOptions,
    SessionsPage,
    Skill,
    SkillArchiveType,
    SkillArchiveUpload,
    SkillCopy,
    SkillCopyCreated,
    SkillCopyFailed,
    SkillCreate,
    SkillDetail,
    SkillsListOptions,
    SkillsPage,
    StreamError,
    Task,
    TaskCreate,
    TaskCreateResponse,
    TaskCronSchedule,
    TaskCronScheduleInput,
    TaskIntervalSchedule,
    TaskListItem,
    TaskOnceSchedule,
    TaskRun,
    TaskRunCreate,
    TaskRunMessagesOptions,
    TaskRunMessagesPage,
    TaskRunsListOptions,
    TaskRunsPage,
    TaskRunSubmission,
    TaskScheduleInput,
    TasksListOptions,
    TasksPage,
    TaskUpdate,
    ToolApproval,
    ToolApprovalContinuation,
    ToolApprovalDecision,
    ToolApprovalDecisionInput,
    ToolApprovals,
    __version__,
)

TENANT = {
    "name": "Blazing",
    "quota": {
        "monthlyTokenLimit": 1_000,
        "monthlyRequestLimit": None,
        "resetDay": 1,
    },
}
USAGE = {
    "buckets": [
        {
            "day": "2026-08-01",
            "agentId": "ag_0123456789abcdef",
            "sessionId": None,
            "userId": "",
            "provider": "future-provider",
            "model": "future-model",
            "inputTokens": 10,
            "outputTokens": 5,
            "requestCount": 1,
            "durationMs": 100,
        }
    ],
    "totals": {
        "inputTokens": 10,
        "outputTokens": 5,
        "requestCount": 1,
        "durationMs": 100,
    },
}
AGENT: dict[str, Any] = {
    "id": "ag_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "name": "Builder",
    "model": None,
    "providerId": None,
    "workspaceId": "ws_aaaaaaaaaaaaaaaa",
    "memoryInjectionEnabled": False,
    "tools": ["workspace", "write_todos"],
    "instructions": "Build carefully.",
    "userId": "",
    "metadata": {},
    "mcpConnectionIds": [],
    "avatarUrl": None,
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
    "version": 1,
    "status": "active",
}
AGENT_VERSION: dict[str, Any] = {
    "agentId": "ag_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "version": 3,
    "name": "Historical Builder",
    "model": "anthropic/claude-sonnet-4.5",
    "providerId": "prv_0123456789abcdef",
    "memoryInjectionEnabled": True,
    "tools": ["workspace", "write_todos"],
    "instructions": "Historical instructions.",
    "metadata": {"source": "version-3"},
    "mcpConnectionIds": ["mcp_0123456789abcdef"],
    "createdAt": "2026-08-01T00:00:00.000Z",
}
MCP_ATTACHMENT: dict[str, Any] = {
    "mcpConnectionId": "mcp_0123456789abcdef",
    "forwardUserId": False,
    "forwardedMetadataKeys": [],
    "createdAt": "2026-08-01T00:00:00.000Z",
    "updatedAt": "2026-08-01T00:00:00.000Z",
}
WORKSPACE: dict[str, Any] = {
    "id": "ws_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "name": "Build files",
    "userId": "end-user",
    "metadata": {"OpaqueKey": {"nested_key": True}},
    "networkPolicy": {"mode": "unrestricted"},
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
}
PROVIDER: dict[str, Any] = {
    "id": "prv_0123456789abcdef",
    "name": "OpenAI",
    "providerType": "future-provider",
    "baseUrl": None,
    "keyFragment": "cdef",
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
}
MCP_CONNECTION: dict[str, Any] = {
    "id": "mcp_0123456789abcdef",
    "name": "Tools",
    "url": "https://mcp.example.com/",
    "authType": "future-auth",
    "status": "future-status",
    "credentialFragment": None,
    "lastAuthErrorCode": "FUTURE_ERROR",
    "oauthIssuer": None,
    "oauthResource": None,
    "tokenExpiresAt": None,
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
}
PROMPT: dict[str, Any] = {
    "id": "prompt_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "name": "Greeting",
    "template": "Hello {{name}}",
    "variables": ["name"],
    "userId": "",
    "metadata": {"OpaqueKey": {"nested_key": None}},
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
}
MEMORY: dict[str, Any] = {
    "id": "mem_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "userId": "",
    "text": "Prefers dark mode",
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
    "lastAccessedAt": "2026-08-02T00:00:00.000Z",
}
SKILL: dict[str, Any] = {
    "id": "skill_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "name": "deploy",
    "description": "Deploy the application.",
    "metadata": {"owner": "platform"},
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
}
SKILL_DETAIL: dict[str, Any] = {
    **SKILL,
    "files": [
        {"path": "SKILL.md", "sizeBytes": 72},
        {"path": "assets/icon.bin", "sizeBytes": 4},
    ],
}
ARTIFACT: dict[str, Any] = {
    "artifactId": "at_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "sessionId": "ss_0123456789abcdef",
    "filename": "report µ.pdf",
    "mediaType": "application/pdf",
    "sizeBytes": 12,
    "userId": "",
    "metadata": {"OpaqueKey": {"nested_key": True}},
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T01:00:00.000Z",
}
SESSION: dict[str, Any] = {
    "id": "ss_0123456789abcdef",
    "agentVersion": None,
    "messageCount": 2,
    "lastMessagePreview": "Done",
    "userId": "end-user",
    "metadata": {"OpaqueKey": {"nested_key": True}},
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T01:00:00.000Z",
}
SESSION_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "user-message",
        "role": "user",
        "parts": [{"type": "text", "text": "Build it"}],
        "metadata": {"source": "stored"},
    },
    {
        "id": "assistant-message",
        "role": "assistant",
        "parts": [
            {
                "type": "future-part",
                "OpaqueKey": {"nested_key": True},
            }
        ],
    },
]
TOOL_APPROVAL = {
    "approvalId": "approval-1",
    "toolName": "tenant",
    "toolCallId": "tool-call-1",
    "input": {"action": "update", "OpaqueKey": {"nested_key": True}},
    "decision": "pending",
    "reason": None,
}
TASK: dict[str, Any] = {
    "id": "tk_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "agentVersion": 3,
    "name": "Nightly report",
    "prompt": "Produce the nightly report.",
    "schedule": {
        "kind": "cron",
        "config": {
            "expression": "0 2 * * *",
            "timezone": "Europe/London",
            "staggerMs": 500,
        },
    },
    "enabled": True,
    "activeRunId": None,
    "latestRunId": "tr_0123456789abcdef",
    "userId": "end-user",
    "metadata": {"OpaqueKey": {"nested_key": True}},
    "deletedAt": None,
    "createdAt": "2026-08-01T00:00:00.000Z",
    "updatedAt": "2026-08-02T02:01:00.000Z",
}
TASK_LIST_ITEM: dict[str, Any] = {
    **TASK,
    "latestRun": {
        "id": "tr_0123456789abcdef",
        "status": "succeeded",
        "finishedAt": "2026-08-02T02:01:00.000Z",
    },
}
TASK_RUN: dict[str, Any] = {
    "id": "tr_0123456789abcdef",
    "taskId": "tk_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "agentVersion": 3,
    "sessionId": "ss_0123456789abcdef",
    "turnId": "turn_0123456789abcdef",
    "status": "blocked",
    "error": "Monthly token quota reached",
    "userId": "end-user",
    "metadata": {"OpaqueKey": {"nested_key": True}},
    "startedAt": "2026-08-02T02:00:00.000Z",
    "finishedAt": "2026-08-02T02:00:01.000Z",
    "cancelRequestedAt": None,
    "canceledAt": None,
    "createdAt": "2026-08-02T02:00:00.000Z",
    "updatedAt": "2026-08-02T02:00:01.000Z",
}


def _empty_headers() -> dict[str, str]:
    return {}


def _empty_requests() -> list[Request]:
    return []


@dataclass
class Response:
    body: Any = field(default_factory=lambda: TENANT)
    body_factory: Callable[[Request], Any] | None = None
    status: int = 200
    headers: dict[str, str] = field(default_factory=_empty_headers)
    delay: float = 0
    raw_body: bytes | None = None
    chunks: tuple[bytes, ...] | None = None
    chunk_gate: Event | None = None
    complete_chunks: bool = True
    chunk_delay: float = 0
    cancelled: Event | None = None


@dataclass
class Request:
    method: str
    target: str
    headers: httpx.Headers
    body: bytes


@dataclass
class ServerState:
    responses: deque[Response]
    requests: list[Request] = field(default_factory=_empty_requests)


@contextmanager
def loopback(*responses: Response) -> Generator[tuple[str, ServerState]]:
    state = ServerState(deque(responses))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            self._handle()

        def do_PATCH(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

        def do_PUT(self) -> None:
            self._handle()

        def do_DELETE(self) -> None:
            self._handle()

        def _handle(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            state.requests.append(
                Request(
                    method=self.command,
                    target=self.path,
                    headers=httpx.Headers(self.headers.items()),
                    body=self.rfile.read(length),
                )
            )
            response = state.responses.popleft()
            if response.delay:
                time.sleep(response.delay)
            response_body = (
                response.body_factory(state.requests[-1])
                if response.body_factory is not None
                else response.body
            )
            body = (
                response.raw_body
                if response.raw_body is not None
                else json.dumps(response_body).encode()
            )
            self.send_response(response.status)
            if not any(name.lower() == "content-type" for name in response.headers):
                self.send_header("content-type", "application/json")
            if response.chunks is None:
                self.send_header("content-length", str(len(body)))
            else:
                self.send_header("transfer-encoding", "chunked")
            self.send_header("connection", "close")
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.end_headers()
            try:
                if response.chunks is None:
                    self.wfile.write(body)
                else:
                    if response.chunk_delay:
                        time.sleep(response.chunk_delay)
                    for index, chunk in enumerate(response.chunks):
                        self.wfile.write(f"{len(chunk):X}\r\n".encode())
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                        if index == 0 and response.chunk_gate is not None:
                            response.chunk_gate.wait(timeout=5)
                            if response.cancelled is not None:
                                self.connection.settimeout(1)
                                try:
                                    if self.connection.recv(1) == b"":
                                        response.cancelled.set()
                                        return
                                except TimeoutError:
                                    pass
                    if response.complete_chunks:
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                if response.cancelled is not None:
                    response.cancelled.set()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_public_surface_and_sync_tenant_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLAZING_AGENTS_API_KEY", "ba_environment")
    response = Response(
        body={**TENANT, "futureField": {"opaque_key": True}},
        headers={"x-request-id": "req_sync"},
    )
    with loopback(response) as (base_url, state):
        with BlazingAgents(
            api_key="ba_explicit",
            base_url=f"{base_url}///",
            default_headers={
                "x-client": "default",
                "authorization": "Bearer hostile",
            },
        ) as client:
            tenant = client.tenant.get(
                extra_headers={"x-client": "operation", "x-extra": "yes"}
            )

    request = state.requests[0]
    assert request.target == "/v1/tenant"
    assert request.headers["authorization"] == "Bearer ba_explicit"
    assert request.headers["x-client"] == "operation"
    assert request.headers["x-extra"] == "yes"
    assert request.headers["user-agent"] == f"blazing_agents/{__version__}"
    assert tenant.name == "Blazing"
    assert tenant.quota is not None
    assert tenant.quota.monthly_token_limit == 1_000
    assert tenant.model_extra == {"futureField": {"opaque_key": True}}
    assert tenant._request_id == "req_sync"
    assert "_request_id" not in tenant.model_dump()
    assert issubclass(APIStatusError, BlazingAgentsError)
    assert issubclass(APIConnectionError, BlazingAgentsError)
    assert issubclass(APITimeoutError, APIConnectionError)
    assert issubclass(StreamError, BlazingAgentsError)
    assert logging.getLogger("blazing_agents").handlers == []


def test_wheel_metadata_and_typing_marker() -> None:
    installed = distribution("blazing_agents")
    assert installed.metadata["Name"] == "blazing_agents"
    assert installed.metadata["Requires-Python"] == ">=3.11"
    assert installed.metadata.get_all("Requires-Dist") == [
        "httpx<1,>=0.27",
        "pydantic<3,>=2",
    ]
    assert files("blazing_agents").joinpath("py.typed").is_file()


def test_sync_tasks_manage_definitions_runs_and_lazy_pages() -> None:
    second_task = {
        **TASK_LIST_ITEM,
        "id": "tk_fedcba9876543210",
        "name": "Second task",
    }
    second_run = {
        **TASK_RUN,
        "id": "tr_fedcba9876543210",
        "status": "future_terminal",
        "error": None,
        "futureRunField": {"opaque_key": True},
    }
    submitted_runs: dict[str, str] = {}

    def idempotent_submission(request: Request) -> dict[str, str]:
        key = cast(dict[str, str], json.loads(request.body))["idempotencyKey"]
        run_id = submitted_runs.setdefault(key, "tr_0123456789abcdef")
        return {"runId": run_id}

    with loopback(
        Response(
            body={
                "task": {**TASK, "futureTaskField": {"opaque_key": True}},
                "runId": TASK_RUN["id"],
                "futureResponseField": True,
            },
            headers={"x-request-id": "req_task_create"},
        ),
        Response(
            body={"data": [TASK_LIST_ITEM], "nextCursor": None},
            headers={"x-request-id": "req_tasks_page"},
        ),
        Response(body={"data": [TASK_LIST_ITEM], "nextCursor": "tasks-next"}),
        Response(body={"data": [second_task], "nextCursor": None}),
        Response(body=TASK),
        Response(body={**TASK, "agentVersion": None, "schedule": None}),
        Response(
            body={
                **TASK,
                "schedule": {
                    "kind": "once",
                    "config": {"at": "2026-08-04T12:00:00.000Z"},
                },
            }
        ),
        Response(body=TASK),
        Response(status=204, raw_body=b""),
        Response(body_factory=idempotent_submission),
        Response(body_factory=idempotent_submission),
        Response(body={"data": [TASK_RUN], "nextCursor": None}),
        Response(body={"data": [TASK_RUN], "nextCursor": "runs-next"}),
        Response(body={"data": [second_run], "nextCursor": None}),
        Response(body=second_run, headers={"x-request-id": "req_task_run"}),
        Response(
            body={
                "data": SESSION_MESSAGES,
                "nextCursor": "older",
                "latestCursor": "tail",
            }
        ),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.tasks.create(
                agent_id=TASK["agentId"],
                name="Nightly report",
                prompt="Produce the nightly report.",
                agent_version=3,
                schedule={
                    "kind": "interval",
                    "config": {"every_ms": 60_000},
                },
                enabled=True,
                submit=True,
                user_id="end-user",
                metadata={"OpaqueKey": {"nested_key": True}},
            )
            page = client.tasks.list(
                agent_id=TASK["agentId"],
                user_id="end-user",
                cursor="opaque page",
                limit=1,
            )
            tasks = client.tasks.iter(agent_id=TASK["agentId"], limit=1)
            assert len(state.requests) == 2
            assert next(tasks).name == "Nightly report"
            assert len(state.requests) == 3
            assert next(tasks).name == "Second task"
            with pytest.raises(StopIteration):
                next(tasks)
            fetched = client.tasks.get("task/with space")
            unpinned = client.tasks.update(
                TASK["id"],
                agent_version=None,
                schedule=None,
                enabled=False,
                metadata={"OpaqueKey": {"explicit_null": None}},
            )
            once = client.tasks.update(
                TASK["id"],
                schedule={
                    "kind": "once",
                    "config": {"at": "2026-08-04T12:00:00.000Z"},
                },
            )
            cron = client.tasks.update(
                TASK["id"],
                name="Renamed",
                prompt="Updated prompt.",
                schedule={
                    "kind": "cron",
                    "config": {
                        "expression": "0 3 * * *",
                        "timezone": "UTC",
                        "stagger_ms": 1_000,
                    },
                },
            )
            client.tasks.delete(TASK["id"])
            first_submission = client.tasks.submit(
                TASK["id"],
                idempotency_key="stable-key",
            )
            replayed_submission = client.tasks.submit(
                TASK["id"],
                idempotency_key="stable-key",
            )
            runs_page = client.tasks.list_runs(
                TASK["id"],
                cursor="opaque run",
                limit=1,
            )
            runs = client.tasks.iter_runs(TASK["id"], limit=1)
            assert len(state.requests) == 12
            assert next(runs).status == "blocked"
            assert len(state.requests) == 13
            assert next(runs).status == "future_terminal"
            with pytest.raises(StopIteration):
                next(runs)
            run = client.tasks.get_run(TASK["id"], "tr_fedcba9876543210")
            messages = client.tasks.run_messages(
                TASK["id"],
                TASK_RUN["id"],
                after="tail before",
                limit=25,
            )
            client.tasks.cancel_run(TASK["id"], TASK_RUN["id"])

    assert isinstance(created, TaskCreateResponse)
    assert isinstance(created.task, Task)
    assert created.run_id == TASK_RUN["id"]
    assert created._request_id == "req_task_create"
    assert created.model_extra == {"futureResponseField": True}
    assert created.task.model_extra == {"futureTaskField": {"opaque_key": True}}
    assert isinstance(page, TasksPage)
    assert isinstance(page.data[0], TaskListItem)
    assert page._request_id == "req_tasks_page"
    assert isinstance(page.data[0].schedule, TaskCronSchedule)
    assert fetched.id == TASK["id"]
    assert unpinned.agent_version is None
    assert unpinned.schedule is None
    assert isinstance(once.schedule, TaskOnceSchedule)
    assert isinstance(cron.schedule, TaskCronSchedule)
    assert first_submission.run_id == replayed_submission.run_id
    assert isinstance(first_submission, TaskRunSubmission)
    assert isinstance(runs_page, TaskRunsPage)
    assert runs_page.data[0].status == "blocked"
    assert runs_page.data[0].error == "Monthly token quota reached"
    assert runs_page.data[0].turn_id == TASK_RUN["turnId"]
    assert run.status == "future_terminal"
    assert run.turn_id == TASK_RUN["turnId"]
    assert run.model_extra == {"futureRunField": {"opaque_key": True}}
    assert run._request_id == "req_task_run"
    assert isinstance(messages, TaskRunMessagesPage)
    assert messages.latest_cursor == "tail"
    assert messages.data[1].parts[0].model_extra == {"OpaqueKey": {"nested_key": True}}

    assert json.loads(state.requests[0].body) == {
        "agentId": TASK["agentId"],
        "agentVersion": 3,
        "name": "Nightly report",
        "prompt": "Produce the nightly report.",
        "schedule": {"kind": "interval", "config": {"everyMs": 60_000}},
        "enabled": True,
        "submit": True,
        "userId": "end-user",
        "metadata": {"OpaqueKey": {"nested_key": True}},
    }
    listed = urlsplit(state.requests[1].target)
    assert listed.path == "/v1/tasks"
    assert parse_qs(listed.query) == {
        "agentId": [TASK["agentId"]],
        "userId": ["end-user"],
        "cursor": ["opaque page"],
        "limit": ["1"],
    }
    assert state.requests[3].target.endswith(
        "?agentId=ag_0123456789abcdef&cursor=tasks-next&limit=1"
    )
    assert state.requests[4].target == "/v1/tasks/task%2Fwith%20space"
    assert json.loads(state.requests[5].body) == {
        "agentVersion": None,
        "enabled": False,
        "metadata": {"OpaqueKey": {"explicit_null": None}},
        "schedule": None,
    }
    assert json.loads(state.requests[6].body) == {
        "schedule": {
            "kind": "once",
            "config": {"at": "2026-08-04T12:00:00.000Z"},
        }
    }
    assert json.loads(state.requests[7].body)["schedule"] == {
        "kind": "cron",
        "config": {
            "expression": "0 3 * * *",
            "timezone": "UTC",
            "staggerMs": 1_000,
        },
    }
    assert state.requests[8].method == "DELETE"
    for request in state.requests[9:11]:
        assert json.loads(request.body) == {"idempotencyKey": "stable-key"}
        assert "idempotency-key" not in request.headers
    assert state.requests[13].target.endswith("?cursor=runs-next&limit=1")
    assert state.requests[15].target.endswith("/messages?after=tail+before&limit=25")
    assert state.requests[16].method == "POST"
    assert state.requests[16].body == b""


def test_async_tasks_match_sync_resources_and_lazy_pagination() -> None:
    interval_task = {
        **TASK,
        "schedule": {"kind": "interval", "config": {"everyMs": 120_000}},
    }
    once_task = {
        **TASK,
        "schedule": {
            "kind": "once",
            "config": {"at": "2026-08-05T12:00:00.000Z"},
        },
    }
    with loopback(
        Response(body={"task": interval_task, "runId": None}),
        Response(body={"data": [TASK_LIST_ITEM], "nextCursor": None}),
        Response(body={"data": [TASK_LIST_ITEM], "nextCursor": "next"}),
        Response(
            body={"data": [{**TASK_LIST_ITEM, "name": "Async 2"}], "nextCursor": None}
        ),
        Response(body=TASK),
        Response(body=once_task),
        Response(status=204, raw_body=b""),
        Response(body={"runId": TASK_RUN["id"]}),
        Response(body={"data": [TASK_RUN], "nextCursor": None}),
        Response(body={"data": [TASK_RUN], "nextCursor": "next-run"}),
        Response(
            body={"data": [{**TASK_RUN, "status": "succeeded"}], "nextCursor": None}
        ),
        Response(body=TASK_RUN),
        Response(body={"data": [], "nextCursor": None, "latestCursor": None}),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                created = await client.tasks.create(
                    agent_id=TASK["agentId"],
                    name="Async task",
                    prompt="Run async.",
                    schedule={
                        "kind": "interval",
                        "config": {"every_ms": 120_000},
                    },
                )
                page = await client.tasks.list(user_id="", limit=1)
                tasks = client.tasks.iter(user_id="", limit=1)
                assert len(state.requests) == 2
                assert (await anext(tasks)).name == "Nightly report"
                assert len(state.requests) == 3
                assert (await anext(tasks)).name == "Async 2"
                with pytest.raises(StopAsyncIteration):
                    await anext(tasks)
                fetched = await client.tasks.get(TASK["id"])
                updated = await client.tasks.update(
                    TASK["id"],
                    schedule={
                        "kind": "once",
                        "config": {"at": "2026-08-05T12:00:00.000Z"},
                    },
                )
                await client.tasks.delete(TASK["id"])
                submitted = await client.tasks.submit(TASK["id"])
                runs_page = await client.tasks.list_runs(TASK["id"], limit=1)
                runs = client.tasks.iter_runs(TASK["id"], limit=1)
                assert len(state.requests) == 9
                assert (await anext(runs)).status == "blocked"
                assert len(state.requests) == 10
                assert (await anext(runs)).status == "succeeded"
                with pytest.raises(StopAsyncIteration):
                    await anext(runs)
                run = await client.tasks.get_run(TASK["id"], TASK_RUN["id"])
                messages = await client.tasks.run_messages(
                    TASK["id"],
                    TASK_RUN["id"],
                    cursor="older",
                )
                await client.tasks.cancel_run(TASK["id"], TASK_RUN["id"])

            assert isinstance(created.task.schedule, TaskIntervalSchedule)
            assert created.run_id is None
            assert isinstance(page, TasksPage)
            assert fetched.agent_version == 3
            assert isinstance(updated.schedule, TaskOnceSchedule)
            assert submitted.run_id == TASK_RUN["id"]
            assert isinstance(runs_page, TaskRunsPage)
            assert isinstance(run, TaskRun)
            assert run.turn_id == TASK_RUN["turnId"]
            assert messages.data == []

        asyncio.run(exercise())

    assert json.loads(state.requests[0].body) == {
        "agentId": TASK["agentId"],
        "name": "Async task",
        "prompt": "Run async.",
        "schedule": {"kind": "interval", "config": {"everyMs": 120_000}},
    }
    assert state.requests[1].target == "/v1/tasks?userId=&limit=1"
    assert json.loads(state.requests[7].body) == {}
    assert "idempotency-key" not in state.requests[7].headers
    assert state.requests[10].target.endswith("?cursor=next-run&limit=1")
    assert state.requests[12].target.endswith("/messages?cursor=older")
    assert state.requests[13].body == b""


def test_task_public_request_types_are_available_from_installed_wheel() -> None:
    schedule: TaskScheduleInput = {
        "kind": "cron",
        "config": {
            "expression": "0 2 * * *",
            "timezone": "UTC",
            "stagger_ms": 250,
        },
    }
    cron: TaskCronScheduleInput = {
        "kind": "cron",
        "config": {"expression": "0 2 * * *"},
    }
    create: TaskCreate = {
        "agent_id": TASK["agentId"],
        "name": "Nightly report",
        "prompt": "Produce it.",
        "schedule": schedule,
    }
    update: TaskUpdate = {"agent_version": None, "schedule": None}
    listed: TasksListOptions = {"agent_id": TASK["agentId"], "limit": 50}
    submit: TaskRunCreate = {"idempotency_key": "stable-key"}
    runs: TaskRunsListOptions = {"cursor": "opaque", "limit": 25}
    messages: TaskRunMessagesOptions = {"after": "tail", "limit": 25}

    assert cron["kind"] == "cron"
    assert create["schedule"] == schedule
    assert update["agent_version"] is None
    assert listed["limit"] == 50
    assert submit["idempotency_key"] == "stable-key"
    assert runs["cursor"] == "opaque"
    assert messages["after"] == "tail"


@pytest.mark.parametrize(
    "schedule,error",
    [
        (cast(Any, []), TypeError),
        (cast(Any, {"kind": "once"}), TypeError),
        (cast(Any, {"kind": "once", "config": []}), TypeError),
        (
            cast(Any, {"kind": "once", "config": {"at": 1}}),
            TypeError,
        ),
        (
            cast(Any, {"kind": "once", "config": {"at": "not-a-date"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "interval", "config": {"every_ms": 1}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "interval", "config": {"every_ms": True}}),
            ValueError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "interval",
                    "config": {"every_ms": 60_000, "unknown": True},
                },
            ),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"timezone": "UTC"}}),
            TypeError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "cron",
                    "config": {"expression": "* * * * *", "unknown": True},
                },
            ),
            TypeError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": 1}}),
            TypeError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "not cron"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "60 * * * *"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "*/61 * * * *"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "* */25 * * *"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "* * */32 * *"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "* * * */13 *"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "* * * * */8"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "2-1 * * * *"}}),
            ValueError,
        ),
        (
            cast(
                Any,
                {"kind": "cron", "config": {"expression": "1-2-3 * * * *"}},
            ),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "*/0 * * * *"}}),
            ValueError,
        ),
        (
            cast(Any, {"kind": "cron", "config": {"expression": "1/2 * * * *"}}),
            ValueError,
        ),
        (
            cast(
                Any,
                {"kind": "cron", "config": {"expression": "0 0 31 2 *"}},
            ),
            ValueError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "cron",
                    "config": {"expression": "* * * * *", "timezone": 1},
                },
            ),
            TypeError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "cron",
                    "config": {
                        "expression": "* * * * *",
                        "timezone": "PST",
                    },
                },
            ),
            ValueError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "cron",
                    "config": {
                        "expression": "* * * * *",
                        "timezone": "Area/NoSuchZone",
                    },
                },
            ),
            ValueError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "cron",
                    "config": {"expression": "* * * * *", "stagger_ms": -1},
                },
            ),
            ValueError,
        ),
        (
            cast(
                Any,
                {
                    "kind": "cron",
                    "config": {"expression": "* * * * *", "stagger_ms": True},
                },
            ),
            ValueError,
        ),
        (
            cast(Any, {"kind": "future", "config": {}}),
            ValueError,
        ),
    ],
)
def test_task_schedule_requests_reject_malformed_values(
    schedule: Any,
    error: type[Exception],
) -> None:
    client = BlazingAgents(api_key="ba_test", base_url="http://127.0.0.1:1")
    with pytest.raises(error):
        client.tasks.create(
            agent_id=TASK["agentId"],
            name="Task",
            prompt="Prompt",
            schedule=schedule,
        )
    client.close()


def test_task_cron_accepts_dom_or_dow_and_range_schedules() -> None:
    schedule = {
        "kind": "cron",
        "config": {
            "expression": "0 0 31 2 1",
            "timezone": "UTC",
        },
    }
    range_schedule = {
        "kind": "cron",
        "config": {"expression": "1-5 0 * * *"},
    }
    range_response_schedule = {
        "kind": "cron",
        "config": {"expression": "1-5 0 * * *", "timezone": "UTC"},
    }
    response_task = {**TASK, "schedule": schedule}
    with loopback(
        Response(body={"task": response_task, "runId": None}),
        Response(
            body={
                "task": {**TASK, "schedule": range_response_schedule},
                "runId": None,
            }
        ),
    ) as (
        base_url,
        state,
    ):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.tasks.create(
                agent_id=TASK["agentId"],
                name=TASK["name"],
                prompt=TASK["prompt"],
                schedule=cast(Any, schedule),
            )
            ranged = client.tasks.create(
                agent_id=TASK["agentId"],
                name=TASK["name"],
                prompt=TASK["prompt"],
                schedule=cast(Any, range_schedule),
            )

    assert isinstance(created.task.schedule, TaskCronSchedule)
    assert json.loads(state.requests[0].body)["schedule"] == schedule
    assert isinstance(ranged.task.schedule, TaskCronSchedule)
    assert json.loads(state.requests[1].body)["schedule"] == range_schedule


@pytest.mark.parametrize(
    "expression",
    ["1-2/3 * * * *", "1-2/60 * * * *", "* * * * 6-7/7"],
)
def test_task_cron_accepts_field_maximum_range_steps(expression: str) -> None:
    schedule = {
        "kind": "cron",
        "config": {"expression": expression, "timezone": "UTC"},
    }
    response_task = {**TASK, "schedule": schedule}
    with loopback(Response(body={"task": response_task, "runId": None})) as (
        base_url,
        state,
    ):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.tasks.create(
                agent_id=TASK["agentId"],
                name=TASK["name"],
                prompt=TASK["prompt"],
                schedule=cast(Any, schedule),
            )

    assert isinstance(created.task.schedule, TaskCronSchedule)
    assert json.loads(state.requests[0].body)["schedule"] == schedule


def test_task_cron_timezone_is_trimmed_for_request_and_response() -> None:
    schedule = {
        "kind": "cron",
        "config": {"expression": "0 2 * * *", "timezone": " UTC "},
    }
    response_schedule = {
        "kind": "cron",
        "config": {"expression": "0 2 * * *", "timezone": " UTC "},
    }
    with loopback(
        Response(body={"task": {**TASK, "schedule": response_schedule}, "runId": None})
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.tasks.create(
                agent_id=TASK["agentId"],
                name=TASK["name"],
                prompt=TASK["prompt"],
                schedule=cast(Any, schedule),
            )

    assert isinstance(created.task.schedule, TaskCronSchedule)
    assert created.task.schedule.config.timezone == "UTC"
    assert json.loads(state.requests[0].body)["schedule"]["config"]["timezone"] == (
        "UTC"
    )


def test_task_boundaries_preserve_api_errors_and_reject_malformed_responses() -> None:
    error = {
        "error": {
            "code": "task_run_conflict",
            "message": "Task already has an active run",
            "details": {"activeRunId": TASK_RUN["id"]},
        }
    }
    missing_turn_id = {key: value for key, value in TASK_RUN.items() if key != "turnId"}
    malformed: list[dict[str, Any]] = [
        {"task": {**TASK, "agentVersion": 0}, "runId": None},
        {**TASK_RUN, "id": "wrong"},
        missing_turn_id,
        {**TASK_RUN, "turnId": 1},
        {
            "task": {
                **TASK,
                "schedule": {
                    "kind": "cron",
                    "config": {"expression": "60 * * * *", "timezone": "UTC"},
                },
            },
            "runId": None,
        },
        {
            "task": {
                **TASK,
                "schedule": {
                    "kind": "cron",
                    "config": {"expression": "0 0 * * *", "timezone": "PST"},
                },
            },
            "runId": None,
        },
        {"data": "wrong", "nextCursor": None},
        {"data": [], "nextCursor": None},
    ]
    with loopback(
        Response(
            body=error,
            status=409,
            headers={"x-request-id": "req_task_conflict"},
        ),
        *(Response(body=value) for value in malformed),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(ValueError, match="At least one"):
                client.tasks.update(TASK["id"])
            with pytest.raises(ValueError, match="blank"):
                client.tasks.submit(TASK["id"], idempotency_key=" ")
            with pytest.raises(TypeError, match="string"):
                client.tasks.submit(
                    TASK["id"],
                    idempotency_key=cast(Any, 1),
                )
            with pytest.raises(TypeError):
                cast(Any, client.tasks.create)(
                    agent_id=TASK["agentId"],
                    name="Task",
                    prompt="Prompt",
                    unknown=True,
                )
            with pytest.raises(APIStatusError) as conflict:
                client.tasks.submit(TASK["id"], idempotency_key="stable")
            with pytest.raises(ValidationError):
                client.tasks.create(
                    agent_id=TASK["agentId"],
                    name="Task",
                    prompt="Prompt",
                )
            with pytest.raises(ValidationError):
                client.tasks.get_run(TASK["id"], TASK_RUN["id"])
            with pytest.raises(ValidationError):
                client.tasks.get_run(TASK["id"], TASK_RUN["id"])
            with pytest.raises(ValidationError):
                client.tasks.get_run(TASK["id"], TASK_RUN["id"])
            with pytest.raises(ValidationError):
                client.tasks.create(
                    agent_id=TASK["agentId"],
                    name="Task",
                    prompt="Prompt",
                )
            with pytest.raises(ValidationError):
                client.tasks.create(
                    agent_id=TASK["agentId"],
                    name="Task",
                    prompt="Prompt",
                )
            with pytest.raises(ValidationError):
                client.tasks.list_runs(TASK["id"])
            with pytest.raises(ValidationError):
                client.tasks.run_messages(TASK["id"], TASK_RUN["id"])

    assert conflict.value.code == "task_run_conflict"
    assert conflict.value.request_id == "req_task_conflict"
    assert conflict.value.details == {"activeRunId": TASK_RUN["id"]}
    assert len(state.requests) == 9

    async def reject_invalid_async_requests() -> None:
        client = AsyncBlazingAgents(
            api_key="ba_test",
            base_url="http://127.0.0.1:1",
        )
        with pytest.raises(ValueError, match="At least one"):
            await client.tasks.update(TASK["id"])
        with pytest.raises(ValueError, match="blank"):
            await client.tasks.submit(TASK["id"], idempotency_key=" ")
        await client.aclose()

    asyncio.run(reject_invalid_async_requests())

    with loopback(
        Response(
            body={
                "task": {
                    **TASK,
                    "schedule": {"kind": "interval", "config": {"everyMs": 1}},
                },
                "runId": None,
            }
        ),
        Response(
            body={
                "task": {
                    **TASK,
                    "schedule": {
                        "kind": "cron",
                        "config": {
                            "expression": "60 * * * *",
                            "timezone": "UTC",
                        },
                    },
                },
                "runId": None,
            }
        ),
        Response(
            body={
                "task": {
                    **TASK,
                    "schedule": {
                        "kind": "cron",
                        "config": {
                            "expression": "0 0 * * *",
                            "timezone": "PST",
                        },
                    },
                },
                "runId": None,
            }
        ),
        Response(
            body={key: value for key, value in TASK_RUN.items() if key != "turnId"}
        ),
        Response(body={**TASK_RUN, "turnId": 1}),
        Response(body={"data": "wrong", "nextCursor": None}),
        Response(body={"data": [], "nextCursor": None}),
    ) as (base_url, async_state):

        async def reject_invalid_async_responses() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(ValidationError):
                    await client.tasks.create(
                        agent_id=TASK["agentId"],
                        name="Task",
                        prompt="Prompt",
                    )
                with pytest.raises(ValidationError):
                    await client.tasks.create(
                        agent_id=TASK["agentId"],
                        name="Task",
                        prompt="Prompt",
                    )
                with pytest.raises(ValidationError):
                    await client.tasks.create(
                        agent_id=TASK["agentId"],
                        name="Task",
                        prompt="Prompt",
                    )
                with pytest.raises(ValidationError):
                    await client.tasks.get_run(TASK["id"], TASK_RUN["id"])
                with pytest.raises(ValidationError):
                    await client.tasks.get_run(TASK["id"], TASK_RUN["id"])
                with pytest.raises(ValidationError):
                    await client.tasks.list_runs(TASK["id"])
                with pytest.raises(ValidationError):
                    await client.tasks.run_messages(TASK["id"], TASK_RUN["id"])

        asyncio.run(reject_invalid_async_responses())

    assert len(async_state.requests) == 7


def test_sync_tenant_update_preserves_omission_and_null() -> None:
    with loopback(Response(), Response(body={**TENANT, "quota": None})) as (
        base_url,
        state,
    ):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            client.tenant.update(
                name="Renamed",
                quota={
                    "monthly_token_limit": None,
                    "monthly_request_limit": 25,
                    "reset_day": 7,
                },
            )
            result = client.tenant.update(quota=None)

    first, second = state.requests
    assert first.method == "PATCH"
    assert json.loads(first.body) == {
        "name": "Renamed",
        "quota": {
            "monthlyTokenLimit": None,
            "monthlyRequestLimit": 25,
            "resetDay": 7,
        },
    }
    assert json.loads(second.body) == {"quota": None}
    assert result.quota is None


def test_tenant_update_rejects_empty_and_unknown_nested_fields() -> None:
    client = BlazingAgents(api_key="ba_test", base_url="http://127.0.0.1:1")
    with pytest.raises(ValueError, match="At least one"):
        client.tenant.update()
    with pytest.raises(TypeError, match="exactly"):
        client.tenant.update(
            quota=cast(
                Any,
                {
                    "monthly_token_limit": 1,
                    "monthly_request_limit": 1,
                    "reset_day": 1,
                    "opaque": {"DoNotChange": True},
                },
            )
        )
    client.close()


def test_sync_usage_queries_translate_only_owned_names() -> None:
    with loopback(Response(body=USAGE), Response(body=USAGE)) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            usage = client.usage.get(
                from_="2026-08-01",
                to="2026-08-02",
                agent_id="ag_0123456789abcdef",
                session_id="",
                user_id="tenant/User",
                group_by="user",
                limit=20,
            )
            agent_usage = client.usage.get_for_agent(
                "agent/with space",
                group_by="model",
            )

    first = urlsplit(state.requests[0].target)
    assert first.path == "/v1/usage"
    assert parse_qs(first.query, keep_blank_values=True) == {
        "from": ["2026-08-01"],
        "to": ["2026-08-02"],
        "agentId": ["ag_0123456789abcdef"],
        "sessionId": [""],
        "userId": ["tenant/User"],
        "groupBy": ["user"],
        "limit": ["20"],
    }
    assert state.requests[1].target == (
        "/v1/agents/agent%2Fwith%20space/usage?groupBy=model"
    )
    assert usage.buckets[0].provider == "future-provider"
    assert usage.buckets[0].user_id == ""
    assert usage.totals.request_count == 1
    assert agent_usage.totals.input_tokens == 10


def test_async_clients_match_tenant_and_usage_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLAZING_AGENTS_API_KEY", "ba_async_environment")
    with loopback(
        Response(
            body={**TENANT, "futureAsyncField": {"OpaqueKey": True}},
            headers={"x-request-id": "req_async_get"},
        ),
        Response(body={**TENANT, "name": "Async update"}),
        Response(body=USAGE),
        Response(body=USAGE),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                base_url=f"{base_url}/",
                default_headers={"x-default": "async"},
            ) as client:
                tenant = await client.tenant.get(
                    extra_headers={
                        "x-extra": "async",
                        "Authorization": "Bearer ignored",
                    }
                )
                updated = await client.tenant.update(name="Async update")
                usage = await client.usage.get(user_id="", group_by="day")
                agent_usage = await client.usage.get_for_agent(
                    "ag_0123456789abcdef",
                    session_id="ss_0123456789abcdef",
                )
            assert tenant._request_id == "req_async_get"
            assert tenant.model_extra == {"futureAsyncField": {"OpaqueKey": True}}
            assert updated.name == "Async update"
            assert usage.totals.output_tokens == 5
            assert agent_usage.buckets[0].model == "future-model"

        asyncio.run(exercise())

    assert state.requests[0].headers["authorization"] == ("Bearer ba_async_environment")
    assert state.requests[0].headers["x-default"] == "async"
    assert state.requests[0].headers["x-extra"] == "async"
    assert json.loads(state.requests[1].body) == {"name": "Async update"}
    assert state.requests[2].target == "/v1/usage?userId=&groupBy=day"
    assert state.requests[3].target.endswith("/usage?sessionId=ss_0123456789abcdef")


def test_injected_clients_remain_caller_owned() -> None:
    with loopback(Response(), Response()) as (base_url, _state):
        sync_http = httpx.Client()
        with BlazingAgents(
            api_key="ba_test",
            base_url=base_url,
            http_client=sync_http,
        ) as client:
            client.tenant.get()
        assert not sync_http.is_closed
        sync_http.close()

        async def exercise() -> None:
            async_http = httpx.AsyncClient()
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
                http_client=async_http,
            ) as client:
                await client.tenant.get()
            assert not async_http.is_closed
            await async_http.aclose()

        asyncio.run(exercise())


def test_internally_created_clients_close_explicitly() -> None:
    sync_client = BlazingAgents(api_key="ba_test", base_url="http://127.0.0.1:1")
    sync_client.close()
    with pytest.raises(RuntimeError, match="closed"):
        sync_client.tenant.get()

    async def exercise() -> None:
        async_client = AsyncBlazingAgents(
            api_key="ba_test",
            base_url="http://127.0.0.1:1",
        )
        await async_client.aclose()
        with pytest.raises(RuntimeError, match="closed"):
            await async_client.tenant.get()

    asyncio.run(exercise())


def test_configuration_validation_and_production_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BLAZING_AGENTS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        BlazingAgents()
    with pytest.raises(ValueError, match="base_url"):
        BlazingAgents(api_key="ba_test", base_url="///")
    with pytest.raises(TypeError, match="httpx.Client"):
        BlazingAgents(api_key="ba_test", http_client=httpx.AsyncClient())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="httpx.AsyncClient"):
        AsyncBlazingAgents(api_key="ba_test", http_client=httpx.Client())  # type: ignore[arg-type]

    requested: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request)
        return httpx.Response(200, json=TENANT)

    http_client = httpx.Client(transport=httpx.MockTransport(respond))
    client = BlazingAgents(api_key="ba_test", http_client=http_client)
    client.tenant.get()
    client.close()
    assert str(requested[0].url) == "https://api.blazingagents.com/v1/tenant"
    assert not http_client.is_closed
    http_client.close()

    async_requested: list[httpx.Request] = []

    def async_respond(request: httpx.Request) -> httpx.Response:
        async_requested.append(request)
        return httpx.Response(200, json=TENANT)

    async def exercise() -> None:
        async_http = httpx.AsyncClient(transport=httpx.MockTransport(async_respond))
        client = AsyncBlazingAgents(
            api_key="ba_test",
            http_client=async_http,
        )
        await client.tenant.get()
        await client.aclose()
        assert not async_http.is_closed
        await async_http.aclose()

    asyncio.run(exercise())
    assert str(async_requested[0].url) == ("https://api.blazingagents.com/v1/tenant")


def test_api_status_errors_preserve_server_metadata_without_retry() -> None:
    error = {
        "error": {
            "code": "future_domain_code",
            "message": "Slow down",
            "details": {"opaque_Key": {"NestedKey": True}},
            "param": "limit",
        }
    }
    response = Response(
        body=error,
        status=429,
        headers={"x-request-id": "req_error", "retry-after": "17"},
    )
    with loopback(response) as (base_url, state):
        client = BlazingAgents(api_key="ba_test", base_url=base_url)
        with pytest.raises(APIStatusError) as captured:
            client.tenant.get()
        client.close()

    exception = captured.value
    assert str(exception) == "Slow down"
    assert exception.status_code == 429
    assert exception.code == "future_domain_code"
    assert exception.details == {"opaque_Key": {"NestedKey": True}}
    assert exception.param == "limit"
    assert exception.request_id == "req_error"
    assert exception.retry_after == "17"
    assert exception.headers["retry-after"] == "17"
    assert json.loads(exception.response_body) == error
    assert len(state.requests) == 1


def test_malformed_api_status_error_is_still_actionable() -> None:
    with loopback(
        Response(status=502, raw_body=b"not-json", headers={"x-request-id": "req"})
    ) as (base_url, _state):
        client = BlazingAgents(api_key="ba_test", base_url=base_url)
        with pytest.raises(APIStatusError) as captured:
            client.tenant.get()
        client.close()
    assert captured.value.status_code == 502
    assert captured.value.code == "invalid_response"
    assert captured.value.request_id == "req"
    assert captured.value.response_body == "not-json"


def test_redirects_are_api_status_errors_in_both_clients() -> None:
    redirect = Response(
        status=307,
        raw_body=b"",
        headers={"location": "https://example.invalid", "x-request-id": "req_redirect"},
    )
    with loopback(redirect, redirect) as (base_url, _state):
        client = BlazingAgents(api_key="ba_test", base_url=base_url)
        with pytest.raises(APIStatusError) as sync_error:
            client.tenant.get()
        client.close()
        assert sync_error.value.status_code == 307
        assert sync_error.value.code == "invalid_response"

        async def exercise() -> None:
            async_client = AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            )
            with pytest.raises(APIStatusError) as async_error:
                await async_client.tenant.get()
            await async_client.aclose()
            assert async_error.value.status_code == 307
            assert async_error.value.request_id == "req_redirect"

        asyncio.run(exercise())


def _unused_origin() -> str:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    return f"http://127.0.0.1:{port}"


def test_sync_connection_timeout_and_operation_override() -> None:
    unavailable = BlazingAgents(api_key="ba_test", base_url=_unused_origin())
    with pytest.raises(APIConnectionError):
        unavailable.tenant.get()
    unavailable.close()

    with loopback(Response(delay=0.3), Response(delay=0.3)) as (
        base_url,
        _state,
    ):
        client = BlazingAgents(
            api_key="ba_test",
            base_url=base_url,
            timeout=0.1,
        )
        assert client.tenant.get(timeout=1).name == "Blazing"
        with pytest.raises(APITimeoutError):
            client.tenant.get()
        client.close()


def test_async_status_connection_timeout_and_operation_override() -> None:
    status = Response(
        status=503,
        body={"error": {"code": "service_unavailable", "message": "Later"}},
        headers={"x-request-id": "req_async_error"},
    )
    with loopback(status, Response(delay=0.3), Response(delay=0.3)) as (
        base_url,
        _state,
    ):

        async def exercise() -> None:
            client = AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
                timeout=0.1,
            )
            with pytest.raises(APIStatusError) as captured:
                await client.tenant.get()
            assert captured.value.code == "service_unavailable"
            assert captured.value.request_id == "req_async_error"
            assert (await client.tenant.get(timeout=1)).name == "Blazing"
            with pytest.raises(APITimeoutError):
                await client.tenant.get()
            await client.aclose()

            unavailable = AsyncBlazingAgents(
                api_key="ba_test",
                base_url=_unused_origin(),
            )
            with pytest.raises(APIConnectionError):
                await unavailable.tenant.get()
            await unavailable.aclose()

        asyncio.run(exercise())


def test_streaming_transport_timeouts_map_to_public_timeout_errors() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    sync_http = httpx.Client(transport=httpx.MockTransport(timeout))
    with BlazingAgents(api_key="ba_test", http_client=sync_http) as client:
        with pytest.raises(APITimeoutError):
            client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Slow connection",
            )
    sync_http.close()

    async def exercise() -> None:
        async_http = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
        async with AsyncBlazingAgents(
            api_key="ba_test",
            http_client=async_http,
        ) as client:
            with pytest.raises(APITimeoutError):
                await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Slow connection",
                )
        await async_http.aclose()

    asyncio.run(exercise())


def test_response_validation_rejects_wrong_documented_types() -> None:
    invalid = {**TENANT, "name": 123}
    with loopback(Response(body=invalid), Response(body=invalid)) as (
        base_url,
        _state,
    ):
        client = BlazingAgents(api_key="ba_test", base_url=base_url)
        with pytest.raises(ValidationError):
            client.tenant.get()
        client.close()

        async def exercise() -> None:
            async_client = AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            )
            with pytest.raises(ValidationError):
                await async_client.tenant.get()
            await async_client.aclose()

        asyncio.run(exercise())


def test_public_request_and_response_validation_rejects_invalid_invariants() -> None:
    duplicate_tools = {**AGENT, "tools": ["memory", "memory"]}
    oversized_memory = {**MEMORY, "text": "µ" * 5_121}
    with loopback(
        Response(body=duplicate_tools),
        Response(body={"memory": oversized_memory}),
    ) as (base_url, _state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(ValidationError, match="unique"):
                client.agents.get(AGENT["id"])
            with pytest.raises(ValidationError, match="10240 bytes"):
                client.memories.get(
                    agent_id=AGENT["id"],
                    memory_id=MEMORY["id"],
                )


def test_generation_rejects_ambiguous_prompts_and_misplaced_variables() -> None:
    with BlazingAgents(
        api_key="ba_test",
        base_url="http://127.0.0.1:1",
    ) as client:
        with pytest.raises(ValueError, match="exactly one"):
            client.completion(
                agent_id=AGENT["id"],
                prompt="literal",
                prompt_id=PROMPT["id"],
            )
        with pytest.raises(ValueError, match="variables"):
            client.completion(
                agent_id=AGENT["id"],
                prompt="literal",
                variables={"name": "Ada"},
            )


def test_debug_logging_contains_only_approved_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    query_secret = "secret-query-value"
    prompt_secret = "secret-prompt-body"
    file_secret = b"secret-file-content"
    stream_secret = b"secret-stream-content"
    with loopback(
        Response(body=USAGE, headers={"x-request-id": "req_log"}),
        Response(body=AGENT, headers={"x-request-id": "req_upload_log"}),
        Response(
            chunks=(stream_secret,),
            headers={"x-request-id": "req_stream_log"},
        ),
        Response(body=USAGE, headers={"x-request-id": "req_async_log"}),
    ) as (base_url, state):
        client = BlazingAgents(
            api_key="ba_secret",
            base_url=base_url,
            default_headers={"x-secret": "hidden-header"},
        )
        assert state.requests == []
        with caplog.at_level(logging.DEBUG, logger="blazing_agents"):
            client.usage.get(user_id=query_secret)
            client.agents.upload_avatar(
                AGENT["id"],
                file=file_secret,
                filename="secret.bin",
            )
            stream = client.completion_stream(
                agent_id=AGENT["id"],
                prompt=prompt_secret,
            )
            assert b"".join(delta.encode() for delta in stream) == stream_secret
        client.close()

        async def exercise() -> None:
            client = AsyncBlazingAgents(
                api_key="ba_async_secret",
                base_url=base_url,
                default_headers={"x-secret": "hidden-async-header"},
            )
            with caplog.at_level(logging.DEBUG, logger="blazing_agents"):
                await client.usage.get(user_id=query_secret)
            await client.aclose()

        asyncio.run(exercise())

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 4
    assert "request_id=req_log" in messages[0]
    assert "request_id=req_upload_log" in messages[1]
    assert "request_id=req_stream_log" in messages[2]
    assert "request_id=req_async_log" in messages[3]
    assert "method=GET path=/v1/usage" in messages[0]
    assert f"method=POST path=/v1/agents/{AGENT['id']}/avatar" in messages[1]
    assert f"method=POST path=/v1/agents/{AGENT['id']}/generation" in messages[2]
    assert "method=GET path=/v1/usage" in messages[3]
    for message in messages:
        assert "status=200" in message
        assert "elapsed_ms=" in message
        assert query_secret not in message
        assert prompt_secret not in message
        assert file_secret.decode() not in message
        assert stream_secret.decode() not in message
        assert "ba_secret" not in message
        assert "hidden-header" not in message
    assert [request.target for request in state.requests] == [
        "/v1/usage?userId=secret-query-value",
        f"/v1/agents/{AGENT['id']}/avatar",
        f"/v1/agents/{AGENT['id']}/generation",
        "/v1/usage?userId=secret-query-value",
    ]
    for request in state.requests:
        assert request.headers["user-agent"] == f"blazing_agents/{__version__}"
        assert not any(
            name.startswith(("x-analytics", "x-telemetry", "x-device"))
            for name in request.headers
        )


def test_sync_agents_manage_complete_lifecycle_and_attribution() -> None:
    attributed = {
        **AGENT,
        "userId": "end-user",
        "metadata": {"OpaqueKey": {"nested_key": True}},
        "workspaceId": "ws_0123456789abcdef",
        "futureField": "retained",
    }
    with loopback(
        Response(
            body={
                **attributed,
                "status": "future-status",
                "tools": ["future-tool"],
            },
            headers={"x-request-id": "req_agent"},
        ),
        Response(body={"agents": [attributed]}),
        Response(body=attributed),
        Response(
            body={
                **attributed,
                "name": "Renamed",
                "workspaceId": "ws_fedcba9876543210",
            }
        ),
        Response(body={**attributed, "status": "disabled"}),
        Response(body=attributed),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.agents.create(
                name="Builder",
                model="openrouter/test-model",
                provider_id="prv_0123456789abcdef",
                workspace_id="ws_0123456789abcdef",
                memory_injection_enabled=False,
                tools=["workspace", "write_todos"],
                instructions="Build carefully.",
                user_id="end-user",
                metadata={"OpaqueKey": {"nested_key": True}},
                mcp_connection_ids=[],
            )
            listed = client.agents.list(
                user_id="end-user",
                workspace_id="ws_0123456789abcdef",
            )
            fetched = client.agents.get("ag_0123456789abcdef")
            updated = client.agents.update(
                "ag_0123456789abcdef",
                name="Renamed",
                model=None,
                provider_id=None,
                workspace_id="ws_fedcba9876543210",
            )
            disabled = client.agents.disable("ag_0123456789abcdef")
            enabled = client.agents.enable("ag_0123456789abcdef")
            client.agents.delete("ag_0123456789abcdef", include_artifacts=False)

    assert created.user_id == "end-user"
    assert created.metadata == {"OpaqueKey": {"nested_key": True}}
    assert created.model_extra == {"futureField": "retained"}
    assert created.status == "future-status"
    assert created.tools == ["future-tool"]
    assert created._request_id == "req_agent"
    assert listed.agents[0].workspace_id == "ws_0123456789abcdef"
    assert fetched.id == "ag_0123456789abcdef"
    assert updated.workspace_id == "ws_fedcba9876543210"
    assert disabled.status == "disabled"
    assert enabled.status == "active"
    assert [request.method for request in state.requests] == [
        "POST",
        "GET",
        "GET",
        "PUT",
        "POST",
        "POST",
        "DELETE",
    ]
    assert json.loads(state.requests[0].body) == {
        "name": "Builder",
        "model": "openrouter/test-model",
        "providerId": "prv_0123456789abcdef",
        "workspaceId": "ws_0123456789abcdef",
        "memoryInjectionEnabled": False,
        "tools": ["workspace", "write_todos"],
        "instructions": "Build carefully.",
        "userId": "end-user",
        "metadata": {"OpaqueKey": {"nested_key": True}},
        "mcpConnectionIds": [],
    }
    assert state.requests[1].target.endswith(
        "?userId=end-user&workspaceId=ws_0123456789abcdef"
    )
    assert json.loads(state.requests[3].body) == {
        "name": "Renamed",
        "model": None,
        "providerId": None,
        "workspaceId": "ws_fedcba9876543210",
    }


def test_sync_agent_versions_page_lazy_iteration_get_and_restore() -> None:
    first_version = {**AGENT_VERSION, "version": 4, "name": "Latest"}
    restored_agent = {**AGENT, "name": AGENT_VERSION["name"], "version": 5}
    with loopback(
        Response(
            body={"data": [first_version], "nextCursor": "next"},
            headers={"x-request-id": "req_versions"},
        ),
        Response(body={"data": [first_version], "nextCursor": "next"}),
        Response(body={"data": [AGENT_VERSION], "nextCursor": None}),
        Response(body={**AGENT_VERSION, "futureVersionField": True}),
        Response(body=AGENT_VERSION),
        Response(body=restored_agent),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            page = client.agents.list_versions(
                "ag_0123456789abcdef",
                cursor="opaque page",
                limit=1,
            )
            versions = client.agents.iter_versions(
                "ag_0123456789abcdef",
                limit=1,
            )
            assert len(state.requests) == 1
            assert next(versions).version == 4
            assert len(state.requests) == 2
            assert next(versions).version == 3
            assert len(state.requests) == 3
            with pytest.raises(StopIteration):
                next(versions)
            historical = client.agents.get_version("ag_0123456789abcdef", 3)
            restored = client.agents.restore_version(
                "ag_0123456789abcdef",
                3,
            )

    assert page.next_cursor == "next"
    assert page._request_id == "req_versions"
    assert historical.model_extra == {"futureVersionField": True}
    assert restored.name == "Historical Builder"
    first_target = urlsplit(state.requests[0].target)
    assert first_target.path == ("/v1/agents/ag_0123456789abcdef/versions")
    assert parse_qs(first_target.query) == {
        "cursor": ["opaque page"],
        "limit": ["1"],
    }
    assert state.requests[2].target.endswith("?cursor=next&limit=1")
    assert state.requests[3].target.endswith("/versions/3")
    assert json.loads(state.requests[5].body) == {
        "name": "Historical Builder",
        "model": "anthropic/claude-sonnet-4.5",
        "providerId": "prv_0123456789abcdef",
        "memoryInjectionEnabled": True,
        "tools": ["workspace", "write_todos"],
        "instructions": "Historical instructions.",
        "metadata": {"source": "version-3"},
        "mcpConnectionIds": ["mcp_0123456789abcdef"],
    }


def test_sync_agent_mcp_attachment_settings() -> None:
    with loopback(
        Response(body={"mcpAttachments": [MCP_ATTACHMENT]}),
        Response(
            body={
                **MCP_ATTACHMENT,
                "forwardUserId": True,
                "forwardedMetadataKeys": ["locale"],
                "futureSetting": "retained",
            },
            headers={"x-request-id": "req_attachment"},
        ),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            listed = client.agents.list_mcp_attachments(
                "ag_0123456789abcdef",
            )
            updated = client.agents.update_mcp_attachment(
                "ag_0123456789abcdef",
                "mcp_0123456789abcdef",
                forward_user_id=True,
                forwarded_metadata_keys=["locale"],
            )
            with pytest.raises(ValueError, match="At least one"):
                client.agents.update_mcp_attachment(
                    "ag_0123456789abcdef",
                    "mcp_0123456789abcdef",
                )

    assert listed.mcp_attachments[0].forward_user_id is False
    assert updated.forwarded_metadata_keys == ["locale"]
    assert updated.model_extra == {"futureSetting": "retained"}
    assert updated._request_id == "req_attachment"
    assert state.requests[0].target.endswith("/mcp-attachments")
    assert state.requests[1].target.endswith("/mcp-attachments/mcp_0123456789abcdef")
    assert json.loads(state.requests[1].body) == {
        "forwardUserId": True,
        "forwardedMetadataKeys": ["locale"],
    }


def test_sync_agent_avatar_upload_sources_and_removal(tmp_path: Path) -> None:
    avatar_response = {
        **AGENT,
        "avatarUrl": "https://signed.example/avatar.png",
    }
    path = tmp_path / "path-avatar.png"
    path.write_bytes(b"path-image")
    caller_path = tmp_path / "caller-avatar.webp"
    caller_path.write_bytes(b"caller-image")

    with caller_path.open("rb") as caller_file:
        with loopback(
            Response(body=avatar_response),
            Response(body=avatar_response),
            Response(body=avatar_response),
            Response(body=AGENT),
        ) as (base_url, state):
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                from_bytes = client.agents.upload_avatar(
                    "ag_0123456789abcdef",
                    b"bytes-image",
                    filename="bytes-avatar.png",
                )
                client.agents.upload_avatar("ag_0123456789abcdef", path)
                client.agents.upload_avatar(
                    "ag_0123456789abcdef",
                    caller_file,
                )
                removed = client.agents.remove_avatar("ag_0123456789abcdef")
                with pytest.raises(ValueError, match="filename"):
                    client.agents.upload_avatar(
                        "ag_0123456789abcdef",
                        b"missing-name",
                    )
        assert caller_file.closed is False

    assert str(from_bytes.avatar_url) == "https://signed.example/avatar.png"
    assert removed.avatar_url is None
    assert path.read_bytes() == b"path-image"
    for request in state.requests[:3]:
        assert request.method == "POST"
        assert request.headers["content-type"].startswith("multipart/form-data;")
    assert b'filename="bytes-avatar.png"' in state.requests[0].body
    assert b"bytes-image" in state.requests[0].body
    assert b'filename="path-avatar.png"' in state.requests[1].body
    assert b"path-image" in state.requests[1].body
    assert b'filename="caller-avatar.webp"' in state.requests[2].body
    assert b"caller-image" in state.requests[2].body
    assert state.requests[3].method == "DELETE"
    assert state.requests[3].target.endswith("/avatar")


def test_async_agents_match_every_sync_operation() -> None:
    page = {"data": [AGENT_VERSION], "nextCursor": None}
    with loopback(
        Response(body=AGENT),
        Response(body={"agents": [AGENT]}),
        Response(body=AGENT),
        Response(body={**AGENT, "workspaceId": "ws_0123456789abcdef"}),
        Response(body={**AGENT, "status": "disabled"}),
        Response(body=AGENT),
        Response(body=page),
        Response(
            body={
                "data": [{**AGENT_VERSION, "version": 4}],
                "nextCursor": "next",
            }
        ),
        Response(body=page),
        Response(body=AGENT_VERSION),
        Response(body=AGENT_VERSION),
        Response(body={**AGENT, "version": 4}),
        Response(body={"mcpAttachments": [MCP_ATTACHMENT]}),
        Response(body={**MCP_ATTACHMENT, "forwardUserId": True}),
        Response(body={**AGENT, "avatarUrl": "https://signed.example/avatar.png"}),
        Response(body=AGENT),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):

        async def exercise() -> None:
            caller_file = io.BytesIO(b"async-avatar")
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                assert (await client.agents.create(name="Builder")).id == AGENT["id"]
                assert (await client.agents.list()).agents[0].name == "Builder"
                assert (await client.agents.get("ag_0123456789abcdef")).version == 1
                updated = await client.agents.update(
                    "ag_0123456789abcdef",
                    workspace_id="ws_0123456789abcdef",
                )
                assert updated.workspace_id == "ws_0123456789abcdef"
                assert (
                    await client.agents.disable("ag_0123456789abcdef")
                ).status == "disabled"
                assert (
                    await client.agents.enable("ag_0123456789abcdef")
                ).status == "active"
                assert (
                    await client.agents.list_versions(
                        "ag_0123456789abcdef",
                    )
                ).data[0].version == 3
                versions = client.agents.iter_versions(
                    "ag_0123456789abcdef",
                    limit=1,
                )
                assert len(state.requests) == 7
                assert (await anext(versions)).version == 4
                assert len(state.requests) == 8
                assert (await anext(versions)).version == 3
                assert len(state.requests) == 9
                with pytest.raises(StopAsyncIteration):
                    await anext(versions)
                assert (
                    await client.agents.get_version(
                        "ag_0123456789abcdef",
                        3,
                    )
                ).name == "Historical Builder"
                assert (
                    await client.agents.restore_version(
                        "ag_0123456789abcdef",
                        3,
                    )
                ).version == 4
                assert (
                    await client.agents.list_mcp_attachments(
                        "ag_0123456789abcdef",
                    )
                ).mcp_attachments[0].mcp_connection_id == ("mcp_0123456789abcdef")
                assert (
                    await client.agents.update_mcp_attachment(
                        "ag_0123456789abcdef",
                        "mcp_0123456789abcdef",
                        forward_user_id=True,
                    )
                ).forward_user_id is True
                uploaded = await client.agents.upload_avatar(
                    "ag_0123456789abcdef",
                    caller_file,
                    filename="avatar.png",
                )
                assert str(uploaded.avatar_url) == ("https://signed.example/avatar.png")
                assert caller_file.closed is False
                assert (
                    await client.agents.remove_avatar("ag_0123456789abcdef")
                ).avatar_url is None
                await client.agents.delete(
                    "ag_0123456789abcdef", include_artifacts=True
                )

            assert caller_file.closed is False

        asyncio.run(exercise())

    assert len(state.requests) == 17
    assert json.loads(state.requests[0].body) == {"name": "Builder"}
    assert json.loads(state.requests[11].body)["memoryInjectionEnabled"] is True
    assert state.requests[-1].method == "DELETE"


def test_agent_boundaries_reject_invalid_inputs_and_responses() -> None:
    error = {
        "error": {
            "code": "agent_version_not_found",
            "message": "Agent Version not found",
        }
    }
    with loopback(
        Response(body={**AGENT, "version": "wrong"}),
        Response(body=error, status=404, headers={"x-request-id": "req_version"}),
        Response(body={"error": "wrong"}, status=500),
        Response(body={"error": {"code": 1, "message": False}}, status=500),
        Response(body={"data": "wrong", "nextCursor": None}),
        Response(body={"data": [], "nextCursor": None}),
    ) as (base_url, state):
        client = BlazingAgents(api_key="ba_test", base_url=base_url)
        with pytest.raises(ValueError, match="At least one"):
            client.agents.update("ag_0123456789abcdef")
        with pytest.raises(ValueError, match="both be provided"):
            client.agents.create(name="Builder", model="openai/gpt-5")
        with pytest.raises(ValueError, match="requires model"):
            client.agents.update(
                "ag_0123456789abcdef",
                provider_id="prv_0123456789abcdef",
            )
        with pytest.raises(ValueError, match="both be null"):
            client.agents.update(
                "ag_0123456789abcdef",
                model="openai/gpt-5",
                provider_id=None,
            )
        with pytest.raises(ValidationError):
            client.agents.get("ag_0123456789abcdef")
        with pytest.raises(APIStatusError) as captured:
            client.agents.get_version("ag_0123456789abcdef", 99)
        for _ in range(2):
            with pytest.raises(APIStatusError) as malformed:
                client.agents.get("ag_0123456789abcdef")
            assert malformed.value.code == "invalid_response"
        client.close()

        assert captured.value.code == "agent_version_not_found"
        assert captured.value.request_id == "req_version"

        async def exercise() -> None:
            async_client = AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            )
            with pytest.raises(ValueError, match="At least one"):
                await async_client.agents.update("ag_0123456789abcdef")
            with pytest.raises(ValueError, match="At least one"):
                await async_client.agents.update_mcp_attachment(
                    "ag_0123456789abcdef",
                    "mcp_0123456789abcdef",
                )
            with pytest.raises(ValidationError):
                await async_client.agents.list_versions(
                    "ag_0123456789abcdef",
                )
            versions = async_client.agents.iter_versions(
                "ag_0123456789abcdef",
            )
            with pytest.raises(StopAsyncIteration):
                await anext(versions)
            await async_client.aclose()

        asyncio.run(exercise())

    assert len(state.requests) == 6


def test_agent_and_mcp_models_validate_documented_response_contracts() -> None:
    unconfigured_version = AgentVersion.model_validate_json(
        json.dumps({**AGENT_VERSION, "model": None, "providerId": None})
    )
    assert unconfigured_version.model is None
    for invalid_version in (
        {**AGENT_VERSION, "model": None},
        {**AGENT_VERSION, "providerId": None},
    ):
        with pytest.raises(ValidationError):
            AgentVersion.model_validate_json(json.dumps(invalid_version))

    invalid_agents = [
        {**AGENT, "id": "wrong"},
        {**AGENT, "tenantId": "wrong"},
        {**AGENT, "name": "   "},
        {**AGENT, "model": "missing-separator"},
        {**AGENT, "model": "openai/gpt-5"},
        {**AGENT, "providerId": "prv_0123456789abcdef"},
        {**AGENT, "providerId": "wrong"},
        {**AGENT, "workspaceId": "wrong"},
        {**AGENT, "workspaceId": None},
        {key: value for key, value in AGENT.items() if key != "workspaceId"},
        {**AGENT, "tools": ["write_todos", "write_todos"]},
        {**AGENT, "instructions": "x" * 3_001},
        {**AGENT, "mcpConnectionIds": ["wrong"]},
        {**AGENT, "avatarUrl": "not a URL"},
        {**AGENT, "createdAt": "2026-08-01T00:00:00"},
        {**AGENT, "status": ""},
    ]
    invalid_attachments = [
        {**MCP_ATTACHMENT, "mcpConnectionId": "wrong"},
        {**MCP_ATTACHMENT, "forwardedMetadataKeys": [""]},
        {
            **MCP_ATTACHMENT,
            "forwardedMetadataKeys": ["locale", "locale"],
        },
        {**MCP_ATTACHMENT, "updatedAt": "not-a-timestamp"},
    ]
    responses = [
        *(Response(body=value) for value in invalid_agents),
        *(Response(body={"mcpAttachments": [value]}) for value in invalid_attachments),
    ]
    with loopback(*responses) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            for _ in invalid_agents:
                with pytest.raises(ValidationError):
                    client.agents.get("ag_0123456789abcdef")
            for _ in invalid_attachments:
                with pytest.raises(ValidationError):
                    client.agents.list_mcp_attachments(
                        "ag_0123456789abcdef",
                    )

    assert len(state.requests) == len(responses)


def test_sync_workspaces_manage_lifecycle_pagination_and_agent_attachment() -> None:
    updated = {**WORKSPACE, "name": None, "futureField": "retained"}
    attached_agent = {**AGENT, "workspaceId": WORKSPACE["id"]}
    with loopback(
        Response(
            body={**WORKSPACE, "futureCreateField": {"opaque": True}},
            headers={"x-request-id": "req_workspace"},
        ),
        Response(body={"data": [WORKSPACE], "nextCursor": "next"}),
        Response(body={"data": [WORKSPACE], "nextCursor": "next"}),
        Response(body={"data": [updated], "nextCursor": None}),
        Response(body=WORKSPACE),
        Response(body=updated),
        Response(body=attached_agent),
        Response(body={"agents": [attached_agent]}),
        Response(body=AGENT),
        Response(status=202, raw_body=b""),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.workspaces.create(
                name="Build files",
                user_id="end-user",
                metadata={"OpaqueKey": {"nested_key": True}},
                network_policy={
                    "mode": "allowlist",
                    "allowed_hosts": ["registry.npmjs.org"],
                },
            )
            page = client.workspaces.list(
                cursor="opaque page",
                limit=1,
                user_id="end-user",
            )
            workspaces = client.workspaces.iter(limit=1, user_id="end-user")
            assert len(state.requests) == 2
            assert next(workspaces).id == WORKSPACE["id"]
            assert len(state.requests) == 3
            assert next(workspaces).name is None
            with pytest.raises(StopIteration):
                next(workspaces)
            fetched = client.workspaces.get(workspace_id="ws_0123456789abcdef")
            renamed = client.workspaces.update(
                workspace_id="ws_0123456789abcdef",
                name=None,
                metadata={"OpaqueKey": {"nested_key": False}},
                network_policy={"mode": "offline"},
            )
            attached = client.agents.update(
                "ag_0123456789abcdef",
                workspace_id="ws_0123456789abcdef",
            )
            listed_agents = client.agents.list(
                workspace_id="ws_0123456789abcdef",
            )
            reassigned = client.agents.update(
                "ag_0123456789abcdef",
                workspace_id=cast(str, AGENT["workspaceId"]),
            )
            pending = client.workspaces.delete(workspace_id="ws_0123456789abcdef")
            completed = client.workspaces.delete(workspace_id="ws_0123456789abcdef")

    assert created._request_id == "req_workspace"
    assert created.model_extra == {"futureCreateField": {"opaque": True}}
    assert page.next_cursor == "next"
    assert fetched.name == "Build files"
    assert renamed.name is None
    assert renamed.model_extra == {"futureField": "retained"}
    assert attached.workspace_id == WORKSPACE["id"]
    assert listed_agents.agents[0].workspace_id == WORKSPACE["id"]
    assert reassigned.workspace_id == AGENT["workspaceId"]
    assert pending == "pending"
    assert completed == "completed"
    assert json.loads(state.requests[0].body) == {
        "name": "Build files",
        "userId": "end-user",
        "metadata": {"OpaqueKey": {"nested_key": True}},
        "networkPolicy": {
            "mode": "allowlist",
            "allowedHosts": ["registry.npmjs.org"],
        },
    }
    list_target = urlsplit(state.requests[1].target)
    assert list_target.path == "/v1/workspaces"
    assert parse_qs(list_target.query) == {
        "cursor": ["opaque page"],
        "limit": ["1"],
        "userId": ["end-user"],
    }
    assert state.requests[3].target.endswith(
        "/v1/workspaces?cursor=next&limit=1&userId=end-user"
    )
    assert json.loads(state.requests[5].body) == {
        "name": None,
        "metadata": {"OpaqueKey": {"nested_key": False}},
        "networkPolicy": {"mode": "offline"},
    }
    assert state.requests[7].target.endswith(
        "/v1/agents?workspaceId=ws_0123456789abcdef"
    )
    assert json.loads(state.requests[8].body) == {"workspaceId": AGENT["workspaceId"]}
    assert [request.method for request in state.requests[-2:]] == [
        "DELETE",
        "DELETE",
    ]


def test_async_workspaces_match_every_sync_operation() -> None:
    updated = {**WORKSPACE, "name": "Async files"}
    with loopback(
        Response(body=WORKSPACE),
        Response(body={"data": [WORKSPACE], "nextCursor": "next"}),
        Response(body={"data": [WORKSPACE], "nextCursor": None}),
        Response(body=WORKSPACE),
        Response(body=updated),
        Response(status=202, raw_body=b""),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                created = await client.workspaces.create()
                workspaces = client.workspaces.iter(
                    cursor="first",
                    limit=1,
                    user_id="end-user",
                )
                assert len(state.requests) == 1
                first = await anext(workspaces)
                second = await anext(workspaces)
                with pytest.raises(StopAsyncIteration):
                    await anext(workspaces)
                fetched = await client.workspaces.get(
                    workspace_id="ws_0123456789abcdef"
                )
                renamed = await client.workspaces.update(
                    workspace_id="ws_0123456789abcdef",
                    name="Async files",
                )
                pending = await client.workspaces.delete(
                    workspace_id="ws_0123456789abcdef"
                )
                completed = await client.workspaces.delete(
                    workspace_id="ws_0123456789abcdef"
                )
            assert created.id == WORKSPACE["id"]
            assert first.user_id == "end-user"
            assert second.id == WORKSPACE["id"]
            assert fetched.metadata == {"OpaqueKey": {"nested_key": True}}
            assert renamed.name == "Async files"
            assert pending == "pending"
            assert completed == "completed"

        asyncio.run(exercise())

    assert json.loads(state.requests[0].body) == {}
    assert state.requests[1].target.endswith(
        "/v1/workspaces?cursor=first&limit=1&userId=end-user"
    )
    assert state.requests[2].target.endswith(
        "/v1/workspaces?cursor=next&limit=1&userId=end-user"
    )


def test_workspace_boundaries_reject_invalid_inputs_and_responses() -> None:
    invalid_workspaces: list[dict[str, Any]] = [
        {**WORKSPACE, "id": "wrong"},
        {**WORKSPACE, "tenantId": "wrong"},
        {**WORKSPACE, "name": " "},
        {**WORKSPACE, "userId": 1},
        {**WORKSPACE, "metadata": []},
        {**WORKSPACE, "createdAt": "2026-08-01T00:00:00"},
    ]
    error = {
        "error": {
            "code": "workspace_not_found",
            "message": "Workspace not found",
        }
    }
    responses = [
        *(Response(body=value) for value in invalid_workspaces),
        Response(body={"data": "wrong", "nextCursor": None}),
        Response(body=error, status=404, headers={"x-request-id": "req_workspace"}),
        Response(body={"data": [], "nextCursor": None}),
    ]
    with loopback(*responses) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(ValueError, match="At least one"):
                client.workspaces.update(workspace_id="ws_0123456789abcdef")
            with pytest.raises(TypeError):
                client.workspaces.create(unknown=True)  # type: ignore[call-arg]
            with pytest.raises(TypeError):
                cast(Any, client.workspaces.get)("ws_0123456789abcdef")
            for _ in invalid_workspaces:
                with pytest.raises(ValidationError):
                    client.workspaces.get(workspace_id="ws_0123456789abcdef")
            with pytest.raises(ValidationError):
                client.workspaces.list()
            with pytest.raises(APIStatusError) as captured:
                client.workspaces.get(workspace_id="ws_0123456789abcdef")

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(ValueError, match="At least one"):
                    await client.workspaces.update(workspace_id="ws_0123456789abcdef")
                workspaces = client.workspaces.iter()
                with pytest.raises(StopAsyncIteration):
                    await anext(workspaces)

        asyncio.run(exercise())

    assert captured.value.code == "workspace_not_found"
    assert captured.value.request_id == "req_workspace"
    assert len(state.requests) == len(responses)


def test_sync_providers_cover_crud_and_safe_forward_compatibility(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "secret-canary.provider"
    future = {
        **PROVIDER,
        "futureField": {"OpaqueKey": True},
    }
    unicode_credential_field = (
        json.dumps(PROVIDER)[:-1] + ',"api\\u004bey":"server-secret"}'
    ).encode()
    with loopback(
        Response(body=future, headers={"x-request-id": "req_provider"}),
        Response(body={"providers": [future]}),
        Response(body=future),
        Response(body=future),
        Response(status=204, raw_body=b""),
        Response(raw_body=unicode_credential_field),
        Response(raw_body=b"not-json"),
        Response(
            status=400,
            raw_body=(
                b'{"error":{"code":"invalid_request","message":"Rejected '
                b'secret\\u002dcanary.provider","details":{"leaks":['
                b'"secret\\u002dcanary.provider"]}}}'
            ),
            headers={
                "x-request-id": "req_provider_status",
                "x-echo-secret": secret,
            },
        ),
        Response(status=400, raw_body=b"not-json"),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with caplog.at_level(logging.DEBUG, logger="blazing_agents"):
                created = client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key=secret,
                    base_url=None,
                )
            listed = client.providers.list()
            fetched = client.providers.get("provider/with space")
            updated = client.providers.update(PROVIDER["id"], name="Renamed")
            client.providers.delete(PROVIDER["id"])
            with pytest.raises(BlazingAgentsError, match="credential material"):
                client.providers.get(PROVIDER["id"])
            with pytest.raises(BlazingAgentsError, match="invalid credential-safe"):
                client.providers.get(PROVIDER["id"])
            with pytest.raises(APIStatusError) as captured:
                client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key=secret,
                )
            with pytest.raises(APIStatusError) as malformed_error:
                client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key=secret,
                )

    assert isinstance(created, Provider)
    assert created.provider_type == "future-provider"
    assert created.model_extra == {"futureField": {"OpaqueKey": True}}
    assert created._request_id == "req_provider"
    assert secret not in created.model_dump_json()
    assert listed.providers[0].model_extra == {"futureField": {"OpaqueKey": True}}
    assert fetched.id == PROVIDER["id"]
    assert updated.base_url is None
    assert secret not in str(captured.value)
    assert secret not in captured.value.response_body
    assert captured.value.headers["x-request-id"] == "req_provider_status"
    assert captured.value.headers["x-echo-secret"] == "[REDACTED]"
    assert "[REDACTED]" in captured.value.response_body
    assert captured.value.details == {"leaks": ["[REDACTED]"]}
    assert malformed_error.value.response_body == "[REDACTED]"

    assert [request.method for request in state.requests] == [
        "POST",
        "GET",
        "GET",
        "PATCH",
        "DELETE",
        "GET",
        "GET",
        "POST",
        "POST",
    ]
    assert state.requests[0].target == "/v1/providers"
    assert json.loads(state.requests[0].body) == {
        "name": "OpenAI",
        "providerType": "openai",
        "apiKey": secret,
        "baseUrl": None,
    }
    assert state.requests[2].target == "/v1/providers/provider%2Fwith%20space"
    assert json.loads(state.requests[3].body) == {"name": "Renamed"}
    assert all(secret not in record.getMessage() for record in caplog.records)


def test_provider_model_discovery_has_sync_and_async_resource_parity() -> None:
    response = {"models": [{"id": "a-model"}, {"id": "z-model"}]}
    responses = (Response(body=response), Response(body=response))
    with loopback(*responses) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            sync_models = client.providers.list_models("provider/with space")

        async def exercise() -> ProviderModels:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                return await client.providers.list_models("provider/with space")

        async_models = asyncio.run(exercise())

    assert [model.id for model in sync_models.models] == ["a-model", "z-model"]
    assert [model.id for model in async_models.models] == ["a-model", "z-model"]
    assert [request.target for request in state.requests] == [
        "/v1/providers/provider%2Fwith%20space/models",
        "/v1/providers/provider%2Fwith%20space/models",
    ]


def test_gateway_provider_type_has_sync_request_parity() -> None:
    gateway = {
        **PROVIDER,
        "name": "Gateway",
        "providerType": "vercel_ai_gateway",
    }
    with loopback(Response(body=gateway)) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            provider = client.providers.create(
                name="Gateway",
                provider_type="vercel_ai_gateway",
                api_key="vck_test",
            )

    assert provider.provider_type == "vercel_ai_gateway"
    assert json.loads(state.requests[0].body) == {
        "name": "Gateway",
        "providerType": "vercel_ai_gateway",
        "apiKey": "vck_test",
    }


def test_provider_endpoint_rules_are_validated_before_transport() -> None:
    with BlazingAgents(api_key="ba_test", base_url="https://example.test") as client:
        with pytest.raises(ValueError, match="required for custom"):
            client.providers.create(
                name="Custom",
                provider_type="custom",
                api_key="custom-key",
            )
        with pytest.raises(ValueError, match="not accepted for Vercel"):
            client.providers.create(
                name="Gateway",
                provider_type="vercel_ai_gateway",
                api_key="vck_test",
                base_url="https://example.test/v1",
            )


def test_async_providers_match_sync_and_reject_unsafe_or_invalid_shapes() -> None:
    responses = (
        Response(body=PROVIDER),
        Response(body={"providers": [PROVIDER]}),
        Response(body=PROVIDER),
        Response(body=PROVIDER),
        Response(status=204, raw_body=b""),
        Response(body={**PROVIDER, "id": "wrong"}),
    )
    with loopback(*responses) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.providers.create(
                    name="Anthropic",
                    provider_type="anthropic",
                    api_key="secret-async",
                )
                await client.providers.list()
                await client.providers.get(PROVIDER["id"])
                await client.providers.update(PROVIDER["id"], name="Renamed")
                await client.providers.delete(
                    PROVIDER["id"], confirm_version_invalidation=True
                )
                with pytest.raises(ValidationError):
                    await client.providers.get(PROVIDER["id"])

        asyncio.run(exercise())

    assert len(state.requests) == 6
    assert state.requests[4].target == (
        f"/v1/providers/{PROVIDER['id']}?confirmVersionInvalidation=true"
    )
    client = BlazingAgents(api_key="ba_test", base_url="http://127.0.0.1:1")
    with pytest.raises(ValueError, match="provider_type"):
        client.providers.create(
            name="Invalid",
            provider_type=cast(Any, "bedrock"),
            api_key="secret-not-in-error",
        )
    with pytest.raises(ValueError, match="At least one"):
        client.providers.update(PROVIDER["id"])
    client.close()


@pytest.mark.parametrize(
    ("auth_type", "credentials", "expected"),
    [
        ("none", {}, {}),
        (
            "bearer",
            {"bearer_token": "secret-canary.bearer"},
            {"bearerToken": "secret-canary.bearer"},
        ),
        (
            "oauth_authorization_code",
            {
                "client_id": "client-id",
                "client_secret": "secret-canary.authorization",
                "scope": "tools:call",
            },
            {
                "clientId": "client-id",
                "clientSecret": "secret-canary.authorization",
                "scope": "tools:call",
            },
        ),
        (
            "oauth_client_credentials",
            {
                "client_id": "client-id",
                "client_secret": "secret-canary.client",
                "scope": "tools:call",
            },
            {
                "clientId": "client-id",
                "clientSecret": "secret-canary.client",
                "scope": "tools:call",
            },
        ),
    ],
)
def test_sync_mcp_connection_creation_and_reconnection_auth_shapes(
    auth_type: Any,
    credentials: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    response = {
        **MCP_CONNECTION,
        "authType": auth_type,
        "futureField": {"OpaqueKey": True},
    }
    with loopback(
        Response(body=response),
        Response(body={"status": "future-reconnect", "connection": response}),
        Response(body=response),
        Response(body={"status": "future-reconnect", "connection": response}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.mcp_connections.create(
                name="Tools",
                url="https://mcp.example.com/",
                auth_type=auth_type,
                **credentials,
            )
            reconnected = client.mcp_connections.reconnect(
                MCP_CONNECTION["id"],
                url="https://mcp.example.com/",
                auth_type=auth_type,
                **credentials,
            )

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.mcp_connections.create(
                    name="Tools",
                    url="https://mcp.example.com/",
                    auth_type=auth_type,
                    **credentials,
                )
                await client.mcp_connections.reconnect(
                    MCP_CONNECTION["id"],
                    url="https://mcp.example.com/",
                    auth_type=auth_type,
                    **credentials,
                )

        asyncio.run(exercise())

    assert isinstance(created, McpConnection)
    assert created.auth_type == auth_type
    assert created.model_extra == {"futureField": {"OpaqueKey": True}}
    assert isinstance(reconnected, McpConnectionReconnectResult)
    assert reconnected.status == "future-reconnect"
    assert created.model_dump().keys().isdisjoint({"bearerToken", "clientSecret"})
    assert (
        reconnected.connection.model_dump()
        .keys()
        .isdisjoint({"bearerToken", "clientSecret"})
    )
    assert json.loads(state.requests[0].body) == {
        "name": "Tools",
        "url": "https://mcp.example.com/",
        "authType": auth_type,
        **expected,
    }
    assert json.loads(state.requests[1].body) == {
        "url": "https://mcp.example.com/",
        "authType": auth_type,
        **expected,
    }
    assert json.loads(state.requests[2].body) == json.loads(state.requests[0].body)
    assert json.loads(state.requests[3].body) == json.loads(state.requests[1].body)


def test_sync_mcp_connections_cover_lifecycle_tests_and_oauth_initiation() -> None:
    setup = "A" * 43
    future = {**MCP_CONNECTION, "futureField": "retained"}
    succeeded = {
        "ok": True,
        "latencyMs": 42,
        "server": {"name": "fixture", "version": "1.0.0", "future": True},
        "toolCount": 1,
        "toolNames": ["search"],
        "futureTestField": True,
    }
    failed = {
        "ok": False,
        "error": {
            "code": "FUTURE_MCP_ERROR",
            "message": "Connection failed",
            "future": True,
        },
    }
    with loopback(
        Response(
            body={
                "authorizationUrl": (
                    f"https://app.example.com/app/mcp-connections?mcpOAuthSetup={setup}"
                ),
                "futureField": True,
            }
        ),
        Response(body={"mcpConnections": [future]}),
        Response(body=future),
        Response(body=future),
        Response(body=succeeded),
        Response(body=failed),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="jwt_test", base_url=base_url) as client:
            initiation = client.mcp_connections.connect(MCP_CONNECTION["id"])
            listed = client.mcp_connections.list()
            fetched = client.mcp_connections.get("mcp/with space")
            updated = client.mcp_connections.update(
                MCP_CONNECTION["id"],
                name="Renamed",
            )
            tested = client.mcp_connections.test(MCP_CONNECTION["id"])
            failed_test = client.mcp_connections.test(MCP_CONNECTION["id"])
            client.mcp_connections.delete(MCP_CONNECTION["id"])

    assert str(initiation.authorization_url).endswith(f"mcpOAuthSetup={setup}")
    assert initiation.model_extra == {"futureField": True}
    assert listed.mcp_connections[0].model_extra == {"futureField": "retained"}
    assert fetched.status == "future-status"
    assert updated.name == "Tools"
    assert isinstance(tested, McpConnectionTestResult)
    assert tested.ok is True
    assert tested.server is not None
    assert tested.server.model_extra == {"future": True}
    assert tested.tool_names == ["search"]
    assert tested.model_extra == {"futureTestField": True}
    assert failed_test.error is not None
    assert failed_test.error.code == "FUTURE_MCP_ERROR"
    assert failed_test.error.model_extra == {"future": True}
    assert state.requests[0].target.endswith("/connect")
    assert state.requests[2].target == "/v1/mcp-connections/mcp%2Fwith%20space"
    assert json.loads(state.requests[3].body) == {"name": "Renamed"}


def test_async_mcp_connections_match_sync_and_validate_boundaries() -> None:
    setup = "A" * 43
    responses = (
        Response(body=MCP_CONNECTION),
        Response(body={"mcpConnections": [MCP_CONNECTION]}),
        Response(body=MCP_CONNECTION),
        Response(body=MCP_CONNECTION),
        Response(
            body={
                "ok": True,
                "latencyMs": 1,
                "server": {"name": "fixture", "version": "1"},
                "toolCount": 0,
                "toolNames": [],
            }
        ),
        Response(
            body={"status": "connected", "connection": MCP_CONNECTION},
        ),
        Response(
            body={
                "authorizationUrl": (
                    f"https://app.example.com/app/mcp-connections?mcpOAuthSetup={setup}"
                )
            }
        ),
        Response(status=204, raw_body=b""),
        Response(body={**MCP_CONNECTION, "createdAt": "wrong"}),
        Response(body={"ok": True, "latencyMs": 1}),
    )
    with loopback(*responses) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.mcp_connections.create(
                    name="Tools",
                    url="https://mcp.example.com/",
                    auth_type="none",
                )
                await client.mcp_connections.list()
                await client.mcp_connections.get(MCP_CONNECTION["id"])
                await client.mcp_connections.update(
                    MCP_CONNECTION["id"],
                    name="Renamed",
                )
                await client.mcp_connections.test(MCP_CONNECTION["id"])
                await client.mcp_connections.reconnect(
                    MCP_CONNECTION["id"],
                    url="https://mcp.example.com/",
                    auth_type="none",
                )
                await client.mcp_connections.connect(MCP_CONNECTION["id"])
                await client.mcp_connections.delete(MCP_CONNECTION["id"])
                with pytest.raises(ValueError, match="At least one"):
                    await client.mcp_connections.update(MCP_CONNECTION["id"])
                with pytest.raises(ValidationError):
                    await client.mcp_connections.get(MCP_CONNECTION["id"])
                with pytest.raises(ValidationError):
                    await client.mcp_connections.test(MCP_CONNECTION["id"])

        asyncio.run(exercise())

    assert len(state.requests) == 10
    client = BlazingAgents(api_key="ba_test", base_url="http://127.0.0.1:1")
    with pytest.raises(ValueError, match="auth_type"):
        client.mcp_connections.create(
            name="Tools",
            url="https://mcp.example.com/",
            auth_type=cast(Any, "future"),
        )
    with pytest.raises(ValueError, match="exact"):
        client.mcp_connections.create(
            name="Tools",
            url="https://mcp.example.com/",
            auth_type="none",
            bearer_token="secret-not-in-error",
        )
    with pytest.raises(ValueError, match="exact"):
        client.mcp_connections.create(
            name="Tools",
            url="https://mcp.example.com/",
            auth_type="bearer",
        )
    with pytest.raises(ValueError, match="does not accept"):
        client.mcp_connections.create(
            name="Tools",
            url="https://mcp.example.com/",
            auth_type="oauth_authorization_code",
            bearer_token="secret-not-in-error",
        )
    with pytest.raises(ValueError, match="requires exactly"):
        client.mcp_connections.create(
            name="Tools",
            url="https://mcp.example.com/",
            auth_type="oauth_client_credentials",
        )
    with pytest.raises(ValueError, match="together"):
        client.mcp_connections.reconnect(
            MCP_CONNECTION["id"],
            url="https://mcp.example.com/",
            auth_type="oauth_authorization_code",
            client_id="client-id",
        )
    with pytest.raises(ValueError, match="At least one"):
        client.mcp_connections.update(MCP_CONNECTION["id"])
    client.close()


def test_mcp_authorization_code_without_client_credentials_preserves_wire_shape() -> (
    None
):
    response = {**MCP_CONNECTION, "authType": "oauth_authorization_code"}
    with loopback(
        Response(body=response),
        Response(body={"status": "needs_auth", "connection": response}),
        Response(body=response),
        Response(body={"status": "needs_auth", "connection": response}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            client.mcp_connections.create(
                name="Tools",
                url="https://mcp.example.com/",
                auth_type="oauth_authorization_code",
            )
            client.mcp_connections.reconnect(
                MCP_CONNECTION["id"],
                url="https://mcp.example.com/",
                auth_type="oauth_authorization_code",
            )

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.mcp_connections.create(
                    name="Tools",
                    url="https://mcp.example.com/",
                    auth_type="oauth_authorization_code",
                )
                await client.mcp_connections.reconnect(
                    MCP_CONNECTION["id"],
                    url="https://mcp.example.com/",
                    auth_type="oauth_authorization_code",
                )

        asyncio.run(exercise())

    assert [json.loads(request.body) for request in state.requests] == [
        {
            "name": "Tools",
            "url": "https://mcp.example.com/",
            "authType": "oauth_authorization_code",
        },
        {
            "url": "https://mcp.example.com/",
            "authType": "oauth_authorization_code",
        },
    ] * 2


def test_mcp_authorization_code_initiation_rejects_malformed_urls_in_both_clients() -> (
    None
):
    setup = "A" * 43
    invalid_urls = (
        f"https://auth.example.com/authorize?mcpOAuthSetup={setup}",
        f"https://app.example.com/app/mcp-connections?wrong={setup}",
        f"https://app.example.com/app/mcp-connections?mcpOAuthSetup={'A' * 42}",
        f"https://app.example.com/app/mcp-connections?mcpOAuthSetup={setup}&extra=1",
        f"https://app.example.com/app/mcp-connections?mcpOAuthSetup={setup}&clientSecret=secret-canary",
        f"https://user:secret@app.example.com/app/mcp-connections?mcpOAuthSetup={setup}",
        f"https://app.example.com/app/mcp-connections?mcpOAuthSetup={setup}#secret",
    )
    responses = tuple(
        Response(body={"authorizationUrl": url})
        for url in (*invalid_urls, *invalid_urls)
    )
    with loopback(*responses) as (base_url, _state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            for url in invalid_urls:
                with pytest.raises(ValidationError) as error:
                    client.mcp_connections.connect(MCP_CONNECTION["id"])
                if "secret-canary" in url:
                    assert "secret-canary" not in repr(error.value)
                    assert "secret-canary" not in repr(error.value.errors())
                    assert error.value.__cause__ is None
                    assert error.value.__context__ is None

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                for url in invalid_urls:
                    with pytest.raises(ValidationError) as error:
                        await client.mcp_connections.connect(MCP_CONNECTION["id"])
                    if "secret-canary" in url:
                        assert "secret-canary" not in repr(error.value)
                        assert "secret-canary" not in repr(error.value.errors())
                        assert error.value.__cause__ is None
                        assert error.value.__context__ is None

        asyncio.run(exercise())


def test_async_mcp_test_results_preserve_logical_errors_and_future_fields() -> None:
    succeeded = {
        "ok": True,
        "latencyMs": 42,
        "server": {"name": "fixture", "version": "1.0", "future": True},
        "toolCount": 1,
        "toolNames": ["search"],
        "futureTestField": {"opaque": True},
    }
    failed = {
        "ok": False,
        "error": {
            "code": "MCP_CONNECTION_INVALID",
            "message": "Remote server rejected the connection",
            "futureErrorField": ["retained"],
        },
        "futureResultField": True,
    }
    with loopback(Response(body=succeeded), Response(body=failed)) as (
        base_url,
        _state,
    ):

        async def exercise() -> tuple[McpConnectionTestResult, McpConnectionTestResult]:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                success = await client.mcp_connections.test(MCP_CONNECTION["id"])
                failure = await client.mcp_connections.test(MCP_CONNECTION["id"])
            return success, failure

        success, failure = asyncio.run(exercise())

    assert success.model_extra == {"futureTestField": {"opaque": True}}
    assert success.server is not None
    assert success.server.model_extra == {"future": True}
    assert failure.model_extra == {"futureResultField": True}
    assert failure.error is not None
    assert failure.error.code == "MCP_CONNECTION_INVALID"
    assert failure.error.model_extra == {"futureErrorField": ["retained"]}


def test_async_provider_http_errors_redact_credentials_and_keep_future_fields() -> None:
    secret = "secret-async-provider"
    future = {**PROVIDER, "futureField": {"opaque": True}}
    error = {
        "error": {
            "code": "provider_rejected",
            "message": f"Rejected {secret}",
            "details": {"echo": secret},
        }
    }
    with loopback(
        Response(body=future),
        Response(
            status=400,
            body=error,
            headers={
                "x-request-id": "req_async_provider",
                "x-echo-secret": secret,
            },
        ),
        Response(status=502, raw_body=b"not-json"),
    ) as (base_url, _state):

        async def exercise() -> tuple[
            APIStatusError,
            APIStatusError,
            Provider,
        ]:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                created = await client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key=secret,
                )
                with pytest.raises(APIStatusError) as status:
                    await client.providers.create(
                        name="OpenAI",
                        provider_type="openai",
                        api_key=secret,
                    )
                with pytest.raises(APIStatusError) as malformed:
                    await client.providers.create(
                        name="OpenAI",
                        provider_type="openai",
                        api_key=secret,
                    )
            return status.value, malformed.value, created

        status, malformed, created = asyncio.run(exercise())

    assert created.model_extra == {"futureField": {"opaque": True}}
    assert status.code == "provider_rejected"
    assert status.details == {"echo": "[REDACTED]"}
    assert secret not in str(status)
    assert secret not in status.response_body
    assert status.headers["x-request-id"] == "req_async_provider"
    assert status.headers["x-echo-secret"] == "[REDACTED]"
    assert malformed.response_body == "[REDACTED]"


def test_short_provider_credentials_redact_only_exact_values_sync_and_async() -> None:
    error = {
        "error": {
            "code": "provider_rejected",
            "message": "monkey failure",
            "details": {
                "echo": "key",
                "safe": "monkey-request",
            },
            "param": "monkey-request",
        }
    }
    headers = {
        "x-request-id": "req_short_provider",
        "x-echo-secret": "key",
        "x-safe-value": "monkey-request",
    }
    with loopback(
        Response(status=400, body=error, headers=headers),
        Response(status=400, body=error, headers=headers),
    ) as (base_url, _state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(APIStatusError) as sync_error:
                client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key="key",
                )

        async def exercise() -> APIStatusError:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(APIStatusError) as async_error:
                    await client.providers.create(
                        name="OpenAI",
                        provider_type="openai",
                        api_key="key",
                    )
            return async_error.value

        async_error = asyncio.run(exercise())

    expected_details = {"echo": "[REDACTED]", "safe": "monkey-request"}
    for exception in (sync_error.value, async_error):
        assert str(exception) == "monkey failure"
        assert exception.request_id == "req_short_provider"
        assert exception.headers["x-echo-secret"] == "[REDACTED]"
        assert exception.headers["x-safe-value"] == "monkey-request"
        assert exception.details == expected_details
        assert exception.param == "monkey-request"
        assert json.loads(exception.response_body) == {
            "error": {
                "code": "provider_rejected",
                "message": "monkey failure",
                "details": expected_details,
                "param": "monkey-request",
            }
        }


def test_provider_and_mcp_response_substrings_are_safe_in_sync_and_async_clients() -> (
    None
):
    provider_secret = "provider-substring-secret"
    mcp_secret = "mcp-substring-secret"
    provider_leak = {
        **PROVIDER,
        "baseUrl": f"https://provider.example/{provider_secret}",
    }
    mcp_leak = {
        **MCP_CONNECTION,
        "url": f"https://mcp.example/{mcp_secret}",
    }
    provider_short = {
        **PROVIDER,
        "baseUrl": "https://provider.example/key",
    }
    mcp_short = {
        **MCP_CONNECTION,
        "url": "https://mcp.example/key",
    }
    responses = (
        Response(body=provider_leak),
        Response(body=mcp_leak),
        Response(body=provider_short),
        Response(body=mcp_short),
        Response(body=provider_leak),
        Response(body=mcp_leak),
        Response(body=provider_short),
        Response(body=mcp_short),
    )
    with loopback(*responses) as (base_url, _state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(BlazingAgentsError, match="credential material"):
                client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key=provider_secret,
                )
            with pytest.raises(BlazingAgentsError, match="credential material"):
                client.mcp_connections.create(
                    name="Tools",
                    url="https://mcp.example.com/",
                    auth_type="bearer",
                    bearer_token=mcp_secret,
                )
            provider = client.providers.create(
                name="OpenAI",
                provider_type="openai",
                api_key="key",
            )
            mcp = client.mcp_connections.create(
                name="Tools",
                url="https://mcp.example.com/",
                auth_type="bearer",
                bearer_token="key",
            )

        async def exercise() -> tuple[Provider, McpConnection]:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(BlazingAgentsError, match="credential material"):
                    await client.providers.create(
                        name="OpenAI",
                        provider_type="openai",
                        api_key=provider_secret,
                    )
                with pytest.raises(BlazingAgentsError, match="credential material"):
                    await client.mcp_connections.create(
                        name="Tools",
                        url="https://mcp.example.com/",
                        auth_type="bearer",
                        bearer_token=mcp_secret,
                    )
                provider = await client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key="key",
                )
                mcp = await client.mcp_connections.create(
                    name="Tools",
                    url="https://mcp.example.com/",
                    auth_type="bearer",
                    bearer_token="key",
                )
            return provider, mcp

        async_provider, async_mcp = asyncio.run(exercise())

    assert provider.base_url == provider_short["baseUrl"]
    assert str(mcp.url) == mcp_short["url"]
    assert async_provider.base_url == provider_short["baseUrl"]
    assert str(async_mcp.url) == mcp_short["url"]


def test_provider_and_mcp_transport_errors_never_retain_credential_requests() -> None:
    api_secret = "ba-api-secret"
    provider_secret = "provider-secret"
    mcp_secret = "mcp-secret"
    sync_error_types = deque((httpx.ConnectError, httpx.ConnectTimeout))

    def fail_sync(request: httpx.Request) -> httpx.Response:
        error_type = sync_error_types.popleft()
        raise error_type("transport failed", request=request)

    sync_http = httpx.Client(transport=httpx.MockTransport(fail_sync))
    with BlazingAgents(api_key=api_secret, http_client=sync_http) as client:
        with pytest.raises(APIConnectionError) as provider_error:
            client.providers.create(
                name="OpenAI",
                provider_type="openai",
                api_key=provider_secret,
            )
        with pytest.raises(APITimeoutError) as mcp_error:
            client.mcp_connections.create(
                name="Tools",
                url="https://mcp.example.com/",
                auth_type="bearer",
                bearer_token=mcp_secret,
            )
    sync_http.close()

    async_error_types = deque((httpx.ConnectError, httpx.ConnectTimeout))

    def fail_async(request: httpx.Request) -> httpx.Response:
        error_type = async_error_types.popleft()
        raise error_type("transport failed", request=request)

    async def exercise() -> tuple[APIConnectionError, APITimeoutError]:
        async_http = httpx.AsyncClient(transport=httpx.MockTransport(fail_async))
        async with AsyncBlazingAgents(
            api_key=api_secret,
            http_client=async_http,
        ) as client:
            with pytest.raises(APIConnectionError) as provider:
                await client.providers.create(
                    name="OpenAI",
                    provider_type="openai",
                    api_key=provider_secret,
                )
            with pytest.raises(APITimeoutError) as mcp:
                await client.mcp_connections.create(
                    name="Tools",
                    url="https://mcp.example.com/",
                    auth_type="bearer",
                    bearer_token=mcp_secret,
                )
        return provider.value, mcp.value

    async_provider_error, async_mcp_error = asyncio.run(exercise())

    for error, secret in (
        (provider_error.value, provider_secret),
        (mcp_error.value, mcp_secret),
        (async_provider_error, provider_secret),
        (async_mcp_error, mcp_secret),
    ):
        assert error.__cause__ is None
        assert error.__context__ is None
        assert secret not in str(error)
        assert secret not in repr(error.__dict__)
        assert api_secret not in repr(error.__dict__)


def test_sync_prompts_manage_lifecycle_attribution_and_opaque_metadata() -> None:
    future_prompt = {**PROMPT, "futureField": {"opaque_key": True}}
    with loopback(
        Response(
            body=future_prompt,
            headers={"x-request-id": "req_prompt"},
        ),
        Response(body={"prompts": [PROMPT]}),
        Response(body=PROMPT),
        Response(body={**PROMPT, "name": "Renamed"}),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.prompts.create(
                name="Greeting",
                template="Hello {{name}}",
                user_id="",
                metadata={"OpaqueKey": {"nested_key": None}},
            )
            listed = client.prompts.list(user_id="")
            fetched = client.prompts.get(prompt_id="prompt/with space")
            updated = client.prompts.update(
                prompt_id=PROMPT["id"],
                name="Renamed",
                metadata={"OpaqueKey": {"explicit_null": None}},
            )
            client.prompts.delete(prompt_id=PROMPT["id"])

    assert created.variables == ["name"]
    assert created._request_id == "req_prompt"
    assert created.model_extra == {"futureField": {"opaque_key": True}}
    assert listed.prompts[0].user_id == ""
    assert fetched.id == PROMPT["id"]
    assert updated.name == "Renamed"
    assert json.loads(state.requests[0].body) == {
        "name": "Greeting",
        "template": "Hello {{name}}",
        "userId": "",
        "metadata": {"OpaqueKey": {"nested_key": None}},
    }
    assert state.requests[1].target == "/v1/prompts?userId="
    assert state.requests[2].target == "/v1/prompts/prompt%2Fwith%20space"
    assert json.loads(state.requests[3].body) == {
        "name": "Renamed",
        "metadata": {"OpaqueKey": {"explicit_null": None}},
    }
    assert state.requests[4].method == "DELETE"


def test_async_prompts_match_every_sync_operation_and_omission() -> None:
    with loopback(
        Response(body=PROMPT),
        Response(body={"prompts": [PROMPT]}),
        Response(body=PROMPT),
        Response(body={**PROMPT, "template": "Welcome {{name}}"}),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.prompts.create(
                    name="Greeting",
                    template="Hello {{name}}",
                )
                await client.prompts.list()
                await client.prompts.get(prompt_id=PROMPT["id"])
                updated = await client.prompts.update(
                    prompt_id=PROMPT["id"],
                    template="Welcome {{name}}",
                )
                assert updated.template == "Welcome {{name}}"
                await client.prompts.delete(prompt_id=PROMPT["id"])
                with pytest.raises(ValueError, match="At least one"):
                    await client.prompts.update(prompt_id=PROMPT["id"])

        asyncio.run(exercise())

    assert json.loads(state.requests[0].body) == {
        "name": "Greeting",
        "template": "Hello {{name}}",
    }
    assert state.requests[1].target == "/v1/prompts"
    assert state.requests[-1].method == "DELETE"


def test_sync_memories_manage_lifecycle_query_and_lazy_pages() -> None:
    future_memory = {**MEMORY, "futureField": {"opaque_key": True}}
    with loopback(
        Response(
            body={"memory": future_memory, "futureEnvelopeField": True},
            headers={"x-request-id": "req_memory"},
        ),
        Response(body={"data": [MEMORY], "nextCursor": "next"}),
        Response(body={"data": [MEMORY], "nextCursor": "after"}),
        Response(
            body={
                "data": [{**MEMORY, "userId": "end-user"}],
                "nextCursor": None,
            }
        ),
        Response(body={"memory": MEMORY}),
        Response(body={"memory": {**MEMORY, "text": "Prefers light mode"}}),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.memories.create(
                agent_id=MEMORY["agentId"],
                text="Prefers dark mode",
                user_id="",
            )
            page = client.memories.list(
                agent_id=MEMORY["agentId"],
                user_id="",
                search="dark mode",
                cursor="opaque cursor",
                limit=1,
            )
            memories = client.memories.iter(
                agent_id=MEMORY["agentId"],
                limit=1,
            )
            assert len(state.requests) == 2
            assert next(memories).user_id == ""
            assert len(state.requests) == 3
            assert next(memories).user_id == "end-user"
            with pytest.raises(StopIteration):
                next(memories)
            fetched = client.memories.get(
                agent_id="agent/with space",
                memory_id="memory/with space",
            )
            updated = client.memories.update(
                agent_id=MEMORY["agentId"],
                memory_id=MEMORY["id"],
                text="Prefers light mode",
            )
            client.memories.delete(
                agent_id=MEMORY["agentId"],
                memory_id=MEMORY["id"],
            )

    assert created.memory.id == MEMORY["id"]
    assert created.memory.user_id == ""
    assert created.memory.model_extra == {"futureField": {"opaque_key": True}}
    assert created.model_extra == {"futureEnvelopeField": True}
    assert created._request_id == "req_memory"
    assert page.next_cursor == "next"
    assert fetched.memory.text == "Prefers dark mode"
    assert updated.memory.text == "Prefers light mode"
    assert json.loads(state.requests[0].body) == {
        "text": "Prefers dark mode",
        "userId": "",
    }
    assert state.requests[1].target == (
        "/v1/agents/ag_0123456789abcdef/memories"
        "?userId=&search=dark+mode&cursor=opaque+cursor&limit=1"
    )
    assert state.requests[4].target == (
        "/v1/agents/agent%2Fwith%20space/memories/memory%2Fwith%20space"
    )
    assert state.requests[-1].method == "DELETE"


def test_async_memories_match_sync_lifecycle_and_lazy_pagination() -> None:
    with loopback(
        Response(body={"memory": MEMORY}),
        Response(body={"data": [MEMORY], "nextCursor": None}),
        Response(body={"data": [MEMORY], "nextCursor": "after"}),
        Response(
            body={
                "data": [{**MEMORY, "userId": "end-user"}],
                "nextCursor": None,
            }
        ),
        Response(body={"memory": MEMORY}),
        Response(body={"memory": {**MEMORY, "text": "Updated"}}),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.memories.create(
                    agent_id=MEMORY["agentId"],
                    text="Prefers dark mode",
                )
                page = await client.memories.list(agent_id=MEMORY["agentId"])
                assert page.next_cursor is None
                memories = client.memories.iter(
                    agent_id=MEMORY["agentId"],
                    limit=1,
                )
                assert len(state.requests) == 2
                assert (await anext(memories)).user_id == ""
                assert len(state.requests) == 3
                assert (await anext(memories)).user_id == "end-user"
                with pytest.raises(StopAsyncIteration):
                    await anext(memories)
                await client.memories.get(
                    agent_id=MEMORY["agentId"],
                    memory_id=MEMORY["id"],
                )
                updated = await client.memories.update(
                    agent_id=MEMORY["agentId"],
                    memory_id=MEMORY["id"],
                    text="Updated",
                )
                assert updated.memory.text == "Updated"
                await client.memories.delete(
                    agent_id=MEMORY["agentId"],
                    memory_id=MEMORY["id"],
                )

        asyncio.run(exercise())

    assert json.loads(state.requests[0].body) == {"text": "Prefers dark mode"}
    assert state.requests[1].target == ("/v1/agents/ag_0123456789abcdef/memories")
    assert state.requests[-1].method == "DELETE"


def test_prompt_and_memory_public_types_ship_in_the_installed_wheel() -> None:
    prompt_create: PromptCreate = {
        "name": "Greeting",
        "template": "Hello {{name}}",
    }
    prompt_update: PromptUpdate = {"metadata": {"opaque": None}}
    prompt_list: PromptsListOptions = {"user_id": ""}
    memory_create: MemoryCreate = {"text": "Prefers dark mode"}
    memory_update: MemoryUpdate = {"text": "Prefers light mode"}
    memory_list: MemoriesListOptions = {
        "user_id": "",
        "search": "dark mode",
        "cursor": "opaque",
        "limit": 25,
    }

    assert prompt_create["template"] == "Hello {{name}}"
    assert prompt_update["metadata"] == {"opaque": None}
    assert prompt_list["user_id"] == ""
    assert memory_create["text"] == "Prefers dark mode"
    assert memory_update["text"] == "Prefers light mode"
    assert memory_list["limit"] == 25
    assert issubclass(Prompt, object)
    assert issubclass(Prompts, object)
    assert issubclass(Memory, object)
    assert issubclass(MemoryResponse, object)
    assert issubclass(MemoriesPage, object)


def test_prompt_response_rejects_invalid_inferred_variables() -> None:
    too_many_variables = [f"value{index}" for index in range(11)]
    malformed = [
        {**PROMPT, "variables": ["other"]},
        {
            **PROMPT,
            "template": "{{bad-name}}",
            "variables": ["bad-name"],
        },
        {
            **PROMPT,
            "template": " ".join(f"{{{{{name}}}}}" for name in too_many_variables),
            "variables": too_many_variables,
        },
    ]
    with loopback(*(Response(body=value) for value in malformed)) as (
        base_url,
        state,
    ):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            for _ in malformed:
                with pytest.raises(ValidationError, match="variables"):
                    client.prompts.get(prompt_id=PROMPT["id"])

    assert len(state.requests) == len(malformed)


def test_prompt_and_memory_boundaries_preserve_errors_and_reject_malformed() -> None:
    prompt_error = {
        "error": {
            "code": "prompt_not_found",
            "message": "Prompt not found",
        }
    }
    memory_error = {
        "error": {
            "code": "not_found",
            "message": "Memory not found",
        }
    }
    with loopback(
        Response(
            body=prompt_error,
            status=404,
            headers={"x-request-id": "req_missing_prompt"},
        ),
        Response(body={"prompts": "wrong"}),
        Response(
            body=memory_error,
            status=404,
            headers={"x-request-id": "req_missing_memory"},
        ),
        Response(body={"memory": {**MEMORY, "text": ""}}),
        Response(body={"data": "wrong", "nextCursor": None}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(ValueError, match="At least one"):
                client.prompts.update(prompt_id=PROMPT["id"])
            with pytest.raises(TypeError):
                cast(Any, client.prompts.create)(
                    name="Greeting",
                    template="Hello",
                    unknown=True,
                )
            with pytest.raises(TypeError):
                cast(Any, client.memories.get)(
                    MEMORY["agentId"],
                    MEMORY["id"],
                )
            with pytest.raises(APIStatusError) as missing_prompt:
                client.prompts.get(prompt_id=PROMPT["id"])
            with pytest.raises(ValidationError):
                client.prompts.list()
            with pytest.raises(APIStatusError) as missing_memory:
                client.memories.get(
                    agent_id=MEMORY["agentId"],
                    memory_id=MEMORY["id"],
                )
            with pytest.raises(ValidationError):
                client.memories.get(
                    agent_id=MEMORY["agentId"],
                    memory_id=MEMORY["id"],
                )
            with pytest.raises(ValidationError):
                client.memories.list(agent_id=MEMORY["agentId"])

    assert missing_prompt.value.code == "prompt_not_found"
    assert missing_prompt.value.request_id == "req_missing_prompt"
    assert missing_memory.value.code == "not_found"
    assert missing_memory.value.request_id == "req_missing_memory"
    assert len(state.requests) == 5


def test_skills_are_exposed_only_through_agent_scoped_clients() -> None:
    with loopback(
        Response(body={"data": [SKILL], "nextCursor": None}),
        Response(body={"data": [SKILL], "nextCursor": None}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            assert not hasattr(client, "skills")
            skills = client.agent(SKILL["agentId"]).skills
            with pytest.raises(TypeError):
                cast(Any, skills.list)(agent_id=SKILL["agentId"])
            assert skills.list().data[0].id == SKILL["id"]

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                assert not hasattr(client, "skills")
                skills = client.agent(SKILL["agentId"]).skills
                with pytest.raises(TypeError):
                    await cast(Any, skills.list)(agent_id=SKILL["agentId"])
                page = await skills.list()
                assert page.data[0].id == SKILL["id"]

        asyncio.run(exercise())

    assert [request.target for request in state.requests] == [
        "/v1/agents/ag_0123456789abcdef/skills",
        "/v1/agents/ag_0123456789abcdef/skills",
    ]


def test_sync_skills_manage_files_pagination_and_partial_copies() -> None:
    list_item = dict(SKILL)
    markdown = "---\nname: deploy\ndescription: Deploy the application.\n---\n"
    destination = "ag_fedcba9876543210"
    failed_destination = "ag_1111111111111111"
    copy_results = [
        {
            "agentId": destination,
            "status": "created",
            "skill": {
                **SKILL_DETAIL,
                "agentId": destination,
                "id": "skill_fedcba9876543210",
            },
        },
        {
            "agentId": failed_destination,
            "status": "failed",
            "error": {
                "code": "skill_name_conflict",
                "message": "Already exists",
                "details": {"existingId": "skill_1111111111111111"},
            },
        },
    ]
    with loopback(
        Response(
            body={**SKILL_DETAIL, "futureField": {"opaque_key": True}},
            headers={"x-request-id": "req_skill_create"},
        ),
        Response(
            body={"data": [list_item], "nextCursor": "next"},
            headers={"x-request-id": "req_skill_page"},
        ),
        Response(body={"data": [list_item], "nextCursor": "next"}),
        Response(body={"data": [{**list_item, "name": "second"}], "nextCursor": None}),
        Response(body=SKILL_DETAIL),
        Response(raw_body=b"\x00\xff\x80\x01"),
        Response(body=SKILL_DETAIL),
        Response(body=SKILL_DETAIL),
        Response(body=copy_results, headers={"x-request-id": "req_skill_copy"}),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            created = client.agent(SKILL["agentId"]).skills.create(
                path="SKILL.md",
                content=markdown,
            )
            page = client.agent(SKILL["agentId"]).skills.list(
                cursor="opaque page",
                limit=1,
            )
            skills = client.agent(SKILL["agentId"]).skills.iter(limit=1)
            assert len(state.requests) == 2
            assert next(skills).name == "deploy"
            assert len(state.requests) == 3
            assert next(skills).name == "second"
            with pytest.raises(StopIteration):
                next(skills)
            fetched = client.agent(SKILL["agentId"]).skills.get(
                skill_id=SKILL["id"],
            )
            content = client.agent(SKILL["agentId"]).skills.read_file(
                skill_id=SKILL["id"],
                path="assets/% weird/µ.bin",
            )
            replaced = client.agent(SKILL["agentId"]).skills.replace_file(
                skill_id=SKILL["id"],
                path="assets/% weird/µ.bin",
                content=b"\x00\xff\x80\x01",
            )
            after_delete = client.agent(SKILL["agentId"]).skills.delete_file(
                skill_id=SKILL["id"],
                path="assets/% weird/µ.bin",
            )
            copied = client.agent(SKILL["agentId"]).skills.copy(
                skill_id=SKILL["id"],
                destination_agent_ids=[destination, failed_destination],
            )
            client.agent(SKILL["agentId"]).skills.delete(
                skill_id=SKILL["id"],
            )

    assert isinstance(created, SkillDetail)
    assert isinstance(page, SkillsPage)
    assert isinstance(page.data[0], Skill)
    assert created._request_id == "req_skill_create"
    assert created.model_extra == {"futureField": {"opaque_key": True}}
    assert page._request_id == "req_skill_page"
    assert fetched.files[1].size_bytes == 4
    assert content == b"\x00\xff\x80\x01"
    assert replaced.id == SKILL["id"]
    assert after_delete.name == "deploy"
    assert isinstance(copied[0], SkillCopyCreated)
    assert copied[0].agent_id == destination
    assert copied[0].skill.agent_id == destination
    assert isinstance(copied[1], SkillCopyFailed)
    assert copied[1].agent_id == failed_destination
    assert copied[1].error.details == {"existingId": "skill_1111111111111111"}
    assert copied[0]._request_id == "req_skill_copy"
    assert copied[1]._request_id == "req_skill_copy"

    assert json.loads(state.requests[0].body) == {
        "path": "SKILL.md",
        "content": markdown,
    }
    first_page = urlsplit(state.requests[1].target)
    assert first_page.path == "/v1/agents/ag_0123456789abcdef/skills"
    assert parse_qs(first_page.query) == {
        "cursor": ["opaque page"],
        "limit": ["1"],
    }
    assert state.requests[3].target.endswith("?cursor=next&limit=1")
    encoded_file = (
        "/v1/agents/ag_0123456789abcdef/"
        "skills/skill_0123456789abcdef/files/assets/%25%20weird/%C2%B5.bin"
    )
    assert state.requests[5].target == encoded_file
    assert state.requests[6].target == encoded_file
    assert state.requests[6].method == "PUT"
    assert state.requests[6].body == b"\x00\xff\x80\x01"
    assert state.requests[7].target == encoded_file
    assert state.requests[7].method == "DELETE"
    assert json.loads(state.requests[8].body) == {
        "agentIds": [destination, failed_destination]
    }
    assert state.requests[9].method == "DELETE"


def test_sync_skill_archive_uploads_preserve_multipart_and_file_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    archive_path = tmp_path / "deploy.tar"
    archive_path.write_bytes(b"path-archive-secret")
    opened_files: list[Any] = []
    original_open = cast(Callable[..., Any], Path.open)

    def tracking_open(path: Path, *args: object, **kwargs: object) -> Any:
        opened = original_open(path, *args, **kwargs)
        opened_files.append(opened)
        return opened

    monkeypatch.setattr(Path, "open", tracking_open)
    caller_file = io.BytesIO(b"caller-archive-secret")
    error = {
        "error": {
            "code": "invalid_skill_archive",
            "message": "Archive is invalid",
        }
    }
    with loopback(
        Response(body=SKILL_DETAIL),
        Response(body=SKILL_DETAIL),
        Response(body=error, status=400),
        Response(body=SKILL_DETAIL),
        Response(body=error, status=400),
        Response(body={"id": "malformed"}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with caplog.at_level(logging.DEBUG, logger="blazing_agents"):
                from_bytes = client.agent(SKILL["agentId"]).skills.upload(
                    archive_type="zip",
                    file=b"bytes-archive-secret",
                )
                from_path = client.agent(SKILL["agentId"]).skills.upload(
                    archive_type="tar",
                    file=archive_path,
                )
                assert opened_files[-1].closed is True
                with pytest.raises(APIStatusError) as path_error:
                    client.agent(SKILL["agentId"]).skills.upload(
                        archive_type="tar",
                        file=archive_path,
                    )
                assert opened_files[-1].closed is True
                from_caller = client.agent(SKILL["agentId"]).skills.upload(
                    archive_type="tar.gz",
                    file=caller_file,
                )
                with pytest.raises(APIStatusError):
                    client.agent(SKILL["agentId"]).skills.upload(
                        archive_type="tar.gz",
                        file=caller_file,
                    )
                assert caller_file.closed is False
                with pytest.raises(ValidationError):
                    client.agent(SKILL["agentId"]).skills.upload(
                        archive_type="tar",
                        file=archive_path,
                    )
                assert opened_files[-1].closed is True

    assert from_bytes.name == "deploy"
    assert from_path.id == SKILL["id"]
    assert from_caller.description == "Deploy the application."
    assert path_error.value.code == "invalid_skill_archive"
    assert len(opened_files) == 3
    assert all(opened.closed for opened in opened_files)
    assert caller_file.closed is False
    bodies = [request.body for request in state.requests]
    for body, archive_type, content in (
        (bodies[0], b"zip", b"bytes-archive-secret"),
        (bodies[1], b"tar", b"path-archive-secret"),
        (bodies[2], b"tar", b"path-archive-secret"),
        (bodies[3], b"tar.gz", b"caller-archive-secret"),
        (bodies[4], b"tar.gz", b"caller-archive-secret"),
    ):
        assert b'name="type"' in body
        assert b"\r\n\r\n" + archive_type + b"\r\n" in body
        assert b'name="file"' in body
        assert content in body
    assert b'filename="skill.zip"' in bodies[0]
    assert b'filename="deploy.tar"' in bodies[1]
    assert b'filename="skill.tar.gz"' in bodies[3]
    assert all(request.method == "POST" for request in state.requests)
    assert all(
        request.target == "/v1/agents/ag_0123456789abcdef/skills/upload"
        for request in state.requests
    )
    log_output = "\n".join(record.getMessage() for record in caplog.records)
    assert "archive-secret" not in log_output
    caller_file.close()


def test_async_skills_match_lifecycle_upload_and_file_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path = tmp_path / "async-deploy.zip"
    archive_path.write_bytes(b"async-path-archive")
    opened_files: list[Any] = []
    original_open = cast(Callable[..., Any], Path.open)

    def tracking_open(path: Path, *args: object, **kwargs: object) -> Any:
        opened = original_open(path, *args, **kwargs)
        opened_files.append(opened)
        return opened

    monkeypatch.setattr(Path, "open", tracking_open)
    caller_file = io.BytesIO(b"async-caller-archive")
    error = {
        "error": {
            "code": "invalid_skill_archive",
            "message": "Archive is invalid",
        }
    }
    destination = "ag_fedcba9876543210"
    failed_destination = "ag_1111111111111111"
    copy_results = [
        {
            "agentId": destination,
            "status": "created",
            "skill": {
                **SKILL_DETAIL,
                "agentId": destination,
                "id": "skill_fedcba9876543210",
            },
        },
        {
            "agentId": failed_destination,
            "status": "failed",
            "error": {"code": "skill_name_conflict", "message": "Already exists"},
        },
    ]
    with loopback(
        Response(body=SKILL_DETAIL),
        Response(body=SKILL_DETAIL),
        Response(body=SKILL_DETAIL),
        Response(body=error, status=400),
        Response(body=SKILL_DETAIL),
        Response(body=error, status=400),
        Response(body={"data": [SKILL], "nextCursor": "next"}),
        Response(body={"data": [SKILL], "nextCursor": "next"}),
        Response(body={"data": [{**SKILL, "name": "second"}], "nextCursor": None}),
        Response(body=SKILL_DETAIL),
        Response(raw_body=b"\x00\xffasync"),
        Response(body=SKILL_DETAIL),
        Response(body=SKILL_DETAIL),
        Response(body=copy_results),
        Response(status=204, raw_body=b""),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                created = await client.agent(SKILL["agentId"]).skills.create(
                    path="SKILL.md",
                    content="---\nname: deploy\ndescription: Deploy.\n---\n",
                )
                await client.agent(SKILL["agentId"]).skills.upload(
                    archive_type="zip",
                    file=b"async-bytes-archive",
                )
                await client.agent(SKILL["agentId"]).skills.upload(
                    archive_type="zip",
                    file=archive_path,
                )
                assert opened_files[-1].closed is True
                with pytest.raises(APIStatusError):
                    await client.agent(SKILL["agentId"]).skills.upload(
                        archive_type="zip",
                        file=archive_path,
                    )
                assert opened_files[-1].closed is True
                await client.agent(SKILL["agentId"]).skills.upload(
                    archive_type="tar.gz",
                    file=caller_file,
                )
                with pytest.raises(APIStatusError):
                    await client.agent(SKILL["agentId"]).skills.upload(
                        archive_type="tar.gz",
                        file=caller_file,
                    )
                assert caller_file.closed is False

                page = await client.agent(SKILL["agentId"]).skills.list(
                    cursor="opaque",
                    limit=1,
                )
                skills = client.agent(SKILL["agentId"]).skills.iter(limit=1)
                assert len(state.requests) == 7
                assert (await anext(skills)).name == "deploy"
                assert len(state.requests) == 8
                assert (await anext(skills)).name == "second"
                with pytest.raises(StopAsyncIteration):
                    await anext(skills)
                fetched = await client.agent(SKILL["agentId"]).skills.get(
                    skill_id=SKILL["id"],
                )
                content = await client.agent(SKILL["agentId"]).skills.read_file(
                    skill_id=SKILL["id"],
                    path="references/space name.md",
                )
                replaced = await client.agent(SKILL["agentId"]).skills.replace_file(
                    skill_id=SKILL["id"],
                    path="references/space name.md",
                    content=b"replacement",
                )
                after_delete = await client.agent(SKILL["agentId"]).skills.delete_file(
                    skill_id=SKILL["id"],
                    path="references/space name.md",
                )
                copied = await client.agent(SKILL["agentId"]).skills.copy(
                    skill_id=SKILL["id"],
                    destination_agent_ids=[destination, failed_destination],
                )
                await client.agent(SKILL["agentId"]).skills.delete(
                    skill_id=SKILL["id"],
                )

            assert created.name == "deploy"
            assert page.next_cursor == "next"
            assert fetched.files[0].path == "SKILL.md"
            assert content == b"\x00\xffasync"
            assert replaced.id == SKILL["id"]
            assert after_delete.description == "Deploy the application."
            assert isinstance(copied[0], SkillCopyCreated)
            assert isinstance(copied[1], SkillCopyFailed)

        asyncio.run(exercise())

    assert len(opened_files) == 2
    assert all(opened.closed for opened in opened_files)
    assert caller_file.closed is False
    assert b"async-bytes-archive" in state.requests[1].body
    assert b"async-path-archive" in state.requests[2].body
    assert b"async-caller-archive" in state.requests[4].body
    assert state.requests[10].target.endswith("/files/references/space%20name.md")
    assert state.requests[11].body == b"replacement"
    assert json.loads(state.requests[13].body) == {
        "agentIds": [destination, failed_destination]
    }
    caller_file.close()


def test_skill_request_validation_and_malformed_responses() -> None:
    sync_client = BlazingAgents(
        api_key="ba_test",
        base_url="http://127.0.0.1:1",
    )
    with pytest.raises(ValueError, match="SKILL.md"):
        sync_client.agent(SKILL["agentId"]).skills.create(
            path=cast(Any, "nested/SKILL.md"),
            content="invalid",
        )
    with pytest.raises(ValueError, match="archive_type"):
        sync_client.agent(SKILL["agentId"]).skills.upload(
            archive_type=cast(Any, "rar"),
            file=b"invalid",
        )
    sync_client.close()

    async def reject_async_requests() -> None:
        client = AsyncBlazingAgents(
            api_key="ba_test",
            base_url="http://127.0.0.1:1",
        )
        with pytest.raises(ValueError, match="SKILL.md"):
            await client.agent(SKILL["agentId"]).skills.create(
                path=cast(Any, "nested/SKILL.md"),
                content="invalid",
            )
        with pytest.raises(ValueError, match="archive_type"):
            await client.agent(SKILL["agentId"]).skills.upload(
                archive_type=cast(Any, "rar"),
                file=b"invalid",
            )
        await client.aclose()

    asyncio.run(reject_async_requests())

    missing = {
        "error": {
            "code": "skill_file_not_found",
            "message": "Skill file not found",
        }
    }
    with loopback(
        Response(
            body=missing,
            status=404,
            headers={"x-request-id": "req_missing_skill_file"},
        ),
        Response(body={"data": "wrong", "nextCursor": None}),
        Response(body=[{"agentId": SKILL["agentId"], "status": "future"}]),
        Response(body={**SKILL_DETAIL, "name": "anthropic"}),
        Response(
            body={
                **SKILL_DETAIL,
                "files": [{"path": "../escape", "sizeBytes": 1}],
            }
        ),
        Response(body={**SKILL_DETAIL, "metadata": None}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(APIStatusError) as missing_file:
                client.agent(SKILL["agentId"]).skills.read_file(
                    skill_id=SKILL["id"],
                    path="missing.bin",
                )
            with pytest.raises(ValidationError):
                client.agent(SKILL["agentId"]).skills.list()
            with pytest.raises(ValidationError):
                client.agent(SKILL["agentId"]).skills.copy(
                    skill_id=SKILL["id"],
                    destination_agent_ids=[SKILL["agentId"]],
                )
            with pytest.raises(ValidationError):
                client.agent(SKILL["agentId"]).skills.get(
                    skill_id=SKILL["id"],
                )
            with pytest.raises(ValidationError):
                client.agent(SKILL["agentId"]).skills.get(
                    skill_id=SKILL["id"],
                )
            with pytest.raises(ValidationError):
                client.agent(SKILL["agentId"]).skills.get(
                    skill_id=SKILL["id"],
                )

    assert missing_file.value.code == "skill_file_not_found"
    assert missing_file.value.request_id == "req_missing_skill_file"
    assert len(state.requests) == 6


def test_skill_public_types_ship_in_the_installed_wheel() -> None:
    archive_type: SkillArchiveType = "tar.gz"
    create: SkillCreate = {
        "path": "SKILL.md",
        "content": "---\nname: deploy\ndescription: Deploy.\n---\n",
    }
    upload: SkillArchiveUpload = {
        "archive_type": archive_type,
        "file": b"archive",
    }
    options: SkillsListOptions = {"cursor": "opaque", "limit": 25}
    copy: SkillCopy = {"destination_agent_ids": ["ag_0123456789abcdef"]}

    assert create["path"] == "SKILL.md"
    assert upload["archive_type"] == "tar.gz"
    assert options["limit"] == 25
    assert copy["destination_agent_ids"] == ["ag_0123456789abcdef"]


def test_artifacts_list_get_download_url_and_delete() -> None:
    download_url = {
        "url": "https://r2.example.test/signed-object",
        "expiresAt": "2026-08-02T01:05:00.000Z",
    }
    with loopback(
        Response(body={"data": [ARTIFACT], "nextCursor": None}),
        Response(body=ARTIFACT),
        Response(body=download_url),
        Response(status=204),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            page = client.artifacts.list(agent_id=ARTIFACT["agentId"])
            detail = client.artifacts.get(artifact_id=ARTIFACT["artifactId"])
            signed = client.artifacts.create_download_url(
                artifact_id=ARTIFACT["artifactId"]
            )
            client.artifacts.delete(
                artifact_id=ARTIFACT["artifactId"],
            )

    assert isinstance(page, ArtifactsPage)
    assert isinstance(detail, Artifact)
    assert detail.model_extra == {}
    assert isinstance(signed, ArtifactDownloadUrl)
    assert [request.target for request in state.requests] == [
        "/v1/artifacts?agentId=ag_0123456789abcdef",
        "/v1/artifacts/at_0123456789abcdef",
        "/v1/artifacts/at_0123456789abcdef/download-url",
        "/v1/artifacts/at_0123456789abcdef",
    ]


def test_async_artifacts_match_tenant_detail_and_download_url() -> None:
    async def exercise(base_url: str) -> None:
        async with AsyncBlazingAgents(api_key="ba_test", base_url=base_url) as client:
            detail = await client.artifacts.get(artifact_id=ARTIFACT["artifactId"])
            signed = await client.artifacts.create_download_url(
                artifact_id=ARTIFACT["artifactId"]
            )
            await client.artifacts.delete(
                artifact_id=ARTIFACT["artifactId"],
            )

        assert isinstance(detail, Artifact)
        assert isinstance(signed, ArtifactDownloadUrl)

    with loopback(
        Response(body=ARTIFACT),
        Response(
            body={
                "url": "https://r2.example.test/signed-object",
                "expiresAt": "2026-08-02T01:05:00.000Z",
            }
        ),
        Response(status=204),
    ) as (base_url, state):
        asyncio.run(exercise(base_url))

    assert [request.target for request in state.requests] == [
        "/v1/artifacts/at_0123456789abcdef",
        "/v1/artifacts/at_0123456789abcdef/download-url",
        "/v1/artifacts/at_0123456789abcdef",
    ]


def test_artifact_iterators_page_until_the_terminal_cursor() -> None:
    page_one = {"data": [ARTIFACT], "nextCursor": "next"}
    page_two = {
        "data": [{**ARTIFACT, "artifactId": "at_aaaaaaaaaaaaaaaa"}],
        "nextCursor": None,
    }
    with loopback(Response(body=page_one), Response(body=page_two)) as (
        base_url,
        state,
    ):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            artifacts = list(client.artifacts.iter(session_id=ARTIFACT["sessionId"]))

    assert [artifact.artifact_id for artifact in artifacts] == [
        ARTIFACT["artifactId"],
        "at_aaaaaaaaaaaaaaaa",
    ]
    assert state.requests[1].target.endswith(
        "?sessionId=ss_0123456789abcdef&cursor=next"
    )

    async def exercise(base_url: str) -> list[Artifact]:
        async with AsyncBlazingAgents(api_key="ba_test", base_url=base_url) as client:
            return [
                artifact
                async for artifact in client.artifacts.iter(
                    session_id=ARTIFACT["sessionId"]
                )
            ]

    with loopback(Response(body=page_one), Response(body=page_two)) as (
        base_url,
        state,
    ):
        async_artifacts = asyncio.run(exercise(base_url))

    assert [artifact.artifact_id for artifact in async_artifacts] == [
        ARTIFACT["artifactId"],
        "at_aaaaaaaaaaaaaaaa",
    ]
    assert state.requests[1].target.endswith(
        "?sessionId=ss_0123456789abcdef&cursor=next"
    )


def test_artifact_detail_rejects_internal_or_invalid_filename_shapes() -> None:
    with pytest.raises(ValidationError):
        Artifact.model_validate({**ARTIFACT, "filename": "../object-key"})


def test_generic_byte_stream_maps_incomplete_errors_and_connection_failures() -> None:
    with loopback(
        Response(chunks=(b'{"error":',), status=500, complete_chunks=False),
        Response(chunks=(b'{"error":',), status=500, complete_chunks=False),
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(StreamError, match="read failed"):
                client.sessions.join_tool_approval_continuation(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    continuation_id="tool-approval:ss:assistant",
                )

        async def reject_incomplete_error() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(StreamError, match="read failed"):
                    await client.sessions.join_tool_approval_continuation(
                        agent_id=AGENT["id"],
                        session_id=SESSION["id"],
                        continuation_id="tool-approval:ss:assistant",
                    )

        asyncio.run(reject_incomplete_error())

    unused = _unused_origin()
    with BlazingAgents(api_key="ba_test", base_url=unused) as client:
        with pytest.raises(APIConnectionError):
            client.sessions.join_tool_approval_continuation(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                continuation_id="tool-approval:ss:assistant",
            )

    async def reject_connection() -> None:
        async with AsyncBlazingAgents(api_key="ba_test", base_url=unused) as client:
            with pytest.raises(APIConnectionError):
                await client.sessions.join_tool_approval_continuation(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    continuation_id="tool-approval:ss:assistant",
                )

    asyncio.run(reject_connection())


def test_sync_sessions_list_returns_a_correlated_forward_compatible_page() -> None:
    response = {
        "data": [{**SESSION, "futureSessionField": {"opaque": True}}],
        "nextCursor": "next-session",
        "futurePageField": True,
    }
    with loopback(
        Response(body=response, headers={"x-request-id": "req_sessions_list"})
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            page = client.sessions.list(
                agent_id=AGENT["id"],
                user_id="end/user",
                cursor="cursor value",
                limit=25,
            )

    assert state.requests[0].target == (
        "/v1/agents/ag_0123456789abcdef/sessions"
        "?userId=end%2Fuser&cursor=cursor+value&limit=25"
    )
    assert page.next_cursor == "next-session"
    assert page._request_id == "req_sessions_list"
    assert page.model_extra == {"futurePageField": True}
    assert page.data[0].metadata == {"OpaqueKey": {"nested_key": True}}
    assert page.data[0].model_extra == {"futureSessionField": {"opaque": True}}


def test_sync_tool_approvals_preserve_pending_and_continuation_state() -> None:
    response = {
        "data": [{**TOOL_APPROVAL, "futureApprovalField": True}],
        "continuation": {
            "id": "tool-approval:ss:assistant",
            "state": "waiting",
            "futureContinuationField": "retained",
        },
        "futureResponseField": {"opaque": True},
    }
    with loopback(
        Response(body=response, headers={"x-request-id": "req_approval_list"})
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            approvals = client.sessions.tool_approvals(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
            )

    assert state.requests[0].target == (
        "/v1/agents/ag_0123456789abcdef/sessions/ss_0123456789abcdef/tool-approvals"
    )
    assert isinstance(approvals, ToolApprovals)
    assert approvals._request_id == "req_approval_list"
    assert approvals.model_extra == {"futureResponseField": {"opaque": True}}
    assert approvals.continuation == ToolApprovalContinuation.model_validate(
        {
            "id": "tool-approval:ss:assistant",
            "state": "waiting",
            "futureContinuationField": "retained",
        }
    )
    assert approvals.data == [
        ToolApproval.model_validate({**TOOL_APPROVAL, "futureApprovalField": True})
    ]
    assert approvals.data[0].input == {
        "action": "update",
        "OpaqueKey": {"nested_key": True},
    }


def test_sync_tool_approval_decisions_rejoin_or_surface_server_conflicts() -> None:
    decision = {
        "continuationId": "tool-approval:ss:assistant",
        "state": "queued",
        "futureDecisionField": True,
    }
    conflict = {
        "error": {
            "code": "tool_approval_decision_conflict",
            "message": "Tool approval decision conflicts",
        }
    }
    with loopback(
        Response(status=202, body=decision, headers={"x-request-id": "req_decide"}),
        Response(status=202, body={**decision, "state": "running"}),
        Response(status=409, body=conflict, headers={"x-request-id": "req_conflict"}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            denial: ToolApprovalDecisionInput = {
                "agent_id": AGENT["id"],
                "session_id": SESSION["id"],
                "approval_id": "approval/1",
                "approved": False,
                "reason": "Tenant denied the update.",
            }
            accepted = client.sessions.decide_tool_approval(**denial)
            repeated = client.sessions.decide_tool_approval(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                approval_id="approval/1",
                approved=False,
            )
            with pytest.raises(APIStatusError) as conflicting:
                client.sessions.decide_tool_approval(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    approval_id="approval/1",
                    approved=True,
                )

    assert isinstance(accepted, ToolApprovalDecision)
    assert accepted.continuation_id == repeated.continuation_id
    assert accepted.state == "queued"
    assert accepted._request_id == "req_decide"
    assert accepted.model_extra == {"futureDecisionField": True}
    assert conflicting.value.code == "tool_approval_decision_conflict"
    assert conflicting.value.request_id == "req_conflict"
    assert [request.target for request in state.requests] == [
        (
            "/v1/agents/ag_0123456789abcdef"
            "/sessions/ss_0123456789abcdef/tool-approvals/approval%2F1"
        )
    ] * 3
    assert [json.loads(request.body) for request in state.requests] == [
        {"approved": False, "reason": "Tenant denied the update."},
        {"approved": False},
        {"approved": True},
    ]


def test_sync_tool_approval_continuation_detaches_and_rejoins_untouched() -> None:
    first_chunk = b'data: {"type":"text-delta","delta":"'
    terminal_chunks = (
        first_chunk,
        b'\xff"}\n\ndata: malformed future event\n\n',
        b"data: [DONE]\n\n",
    )
    gate = Event()
    detached = Event()
    continuation_id = "tool-approval:ss:assistant/1"
    with loopback(
        Response(
            chunks=(first_chunk, b"server-owned-work-continues"),
            chunk_gate=gate,
            cancelled=detached,
            headers={
                "content-type": "text/event-stream",
                "x-request-id": "req_join_detach",
            },
        ),
        Response(
            chunks=terminal_chunks,
            headers={
                "content-type": "text/event-stream",
                "x-request-id": "req_join_rejoin",
                "x-future-header": "preserved",
            },
        ),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            joined = client.sessions.join_tool_approval_continuation(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                continuation_id=continuation_id,
            )
            body = iter(joined)
            assert next(body) == first_chunk
            joined.close()
            gate.set()
            assert detached.wait(timeout=1)

            rejoined = client.sessions.join_tool_approval_continuation(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                continuation_id=continuation_id,
                extra_headers={"x-client-request-id": "caller-rejoin"},
            )
            assert isinstance(rejoined, ByteStream)
            assert rejoined.status_code == 200
            assert rejoined.request_id == "req_join_rejoin"
            assert rejoined.headers["x-future-header"] == "preserved"
            assert b"".join(rejoined) == b"".join(terminal_chunks)
            assert rejoined.closed is True
            with pytest.raises(StreamError, match="already"):
                iter(rejoined)

    expected_path = (
        "/v1/agents/ag_0123456789abcdef"
        "/sessions/ss_0123456789abcdef/tool-approval-continuations/"
        "tool-approval%3Ass%3Aassistant%2F1"
    )
    assert [request.target for request in state.requests] == [
        expected_path,
        expected_path,
    ]
    assert state.requests[1].headers["x-client-request-id"] == "caller-rejoin"


def test_async_tool_approval_lifecycle_matches_sync_and_rejoins_after_detach() -> None:
    continuation_id = "tool-approval:ss:assistant"
    approval_state = {
        "data": [
            TOOL_APPROVAL,
            {
                **TOOL_APPROVAL,
                "approvalId": "approval-2",
                "toolCallId": "tool-call-2",
                "decision": "approved",
                "reason": "Approved by tenant.",
            },
        ],
        "continuation": {"id": continuation_id, "state": "waiting"},
    }
    decision = {"continuationId": continuation_id, "state": "running"}
    conflict = {
        "error": {
            "code": "tool_approval_decision_conflict",
            "message": "Tool approval decision conflicts",
        }
    }
    gate = Event()
    detached = Event()
    terminal_chunks = (
        b'data: {"type":"start"}\n\n',
        b"data: future malformed bytes \xff\n\n",
    )
    with loopback(
        Response(
            body=approval_state,
            headers={"x-request-id": "req_async_approvals"},
        ),
        Response(status=202, body=decision),
        Response(status=202, body={**decision, "state": "succeeded"}),
        Response(status=409, body=conflict),
        Response(
            chunks=(b"persisted-first", b"persisted-later"),
            chunk_gate=gate,
            cancelled=detached,
        ),
        Response(
            chunks=terminal_chunks,
            headers={
                "content-type": "text/event-stream",
                "x-request-id": "req_async_rejoin",
            },
        ),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                approvals = await client.sessions.tool_approvals(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                )
                assert approvals.data[0].decision == "pending"
                assert approvals.data[0].reason is None
                assert approvals.data[1].decision == "approved"
                assert approvals.data[1].reason == "Approved by tenant."
                assert approvals.continuation is not None
                assert approvals.continuation.state == "waiting"
                assert approvals._request_id == "req_async_approvals"

                accepted = await client.sessions.decide_tool_approval(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    approval_id="approval-1",
                    approved=True,
                    reason="Approved by tenant.",
                )
                repeated = await client.sessions.decide_tool_approval(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    approval_id="approval-1",
                    approved=True,
                )
                assert accepted.continuation_id == repeated.continuation_id
                with pytest.raises(APIStatusError) as conflicting:
                    await client.sessions.decide_tool_approval(
                        agent_id=AGENT["id"],
                        session_id=SESSION["id"],
                        approval_id="approval-1",
                        approved=False,
                    )
                assert conflicting.value.code == "tool_approval_decision_conflict"

                joined = await client.sessions.join_tool_approval_continuation(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    continuation_id=continuation_id,
                )
                body = aiter(joined)
                assert await anext(body) == b"persisted-first"
                await joined.aclose()
                gate.set()
                assert await asyncio.to_thread(detached.wait, 1)

                rejoined = await client.sessions.join_tool_approval_continuation(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    continuation_id=continuation_id,
                )
                assert isinstance(rejoined, AsyncByteStream)
                assert rejoined.request_id == "req_async_rejoin"
                assert b"".join([chunk async for chunk in rejoined]) == b"".join(
                    terminal_chunks
                )
                assert rejoined.closed is True
                with pytest.raises(StreamError, match="already"):
                    aiter(rejoined)

        asyncio.run(exercise())

    assert [request.method for request in state.requests] == [
        "GET",
        "POST",
        "POST",
        "POST",
        "GET",
        "GET",
    ]


def test_sync_sessions_iter_requests_pages_lazily_until_terminal_cursor() -> None:
    second = {
        **SESSION,
        "id": "ss_1123456789abcdef",
        "lastMessagePreview": "Second",
    }
    with loopback(
        Response(body={"data": [SESSION], "nextCursor": "next-session"}),
        Response(body={"data": [second], "nextCursor": None}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            sessions = client.sessions.iter(agent_id=AGENT["id"], limit=1)
            assert state.requests == []
            assert next(sessions).id == SESSION["id"]
            assert len(state.requests) == 1
            assert next(sessions).id == second["id"]
            with pytest.raises(StopIteration):
                next(sessions)

    assert len(state.requests) == 2
    assert state.requests[1].target.endswith("?cursor=next-session&limit=1")


def test_async_sessions_list_and_iter_match_sync_paging() -> None:
    with loopback(
        Response(
            body={"data": [], "nextCursor": None},
            headers={"x-request-id": "req_sessions_empty"},
        ),
        Response(body={"data": [SESSION], "nextCursor": "next-session"}),
        Response(body={"data": [], "nextCursor": None}),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                page = await client.sessions.list(
                    agent_id=AGENT["id"],
                    user_id="",
                    cursor="start",
                    limit=10,
                )
                assert page.data == []
                assert page.next_cursor is None
                assert page._request_id == "req_sessions_empty"

                sessions = client.sessions.iter(agent_id=AGENT["id"], limit=1)
                assert len(state.requests) == 1
                assert [session.id async for session in sessions] == [SESSION["id"]]

        asyncio.run(exercise())

    assert [request.target for request in state.requests] == [
        ("/v1/agents/ag_0123456789abcdef/sessions?userId=&cursor=start&limit=10"),
        "/v1/agents/ag_0123456789abcdef/sessions?limit=1",
        ("/v1/agents/ag_0123456789abcdef/sessions?cursor=next-session&limit=1"),
    ]


def test_sync_session_messages_preserve_stored_history_and_order() -> None:
    response = {
        "data": [
            SESSION_MESSAGES[0],
            {**SESSION_MESSAGES[1], "futureMessageField": True},
        ],
        "nextCursor": "older",
        "latestCursor": "tail",
        "futurePageField": "retained",
    }
    with loopback(
        Response(body=response, headers={"x-request-id": "req_messages"})
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            page = client.sessions.messages(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                after="tail value",
                limit=20,
            )

    assert state.requests[0].target == (
        "/v1/agents/ag_0123456789abcdef"
        "/sessions/ss_0123456789abcdef/messages"
        "?after=tail+value&limit=20"
    )
    assert [message.id for message in page.data] == [
        "user-message",
        "assistant-message",
    ]
    assert page.next_cursor == "older"
    assert page.latest_cursor == "tail"
    assert page._request_id == "req_messages"
    assert page.model_extra == {"futurePageField": "retained"}
    assert page.data[1].model_extra == {"futureMessageField": True}
    assert page.data[1].parts[0].model_extra == {"OpaqueKey": {"nested_key": True}}


def test_async_session_messages_match_sync_history_retrieval() -> None:
    response = {
        "data": SESSION_MESSAGES,
        "nextCursor": None,
        "latestCursor": "tail",
    }
    with loopback(
        Response(body=response),
        Response(
            body={
                "data": [],
                "nextCursor": None,
                "latestCursor": None,
            }
        ),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                page = await client.sessions.messages(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    cursor="older value",
                    limit=5,
                )
                assert [message.id for message in page.data] == [
                    "user-message",
                    "assistant-message",
                ]
                assert page.next_cursor is None
                assert page.latest_cursor == "tail"
                empty = await client.sessions.messages(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    after="tail",
                )
                assert empty.data == []
                assert empty.next_cursor is None
                assert empty.latest_cursor is None

        asyncio.run(exercise())

    assert [request.target for request in state.requests] == [
        (
            "/v1/agents/ag_0123456789abcdef"
            "/sessions/ss_0123456789abcdef/messages"
            "?cursor=older+value&limit=5"
        ),
        (
            "/v1/agents/ag_0123456789abcdef"
            "/sessions/ss_0123456789abcdef/messages?after=tail"
        ),
    ]


def test_session_delete_and_domain_errors_use_the_shared_exception_contract() -> None:
    missing = {
        "error": {
            "code": "not_found",
            "message": "Session not found",
        }
    }
    foreign = {
        "error": {
            "code": "not_found",
            "message": "Session not found",
            "details": {"scope": "tenant"},
        }
    }
    busy = {
        "error": {
            "code": "session_busy",
            "message": "Session is busy",
        }
    }
    future = {
        "error": {
            "code": "future_session_domain_error",
            "message": "Future domain failure",
        }
    }
    with loopback(
        Response(status=204, raw_body=b""),
        Response(status=404, body=missing),
        Response(status=404, body=foreign),
        Response(status=204, raw_body=b""),
        Response(status=409, body=busy, headers={"x-request-id": "req_busy"}),
        Response(status=422, body=future),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            client.sessions.delete(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                delete_artifacts=True,
            )
            with pytest.raises(APIStatusError) as missing_error:
                client.sessions.delete(
                    agent_id=AGENT["id"],
                    session_id="ss_1123456789abcdef",
                    delete_artifacts=False,
                )
            with pytest.raises(APIStatusError) as foreign_error:
                client.sessions.delete(
                    agent_id=AGENT["id"],
                    session_id="ss_2123456789abcdef",
                    delete_artifacts=False,
                )

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                await client.sessions.delete(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    delete_artifacts=True,
                )
                with pytest.raises(APIStatusError) as busy_error:
                    await client.sessions.delete(
                        agent_id=AGENT["id"],
                        session_id="ss_3123456789abcdef",
                        delete_artifacts=False,
                    )
                with pytest.raises(APIStatusError) as future_error:
                    await client.sessions.delete(
                        agent_id=AGENT["id"],
                        session_id="ss_4123456789abcdef",
                        delete_artifacts=False,
                    )

            assert busy_error.value.code == "session_busy"
            assert busy_error.value.status_code == 409
            assert busy_error.value.request_id == "req_busy"
            assert future_error.value.code == "future_session_domain_error"

        asyncio.run(exercise())

    assert missing_error.value.code == "not_found"
    assert foreign_error.value.code == "not_found"
    assert foreign_error.value.details == {"scope": "tenant"}
    assert [request.method for request in state.requests] == ["DELETE"] * 6


def test_session_pages_reject_malformed_documented_fields() -> None:
    invalid_session = {**SESSION, "messageCount": -1}
    invalid_role = {**SESSION_MESSAGES[0], "role": "tool"}
    invalid_message: dict[str, Any] = {
        **SESSION_MESSAGES[0],
        "parts": [],
    }
    with loopback(
        Response(body={"data": [invalid_session], "nextCursor": None}),
        Response(
            body={
                "data": [invalid_role],
                "nextCursor": None,
                "latestCursor": "tail",
            }
        ),
        Response(
            body={
                "data": [invalid_message],
                "nextCursor": None,
                "latestCursor": "tail",
            }
        ),
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(ValidationError):
                client.sessions.list(agent_id=AGENT["id"])
            with pytest.raises(ValidationError):
                client.sessions.messages(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                )

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(ValidationError):
                    await client.sessions.messages(
                        agent_id=AGENT["id"],
                        session_id=SESSION["id"],
                    )

        asyncio.run(exercise())


def test_session_models_and_request_options_are_public() -> None:
    list_options: SessionsListOptions = {
        "user_id": "end-user",
        "cursor": "next",
        "limit": 25,
    }
    message_options: SessionMessagesOptions = {
        "cursor": "older",
        "limit": 10,
    }
    session = Session.model_validate_json(json.dumps(SESSION))
    message = SessionMessage.model_validate_json(json.dumps(SESSION_MESSAGES[0]))
    part = SessionMessagePart.model_validate_json(
        json.dumps(SESSION_MESSAGES[0]["parts"][0])
    )
    sessions_page = SessionsPage.model_validate_json(
        json.dumps({"data": [SESSION], "nextCursor": None})
    )
    messages_page = SessionMessagesPage.model_validate_json(
        json.dumps(
            {
                "data": SESSION_MESSAGES,
                "nextCursor": None,
                "latestCursor": "tail",
            }
        )
    )

    assert list_options["user_id"] == session.user_id
    assert message_options["cursor"] == "older"
    assert message.parts[0].type == part.type
    assert sessions_page.data == [session]
    assert messages_page.data[0] == message


def test_sync_chat_create_relays_exact_bytes_and_exposes_headers_immediately() -> None:
    chunks = (
        b'data: {"type":"text-delta","delta":"',
        b'\xff"}\n\ndata: future malformed event\n\n',
        b"data: [DONE]\n\n",
    )
    gate = Event()
    with loopback(
        Response(
            status=201,
            chunks=chunks,
            chunk_delay=0.05,
            chunk_gate=gate,
            headers={
                "content-type": "text/event-stream",
                "location": (
                    "/v1/agents/ag_0123456789abcdef/sessions/ss_1123456789abcdef"
                ),
                "x-request-id": "req_chat_create",
                "x-future-header": "preserved",
            },
        )
    ) as (base_url, state):
        with BlazingAgents(
            api_key="ba_test",
            base_url=base_url,
            timeout=0.01,
        ) as client:
            stream = client.chat(
                agent_id=AGENT["id"],
                message={
                    "id": "user-message",
                    "role": "user",
                    "parts": [{"type": "text", "text": "hello"}],
                },
                version=3,
                user_id="end-user",
                metadata={"OpaqueKey": {"nested_key": True}},
                extra_headers={"x-client-request-id": "caller-attempt"},
            )
            assert isinstance(stream, ChatStream)
            assert stream.status_code == 201
            assert stream.session_id == "ss_1123456789abcdef"
            assert stream.request_id == "req_chat_create"
            assert stream.headers["x-future-header"] == "preserved"
            body = iter(stream)
            assert next(body) == chunks[0]
            gate.set()
            assert b"".join((chunks[0], *body)) == b"".join(chunks)
            assert stream.closed is True
            with pytest.raises(StreamError, match="already"):
                iter(stream)

    request = state.requests[0]
    assert request.method == "POST"
    assert request.target == "/v1/agents/ag_0123456789abcdef/sessions"
    assert request.headers["x-client-request-id"] == "caller-attempt"
    assert json.loads(request.body) == {
        "message": {
            "id": "user-message",
            "role": "user",
            "parts": [{"type": "text", "text": "hello"}],
        },
        "version": 3,
        "userId": "end-user",
        "metadata": {"OpaqueKey": {"nested_key": True}},
    }


def test_sync_chat_resume_supports_prompt_input_and_retains_session_id() -> None:
    chunks = (b"data: not-json\n", b"\nunknown bytes")
    with loopback(
        Response(
            chunks=chunks,
            headers={
                "content-type": "text/event-stream",
                "x-request-id": "req_chat_resume",
            },
        )
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            stream = client.chat(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                prompt_id=PROMPT["id"],
                variables={"name": "Ada"},
                trigger="regenerate-message",
                message_id="user-message",
                user_id="end-user",
                metadata={"source": "resume"},
            )
            assert stream.session_id == SESSION["id"]
            assert stream.status_code == 200
            assert stream.request_id == "req_chat_resume"
            assert b"".join(stream) == b"".join(chunks)

    assert state.requests[0].target == (
        "/v1/agents/ag_0123456789abcdef/sessions/ss_0123456789abcdef"
    )
    assert json.loads(state.requests[0].body) == {
        "promptId": "prompt_0123456789abcdef",
        "variables": {"name": "Ada"},
        "trigger": "regenerate-message",
        "messageId": "user-message",
        "userId": "end-user",
        "metadata": {"source": "resume"},
    }


def test_sync_chat_validates_create_location_and_request_shapes() -> None:
    with loopback(
        Response(
            status=201,
            chunks=(b"unused",),
            headers={"x-request-id": "req_missing_location"},
        ),
        Response(
            status=201,
            chunks=(b"unused",),
            headers={
                "location": "/v1/agents/ag_0123456789abcdef/sessions/not-a-session",
                "x-request-id": "req_bad_location",
            },
        ),
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(StreamError, match="Location header") as missing:
                client.chat(agent_id=AGENT["id"], message={"role": "user"})
            with pytest.raises(StreamError, match="malformed") as malformed:
                client.chat(agent_id=AGENT["id"], prompt_id=PROMPT["id"])
            assert missing.value.status_code == 201
            assert missing.value.request_id == "req_missing_location"
            assert missing.value.headers["x-request-id"] == "req_missing_location"
            assert malformed.value.request_id == "req_bad_location"

            with pytest.raises(ValueError, match="exactly one"):
                client.chat(
                    agent_id=AGENT["id"],
                    message={"role": "user"},
                    prompt_id=PROMPT["id"],
                )
            with pytest.raises(ValueError, match="exactly one"):
                client.chat(agent_id=AGENT["id"])
            with pytest.raises(ValueError, match="variables"):
                client.chat(
                    agent_id=AGENT["id"],
                    message={"role": "user"},
                    variables={"name": "Ada"},
                )
            with pytest.raises(ValueError, match="Version Pin"):
                client.chat(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    message={"role": "user"},
                    version=3,
                )
            with pytest.raises(ValueError, match="regenerate"):
                cast(Any, client).chat(
                    agent_id=AGENT["id"],
                    message={"role": "user"},
                    trigger="regenerate-message",
                )
            with pytest.raises(ValueError, match="trigger"):
                client.chat(
                    agent_id=AGENT["id"],
                    message={"role": "user"},
                    trigger=cast(Any, "future-trigger"),
                )
            with pytest.raises(ValueError, match="message_id"):
                client.chat(
                    agent_id=AGENT["id"],
                    message={"role": "user"},
                    message_id="",
                )


def test_sync_chat_close_cancels_and_failures_do_not_allow_body_reuse() -> None:
    gate = Event()
    cancelled = Event()
    error = {
        "error": {
            "code": "invalid_request",
            "message": "Bad chat input",
            "details": {"field": "message"},
        }
    }
    with loopback(
        Response(
            status=201,
            chunks=(b"first", b"server-still-working"),
            chunk_gate=gate,
            cancelled=cancelled,
            headers={
                "location": (
                    "/v1/agents/ag_0123456789abcdef/sessions/ss_2123456789abcdef"
                )
            },
        ),
        Response(
            status=201,
            chunks=(b"partial",),
            complete_chunks=False,
            headers={
                "location": (
                    "/v1/agents/ag_0123456789abcdef/sessions/ss_3123456789abcdef"
                ),
                "x-request-id": "req_chat_read_failure",
            },
        ),
        Response(chunks=(b"context",)),
        Response(
            body=error,
            status=422,
            headers={"x-request-id": "req_chat_status"},
        ),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            stream = client.chat(agent_id=AGENT["id"], message={"role": "user"})
            body = iter(stream)
            assert next(body) == b"first"
            stream.close()
            assert stream.closed is True
            gate.set()
            assert cancelled.wait(timeout=1)
            with pytest.raises(StreamError, match="already"):
                iter(stream)

            failed = client.chat(agent_id=AGENT["id"], message={"role": "user"})
            failed_body = iter(failed)
            assert next(failed_body) == b"partial"
            with pytest.raises(StreamError, match="read failed") as read_failure:
                next(failed_body)
            assert failed.closed is True
            assert read_failure.value.request_id == "req_chat_read_failure"
            with pytest.raises(StreamError, match="already"):
                iter(failed)

            context_stream = client.chat(
                agent_id=AGENT["id"],
                session_id=SESSION["id"],
                message={"role": "user"},
            )
            with context_stream:
                pass
            assert context_stream.closed is True

            with pytest.raises(APIStatusError) as status_error:
                client.chat(agent_id=AGENT["id"], message={"role": "user"})

    assert status_error.value.code == "invalid_request"
    assert status_error.value.request_id == "req_chat_status"
    assert json.loads(status_error.value.response_body) == error
    assert len(state.requests) == 4

    with BlazingAgents(
        api_key="ba_test",
        base_url=_unused_origin(),
    ) as client:
        with pytest.raises(APIConnectionError):
            client.chat(agent_id=AGENT["id"], message={"role": "user"})


def test_async_chat_matches_create_resume_relay_and_lifecycle() -> None:
    create_chunks = (b"data: create-", b"\xff\n\n")
    resume_chunks = (b"data: resume\n\n",)
    gate = Event()
    cancelled = Event()
    with loopback(
        Response(
            status=201,
            chunks=create_chunks,
            chunk_delay=0.05,
            headers={
                "location": (
                    "/v1/agents/ag_0123456789abcdef/sessions/ss_4123456789abcdef"
                ),
                "x-request-id": "req_async_create",
            },
        ),
        Response(
            chunks=resume_chunks,
            headers={"x-request-id": "req_async_resume"},
        ),
        Response(
            chunks=(b"first", b"server-still-working"),
            chunk_gate=gate,
            cancelled=cancelled,
        ),
        Response(chunks=(b"context",)),
        Response(
            chunks=(b"partial",),
            complete_chunks=False,
            headers={"x-request-id": "req_async_read_failure"},
        ),
        Response(status=201, chunks=(b"unused",)),
        Response(
            status=201,
            chunks=(b"unused",),
            headers={"location": "/sessions/not-a-session"},
        ),
        Response(
            status=429,
            body={
                "error": {
                    "code": "quota_exceeded",
                    "message": "Try later",
                }
            },
            headers={"x-request-id": "req_async_status", "retry-after": "3"},
        ),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
                timeout=0.01,
            ) as client:
                created = await client.chat(
                    agent_id=AGENT["id"],
                    prompt_id=PROMPT["id"],
                    variables={"name": "Ada"},
                    version=4,
                    user_id="end-user",
                    metadata={"OpaqueKey": True},
                )
                assert isinstance(created, AsyncChatStream)
                assert created.session_id == "ss_4123456789abcdef"
                assert created.status_code == 201
                assert created.request_id == "req_async_create"
                assert b"".join([chunk async for chunk in created]) == b"".join(
                    create_chunks
                )
                assert created.closed is True
                with pytest.raises(StreamError, match="already"):
                    created.__aiter__()

                resumed = await client.chat(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    message={"role": "user", "parts": []},
                )
                assert resumed.session_id == SESSION["id"]
                assert b"".join([chunk async for chunk in resumed]) == b"".join(
                    resume_chunks
                )

                live = await client.chat(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    message={"role": "user"},
                )
                body = live.__aiter__()
                assert await anext(body) == b"first"
                await live.aclose()
                gate.set()
                assert await asyncio.to_thread(cancelled.wait, 1)
                with pytest.raises(StreamError, match="already"):
                    live.__aiter__()

                context_stream = await client.chat(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    message={"role": "user"},
                )
                async with context_stream:
                    pass
                assert context_stream.closed is True

                failed = await client.chat(
                    agent_id=AGENT["id"],
                    session_id=SESSION["id"],
                    message={"role": "user"},
                )
                failed_body = failed.__aiter__()
                assert await anext(failed_body) == b"partial"
                with pytest.raises(StreamError, match="read failed") as read_failure:
                    await anext(failed_body)
                assert failed.closed is True
                assert read_failure.value.request_id == "req_async_read_failure"
                with pytest.raises(StreamError, match="already"):
                    failed.__aiter__()

                with pytest.raises(StreamError, match="Location header") as missing:
                    await client.chat(
                        agent_id=AGENT["id"],
                        message={"role": "user"},
                    )
                with pytest.raises(StreamError, match="malformed") as malformed:
                    await client.chat(
                        agent_id=AGENT["id"],
                        prompt_id=PROMPT["id"],
                    )
                assert missing.value.status_code == 201
                assert malformed.value.status_code == 201

                with pytest.raises(APIStatusError) as status_error:
                    await client.chat(
                        agent_id=AGENT["id"],
                        message={"role": "user"},
                    )
                assert status_error.value.request_id == "req_async_status"
                assert status_error.value.retry_after == "3"

        asyncio.run(exercise())

    async def reject_connection() -> None:
        async with AsyncBlazingAgents(
            api_key="ba_test",
            base_url=_unused_origin(),
        ) as client:
            with pytest.raises(APIConnectionError):
                await client.chat(
                    agent_id=AGENT["id"],
                    message={"role": "user"},
                )

    asyncio.run(reject_connection())

    assert json.loads(state.requests[0].body) == {
        "promptId": "prompt_0123456789abcdef",
        "variables": {"name": "Ada"},
        "version": 4,
        "userId": "end-user",
        "metadata": {"OpaqueKey": True},
    }
    assert json.loads(state.requests[1].body) == {
        "message": {"role": "user", "parts": []},
    }


def test_chat_input_types_ship_in_the_installed_wheel() -> None:
    trigger: ChatTrigger = "regenerate-message"
    message: ChatMessageInput = {
        "agent_id": AGENT["id"],
        "message": {"role": "user", "parts": []},
        "version": 3,
        "user_id": "end-user",
        "metadata": {"OpaqueKey": True},
    }
    prompt: ChatPromptInput = {
        "agent_id": AGENT["id"],
        "session_id": SESSION["id"],
        "prompt_id": PROMPT["id"],
        "variables": {"name": "Ada"},
        "trigger": trigger,
        "message_id": "user-message",
    }

    assert message["version"] == 3
    assert prompt["prompt_id"] == PROMPT["id"]
    assert callable(_sync_chat_context_typing)
    assert callable(_async_chat_context_typing)


def _sync_chat_context_typing(client: BlazingAgents) -> None:
    with client.chat(
        agent_id=AGENT["id"],
        message={"role": "user"},
    ) as stream:
        session_id: str = stream.session_id
        assert session_id


async def _async_chat_context_typing(client: AsyncBlazingAgents) -> None:
    async with await client.chat(
        agent_id=AGENT["id"],
        message={"role": "user"},
    ) as stream:
        session_id: str = stream.session_id
        assert session_id


def test_sync_buffered_completion_accepts_literal_and_stored_prompt() -> None:
    with loopback(
        Response(
            raw_body="Hello, 世界".encode(),
            headers={"x-request-id": "req_completion_literal"},
        ),
        Response(raw_body=b"", headers={"x-request-id": "req_completion_prompt"}),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            literal = client.completion(
                agent_id="ag_0123456789abcdef",
                prompt="Say hello",
                version=4,
                user_id="end-user",
                metadata={"OpaqueKey": {"nested_key": True}},
            )
            stored = client.completion(
                agent_id="agent/with space",
                prompt_id="prompt_0123456789abcdef",
                variables={"name": "Ada"},
            )

    assert literal == "Hello, 世界"
    assert literal.request_id == "req_completion_literal"
    assert stored == ""
    assert stored.request_id == "req_completion_prompt"
    assert state.requests[0].target == ("/v1/agents/ag_0123456789abcdef/generation")
    assert json.loads(state.requests[0].body) == {
        "prompt": "Say hello",
        "output": {"type": "text"},
        "version": 4,
        "userId": "end-user",
        "metadata": {"OpaqueKey": {"nested_key": True}},
    }
    assert state.requests[1].target == "/v1/agents/agent%2Fwith%20space/generation"
    assert json.loads(state.requests[1].body) == {
        "promptId": "prompt_0123456789abcdef",
        "variables": {"name": "Ada"},
        "output": {"type": "text"},
    }


def test_sync_completion_stream_decodes_incrementally_and_drains_final_text() -> None:
    gate = Event()
    with loopback(
        Response(
            chunks=(b"A\xf0\x9f", b"\x98\x80B"),
            chunk_gate=gate,
            chunk_delay=0.05,
            headers={
                "content-type": "text/plain; charset=utf-8",
                "x-request-id": "req_completion_stream",
            },
        ),
        Response(chunks=(b"early ", b"final")),
        Response(chunks=(b"part ", b"rest")),
    ) as (base_url, _):
        with BlazingAgents(
            api_key="ba_test",
            base_url=base_url,
            timeout=0.01,
        ) as client:
            stream = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Stream",
            )
            assert stream.status_code == 200
            assert stream.request_id == "req_completion_stream"
            assert stream.content_type == "text/plain; charset=utf-8"
            deltas = iter(stream)
            assert next(deltas) == "A"
            gate.set()
            assert list(deltas) == ["😀B"]
            final = stream.get_final_text()
            assert final == "A😀B"
            assert final.request_id == "req_completion_stream"
            assert stream.closed is True
            with pytest.raises(StreamError, match="already"):
                iter(stream)

            early = client.completion_stream(
                agent_id=AGENT["id"],
                prompt_id=PROMPT["id"],
            )
            assert early.get_final_text() == "early final"
            assert early.closed is True

            partial = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Partial",
            )
            partial_deltas = iter(partial)
            assert next(partial_deltas) == "part "
            assert partial.get_final_text() == "part rest"
            assert partial.closed is True


def test_async_completion_matches_buffered_and_streaming_behavior() -> None:
    with loopback(
        Response(
            raw_body=b"async buffered",
            headers={"x-request-id": "req_async_completion"},
        ),
        Response(
            chunks=(b"\xe2", b"\x82\xac!"),
            headers={"x-request-id": "req_async_completion_stream"},
        ),
        Response(chunks=(b"one", b" two")),
        Response(chunks=(b"part ", b"rest")),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                buffered = await client.completion(
                    agent_id=AGENT["id"],
                    prompt="Buffer",
                )
                assert buffered == "async buffered"
                assert buffered.request_id == "req_async_completion"

                early = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt_id=PROMPT["id"],
                    variables={"name": "Ada"},
                )
                final = await early.get_final_text()
                assert final == "€!"
                assert final.request_id == "req_async_completion_stream"
                assert early.closed is True

                stream = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Iterate",
                )
                assert [delta async for delta in stream] == ["one", " two"]
                assert await stream.get_final_text() == "one two"
                with pytest.raises(StreamError, match="already"):
                    stream.__aiter__()

                partial = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Partial",
                )
                partial_deltas = partial.__aiter__()
                assert await anext(partial_deltas) == "part "
                assert await partial.get_final_text() == "part rest"
                assert partial.closed is True

        asyncio.run(exercise())

    assert json.loads(state.requests[1].body) == {
        "promptId": "prompt_0123456789abcdef",
        "variables": {"name": "Ada"},
        "output": {"type": "text"},
    }


def test_sync_completion_stream_closes_cancels_and_preserves_failures() -> None:
    gate = Event()
    cancelled = Event()
    api_error = {
        "error": {
            "code": "quota_exceeded",
            "message": "Try later",
        }
    }
    with loopback(
        Response(
            chunks=(b"first", b"second"),
            chunk_gate=gate,
            cancelled=cancelled,
        ),
        Response(chunks=(b"unused",)),
        Response(chunks=(b"unused",)),
        Response(
            chunks=(b"partial",),
            complete_chunks=False,
            headers={
                "x-request-id": "req_completion_read_failure",
                "retry-after": "7",
            },
        ),
        Response(
            body=api_error,
            status=429,
            headers={"x-request-id": "req_completion_status"},
        ),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            live = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Cancel",
            )
            live_body = iter(live)
            assert next(live_body) == "first"
            live.close()
            gate.set()
            assert cancelled.wait(timeout=1)
            assert live.closed is True

            context_stream = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Context",
            )
            with context_stream:
                pass
            assert context_stream.closed is True

            explicit = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Explicit",
            )
            explicit.close()
            with pytest.raises(StreamError, match="closed"):
                explicit.get_final_text()

            failed = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Fail",
            )
            failed_body = iter(failed)
            assert next(failed_body) == "partial"
            with pytest.raises(StreamError, match="read failed") as read_failure:
                next(failed_body)
            assert read_failure.value.request_id == "req_completion_read_failure"
            assert read_failure.value.retry_after == "7"
            with pytest.raises(StreamError) as repeated:
                failed.get_final_text()
            assert repeated.value is read_failure.value

            with pytest.raises(APIStatusError) as status_error:
                client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Status",
                )
            assert status_error.value.code == "quota_exceeded"
            assert status_error.value.request_id == "req_completion_status"

    assert len(state.requests) == 5

    with BlazingAgents(
        api_key="ba_test",
        base_url=_unused_origin(),
    ) as unavailable:
        with pytest.raises(APIConnectionError):
            unavailable.completion_stream(
                agent_id=AGENT["id"],
                prompt="Connection",
            )


def test_async_completion_stream_closes_cancels_and_preserves_failures() -> None:
    gate = Event()
    cancelled = Event()
    with loopback(
        Response(
            chunks=(b"first", b"second"),
            chunk_gate=gate,
            cancelled=cancelled,
        ),
        Response(chunks=(b"unused",)),
        Response(chunks=(b"unused",)),
        Response(
            chunks=(b"partial",),
            complete_chunks=False,
            headers={"x-request-id": "req_async_completion_failure"},
        ),
        Response(
            body={"error": {"code": "agent_disabled", "message": "Disabled"}},
            status=409,
            headers={"x-request-id": "req_async_completion_status"},
        ),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                live = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Cancel",
                )
                live_body = live.__aiter__()
                assert await anext(live_body) == "first"
                await live.aclose()
                gate.set()
                assert await asyncio.to_thread(cancelled.wait, 1)

                context_stream = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Context",
                )
                async with context_stream:
                    pass
                assert context_stream.closed is True

                explicit = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Explicit",
                )
                await explicit.aclose()
                with pytest.raises(StreamError, match="closed"):
                    await explicit.get_final_text()

                failed = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Fail",
                )
                failed_body = failed.__aiter__()
                assert await anext(failed_body) == "partial"
                with pytest.raises(StreamError) as read_failure:
                    await anext(failed_body)
                assert read_failure.value.request_id == ("req_async_completion_failure")
                with pytest.raises(StreamError) as repeated:
                    await failed.get_final_text()
                assert repeated.value is read_failure.value

                with pytest.raises(APIStatusError) as status_error:
                    await client.completion_stream(
                        agent_id=AGENT["id"],
                        prompt="Status",
                    )
                assert status_error.value.code == "agent_disabled"
                assert status_error.value.request_id == ("req_async_completion_status")

        asyncio.run(exercise())

    assert len(state.requests) == 5


def test_completion_stream_final_text_requires_terminal_completion() -> None:
    cancellation_gate = Event()
    with loopback(
        Response(
            chunks=(b"partial", b"rest"),
            chunk_gate=cancellation_gate,
        ),
        Response(raw_body=b""),
    ) as (base_url, _):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                interrupted = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Interrupted final",
                )
                interrupted_body = interrupted.__aiter__()
                assert await anext(interrupted_body) == "partial"
                final_task = asyncio.create_task(interrupted.get_final_text())
                await asyncio.sleep(0)
                final_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await final_task
                cancellation_gate.set()
                with pytest.raises(StreamError, match="did not complete"):
                    await interrupted.get_final_text()

        asyncio.run(exercise())

        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            empty = client.completion_stream(
                agent_id=AGENT["id"],
                prompt="Empty",
            )
            assert list(empty) == []
            assert empty.get_final_text() == ""


def test_async_empty_completion_stream_returns_empty_final_text() -> None:
    with loopback(Response(raw_body=b"")) as (base_url, _):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                empty = await client.completion_stream(
                    agent_id=AGENT["id"],
                    prompt="Empty",
                )
                assert [delta async for delta in empty] == []
                assert await empty.get_final_text() == ""

        asyncio.run(exercise())


def test_completion_types_ship_in_the_installed_wheel() -> None:
    literal: CompletionLiteralInput = {
        "agent_id": AGENT["id"],
        "prompt": "Hello",
        "version": 2,
        "user_id": "end-user",
        "metadata": {"OpaqueKey": True},
    }
    stored: CompletionPromptInput = {
        "agent_id": AGENT["id"],
        "prompt_id": PROMPT["id"],
        "variables": {"name": "Ada"},
    }

    assert literal["prompt"] == "Hello"
    assert stored["prompt_id"] == PROMPT["id"]
    assert callable(_sync_completion_typing)
    assert callable(_async_completion_typing)


def _sync_completion_typing(client: BlazingAgents) -> None:
    result: Completion = client.completion(
        agent_id=AGENT["id"],
        prompt="Typed",
    )
    assert result
    stream: CompletionStream = client.completion_stream(
        agent_id=AGENT["id"],
        prompt="Typed stream",
    )
    with stream:
        delta: str = next(iter(stream))
        assert delta


async def _async_completion_typing(client: AsyncBlazingAgents) -> None:
    result: Completion = await client.completion(
        agent_id=AGENT["id"],
        prompt="Typed",
    )
    assert result
    stream: AsyncCompletionStream = await client.completion_stream(
        agent_id=AGENT["id"],
        prompt="Typed stream",
    )
    async with stream:
        delta: str = await anext(stream.__aiter__())
        assert delta


class GeneratedPerson(BaseModel):
    name: str
    age: int


class RecursiveNode(BaseModel):
    value: int
    next: RecursiveNode | None = None


PERSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


def test_sync_buffered_objects_validate_typed_and_raw_modes() -> None:
    with loopback(
        Response(
            raw_body=b'{"name":"Ada","age":36}',
            headers={"x-request-id": "req_typed_object"},
        ),
        Response(raw_body=b'[1,{"OpaqueKey":true}]'),
        Response(raw_body=b"null"),
        Response(raw_body=b"5"),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            person: GeneratedPerson = client.object(
                agent_id=AGENT["id"],
                prompt="Invent a person",
                output_type=GeneratedPerson,
                version=3,
                user_id="end-user",
                metadata={"OpaqueKey": {"nested_key": True}},
            )
            raw: JsonValue = client.object(
                agent_id="agent/with space",
                prompt_id=PROMPT["id"],
                variables={"name": "Ada"},
                json_schema=PERSON_SCHEMA,
            )
            optional_number = cast(Any, client).object(
                agent_id="ag_0123456789abcdef",
                prompt="Optional number",
                output_type=int | None,
            )
            positive_number = cast(Any, client).object(
                agent_id="ag_0123456789abcdef",
                prompt="Positive number",
                output_type=Annotated[int, "positive"],
            )
            with pytest.raises(ValueError, match="exactly one"):
                cast(Any, client).object(
                    agent_id=AGENT["id"],
                    prompt="Missing mode",
                )
            with pytest.raises(ValueError, match="exactly one"):
                cast(Any, client).object(
                    agent_id=AGENT["id"],
                    prompt="Both modes",
                    output_type=GeneratedPerson,
                    json_schema=PERSON_SCHEMA,
                )

    assert person == GeneratedPerson(name="Ada", age=36)
    assert raw == [1, {"OpaqueKey": True}]
    assert optional_number is None
    assert positive_number == 5
    typed_body = json.loads(state.requests[0].body)
    assert typed_body["output"]["type"] == "object"
    assert typed_body["output"]["schema"]["properties"]["name"] == {
        "title": "Name",
        "type": "string",
    }
    assert typed_body["version"] == 3
    assert typed_body["userId"] == "end-user"
    assert typed_body["metadata"] == {"OpaqueKey": {"nested_key": True}}
    assert state.requests[1].target == "/v1/agents/agent%2Fwith%20space/generation"
    assert json.loads(state.requests[1].body) == {
        "promptId": PROMPT["id"],
        "variables": {"name": "Ada"},
        "output": {"type": "object", "schema": PERSON_SCHEMA},
    }
    assert json.loads(state.requests[2].body)["output"]["schema"] == {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
    }


def test_sync_object_stream_yields_raw_text_and_drains_for_typed_final() -> None:
    with loopback(
        Response(
            chunks=(b'{"name":"A', b'da","age":', b"36}"),
            headers={"x-request-id": "req_object_stream"},
        ),
        Response(chunks=(b'{"name":"Grace",', b'"age":40}')),
        Response(chunks=(b'{"name":"Lin', b'","age":28}')),
        Response(chunks=(b"unused",)),
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            stream: ObjectStream[GeneratedPerson] = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Stream person",
                output_type=GeneratedPerson,
            )
            deltas = list(stream)
            assert deltas == ['{"name":"A', 'da","age":', "36}"]
            assert stream.get_final_object() == GeneratedPerson(name="Ada", age=36)
            assert stream.get_final_object() == GeneratedPerson(name="Ada", age=36)
            assert stream.request_id == "req_object_stream"
            assert stream.closed is True
            with pytest.raises(StreamError, match="already"):
                iter(stream)

            untouched = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Drain untouched",
                output_type=GeneratedPerson,
            )
            assert untouched.get_final_object() == GeneratedPerson(
                name="Grace",
                age=40,
            )

            partial = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Drain partial",
                output_type=GeneratedPerson,
            )
            partial_deltas = iter(partial)
            assert next(partial_deltas) == '{"name":"Lin'
            assert partial.get_final_object() == GeneratedPerson(name="Lin", age=28)

            context_stream = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Context close",
                json_schema=PERSON_SCHEMA,
            )
            with context_stream:
                pass
            assert context_stream.closed is True


def test_recursive_output_type_schemas_are_wire_compatible() -> None:
    with loopback(
        Response(raw_body=b'{"value":1}'),
        Response(chunks=(b'{"value":2}',)),
        Response(raw_body=b'{"value":3}'),
        Response(chunks=(b'{"value":4}',)),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            assert client.object(
                agent_id=AGENT["id"],
                prompt="Recursive buffered",
                output_type=RecursiveNode,
            ) == RecursiveNode(value=1)
            stream = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Recursive stream",
                output_type=RecursiveNode,
            )
            assert list(stream) == ['{"value":2}']
            assert stream.get_final_object() == RecursiveNode(value=2)

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                assert await client.object(
                    agent_id=AGENT["id"],
                    prompt="Recursive async buffered",
                    output_type=RecursiveNode,
                ) == RecursiveNode(value=3)
                stream = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Recursive async stream",
                    output_type=RecursiveNode,
                )
                assert [delta async for delta in stream] == ['{"value":4}']
                assert await stream.get_final_object() == RecursiveNode(value=4)

        asyncio.run(exercise())

    for request in state.requests:
        schema = json.loads(request.body)["output"]["schema"]
        assert schema["$ref"] == "#/$defs/RecursiveNode"
        assert (
            schema["$defs"]["RecursiveNode"]["properties"]["next"]["anyOf"][0]["$ref"]
            == "#/$defs/RecursiveNode"
        )


def test_composition_root_object_stream_requests_are_wire_compatible() -> None:
    with loopback(
        Response(chunks=(b"null",)),
        Response(chunks=(b"5",)),
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            stream = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Optional number",
                output_type=int | None,
            )
            assert list(stream) == ["null"]
            assert stream.get_final_object() is None

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                stream = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Optional number",
                    output_type=int | None,
                )
                assert [delta async for delta in stream] == ["5"]
                assert await stream.get_final_object() == 5

        asyncio.run(exercise())

    for request in state.requests:
        assert json.loads(request.body)["output"]["schema"] == {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
        }


def test_sync_object_failures_are_distinct_and_preserve_metadata() -> None:
    with loopback(
        Response(
            chunks=(b'{"name":',),
            headers={"x-request-id": "req_object_truncated"},
        ),
        Response(
            chunks=(b'{"name": nope}',),
            headers={"x-request-id": "req_object_invalid"},
        ),
        Response(
            chunks=(b'{"name":"Ada","age":"old"}',),
            headers={"x-request-id": "req_object_validation"},
        ),
        Response(
            chunks=(b'{"name":"Ada"',),
            complete_chunks=False,
            headers={
                "x-request-id": "req_object_transport",
                "retry-after": "9",
            },
        ),
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            truncated = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Truncate",
                output_type=GeneratedPerson,
            )
            with pytest.raises(ObjectTruncationError) as truncation:
                truncated.get_final_object()
            assert truncation.value.request_id == "req_object_truncated"

            invalid = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Invalid",
                output_type=GeneratedPerson,
            )
            with pytest.raises(ObjectJSONDecodeError) as invalid_json:
                invalid.get_final_object()
            assert invalid_json.value.request_id == "req_object_invalid"

            mismatched = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Wrong shape",
                output_type=GeneratedPerson,
            )
            with pytest.raises(ObjectValidationError) as validation:
                mismatched.get_final_object()
            assert validation.value.request_id == "req_object_validation"
            assert validation.value.validation_error.errors()[0]["loc"] == ("age",)
            with pytest.raises(ObjectValidationError) as repeated_validation:
                mismatched.get_final_object()
            assert repeated_validation.value is validation.value

            failed = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Transport failure",
                output_type=GeneratedPerson,
            )
            with pytest.raises(StreamError) as transport:
                failed.get_final_object()
            assert type(transport.value) is StreamError
            assert transport.value.request_id == "req_object_transport"
            assert transport.value.retry_after == "9"
            with pytest.raises(StreamError) as repeated:
                failed.get_final_object()
            assert repeated.value is transport.value


def test_sync_buffered_object_parse_and_validation_failures_have_metadata() -> None:
    with loopback(
        Response(
            raw_body=b'{"name": nope}',
            headers={"x-request-id": "req_buffered_invalid"},
        ),
        Response(
            raw_body=b'{"name":"Ada","age":null}',
            headers={"x-request-id": "req_buffered_validation"},
        ),
        Response(
            raw_body=b'{"ok": tru',
            headers={"x-request-id": "req_buffered_truncated_literal"},
        ),
        Response(
            raw_body=b'{"ok":NaN}',
            headers={"x-request-id": "req_buffered_non_json_number"},
        ),
        Response(
            raw_body=b"[1e",
            headers={"x-request-id": "req_buffered_truncated_number"},
        ),
        Response(
            raw_body=b'{"n": 1.e',
            headers={"x-request-id": "req_buffered_invalid_number"},
        ),
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(ObjectJSONDecodeError) as invalid:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Invalid",
                    json_schema=PERSON_SCHEMA,
                )
            assert invalid.value.request_id == "req_buffered_invalid"

            with pytest.raises(ObjectValidationError) as validation:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Wrong shape",
                    output_type=GeneratedPerson,
                )
            assert validation.value.request_id == "req_buffered_validation"

            with pytest.raises(ObjectTruncationError) as truncated:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Truncated literal",
                    json_schema={"type": "object"},
                )
            assert truncated.value.request_id == "req_buffered_truncated_literal"

            with pytest.raises(ObjectJSONDecodeError) as non_json_number:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Non-JSON number",
                    json_schema={"type": "object"},
                )
            assert non_json_number.value.request_id == "req_buffered_non_json_number"

            with pytest.raises(ObjectTruncationError) as truncated_number:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Truncated number",
                    json_schema={"type": "array"},
                )
            assert truncated_number.value.request_id == (
                "req_buffered_truncated_number"
            )

            with pytest.raises(ObjectJSONDecodeError) as invalid_number:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Invalid number",
                    json_schema={"type": "object"},
                )
            assert invalid_number.value.request_id == "req_buffered_invalid_number"


def test_buffered_object_body_failures_preserve_post_header_metadata() -> None:
    with loopback(
        Response(
            chunks=(b'{"ok":',),
            complete_chunks=False,
            headers={
                "x-request-id": "req_buffered_sync_transport",
                "retry-after": "11",
                "x-test-header": "sync",
            },
        ),
        Response(
            chunks=(b'{"ok":',),
            complete_chunks=False,
            headers={
                "x-request-id": "req_buffered_async_transport",
                "retry-after": "12",
                "x-test-header": "async",
            },
        ),
    ) as (base_url, _):
        async_failures: list[StreamError] = []
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(StreamError) as sync_failure:
                client.object(
                    agent_id=AGENT["id"],
                    prompt="Sync transport failure",
                    json_schema={"type": "object"},
                )

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                with pytest.raises(StreamError) as async_failure:
                    await client.object(
                        agent_id=AGENT["id"],
                        prompt="Async transport failure",
                        json_schema={"type": "object"},
                    )
                async_failures.append(async_failure.value)

        asyncio.run(exercise())

    assert sync_failure.value.status_code == 200
    assert sync_failure.value.headers["x-test-header"] == "sync"
    assert sync_failure.value.request_id == "req_buffered_sync_transport"
    assert sync_failure.value.retry_after == "11"
    assert async_failures[0].status_code == 200
    assert async_failures[0].headers["x-test-header"] == "async"
    assert async_failures[0].request_id == "req_buffered_async_transport"
    assert async_failures[0].retry_after == "12"


def test_sync_object_stream_early_close_cancels_live_turn() -> None:
    gate = Event()
    cancelled = Event()
    with loopback(
        Response(
            chunks=(b'{"name":"Ada"', b',"age":36}'),
            chunk_gate=gate,
            cancelled=cancelled,
        )
    ) as (base_url, _):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            stream = client.object_stream(
                agent_id=AGENT["id"],
                prompt="Cancel",
                output_type=GeneratedPerson,
            )
            body = iter(stream)
            assert next(body) == '{"name":"Ada"'
            stream.close()
            gate.set()
            assert cancelled.wait(timeout=1)
            with pytest.raises(StreamError):
                stream.get_final_object()


def test_async_objects_match_sync_validation_and_lifecycle() -> None:
    gate = Event()
    cancelled = Event()
    cancellation_gate = Event()
    with loopback(
        Response(raw_body=b'{"name":"Ada","age":36}'),
        Response(raw_body=b'{"OpaqueKey":[1,true]}'),
        Response(
            chunks=(b'{"name":"Gr', b'ace","age":40}'),
            headers={"x-request-id": "req_async_object"},
        ),
        Response(chunks=(b'{"name":',)),
        Response(chunks=(b'{"name":"Ada","age":null}',)),
        Response(chunks=(b'{"name": nope}',)),
        Response(
            chunks=(b'{"name":"Ada"',),
            complete_chunks=False,
            headers={"x-request-id": "req_async_object_transport"},
        ),
        Response(chunks=(b'{"name":"Lin', b'","age":28}')),
        Response(chunks=(b"unused",)),
        Response(chunks=(b"unused",)),
        Response(
            chunks=(b'{"name":"Ada"', b',"age":36}'),
            chunk_gate=cancellation_gate,
        ),
        Response(
            chunks=(b'{"name":"Ada"', b',"age":36}'),
            chunk_gate=gate,
            cancelled=cancelled,
        ),
    ) as (base_url, state):

        async def exercise() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test",
                base_url=base_url,
            ) as client:
                person: GeneratedPerson = await client.object(
                    agent_id=AGENT["id"],
                    prompt="Typed",
                    output_type=GeneratedPerson,
                )
                assert person.age == 36
                raw: JsonValue = await client.object(
                    agent_id=AGENT["id"],
                    prompt_id=PROMPT["id"],
                    json_schema=PERSON_SCHEMA,
                )
                assert raw == {"OpaqueKey": [1, True]}

                stream: AsyncObjectStream[GeneratedPerson] = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Stream",
                    output_type=GeneratedPerson,
                )
                assert [delta async for delta in stream] == [
                    '{"name":"Gr',
                    'ace","age":40}',
                ]
                assert await stream.get_final_object() == GeneratedPerson(
                    name="Grace",
                    age=40,
                )
                assert stream.request_id == "req_async_object"

                truncated = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Truncated",
                    json_schema=PERSON_SCHEMA,
                )
                with pytest.raises(ObjectTruncationError):
                    await truncated.get_final_object()

                invalid = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Validation",
                    output_type=GeneratedPerson,
                )
                with pytest.raises(ObjectValidationError):
                    await invalid.get_final_object()

                malformed = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Invalid JSON",
                    json_schema=PERSON_SCHEMA,
                )
                with pytest.raises(ObjectJSONDecodeError):
                    await malformed.get_final_object()

                failed = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Transport failure",
                    output_type=GeneratedPerson,
                )
                with pytest.raises(StreamError) as transport:
                    await failed.get_final_object()
                assert type(transport.value) is StreamError
                assert transport.value.request_id == "req_async_object_transport"

                partial = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Partial drain",
                    output_type=GeneratedPerson,
                )
                partial_deltas = partial.__aiter__()
                assert await anext(partial_deltas) == '{"name":"Lin'
                assert await partial.get_final_object() == GeneratedPerson(
                    name="Lin",
                    age=28,
                )

                context_stream = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Context close",
                    json_schema=PERSON_SCHEMA,
                )
                async with context_stream:
                    pass
                assert context_stream.closed is True

                explicit = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Explicit close",
                    json_schema=PERSON_SCHEMA,
                )
                await explicit.aclose()
                with pytest.raises(StreamError, match="closed"):
                    await explicit.get_final_object()

                interrupted = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Interrupted final",
                    output_type=GeneratedPerson,
                )
                interrupted_body = interrupted.__aiter__()
                assert await anext(interrupted_body) == '{"name":"Ada"'
                final_task = asyncio.create_task(interrupted.get_final_object())
                await asyncio.sleep(0)
                final_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await final_task
                cancellation_gate.set()
                with pytest.raises(StreamError, match="did not complete"):
                    await interrupted.get_final_object()

                live = await client.object_stream(
                    agent_id=AGENT["id"],
                    prompt="Cancel",
                    output_type=GeneratedPerson,
                )
                live_body = live.__aiter__()
                assert await anext(live_body) == '{"name":"Ada"'
                await live.aclose()
                gate.set()
                assert await asyncio.to_thread(cancelled.wait, 1)

        asyncio.run(exercise())

    assert len(state.requests) == 12
