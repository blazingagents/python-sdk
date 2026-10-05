# Changelog

## 0.13.0

- Remove `join_input_turn()` from the sync and async clients and Session
  resources. Call `run_inputs()` to stream a queued batch. Inputs wait until
  a client runs them, including after stop or resume. Settled results remain
  available in Session history.

## 0.12.0

- Add durable Session inputs on the sync and async `sessions` resources.
  `submit_input(agent_id=..., session_id=..., request_id=..., message=...,
  when_busy="queue" | "steer")` returns a `SessionInputResponse` receipt once
  the input is stored. An idle Session starts a new Turn. While a Turn is
  running, `"queue"` (the default) waits for the next Turn and `"steer"` joins
  the running Turn. When an outcome is unknown, retry with the same
  `request_id` and payload; a changed payload raises `APIStatusError` with code
  `input_idempotency_conflict`.
- `inputs()` lists receipts in admission order, together with the Session's
  `SessionActivity`. To observe changes, poll without `cursor`; `cursor` only
  pages. `promote_input()` turns a pending queued input into steering without
  changing its identity or order. `delete_input()` withdraws an input that has
  not been delivered. After delivery, both raise `input_not_pending`.
- `stop(turn_id=...)` returns once the named Turn has settled. Pending queued
  inputs then start one new Turn. `resume_inputs()` clears a `failed` or
  `owner_lost` pause and schedules the pending queue. It leaves a
  `function_executor_required` pause in place; use `run_inputs()` for that.
  Neither one bypasses a waiting tool approval (`session_busy`).
- `request_id` and `turn_id` must not be empty, `.`, or `..`; these raise
  `ValueError` before any request is sent, because a URL would collapse them
  onto another route. Every other identity is percent-encoded unchanged.
- Add `run_inputs(agent_id=..., session_id=..., functions=...)` to the sync
  and async clients. It runs the pending queue as one Turn and executes its
  backend functions while you consume the stream. This is how to continue
  after a Session pauses with `function_executor_required`; nonempty
  `functions` clear that pause. `join_input_turn(turn_id=..., functions=...)`
  reattaches a function executor to a queued-input Turn that has already been
  admitted. `sessions.join_input_turn()` streams such a Turn from its start as
  an observer: it removes function events and never runs functions.
  Disconnecting does not stop the Turn; use `stop()` to stop it.
- New public types: `SessionInput`, `SessionInputResponse`,
  `SessionInputsPage`, `SessionActivity`, `SessionActivityResponse`,
  `SessionStopResponse`, `SessionInputMode`, `SessionInputState`,
  `SessionInputReason`, `SessionActivityState`, and `SessionActivityReason`.

## 0.11.0

- Add `AgentConfig` to Session detail and TaskRun responses. Use
  `sessions.get(agent_id, session_id)` to read the configuration saved for a
  Session.
- Remove Agent Version catalog methods and version pin inputs from chat,
  generation, and Tasks. Provider deletion now accepts
  `confirm_snapshot_invalidation=True`.

## 0.10.0

- Add backend functions to `chat()` on the sync and async clients. Define each
  with `define_function(description=..., input_schema=..., execute=...)`, where
  `input_schema` is a Pydantic model or other type, and pass them as
  `functions={"name": function}`. Only descriptions and JSON Schema go to Blazing
  Agents. The handler runs in your backend while the stream is consumed, inside
  the same live Turn. The stream claims each call, validates its input, runs the
  handler once, and submits its result or a sanitized error. Results must
  already be plain JSON (`None`, `bool`, numbers, `str`, `list`, and `dict`
  with string keys); NaN, Infinity, tuples, models, and dates are rejected
  rather than coerced. Retries reuse the same claim nonce and outcome.
  Function control events are removed from the relayed bytes. A malformed
  control event or a permanent claim or result failure raises from the stream.
- Handlers receive a `FunctionContext` with `idempotency_key` (the `fc_` call
  ID), `deadline_at`, and a `cancelled` `threading.Event`. The event is set at
  the call deadline or when the stream closes. Async handlers are also
  cancelled. Sync handlers stop only cooperatively. The sync client rejects
  `async def` handlers; the async client runs sync handlers in a thread.
- Add `resume_chat(agent_id=..., session_id=..., functions=...)`, which joins a
  queued or running tool approval continuation after human approval and
  reattaches handlers by name. `chat()` and `resume_chat()` forward
  `extra_headers`, including `X-BA-User-Id`, to the claim and result requests.
  `sessions.join_tool_approval_continuation()` stays an observer: it removes
  function control events and never runs functions, so it relays complete SSE
  events rather than raw chunks. New public types: `ChatFunction` and
  `FunctionContext`.
- `ToolApproval.tool` is now a `ToolExecutionReference`, which adds
  `FunctionToolReference` (`type="function"`) to the built-in and MCP
  references, so approvals that pause on a backend function parse. Approval
  policy overrides still accept only built-in and MCP tools through
  `ToolReference`. New public types: `FunctionToolReference` and
  `ToolExecutionReference`.

## 0.9.0

- Add `client.chat_deliveries.list()` and lazy `iter()` on the sync and async
  clients for `GET /v1/chat-deliveries`, the Tenant-wide chat delivery feed
  across all Chat Connections, newest first. Filter by `status` (`failed`
  and/or `ambiguous`; omitting it returns both), `since`, `cursor`, and
  `limit`. New public types: `ChatDelivery`, `TenantChatDelivery`,
  `ChatDeliveriesPage`, `ChatDeliveryStatus`, `ChatDeliveryListStatus`, and
  `ChatDeliveriesListOptions`.

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
