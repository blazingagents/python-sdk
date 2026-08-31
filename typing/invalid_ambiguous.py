from blazing_agents import AsyncBlazingAgents, BlazingAgents


def sync_example(client: BlazingAgents) -> None:
    client.object(
        agent_id="ag_0123456789abcdef",
        prompt="Missing output mode",
    )


async def async_example(client: AsyncBlazingAgents) -> None:
    await client.object_stream(
        agent_id="ag_0123456789abcdef",
        prompt="Missing output mode",
    )
