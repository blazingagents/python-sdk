# Changelog

## 0.5.0

- Add typed chat and task tool approval policies to synchronous and asynchronous
  Agent create/update methods and Agent/version responses. Preserve omitted
  updates, policy replacement, empty overrides and structured builtin/MCP tools.
- Restore both approval policies when restoring an Agent version.
- Export policy inputs, response models, tool references and policy mode literals.
- Parse optional approval tool/message/timestamp metadata and distinguish policy
  modes from persisted `pending`, `approved`, `denied` decisions. Continue using
  the existing Session list/decide/join lifecycle.
