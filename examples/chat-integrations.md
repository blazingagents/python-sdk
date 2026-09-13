# Chat integrations

Use `client.chat_connections` (0.6.0+) to connect an existing Agent to Slack or
Telegram. BA handles incoming messages and approvals.

## Create a Telegram connection

Set `BLAZING_AGENTS_API_KEY`, `BA_AGENT_ID`, `TELEGRAM_BOT_ID`,
`TELEGRAM_BOT_TOKEN`, and `TELEGRAM_WEBHOOK_SECRET` in your environment.
Run setup once in a trusted environment.

```python
import os
from blazing_agents import BlazingAgents

base_url = "https://api.blazingagents.com"
with BlazingAgents(base_url=base_url) as client:
    connection = client.chat_connections.create(
        name="Support on Telegram",
        agent_id=os.environ["BA_AGENT_ID"],
        platform="telegram",
        enabled=False,
        configuration={
            "bot_id": os.environ["TELEGRAM_BOT_ID"],
            "webhook_url": f"{base_url}/v1/chat/webhooks/telegram/pending",
        },
        credentials={
            "bot_token": os.environ["TELEGRAM_BOT_TOKEN"],
            "webhook_secret": os.environ["TELEGRAM_WEBHOOK_SECRET"],
        },
    )
    webhook_url = f"{base_url}/v1/chat/webhooks/telegram/{connection.id}"
    client.chat_connections.update(connection.id, webhook_url=webhook_url)
    print(webhook_url)
```

Register the printed URL with Telegram using the same webhook secret. Then call
`client.chat_connections.check_health(connection.id)`, review the checks, and
call `client.chat_connections.enable(connection.id)` when setup is complete.
See [Slack and Telegram setup](https://docs.blazingagents.com/platform/chat-integrations)
for external registration and Slack permissions.

For Slack, use `platform="slack"`, configuration fields `team_id`, `app_id`,
`webhook_url`, and optional `channel_ids`, with `bot_token` and `signing_secret`
credentials. Telegram accepts optional `chat_ids`. These IDs are health-check
targets, not access restrictions.

Use `list().chat_connections`, `get(id)`, `update(id, name=...)`,
`rotate_credentials(id, platform=..., credentials=...)`, `disable(id)`, and
`delete(id)` to manage connections. `AsyncBlazingAgents` supports the same
methods with `await`. Responses never return credentials.

If creation times out, list and reconcile before retrying. If the callback
update fails, retry it using the existing connection ID.
