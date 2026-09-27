from blazing_agents import AsyncBlazingAgents, BlazingAgents


def sync_example(client: BlazingAgents) -> None:
    client.chat_deliveries.list(status=["pending"])
    client.chat_deliveries.iter(status=["confirmed"])


async def async_example(client: AsyncBlazingAgents) -> None:
    await client.chat_deliveries.list(status=["pending"])
    client.chat_deliveries.iter(status=["confirmed"])
