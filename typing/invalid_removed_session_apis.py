from blazing_agents import AsyncBlazingAgents, BlazingAgents


def sync_example(client: BlazingAgents) -> None:
    client.resume_chat(agent_id="ag_example", session_id="ss_example", functions={})
    client.run_inputs(agent_id="ag_example", session_id="ss_example")
    client.sessions.promote_input(
        agent_id="ag_example", session_id="ss_example", request_id="r1"
    )
    client.sessions.delete_input(
        agent_id="ag_example", session_id="ss_example", request_id="r1"
    )
    client.sessions.resume_inputs(agent_id="ag_example", session_id="ss_example")
    client.sessions.decide_tool_approval(
        agent_id="ag_example", session_id="ss_example", approval_id="a1", approved=True
    )
    client.sessions.join_tool_approval_continuation(
        agent_id="ag_example", session_id="ss_example", continuation_id="c1"
    )


async def async_example(client: AsyncBlazingAgents) -> None:
    await client.resume_chat(
        agent_id="ag_example", session_id="ss_example", functions={}
    )
    await client.run_inputs(agent_id="ag_example", session_id="ss_example")
    await client.sessions.promote_input(
        agent_id="ag_example", session_id="ss_example", request_id="r1"
    )
    await client.sessions.delete_input(
        agent_id="ag_example", session_id="ss_example", request_id="r1"
    )
    await client.sessions.resume_inputs(agent_id="ag_example", session_id="ss_example")
    await client.sessions.decide_tool_approval(
        agent_id="ag_example", session_id="ss_example", approval_id="a1", approved=True
    )
    await client.sessions.join_tool_approval_continuation(
        agent_id="ag_example", session_id="ss_example", continuation_id="c1"
    )
