# Changelog

## Unreleased

### Removed

- `MerchantUsageEvent.workflow_issue`. The API no longer sends
  `workflowIssue`; if it appears, the SDK keeps it in `model_extra` like any
  other unknown field. Read `next_action` instead. It is `"retry"` for a
  `pending` event whose automatic delivery has stopped, which is when
  `workflow_issue` was set:

  ```python
  # Before
  if event.workflow_issue is not None:
      client.merchant_usage_events.retry(event.id)
  # After
  if event.next_action == "retry":
      client.merchant_usage_events.retry(event.id)
  ```

## 0.30.1

### Changed

- The vendored contract now matches the platform, which no longer sends the
  merchant connection `status`, the usage summary counts `uncertain` and
  `unmapped`, or the steer receipt states `delivered` and `uncertain`. The SDK
  stopped reading them in 0.30.0, so no code changes.

## 0.30.0

This release removes API surface the platform no longer serves. The SDK has no
production users yet, so each removal ships in one release with no
deprecation step.

### Removed

- Chat delivery listing and repair. The platform no longer keeps a chat
  delivery outbox: the workflow that runs a Slack or Telegram Turn posts the
  reply or approval card itself, with a bounded retry, and a reply that still
  fails stays in the Session transcript. Removed `client.chat_deliveries`
  (`list` and `iter`), `client.chat_connections.list_deliveries`,
  `iter_deliveries` and `repair_delivery`, and the types `ChatDelivery`,
  `TenantChatDelivery`, `ChatDeliveriesPage`, `ChatConnectionDeliveriesPage`,
  `ChatDeliveryResult`, `ChatDeliveryStatus`, `ChatDeliveryListStatus` and
  `ChatDeliveriesListOptions`. Migration: delete these calls; there is no
  replacement. Read a failed reply from the Session's messages.
- `SpendingLimitPeriod.reserved_usd` and `SpendingLimitStopDetails.reserved_usd`,
  and the `reserved` and `unknown_usage` stop reasons. The platform no longer
  holds spend for in-flight model requests: it checks the period total before
  each request and adds each response's cost after it, so a running Turn may
  finish one request past the limit. `reason` is now `exhausted` or `unpriced`,
  and `unpriced` also covers a response whose cost could not be determined.
  `available_usd` is `max(0, amount_usd - spent_usd)`. Migration: stop reading
  `reserved_usd`, and handle `reserved` as `exhausted` and `unknown_usage` as
  `unpriced`.
- The `delivered` and `uncertain` steer receipt states. `SessionInputState` is
  now `accepted`, `committed` or `not_placed`, and a lost owner is reported as
  `not_placed` with reason `owner_lost`. Migration: treat `delivered` as
  `accepted` and `uncertain` as `not_placed`.
- `WorkspaceDeletionOutcome`. See `workspaces.delete` under Changed.
- `MerchantConnectionStatus`, `MerchantConnection.status` and the `status`
  parameter of `merchant_connection.update()`. A merchant connection has no
  `disconnected` state. Migration: stop passing `status`; to pause billing,
  turn monetization off with `client.tenant.update(monetization_enabled=False)`.
- The `uncertain` usage event status and `MerchantUsageSummaryCounts.uncertain`.
  An exhausted transient delivery now ends `failed` with `last_error_code`
  `MERCHANT_RETRIES_EXHAUSTED`. Migration: retry `failed` events with
  `merchant_usage_events.retry()`; providers drop duplicates by the `mev_` ID.
- `merchant_usage_events.release()`, the `unmapped` usage event status, the
  `bind_and_release` next action and `MerchantUsageSummaryCounts.unmapped`. A
  Turn whose End-user has no customer binding records its usage event once as
  `discarded` with `last_error_code` `MERCHANT_CUSTOMER_UNMAPPED`, and it is
  never billed later. Migration: bind an End-user with `merchant_bindings.put()`
  before their first Turn, or turn on the merchant guard so an unbound
  End-user's Turn is refused with `merchant_customer_unmapped`.

### Changed

- `workspaces.delete()` returns `None`, sync and async. The API now deletes the
  Workspace at once and answers 204, so the `"pending"` outcome can no longer
  occur. Migration: drop any check of the returned value; `409
  workspace_in_use` still raises `APIStatusError`.

## 0.29.0

### Added

- `TaskRun.error_code` is the API error code a `blocked` or `failed` run
  ended with, such as `usage_credit_required`, `quota_exceeded` or
  `provider_required`. It is `None` for every other run and for a failure
  without a code; `error` still carries the message. `tasks.get_run`,
  `tasks.list_runs` and `tasks.iter_runs` return it, sync and async.

## 0.28.0

### Changed

- Every operation the API contract marks `x-credential-bearing` (all
  `providers`, `mcp_connections` and `chat_connections` methods,
  `chat_deliveries.list` and `iter`, and `merchant_connection.get`, `create`,
  `update` and `retire`) now rejects a successful JSON response that contains a
  credential field (`apiKey`, `botToken`, `signingSecret`, `webhookSecret`,
  `bearerToken`, `clientSecret`, `credential`, or their snake_case forms) or
  echoes a submitted secret. It raises the new `CredentialEchoError`, a
  `BlazingAgentsError` subclass that carries `request_id` and none of the body.
  Before, only `providers`, `mcp_connections` and `chat_connections` responses
  were checked, and they raised a plain `BlazingAgentsError`; a non-JSON
  response from those methods now raises the decoder's `ValidationError`
  instead. Migration: catch `CredentialEchoError` where you matched the
  `BlazingAgentsError` message "credential material".

- The client no longer checks rules that the API already enforces. These calls
  now send the request, and the API rejects an invalid one with
  `APIStatusError` (status 400) instead of the SDK raising `ValueError` (or
  `TypeError`) before sending:

  - `agents.create`: `provider_id` and `model` must be given together;
    `workspace_id` and `workspace_tier` are mutually exclusive.
  - `agents.update`: changing `provider_id` requires `model`; clearing needs
    both `None`; at least one field must be given.
  - `agents.update_mcp_attachment`, `prompts.update`, `providers.update`,
    `tasks.update`, `tenant.update`, `workspaces.update`,
    `mcp_connections.update` and `chat_connections.update`: at least one field
    must be given.
  - `providers.create`: `provider_type` must be supported; `custom` requires
    `base_url`; `vercel_ai_gateway` rejects `base_url`.
  - `mcp_connections.create` and `mcp_connections.reconnect`: `auth_type` must
    be supported and the credential fields must match it.
  - `chat_connections.create` and `chat_connections.rotate_credentials`:
    credentials and configuration must match `platform`;
    `chat_connections.update` rejects unknown configuration fields.
  - `tasks.create` and `tasks.update`: the schedule's shape, `at` offset
    datetime, `every_ms` minimum, cron expression, timezone and `stagger_ms`
    are no longer validated, and a cron timezone is sent as given (the API
    trims it). `tenant.update` no longer validates the `quota` shape.
  - `tasks.create` and `tasks.submit`: a blank or non-string
    `idempotency_key`.
  - `skills.create`: `path` must be `SKILL.md`; `skills.upload`:
    `archive_type` must be supported.

  Checks that stop the SDK from building a wrong request stay: path segments,
  the end-user ID header, a missing upload filename, and keyword combinations
  that cannot become one request body. Migrate by catching `APIStatusError`
  where you caught `ValueError` for these calls:

  ```python
  # Before
  try:
      client.tenant.update()
  except ValueError:
      ...

  # After
  try:
      client.tenant.update()
  except APIStatusError as error:
      assert error.status_code == 400
  ```

## 0.27.0

### Changed

- A Turn stream that fails after it starts now names its error in one
  transient `data-ba-error` event before the `error` chunk. Its `data` has the
  shape of an HTTP error body's `error`: `code`, `message` and optional
  `details`. `code` is an API error code or `turn_interrupted`, which only a
  stream sends. `TurnStreamErrorEvent` and `TurnStreamError` model it.

### Removed

- `SpendingLimitStopEvent`, `SpendingLimitStopData`, `TurnInterruptedEvent` and
  `TurnInterruptedData`, with the `data-model-spending-limit` and
  `data-turn-interrupted` events they modeled. A spending stop now arrives as
  `data-ba-error` with code `model_spending_limit_exceeded`, and its numbers
  move to `details`:

  ```python
  # Before
  event = SpendingLimitStopEvent.model_validate_json(payload)
  reason = event.data.reason

  # After
  event = TurnStreamErrorEvent.model_validate_json(payload)
  if event.data.code == "model_spending_limit_exceeded":
      details = event.data.details
      reason = SpendingLimitStopDetails.model_validate(details, strict=False).reason
  ```

## 0.26.0

### Removed

- `client.mcp_connections.connect()`, with its `McpConnectionAuthorization`
  response model. The API serves `POST /v1/mcp-connections/{id}/connect` only
  to a dashboard session and refuses an API key, so the method always failed.
  Finish OAuth sign-in for an `oauth_authorization_code` connection from the
  dashboard. To replace a connection's URL or credentials from code, call
  `reconnect()`:

  ```python
  # Before (always refused)
  client.mcp_connections.connect(mcp_connection_id)

  # After
  client.mcp_connections.reconnect(
      mcp_connection_id,
      auth_type="bearer",
      url="https://mcp.example.com/mcp",
      bearer_token=bearer_token,
  )
  ```

## 0.25.0

- Fixed: every method that puts an identifier in the URL path now raises
  `ValueError` for an empty, `.` or `..` identifier. Before, such a value
  changed the path, so `providers.delete(".")` sent `DELETE /v1/providers`.
- `client.chat_connections.list_deliveries()` and lazy `iter_deliveries()`
  list one Chat Connection's deliveries in every status, newest first
  (`GET /v1/chat-connections/{id}/deliveries`), with `cursor` and `limit`.
- `client.chat_connections.repair_delivery(chat_connection_id, delivery_id,
  expected_attempt=...)` sends a stuck reply or approval card again
  (`POST /v1/chat-connections/{id}/deliveries/{deliveryId}/repair`). It always
  sends `previousSenderStopped` and `acceptDuplicateRisk` as `true`, so calling
  it confirms the previous sender stopped and accepts that the message may
  appear twice. Check the result's `status`.
- New public types: `ChatConnectionDeliveriesPage` and `ChatDeliveryResult`.
- `response_meta(model)` returns a frozen `ResponseMeta` with the HTTP
  `status`, server `request_id`, and read-only `headers` of the response a
  client method decoded into `model`. It raises `ValueError` for models the
  client did not return.
- Removed: the private `_request_id` attribute on response models. Use
  `response_meta()`:

  ```python
  # Before
  agent._request_id

  # After
  from blazing_agents import response_meta

  response_meta(agent).request_id
  ```
- A malformed Task `schedule` or tenant `quota` now raises pydantic's
  `ValidationError`, a `ValueError` subclass, for every kind of mistake. Some
  shape errors raised `TypeError` before. Catch `ValueError` for both.

## 0.24.0

- Removed: `for_user(...).agents.get_spending_limit()` and
  `for_user(...).agents.update_spending_limit()`, deprecated in 0.23.0. The API
  always refused them for user-scoped callers. Call them on the tenant client:

  ```python
  # Before
  client.for_user(user_id).agents.get_spending_limit(agent_id)

  # After
  client.agents.get_spending_limit(agent_id)
  ```

## 0.23.0

- `for_user(...).usage.get_for_agent()` reads one Agent's usage for the scoped
  user. The API already allowed it.
- Deprecated: `for_user(...).agents.get_spending_limit()` and
  `for_user(...).agents.update_spending_limit()`. The API always refuses them
  for user-scoped callers with `forbidden` (403), so they never worked there.
  They now emit a `DeprecationWarning` and are removed from user-scoped clients
  in a later release. Call them on the tenant client:

  ```python
  # Before
  client.for_user(user_id).agents.get_spending_limit(agent_id)

  # After
  client.agents.get_spending_limit(agent_id)
  ```

## 0.22.0

- Add `AGENT_TOOLS` and `AGENT_TOOL_GROUPS`, the built-in tool catalog. Each
  `AgentToolDefinition` has a description, `requires_workspace`, and `tags`:
  its group tag first, plus `file_read`, `file_write`, or `execute` on file
  operation tools. An Agent whose file tools are all `file_read` cannot change
  Workspace files.

## 0.14.0

- Send one message or an ordered `messages` batch through `chat()`. Literal
  input uses one `messages` array on the wire. Applications own waiting messages.
- `sessions.submit_input()` steers a running Turn. Receipts use `accepted`,
  `delivered`, `committed`, `not_placed`, or `uncertain`. Only `committed`
  proves durable history inclusion. The `data-ba-steer-consumed` event reports
  provisional placement. Never replay an uncertain message automatically.
- `sessions.stop()` returns as soon as cancellation is recorded. Read the
  existing stream to observe settlement.
- `continue_chat(decisions=..., functions=...)` records a complete approval
  round and streams the rest of the Turn in one request. Functions are optional
  and run in the caller while the stream is consumed.
- Remove `run_inputs()`, `promote_input()`, `delete_input()`, `resume_inputs()`,
  `decide_tool_approval()`, `join_tool_approval_continuation()`, and `resume_chat()`.
  Remove queue modes, paused activity, and their obsolete response types.

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
