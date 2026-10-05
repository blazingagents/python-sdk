from blazing_agents import ChatMessagesInput, ContinueChatInput

batch: ChatMessagesInput = {
    "agent_id": "ag_example",
    "messages": [],
    "prompt_id": "prompt_example",
}
continuation: ContinueChatInput = {
    "agent_id": "ag_example",
    "session_id": "ss_example",
    "decisions": [{"approval_id": "a1", "approved": "yes"}],
}
