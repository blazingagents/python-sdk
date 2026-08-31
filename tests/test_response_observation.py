from __future__ import annotations

import asyncio

import httpx
import pytest

from blazing_agents import (
    APIConnectionError,
    APIStatusError,
    AsyncBlazingAgents,
    BlazingAgents,
    ResponseObservation,
)


def test_sync_response_observation_and_client_request_id() -> None:
    observations: list[ResponseObservation] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-client-request-id"] == "tenant-attempt-1"
        return httpx.Response(
            200,
            content=b"completed",
            headers={"x-request-id": "req_0123456789abcdef"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = BlazingAgents(
            api_key="ba_test",
            http_client=http_client,
            on_response=observations.append,
        )
        result = client.completion(
            agent_id="ag_0123456789abcdef",
            prompt="Hello",
            client_request_id="tenant-attempt-1",
        )

    assert str(result) == "completed"
    assert len(observations) == 1
    observation = observations[0]
    assert observation.method == "POST"
    assert observation.path == "/v1/agents/ag_0123456789abcdef/generation"
    assert observation.status == 200
    assert observation.duration_ms >= 0
    assert observation.request_id == "req_0123456789abcdef"
    assert observation.client_request_id == "tenant-attempt-1"


def test_sync_scopes_client_request_id_to_resource_client_view() -> None:
    observations: list[ResponseObservation] = []
    headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers.get("x-client-request-id"))
        return httpx.Response(
            200,
            json={"name": "Blazing", "quota": None},
            headers={"x-request-id": "req_0123456789abcdef"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = BlazingAgents(
            api_key="ba_test",
            http_client=http_client,
            on_response=observations.append,
        )
        scoped = client.with_options(client_request_id="management-attempt")
        scoped.tenant.get()
        client.tenant.get()
        scoped.close()

    assert headers == ["management-attempt", None]
    assert observations[0].client_request_id == "management-attempt"
    assert observations[1].client_request_id is None


@pytest.mark.parametrize(
    ("status", "body", "error_type"),
    [
        (
            400,
            b'{"error":{"code":"invalid_request","message":"bad"}}',
            APIStatusError,
        ),
        (200, b"not-json", Exception),
    ],
)
def test_sync_observes_errors_before_decoding(
    status: int, body: bytes, error_type: type[Exception]
) -> None:
    observations: list[ResponseObservation] = []
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            status,
            content=body,
            headers={"x-request-id": "req_0123456789abcdef"},
        )
    )
    with httpx.Client(transport=transport) as http_client:
        client = BlazingAgents(
            api_key="ba_test",
            http_client=http_client,
            on_response=observations.append,
        )
        with pytest.raises(error_type):
            client.tenant.get()
    assert len(observations) == 1


def test_sync_observes_stream_handshake_and_contains_hook_failure() -> None:
    calls = 0

    def on_response(_observation: ResponseObservation) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("hook failed")

    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=b"stream",
            headers={"x-request-id": "req_0123456789abcdef"},
        )
    )
    with httpx.Client(transport=transport) as http_client:
        client = BlazingAgents(
            api_key="ba_test",
            http_client=http_client,
            on_response=on_response,
        )
        stream = client.completion_stream(
            agent_id="ag_0123456789abcdef", prompt="Hello"
        )
        assert stream.request_id == "req_0123456789abcdef"
        stream.close()
    assert calls == 1


def test_sync_does_not_observe_transport_failure() -> None:
    observations: list[ResponseObservation] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = BlazingAgents(
            api_key="ba_test",
            http_client=http_client,
            on_response=observations.append,
        )
        with pytest.raises(APIConnectionError):
            client.tenant.get()
    assert observations == []


def test_async_response_observation() -> None:
    async def run() -> None:
        observations: list[ResponseObservation] = []
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                content=b"async",
                headers={"x-request-id": "req_0123456789abcdef"},
            )
        )
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = AsyncBlazingAgents(
                api_key="ba_test",
                http_client=http_client,
                on_response=observations.append,
            )
            result = await client.completion(
                agent_id="ag_0123456789abcdef",
                prompt="Hello",
                client_request_id="async-attempt",
            )
        assert str(result) == "async"
        assert observations[0].client_request_id == "async-attempt"

    asyncio.run(run())


def test_async_scopes_client_request_id_to_resource_client_view() -> None:
    async def run() -> None:
        observations: list[ResponseObservation] = []

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["x-client-request-id"] == "async-management-attempt"
            return httpx.Response(
                200,
                json={"name": "Blazing", "quota": None},
                headers={"x-request-id": "req_0123456789abcdef"},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = AsyncBlazingAgents(
                api_key="ba_test",
                http_client=http_client,
                on_response=observations.append,
            )
            scoped = client.with_options(client_request_id="async-management-attempt")
            await scoped.tenant.get()
            await scoped.aclose()
        assert observations[0].client_request_id == "async-management-attempt"

    asyncio.run(run())


def test_async_cancellation_without_response_is_not_observed() -> None:
    async def run() -> None:
        observations: list[ResponseObservation] = []

        async def handler(_request: httpx.Request) -> httpx.Response:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = AsyncBlazingAgents(
                api_key="ba_test",
                http_client=http_client,
                on_response=observations.append,
            )
            task = asyncio.create_task(client.tenant.get())
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert observations == []

    asyncio.run(run())


def test_sync_server_owns_request_id_header_and_preserves_correlation() -> None:
    observations: list[ResponseObservation] = []
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 3:
            return httpx.Response(
                200,
                content=b"completed",
                headers={"x-request-id": "req_generation"},
            )
        return httpx.Response(
            200,
            json={"name": "Blazing", "quota": None},
            headers={"x-request-id": f"req_tenant_{len(requests)}"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = BlazingAgents(
            api_key="ba_test",
            http_client=http_client,
            default_headers={
                "X-Request-Id": "caller-default-request",
                "X-Client-Request-Id": "default-correlation",
            },
            on_response=observations.append,
        )
        client.tenant.get()
        client.tenant.get(
            extra_headers={
                "X-Request-Id": "caller-operation-request",
                "X-Client-Request-Id": "operation-correlation",
            }
        )
        result = client.completion(
            agent_id="ag_0123456789abcdef",
            prompt="Hello",
            client_request_id="method-correlation",
            extra_headers={"X-Request-Id": "caller-generation-request"},
        )

    assert str(result) == "completed"
    assert [request.headers.get("x-request-id") for request in requests] == [
        None,
        None,
        None,
    ]
    assert [request.headers["x-client-request-id"] for request in requests] == [
        "default-correlation",
        "operation-correlation",
        "method-correlation",
    ]
    assert [observation.request_id for observation in observations] == [
        "req_tenant_1",
        "req_tenant_2",
        "req_generation",
    ]
    assert [observation.client_request_id for observation in observations] == [
        "default-correlation",
        "operation-correlation",
        "method-correlation",
    ]


def test_async_server_owns_request_id_header_and_preserves_correlation() -> None:
    async def run() -> None:
        observations: list[ResponseObservation] = []
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 3:
                return httpx.Response(
                    200,
                    content=b"completed",
                    headers={"x-request-id": "req_async_generation"},
                )
            return httpx.Response(
                200,
                json={"name": "Blazing", "quota": None},
                headers={"x-request-id": f"req_async_tenant_{len(requests)}"},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = AsyncBlazingAgents(
                api_key="ba_test",
                http_client=http_client,
                default_headers={
                    "X-Request-Id": "caller-default-request",
                    "X-Client-Request-Id": "default-correlation",
                },
                on_response=observations.append,
            )
            await client.tenant.get()
            await client.tenant.get(
                extra_headers={
                    "X-Request-Id": "caller-operation-request",
                    "X-Client-Request-Id": "operation-correlation",
                }
            )
            result = await client.completion(
                agent_id="ag_0123456789abcdef",
                prompt="Hello",
                client_request_id="method-correlation",
                extra_headers={"X-Request-Id": "caller-generation-request"},
            )

        assert str(result) == "completed"
        assert [request.headers.get("x-request-id") for request in requests] == [
            None,
            None,
            None,
        ]
        assert [request.headers["x-client-request-id"] for request in requests] == [
            "default-correlation",
            "operation-correlation",
            "method-correlation",
        ]
        assert [observation.request_id for observation in observations] == [
            "req_async_tenant_1",
            "req_async_tenant_2",
            "req_async_generation",
        ]
        assert [observation.client_request_id for observation in observations] == [
            "default-correlation",
            "operation-correlation",
            "method-correlation",
        ]

    asyncio.run(run())


def test_sync_rejects_injected_request_id_without_mutating_client() -> None:
    http_client = httpx.Client(
        headers={
            "X-ReQuEsT-Id": "caller-request",
            "X-Client-Request-Id": "caller-correlation",
        },
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"name": "Blazing"})
        ),
    )
    original_headers = dict(http_client.headers)

    with pytest.raises(ValueError, match="X-Request-Id"):
        BlazingAgents(api_key="ba_test", http_client=http_client)

    assert not http_client.is_closed
    assert dict(http_client.headers) == original_headers
    http_client.close()


def test_sync_preserves_injected_client_request_id_and_client_ownership() -> None:
    observations: list[ResponseObservation] = []
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"name": "Blazing", "quota": None})

    http_client = httpx.Client(
        headers={"X-Client-Request-Id": "caller-correlation"},
        transport=httpx.MockTransport(handler),
    )
    original_headers = dict(http_client.headers)

    with BlazingAgents(
        api_key="ba_test",
        http_client=http_client,
        on_response=observations.append,
    ) as client:
        client.tenant.get()

    assert requests[0].headers["x-client-request-id"] == "caller-correlation"
    assert observations[0].client_request_id == "caller-correlation"
    assert not http_client.is_closed
    assert dict(http_client.headers) == original_headers
    http_client.close()


def test_async_rejects_injected_request_id_without_mutating_client() -> None:
    async def run() -> None:
        http_client = httpx.AsyncClient(
            headers={
                "x-rEqUeSt-iD": "caller-request",
                "X-Client-Request-Id": "caller-correlation",
            },
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"name": "Blazing"})
            ),
        )
        original_headers = dict(http_client.headers)

        with pytest.raises(ValueError, match="X-Request-Id"):
            AsyncBlazingAgents(api_key="ba_test", http_client=http_client)

        assert not http_client.is_closed
        assert dict(http_client.headers) == original_headers
        await http_client.aclose()

    asyncio.run(run())


def test_async_preserves_injected_client_request_id_and_client_ownership() -> None:
    async def run() -> None:
        observations: list[ResponseObservation] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"name": "Blazing", "quota": None})

        async with httpx.AsyncClient(
            headers={"X-Client-Request-Id": "caller-correlation"},
            transport=httpx.MockTransport(handler),
        ) as http_client:
            original_headers = dict(http_client.headers)
            async with AsyncBlazingAgents(
                api_key="ba_test",
                http_client=http_client,
                on_response=observations.append,
            ) as client:
                await client.tenant.get()

            assert requests[0].headers["x-client-request-id"] == ("caller-correlation")
            assert observations[0].client_request_id == "caller-correlation"
            assert not http_client.is_closed
            assert dict(http_client.headers) == original_headers

    asyncio.run(run())
