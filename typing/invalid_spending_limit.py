from blazing_agents import BlazingAgents, SpendingLimitInput

client = BlazingAgents(api_key="ba_test")
invalid_interval: SpendingLimitInput = {
    "amount_usd": 1.0,
    "reset_start_date": "2026-10-09",
    "reset_interval": "yearly",
}
client.tenant.update_spending_limit()
client.agents.update_spending_limit(
    "ag_0123456789abcdef", spending_limit={"amount_usd": 1.0}
)
