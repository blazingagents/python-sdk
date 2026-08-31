from blazing_agents import AsyncBlazingAgents, BlazingAgents


def sync_example(client: BlazingAgents) -> None:
    client.agents.create(name="Release agent", workspace_id=None)
    client.agents.update("ag_0123456789abcdef", workspace_id=None)


async def async_example(client: AsyncBlazingAgents) -> None:
    await client.agents.create(name="Release agent", workspace_id=None)
    await client.agents.update("ag_0123456789abcdef", workspace_id=None)
