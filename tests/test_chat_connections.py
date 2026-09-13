from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from test_clients import Response, loopback

from blazing_agents import APIStatusError, AsyncBlazingAgents, BlazingAgents

CONNECTION: dict[str, Any] = {
    "id": "cc_0123456789abcdef",
    "agentId": "ag_0123456789abcdef",
    "tenantId": "ten_0123456789abcdef",
    "name": "Support",
    "platform": "telegram",
    "enabled": False,
    "configuration": {
        "platform": "telegram",
        "botId": "123",
        "webhookUrl": "https://example.com/hook",
        "chatIds": [],
    },
    "identity": {"botId": "123", "botUserId": "123", "teamId": None, "appId": None},
    "health": {
        "checkedAt": "",
        "tokenValid": False,
        "identityVerified": False,
        "checks": [{"code": "webhook", "status": "unknown"}],
    },
    "credentialFragment": "abcd",
    "credentialVersion": 0,
    "createdAt": "2026-09-13T12:00:00Z",
    "updatedAt": "2026-09-13T12:00:00Z",
}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_connection_lifecycle(asynchronous: bool) -> None:
    with loopback(
        *[Response(body=CONNECTION) for _ in range(7)],
        Response(body={"chatConnections": [CONNECTION]}),
        Response(status=204),
    ) as (base_url, state):

        async def run_async() -> None:
            async with AsyncBlazingAgents(
                api_key="ba_test", base_url=base_url
            ) as client:
                resource = client.with_options(
                    client_request_id="connection-setup"
                ).chat_connections
                created = await resource.create(
                    name="Support",
                    agent_id=CONNECTION["agentId"],
                    platform="telegram",
                    configuration={
                        "bot_id": "123",
                        "webhook_url": "https://example.com/hook",
                    },
                    credentials={"bot_token": "123:secret", "webhook_secret": "secret"},
                    enabled=False,
                )
                assert created.configuration.platform == "telegram"
                assert created.health.checks[0].status == "unknown"
                await resource.update(
                    created.id, webhook_url="https://example.com/final"
                )
                await resource.rotate_credentials(
                    created.id,
                    platform="telegram",
                    credentials={
                        "bot_token": "123:newsecret",
                        "webhook_secret": "newsecret",
                    },
                )
                await resource.get(created.id)
                await resource.check_health(created.id)
                await resource.enable(created.id)
                await resource.disable(created.id)
                assert (await resource.list()).chat_connections[0].id == created.id
                await resource.delete(created.id)

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
                resource = client.with_options(
                    client_request_id="connection-setup"
                ).chat_connections
                created = resource.create(
                    name="Support",
                    agent_id=CONNECTION["agentId"],
                    platform="telegram",
                    configuration={
                        "bot_id": "123",
                        "webhook_url": "https://example.com/hook",
                    },
                    credentials={"bot_token": "123:secret", "webhook_secret": "secret"},
                    enabled=False,
                )
                assert created.configuration.platform == "telegram"
                assert created.health.checks[0].status == "unknown"
                resource.update(created.id, webhook_url="https://example.com/final")
                resource.rotate_credentials(
                    created.id,
                    platform="telegram",
                    credentials={
                        "bot_token": "123:newsecret",
                        "webhook_secret": "newsecret",
                    },
                )
                resource.get(created.id)
                resource.check_health(created.id)
                resource.enable(created.id)
                resource.disable(created.id)
                assert resource.list().chat_connections[0].id == created.id
                resource.delete(created.id)
    bodies = [
        json.loads(request.body) if request.body else None for request in state.requests
    ]
    assert bodies[0] == {
        "name": "Support",
        "agentId": CONNECTION["agentId"],
        "platform": "telegram",
        "configuration": {"botId": "123", "webhookUrl": "https://example.com/hook"},
        "credentials": {"botToken": "123:secret", "webhookSecret": "secret"},
        "enabled": False,
    }
    assert bodies[1] == {"webhookUrl": "https://example.com/final"}
    assert bodies[2] == {
        "platform": "telegram",
        "botToken": "123:newsecret",
        "webhookSecret": "newsecret",
    }
    assert [(request.method, request.target) for request in state.requests] == [
        (method, "/v1/chat-connections" + path)
        for method, path in [
            ("POST", ""),
            ("PATCH", "/" + CONNECTION["id"]),
            ("POST", "/" + CONNECTION["id"] + "/credentials"),
            ("GET", "/" + CONNECTION["id"]),
            ("POST", "/" + CONNECTION["id"] + "/health"),
            ("POST", "/" + CONNECTION["id"] + "/enable"),
            ("POST", "/" + CONNECTION["id"] + "/disable"),
            ("GET", ""),
            ("DELETE", "/" + CONNECTION["id"]),
        ]
    ]


def test_slack_and_secret_error_redaction() -> None:
    token = "xoxb-secret-token"
    secret = "a" * 32
    with loopback(
        Response(status=400, body={"message": f"Failed {token} {secret}"})
    ) as (base_url, state):
        with BlazingAgents(api_key="ba_test", base_url=base_url) as client:
            with pytest.raises(APIStatusError) as error:
                client.chat_connections.create(
                    name="Slack",
                    agent_id=CONNECTION["agentId"],
                    platform="slack",
                    configuration={
                        "team_id": "T123",
                        "app_id": "A123",
                        "webhook_url": "https://example.com/hook",
                        "channel_ids": ["C123"],
                    },
                    credentials={"bot_token": token, "signing_secret": secret},
                )
            assert token not in str(error.value)
            assert secret not in str(error.value)
            with pytest.raises(ValueError, match="Provide"):
                client.chat_connections.update(CONNECTION["id"])
    body = json.loads(state.requests[0].body)
    assert "enabled" not in body
    assert body["configuration"]["channelIds"] == ["C123"]
    assert body["credentials"] == {"botToken": token, "signingSecret": secret}


@pytest.mark.parametrize("asynchronous", [False, True])
def test_slack_rotation_and_update_validation(asynchronous: bool) -> None:
    slack: dict[str, Any] = {
        **CONNECTION,
        "platform": "slack",
        "configuration": {
            "platform": "slack",
            "teamId": "T123",
            "appId": "A123",
            "webhookUrl": "https://example.com/hook",
            "channelIds": [],
        },
    }
    with loopback(*[Response(body=slack) for _ in range(3)]) as (base_url, state):
        # Dynamic callers still receive useful errors for mismatched platforms.
        invalid: Any = {
            "name": "Support",
            "agent_id": CONNECTION["agentId"],
            "platform": "slack",
            "configuration": {
                "bot_id": "123",
                "webhook_url": "https://example.com/hook",
            },
            "credentials": {"bot_token": "token", "signing_secret": "a" * 32},
        }
        wrong_credentials: Any = {"bot_token": "token", "webhook_secret": "secret"}

        async def run_async() -> None:
            async with AsyncBlazingAgents(api_key="test", base_url=base_url) as client:
                resource = client.chat_connections
                created = await resource.create(
                    name="Support",
                    agent_id=CONNECTION["agentId"],
                    platform="slack",
                    configuration={
                        "team_id": "T123",
                        "app_id": "A123",
                        "webhook_url": "https://example.com/hook",
                    },
                    credentials={"bot_token": "token", "signing_secret": "a" * 32},
                )
                assert created.configuration.platform == "slack"
                await resource.update(created.id, name="Renamed")
                await resource.rotate_credentials(
                    created.id,
                    platform="slack",
                    credentials={"bot_token": "token", "signing_secret": "b" * 32},
                )
                with pytest.raises(ValueError, match="Provide"):
                    await resource.update(created.id)
                with pytest.raises(ValueError, match="Configuration"):
                    await resource.create(**invalid)
                invalid["credentials"] = wrong_credentials
                with pytest.raises(ValueError, match="Credentials"):
                    await resource.create(**invalid)
                with pytest.raises(ValueError, match="Credentials"):
                    await resource.rotate_credentials(
                        created.id, platform="slack", credentials=wrong_credentials
                    )

        if asynchronous:
            asyncio.run(run_async())
        else:
            with BlazingAgents(api_key="test", base_url=base_url) as client:
                resource = client.chat_connections
                created = resource.create(
                    name="Support",
                    agent_id=CONNECTION["agentId"],
                    platform="slack",
                    configuration={
                        "team_id": "T123",
                        "app_id": "A123",
                        "webhook_url": "https://example.com/hook",
                    },
                    credentials={"bot_token": "token", "signing_secret": "a" * 32},
                )
                assert created.configuration.platform == "slack"
                resource.update(created.id, name="Renamed")
                resource.rotate_credentials(
                    created.id,
                    platform="slack",
                    credentials={"bot_token": "token", "signing_secret": "b" * 32},
                )
                with pytest.raises(ValueError, match="Configuration"):
                    resource.create(**invalid)
                invalid["credentials"] = wrong_credentials
                with pytest.raises(ValueError, match="Credentials"):
                    resource.create(**invalid)
                with pytest.raises(ValueError, match="Credentials"):
                    resource.rotate_credentials(
                        created.id, platform="slack", credentials=wrong_credentials
                    )
    assert len(state.requests) == 3
    assert json.loads(state.requests[1].body) == {"name": "Renamed"}
    assert json.loads(state.requests[2].body) == {
        "platform": "slack",
        "botToken": "token",
        "signingSecret": "b" * 32,
    }
