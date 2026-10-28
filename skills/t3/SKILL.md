---
name: t3
description: Enable, disable, toggle, or check T3 remote sharing for the current Codex session. Use when the user invokes $t3 or explicitly asks to change this session's T3 sharing.
---

In the CLI, invoke as `$t3 ...` or through `/skills`. Use `~/.local/bin/t3-session` to control only the current session. It gets the native ID from CODEX_THREAD_ID/CODEX_SESSION_ID; never substitute a guessed ID, title, or another session.

- `$t3 on` / enable: run `~/.local/bin/t3-session on`.
- `$t3 off` / disable: run `~/.local/bin/t3-session off`.
- `$t3 status`: run `~/.local/bin/t3-session status`.
- Bare `$t3`: run `~/.local/bin/t3-session toggle` once.

Do not toggle for questions about the feature or while installing it. No additional confirmation is needed for an explicit on/off/toggle request.

The helper preserves native execution and history. On restores an archived T3 entry through T3's API; off detaches the provider and leaves history visible. Off is not revocation of a paired client's host access.

Report the returned enabled/attached state concisely. If confirmation times out, say intent was saved but attachment/detachment is unconfirmed; use status instead of retrying toggle. Never claim a marker alone proves attachment. Do not edit session databases, print credentials, restart services, or alter Micro as a workaround. If the helper is unavailable, report that installation is missing.

New interactive sessions started by the installed `codex` launcher use the shared native daemon with T3 sharing initially off. `$t3 on` attaches and `$t3 off` detaches in the same running session, without exiting or interrupting its turn. A resumed session retains any existing sharing registration. Explicit `codex --t3` starts with sharing enabled. Non-interactive commands and `codex --standalone` use the standalone runtime.

Only an execution owned by the shared native daemon is attached directly. Legacy standalone sessions already running when the launcher changed cannot be adopted live:

- Started by the supervised launcher: `on` returns `handoff: "armed"` and changes nothing else (no marker, no unarchive). Tell the user sharing starts after they exit Codex normally (Ctrl+D or `/quit`); the same terminal then reopens this conversation through `codex --t3 resume <native-id>`, where `$t3 status` confirms attachment. `off`, or bare `$t3` while armed, cancels. Never report armed as enabled, and never exit, kill, or signal Codex to complete it. A crash, non-zero exit, or another process still holding the session skips the handoff and prints the manual resume command; launch options such as `--profile` are not carried into the reopened session.
- Started before supervision existed or outside the launcher: the helper fails with the limitation and the manual `codex --t3 resume <native-id>` command. Relay it as is; do not work around it or create a second execution of the same saved session.

`status` adds `handoff: armed|available` only inside a supervised session. Run the helper outside the command sandbox: it needs `/bin/ps`, `lsof`, the local T3 port, and the registrations directory.

For a failure, run `~/.local/bin/t3-diagnose --session <actual-native-id>` after obtaining that ID from the current environment. This read-only report correlates sharing intent, runtime state, pending request IDs/ages, discovery decisions and recent toggle operations. Lifecycle traces are in the bridge data directory's `diagnostics/lifecycle.jsonl` (three rotated backups, 2 MiB each). They exclude prompts, answers, tool arguments and credentials. Report an armed handoff, registered intent or healthy discovery separately from confirmed attachment. Do not retry a toggle blindly after a timeout.
