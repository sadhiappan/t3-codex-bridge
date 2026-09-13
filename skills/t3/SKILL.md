---
name: t3
description: Enable, disable, toggle, or check T3 remote sharing for the current Codex session. Use when the user invokes $t3 or explicitly asks to change this session's T3 sharing.
---

Use `~/.local/bin/t3-session` to control only the current session. It gets the native ID from CODEX_THREAD_ID/CODEX_SESSION_ID; never substitute a guessed ID, title, or another session.

- `$t3 on` / enable: run `~/.local/bin/t3-session on`.
- `$t3 off` / disable: run `~/.local/bin/t3-session off`.
- `$t3 status`: run `~/.local/bin/t3-session status`.
- Bare `$t3`: run `~/.local/bin/t3-session toggle` once.

Do not toggle for questions about the feature or while installing it. No additional confirmation is needed for an explicit on/off/toggle request.

The helper preserves native execution and history. On restores an archived T3 entry through T3's API; off detaches the provider and leaves history visible. Off is not revocation of a paired client's host access.

Report the returned enabled/attached state concisely. If confirmation times out, say intent was saved but attachment/detachment is unconfirmed; use status instead of retrying toggle. Never claim a marker alone proves attachment. Do not edit session databases, print credentials, restart services, or alter Micro as a workaround. If the helper is unavailable, report that installation is missing.

Enabling requires the current execution to belong to the shared native daemon. A standalone local Codex process must first be resumed through `codex --t3 resume <native-id>` in the terminal; do not silently create a second execution of the same saved session.
