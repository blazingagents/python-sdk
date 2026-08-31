from blazing_agents import AgentCreate, AgentUpdate

invalid_create: AgentCreate = {
    "name": "Half-configured",
    "model": "openai/gpt-5",
}
invalid_update: AgentUpdate = {"provider_id": "prv_0123456789abcdef"}
