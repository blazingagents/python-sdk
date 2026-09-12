
# Chat integrations

The existing SDK manages your Agent. Use REST to connect it to Slack or Telegram;
BA hosts the Chat SDK runtime and handles incoming messages and approvals.

## Create a Telegram connection

Use an existing configured Agent. Set `BLAZING_AGENTS_BASE_URL` to the API origin
(without `/v1`), `BLAZING_AGENTS_API_KEY`, `BA_AGENT_ID`, `TELEGRAM_BOT_ID`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, and `CHAT_WEBHOOK_URL`.
See [setup and the callback URL limitation](https://docs.blazingagents.com/platform/chat-integrations) before
choosing `CHAT_WEBHOOK_URL`. Run this once on a trusted backend.

```python
import json
import os
from urllib.request import Request, urlopen

request = Request(
    f"{os.environ['BLAZING_AGENTS_BASE_URL']}/v1/chat-connections",
    method="POST",
    headers={
        "Authorization": f"Bearer {os.environ['BLAZING_AGENTS_API_KEY']}",
        "Content-Type": "application/json",
    },
    data=json.dumps(
        {
            "name": "Support on Telegram",
            "agentId": os.environ["BA_AGENT_ID"],
            "platform": "telegram",
            "configuration": {
                "botId": os.environ["TELEGRAM_BOT_ID"],
                "webhookUrl": os.environ["CHAT_WEBHOOK_URL"],
            },
            "credentials": {
                "botToken": os.environ["TELEGRAM_BOT_TOKEN"],
                "webhookSecret": os.environ["TELEGRAM_WEBHOOK_SECRET"],
            },
        }
    ).encode(),
)
with urlopen(request, timeout=30) as response:
    connection = json.load(response)
print(connection["id"])
```

Register the returned ID's webhook URL with Telegram, then start a DM with the
bot. See [Slack and Telegram setup](https://docs.blazingagents.com/platform/chat-integrations) for registration,
permissions, health checks, and conversation behavior.

If creation times out, list your connections and reconcile before retrying.
Connection management has no dedicated SDK methods; use the
[REST reference](https://docs.blazingagents.com/api-reference/rest-api/chat-connections) for lifecycle and repair.
