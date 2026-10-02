from blazing_agents import BlazingAgents

BlazingAgents().agents.update(
    "ag_example",
    approval_in_chat={
        "default": "full",
        "overrides": [
            {
                "tool": {"type": "function", "name": "getOrder"},
                "decision": "manual",
            }
        ],
    },
)
