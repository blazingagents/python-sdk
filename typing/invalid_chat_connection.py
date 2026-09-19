from blazing_agents import BlazingAgents

client = BlazingAgents(api_key="test")
client.chat_connections.create(
    name="invalid",
    agent_id="ag_0123456789abcdef",
    platform="slack",
    configuration={"business_mode": False},
    credentials={"bot_token": "123:secret"},
)
client.chat_connections.rotate_credentials(
    "cc_0123456789abcdef",
    platform="telegram",
    credentials={"bot_token": "token", "signing_secret": "secret"},
)
