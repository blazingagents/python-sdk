"""Loopback HTTP server and shared response fixtures for the client tests."""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from typing import Any

import httpx

TENANT = {
    "name": "Blazing",
    "deletion": None,
    "monetizationEnabled": False,
}
AGENT: dict[str, Any] = {
    "id": "ag_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "name": "Builder",
    "thinkingLevel": None,
    "model": None,
    "providerId": None,
    "workspaceId": "ws_aaaaaaaaaaaaaaaa",
    "autoCompaction": True,
    "compactionReserveTokens": 16384,
    "memoryInjectionEnabled": False,
    "tools": ["read", "grep", "write_todos"],
    "instructions": "Build carefully.",
    "userId": "",
    "metadata": {},
    "mcpConnectionIds": [],
    "avatarUrl": None,
    "createdAt": "2026-08-02T00:00:00.000Z",
    "updatedAt": "2026-08-02T00:00:00.000Z",
    "status": "active",
}
TURN_ID = "turn_0123456789abcdef"
TASK: dict[str, Any] = {
    "id": "tk_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
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
    "nextFireAt": None,
    "userId": "end-user",
    "metadata": {"OpaqueKey": {"nested_key": True}},
    "deletedAt": None,
    "createdAt": "2026-08-01T00:00:00.000Z",
    "updatedAt": "2026-08-02T02:01:00.000Z",
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
    repeated_headers: tuple[tuple[str, str], ...] = ()
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
            for name, value in (*response.headers.items(), *response.repeated_headers):
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
