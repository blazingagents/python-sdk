from pydantic import BaseModel

from blazing_agents import AsyncBlazingAgents, BlazingAgents


class Person(BaseModel):
    name: str


SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
}


def sync_example(client: BlazingAgents) -> None:
    client.object(
        agent_id="ag_0123456789abcdef",
        prompt="Both output modes",
        output_type=Person,
        json_schema=SCHEMA,
    )


async def async_example(client: AsyncBlazingAgents) -> None:
    await client.object_stream(
        agent_id="ag_0123456789abcdef",
        prompt="Both output modes",
        output_type=Person,
        json_schema=SCHEMA,
    )
