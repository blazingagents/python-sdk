from blazing_agents import AsyncBlazingAgents, AsyncChatRelay, RelayContext


class AppRequest:
    user: str


def resolve_context(request: AppRequest) -> RelayContext | None:
    return None


AsyncChatRelay(client=AsyncBlazingAgents(), resolve_context=resolve_context)
