# T3 Codex Bridge

**Continue the same Codex conversation in your Mac terminal and T3 on your phone.**

An independent, open-source **tester alpha**, built on [T3 Code](https://github.com/pingdotgg/t3code). This repository packages a shared-session patch and installer; it is not an official T3 or OpenAI release.

```text
Mac terminal ── bridge codex ──┐
                              ├── Native Codex daemon ── project files + MCP servers
Phone T3 app ── T3 server ─────┘
              on your Mac
```

Sessions use their original native Codex IDs. Only terminal sessions launched through `bridge codex` are registered for discovery. Ordinary `codex` is unchanged. You can also start a Codex chat in T3 and continue it in a terminal. Closing a terminal does not delete its conversation.

**Terminal-independent:** no Ghostty APIs or hardware integrations are included. macOS is the initial test platform; other terminals and Linux need tester validation. Native Windows is not supported by this Unix-socket alpha.

## 1. Prerequisites

- macOS, Git, and **Node.js 24.13.1 or later in the Node 24 series** (npm included).
- A Codex account/subscription or supported API authentication.
- For phone access: T3 mobile app and Tailscale on both devices, signed into the same tailnet. Keep your Mac awake.
- Several GB of free space for the source build and dependencies. First setup takes several minutes.

With Homebrew, install Node 24 using `brew install node@24`, then run:

```bash
export PATH="$(brew --prefix node@24)/bin:$PATH"
node --version
```

The installer downloads **Codex 0.154.0 into this checkout**. It does not replace your global Codex installation. T3 and the patch are pinned in [versions.json](versions.json).

## 2. Install

```bash
git clone https://github.com/sadhiappan/t3-codex-bridge.git "$HOME/t3-codex-bridge"
cd "$HOME/t3-codex-bridge"
./bridge setup
./bridge login
./bridge daemon-start
./bridge serve
```

Leave the last command running. It serves the built web app on `127.0.0.1:18773`. Setup does not install a background service or change shell startup files.

**Already using a shared Codex daemon?** `daemon-start` leaves a reachable daemon untouched. Confirm it runs Codex 0.154.0; this installer cannot upgrade its version, PATH, or file limit while it is running. Do not restart it while other sessions are attached. For an entirely isolated trial, set `CODEX_HOME` to a new directory consistently in every terminal; log in there and configure any required MCPs separately.

## 3. Pair your phone

In a second Mac terminal (also using Node 24; repeat the Homebrew PATH export above if needed):

```bash
cd "$HOME/t3-codex-bridge"
./bridge pair --tailscale
```

Follow the printed pairing instructions in T3 on your phone. Use the full pairing link; if the app asks for host and code, use the printed HTTPS host and pairing credential. **Do not post that credential to a group or GitHub issue.** It grants access to your environment.

This explicitly configures Tailscale Serve on HTTPS port **8243**. It does not enable public Tailscale Funnel. If that port is already used, choose another with `./bridge pair --tailscale --tailscale-serve-port 8244`. Tailscale ACLs still govern who can reach your Mac.

For a local browser instead, run `./bridge pair` and open the printed pairing URL.

## 4. Share a terminal conversation

In a terminal at your project directory:

```bash
export PATH="$HOME/t3-codex-bridge:$PATH"
cd /path/to/your/project
bridge codex
```

Send a small prompt. The conversation should appear in T3 after discovery. Reply from your phone, then verify that reply in the terminal. Both clients act on the same host files and conversation; coordinate prompts rather than submitting conflicting work simultaneously.

```bash
bridge codex resume <native-session-id>  # share/continue an existing conversation
bridge codex unshare <native-session-id> # detach from T3; retain history
codex                                  # ordinary local Codex, unchanged
```

The launcher prints a resume command when you leave a shared terminal. For a phone-created chat, obtain its native Codex ID through the native resume picker (`bridge codex resume`) and select the conversation. Phone-first creation/resume needs explicit tester validation in this packaged release.

Native flags are forwarded, for example `bridge codex --model MODEL`. A profile must already exist in your Codex configuration. **Codex remote resume rejects permission overrides**: do not add `--profile yolo`, sandbox, or approval overrides when resuming a remote task. This project does not bypass native permission rules. Non-interactive utilities such as `bridge codex exec` are passed through locally; they are not registered for T3.

## What to test

Use a disposable project first. Follow [TESTING.md](TESTING.md), then file a [bug report](https://github.com/sadhiappan/t3-codex-bridge/issues/new?template=bug.yml). Each tester installs on their own host and pairs their own phone. This is not a shared public server.

## Alpha limits

- This is **not production-ready**: no multi-day soak, independent security audit, or broad terminal/OS matrix has been completed.
- Shared sessions preserve native permissions. Some approval types must be answered in the native terminal.
- T3 checkpoints/rollback are disabled for shared sessions. Imported historical messages are text; full old tool traces, attachments and diffs are not reconstructed.
- Recovery under a stalled daemon or failed initial discovery needs further hardening. Report missing/stuck imports; do not restart the daemon to work around them while others are attached.
- A shared daemon can run separate MCP instances per loaded session. T3 detaches idle provider connections after roughly 30–35 minutes; native idle cleanup was observed after the last client detached, not immediately when one terminal closed. Closing a phone app is not a guarantee that a session or its MCPs stop.
- Unsharing prevents automatic discovery/reattachment; a historical T3 entry may remain visible. It is not deletion or a per-session security boundary. A paired T3 client has access to the host environment.
- The launcher uses normal-screen mode for terminal scrollback. It does not contain Micro drivers, LED controls, dictation rules, or Ghostty tab automation.

## Data, security, and troubleshooting

- Bundled tools/source: `.runtime/` inside this checkout (ignored by Git).
- T3 database and registration markers: `~/.local/share/t3-codex-bridge/`.
- Codex authentication/history/config: existing `~/.codex`, or your explicit `CODEX_HOME`.
- Terminal diagnostic log: `~/.local/state/t3-codex-bridge/terminal.log`.
- Set `T3_BRIDGE_HOME` for a different T3 data directory or `T3_BRIDGE_PORT` for a different local port; use consistent settings for `serve`, `pair`, and `codex`.

Run `./bridge doctor`. Socket reachability alone does **not** prove MCPs or prompts work: open a real session, verify enabled MCP servers connect, and complete a small prompt.

**MCP startup errors:** the native daemon inherits PATH and file limits when it starts. Ensure required tools (`npx`, `uv`, your secret helper) work in the launching shell. The wrapper raises its soft file limit to 10240, but cannot change an already-running daemon. If this limit exceeds your hard limit, adjust your OS limits before starting; no global settings are changed automatically.

**Resume permission error:** remove permission-changing flags and resume with just the native session ID. **Session missing:** check `bridge serve` output, confirm the session was launched through `bridge codex`, send a small prompt, and confirm it is not archived in T3. **Expired pairing:** issue a new link with `bridge pair`. **Socket exists but is unreachable:** preserve logs and attached-session state; this tool deliberately refuses automatic daemon restart.

**Failed setup:** correct the reported dependency/network error and rerun `./bridge setup`. A checkout from a different release needs a fresh clone; the installer refuses to reset source changes. Do not run `git clean` against directories holding your data.

## Stop / uninstall

Press Ctrl-C in the `bridge serve` terminal to stop that T3 server. This does not stop the native daemon or delete Codex history. Revoke paired clients in T3 Settings → Connections before retiring the server. If you enabled the default tailnet mapping, remove **only that mapping** with `tailscale serve --https=8243 off` (use your chosen port if different).

You can then remove this checkout and, after backing it up, its dedicated T3 data directory. Leave `~/.codex` intact. No background service or shell configuration was installed. Daemon shutdown is deliberately a separate operator decision because other clients may use it.

## Development and attribution

`npm test` checks the companion launcher. `./scripts/test-upstream.sh` runs the focused shared-session tests after setup. CI builds the pinned patched server and web client on macOS.

[MIT license](LICENSE). T3 Code copyright © 2026 T3 Tools Inc.; see [NOTICE](NOTICE). OpenAI Codex is fetched from npm under its own package license. This project is unaffiliated with T3 Tools or OpenAI.
