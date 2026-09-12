
# Chat integrations

The existing SDK manages your Agent. Use REST to connect it to Slack or Telegram;
BA hosts the Chat SDK runtime and handles incoming messages and approvals.

## Create a Telegram connection

Use an existing configured Agent. Set `BLAZING_AGENTS_BASE_URL` to the API origin
(without `/v1`), `BLAZING_AGENTS_API_KEY`, `BA_AGENT_ID`, `TELEGRAM_BOT_ID`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, and `CHAT_WEBHOOK_URL`.
See [callback setup](https://docs.blazingagents.com/platform/chat-integrations) for the create-and-update sequence. Use an initial HTTPS URL for
`CHAT_WEBHOOK_URL`; the example saves the final callback after creation.
Run this once on a trusted backend.

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
webhook_url = (
    f"{os.environ['BLAZING_AGENTS_BASE_URL']}/v1/chat/webhooks/telegram/"
    f"{connection['id']}"
)
update = Request(
    f"{os.environ['BLAZING_AGENTS_BASE_URL']}/v1/chat-connections/{connection['id']}",
    method="PATCH",
    headers=request.headers,
    data=json.dumps({"webhookUrl": webhook_url}).encode(),
)
with urlopen(update, timeout=30) as response:
    json.load(response)
print(webhook_url)
```

Register the printed webhook URL with Telegram, run a fresh health check, then DM the
bot. See [Slack and Telegram setup](https://docs.blazingagents.com/platform/chat-integrations) for registration,
permissions, health checks, and conversation behavior.

If creation times out, list your connections and reconcile before retrying.
Connection management has no dedicated SDK methods; use the
[REST reference](https://docs.blazingagents.com/api-reference/rest-api/chat-connections) for lifecycle and repair.
