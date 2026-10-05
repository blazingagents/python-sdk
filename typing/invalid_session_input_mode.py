from blazing_agents import BlazingAgents


def example(client: BlazingAgents) -> None:
    client.sessions.submit_input(
        agent_id="ag_example",
        session_id="ss_example",
        request_id="draft-1",
        message={"role": "user", "parts": []},
        when_busy="steer",
    )
