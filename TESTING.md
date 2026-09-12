# Tester checklist

Use a disposable Git project. Keep terminal output and filenames non-sensitive. Never attach pairing credentials, Codex auth files, environment dumps, conversation databases, or full logs without reviewing them.

## Install and health

- Clone a fresh copy; run the README commands without relying on an existing T3 installation.
- Record macOS/Linux version, terminal name/version, Node version and `bridge doctor` result.
- Open a real shared Codex session. Confirm every enabled MCP starts without errors. Complete a harmless prompt, such as asking for the current project directory.
- Verify an ordinary `codex` session does not appear automatically in this T3 server.

## Same conversation on both devices

1. Run `bridge codex` in a disposable project. Ask it to reply with `MAC_OK`.
2. Open that chat in T3 on your phone. Confirm the same exchange is present.
3. Ask from the phone for `PHONE_OK`. Confirm both clients show the response once.
4. Exercise a tool requiring approval under your normal permissions. Confirm the expected client can approve it; never broaden permissions just to pass a test.
5. Leave the terminal normally. Resume the same native ID with `bridge codex resume <id>`. Verify history and phone continuity.
6. Create a new Codex chat from T3, then locate and resume it through `bridge codex resume` on the Mac. Report missing IDs or duplicate chats.

## Disconnect and idle behavior

- Background/reopen the phone app and briefly disconnect its network. Check history catches up, messages are not duplicated, and a completed turn is not permanently shown as working.
- Close one terminal while a second client remains attached. Verify the remaining client still works.
- Leave an idle shared session for at least 35 minutes, then resume it. Confirm continuity. Record process/descriptor counts only if comfortable doing so; raw counts alone do not demonstrate a leak.
- Run `bridge codex unshare <id>` after closing its terminal. Confirm T3 detaches and no longer automatically resumes it. Retained history may remain visible. Re-register by resuming it through `bridge codex` and submitting a prompt.
- Check ordinary terminal scrollback and long messages. Report encoded payloads, blank areas, garbled text or unexpected title changes.

## Report

Use the GitHub bug template. Include exact steps, expected/actual behavior and whether the daemon predated installation. Redact secrets and project details. A screenshot is useful when the failure is visual.

## Validation before alpha publication

See [VALIDATION.md](VALIDATION.md) for checks performed on the packaged release. Historical prototype testing is not a substitute for a fresh phone pairing or multi-day reliability test.
