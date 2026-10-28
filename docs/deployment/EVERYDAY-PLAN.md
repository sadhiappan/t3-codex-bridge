# Everyday shared Codex rollout

1. Use the native daemon in the existing ~/.codex home; keep configuration and history in place.
2. Route interactive codex launches through the shared launcher; pass utility commands and noninteractive automation to native Codex. New sessions inherit terminal cwd. Resume keeps native identity.
3. Register only native conversations opened by this launcher. T3 discovers those IDs without scanning other work or personal history.
4. Keep the paired T3 environment and install a login service that starts its native daemon and the T3 runner.
5. Validate real native launcher, T3 import, reverse prompt, process restart, routing, and type/lint checks before enabling shell routing.
6. Existing running local CLIs require exiting and resuming once; do not kill or move them. New shell tabs load the routing automatically.

Rollback: remove the marked Shared Codex block from ~/.zshrc (backup zshrc-before-everyday), unload local.codex-shared-t3, and use the original native binary. No histories copied or deleted. The old isolated daemon remains available for prototype tests. Micro is optional and is not an acceptance gate for shared conversations.

Implemented a67b8dc58. Steps1–5 passed (14 focused tests, type/lint checks, real daemon/T3 forward+reverse exchange, full service restart and third reply without duplicate messages). Routing installed for new shells. Step6 is the user's one-time handoff for previously running CLI sessions. Actual phone retest and long sleep/wake remain practical acceptance work.
