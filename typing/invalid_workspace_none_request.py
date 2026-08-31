from blazing_agents import AgentCreate, AgentUpdate

invalid_create: AgentCreate = {
    "name": "Release agent",
    "workspace_id": None,
}
invalid_update: AgentUpdate = {"workspace_id": None}
