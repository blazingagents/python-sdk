from blazing_agents import ApprovalPolicyInput, BlazingAgents

invalid: ApprovalPolicyInput = {"default": "approved"}
BlazingAgents().agents.update(
    "ag_example",
    approval_in_chat={
        "default": "full",
        "overrides": [
            {
                "tool": {"type": "mcp", "name": "mail"},
                "decision": "auto",
            }
        ],
    },
)
