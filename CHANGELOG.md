# Changelog

## 0.8.0

- Prefix `APIStatusError` text with the server error code, for example
  `[model_validation_unavailable] Provider model discovery is unavailable`, so
  the code can be looked up in the error catalog. `error.code` is unchanged.
- Type `Agent.tools` and `AgentVersion.tools` as `list[AgentTool]` to match the
  platform contract, so tools read from a response type-check when passed back
  to `agents.create()` or `agents.update()`. Responses with tools outside
  `workspace`, `write_todos`, and `memory` now fail validation.

## 0.7.0

- Adopt server-owned chat callbacks. Chat Connection creation now uses bot
  credentials without client-supplied callback URLs or Telegram webhook
  secrets; responses include the computed `webhook_url`.
- Breaking: remove `team_id`, `app_id`, and `webhook_url` from
  `SlackChatConfigurationInput`, `bot_id` and `webhook_url` from
  `TelegramChatConfigurationInput`, and `webhook_secret` from
  `TelegramChatCredentialsInput`. Remove the `webhook_url` parameter from
  `chat_connections.update()`.

## 0.6.2

- Address Skill files with the `path` query parameter to match the platform's
  `?path=` Skill file routes.

## 0.6.1

- Add synchronous and asynchronous dashboard usage overviews with totals, daily
  activity, bounded Agent, End-user, and Model rankings, and active Agent counts.
- Let latest Session queries choose between Tenant-wide recency and one result
  per Agent with `by_agent`.

## 0.6.0

- Configure Slack and Telegram Chat Connections with synchronous and asynchronous clients: list, get, create, update, rotate credentials, check health, enable, disable, and delete.
- Export typed platform configuration, credential inputs, and safe connection responses.

## 0.5.0

- Add typed chat and task tool approval policies to synchronous and asynchronous
  Agent create/update methods and Agent/version responses. Preserve omitted
  updates, policy replacement, empty overrides and structured builtin/MCP tools.
- Restore both approval policies when restoring an Agent version.
- Export policy inputs, response models, tool references and policy mode literals.
- Parse optional approval tool/message/timestamp metadata and distinguish policy
  modes from persisted `pending`, `approved`, `denied` decisions. Continue using
  the existing Session list/decide/join lifecycle.
