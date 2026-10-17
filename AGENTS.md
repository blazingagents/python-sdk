All changes must use a topic branch and merge through a PR after required checks pass. Never commit or push directly to `main`.

README.md is the repository's brief for Tenants: what it is, features, installation, a quick start, and links to the documentation. Document feature behavior on the documentation site (`blazingagents/docs`), not in the README.

Database integration tests run through the shared platform pool: `npm --prefix ../ba-platform run test:integration:sdk:python`. Independent integration commands can run concurrently; a focused command fails clearly when the pool is full. See [pool configuration and concurrency rules](../ba-platform/docs/test-pool.md). Ordinary unit and protocol-fixture tests need no Supabase.

`spec/openapi.json` is a copy of the platform API contract, used only by tests and left out of the wheel and sdist. `tests/test_contract_scope.py` sends a request from every public method of the user clients (`for_user()`) and the tenant clients (`BlazingAgents`), sync and async. It fails unless the user clients send every operation the contract marks `"x-scope": "end-user"` and no other, and the tenant clients send every operation that accepts an API key and no other. User-client requests must carry `X-BA-User-Id`; tenant-client requests must not. When the platform contract changes, refresh the copy and run the tests:

```sh
cp ../ba-platform/servers/api/openapi.json spec/openapi.json
uv run python scripts/run_tests.py
```

When the test fails, change the clients to match the contract, not the test. A new public user-client method needs an entry in the test's `CALLS`, which the tenant clients reuse; a new tenant-only method needs one in `TENANT_CALLS`.

Releases follow `CONTRIBUTING.md`: pushing a `vX.Y.Z` tag publishes to PyPI, and the upload cannot be undone. Never push a `v*` tag without following it.

Breaking changes (a removed or renamed method, field, enum value, or endpoint, or a `!` commit) break Tenant apps already in production, so ship them in two steps. First release the new shape while the old one still works: the server and this SDK keep accepting the old input, and the old input is marked deprecated in its doc comment. Remove the old shape only in a later release. Every release that deprecates or removes something adds a `CHANGELOG.md` entry under its version that names what changed and shows the migration from the old call to the new one.

Tests use only the public API: what `blazing_agents` exports from its package root. `uv run ruff check .` rejects imports from private modules (`blazing_agents._*`, rule TID251) and private attribute access such as `client._transport` (SLF001) under `tests/`. When a test trips either rule, do one of two things:

1. Rewrite the test against the public client, asserting what a Tenant app can observe.
2. If the test really needs the value, the SDK is missing a public way to get it. Add one to the public API, document it on the documentation site, and use that in the test.

Do not silence the rule with `noqa`. A new private module must be added to the `banned-api` list in `pyproject.toml`; `scripts/run_tests.py` fails until it is.
