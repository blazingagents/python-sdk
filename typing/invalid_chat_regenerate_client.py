from blazing_agents import AsyncBlazingAgents, BlazingAgents


def sync_example(client: BlazingAgents) -> None:
    client.chat(
        agent_id="ag_0123456789abcdef",
        message={"role": "user", "parts": []},
        trigger="regenerate-message",
    )


async def async_example(client: AsyncBlazingAgents) -> None:
    await client.chat(
        agent_id="ag_0123456789abcdef",
        message={"role": "user", "parts": []},
        trigger="regenerate-message",
    )
