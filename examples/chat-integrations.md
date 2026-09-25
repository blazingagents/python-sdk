# Chat integrations

Use `client.chat_connections` (0.6.0+) to connect an existing Agent to Slack or
Telegram. BA handles incoming messages and approvals.

## Create a Telegram connection

Set `BLAZING_AGENTS_API_KEY`, `BA_AGENT_ID`, and `TELEGRAM_BOT_TOKEN` in your
environment. Run setup once in a trusted environment.

```python
import os
from blazing_agents import BlazingAgents

with BlazingAgents() as client:
    connection = client.chat_connections.create(
        name="Support on Telegram",
        agent_id=os.environ["BA_AGENT_ID"],
        platform="telegram",
        enabled=False,
        configuration={"business_mode": False},
        credentials={"bot_token": os.environ["TELEGRAM_BOT_TOKEN"]},
    )
    print(connection.webhook_url)
    client.chat_connections.enable(connection.id)
```

BA generates the Telegram webhook secret and registers the returned URL when
the connection is enabled. Call `check_health(connection.id)` and require the
`webhook_url` check to pass.
See [Slack and Telegram setup](https://docs.blazingagents.com/platform/chat-integrations)
for external registration and Slack permissions.

For Slack, use `platform="slack"`, optional `channel_ids`, and `bot_token` plus
`signing_secret`. Paste the response's `webhook_url` into the Slack app's Event
Subscriptions and Interactivity Request URL fields. Telegram accepts optional
`business_mode` and `chat_ids`. Destination IDs are health-check targets, not
access restrictions.

Use `list().chat_connections`, `get(id)`, `update(id, name=...)`,
`rotate_credentials(id, platform=..., credentials=...)`, `disable(id)`, and
`delete(id)` to manage connections. `AsyncBlazingAgents` supports the same
methods with `await`. Responses never return credentials.

If creation times out, list and reconcile before retrying.
