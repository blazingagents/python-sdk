from blazing_agents import ChatMessageInput

invalid_chat: ChatMessageInput = {
    "agent_id": "ag_0123456789abcdef",
    "message": {"role": "user", "parts": []},
    "trigger": "regenerate-message",
}
