from blazing_agents import AsyncBlazingAgents, BlazingAgents


def missing_required_fork_arguments(client: BlazingAgents) -> None:
    client.sessions.fork("ag_example", "ss_example", message_id="assistant")
    client.sessions.fork("ag_example", "ss_example", idempotency_key="key")


async def async_missing_required_fork_arguments(client: AsyncBlazingAgents) -> None:
    await client.sessions.fork("ag_example", "ss_example", message_id="assistant")
    await client.sessions.fork("ag_example", "ss_example", idempotency_key="key")
