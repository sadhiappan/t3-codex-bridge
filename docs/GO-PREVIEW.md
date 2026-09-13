# Go preview

This development branch is not a production release. Builds do not modify or migrate an existing T3 installation; one explicitly authorized Mac deployment has been completed separately.

Build with Go 1.27.1 or later:

```sh
./scripts/build-go.sh
./bin/bridge help
```

For a source build, install the Node 24 version specified in `versions.json`, put it on PATH, and use `./bin/bridge setup`. The preview workflow builds platform-specific unsigned bundles with a private Node runtime. Use a new `T3_BRIDGE_HOME` and `CODEX_HOME` for isolated testing; configure authentication/MCPs there explicitly.

The root `./bridge` launches the compiled Go CLI. Runtime commands no longer invoke the old JavaScript launcher. Builds do not replace an existing installation.

## Implemented checks

- Go WebSocket relay: binary/text identity, large resume responses, private sockets, root-session registration, cancellation and reconnect resource tests.
- CLI configuration: opt-in registration, existing host/port settings, host PATH preservation and ambient web-origin/export isolation.
- Child execution: literal arguments, exit status and cancellation/reaping.
- Diagnostics: initialize/initialized protocol handshake; MCP health explicitly unknown; metadata-only support output.
- T3 adapter: pending imports remain retryable, metadata deadlines cancel silent requests, selected turn settings are forwarded without permission overrides.
- T3 provider event metadata redaction when launched through the Go bridge; raw browser/server traces are disabled in safe logging mode.

## Still required before promotion

- Persistent cross-client settings readback and explicit capability handling in every affected stock T3 control.
- Reboot and failure-recovery validation of login services; general-purpose manual update/migration implementation.
- Both-architecture clean-machine package validation, signing and notarization.
- Redacted trace export and richer native-session/MCP resource reporting. Go process metrics already support opt-in export.
- Independent review, real Mac/iPhone workflow tests, 72-hour soak and native MCP lifecycle verification.

A passing synthetic relay test does not prove native MCP cleanup or phone behavior. See [PRD](PRD.md) for acceptance criteria.

## Current validation (September 13, 2026)

- 89 focused T3 tests passed; scoped server typecheck passed (upstream suggestions remain).
- Go race suite includes 1,000 reconnects; descriptors returned from 4 to 4 in the synthetic Unix-WebSocket test.
- Unsigned Apple Silicon bundle smoke passed with child PATH restricted to system directories: native initialize, Go doctor, built HTML/JS, HTTP 401 for an unauthenticated WebSocket, private pairing link generation.
- The tested `20d1565` bundle was subsequently deployed on one Apple Silicon Mac with separate Go/T3 and one-shot native login jobs. The old development service was disabled; a consistent database copy, pairing identity, and existing phone address were preserved. The running native daemon was not restarted. Original data and configuration were retained for rollback. This was a manual deployment, not validation of an automated installer.

Commit `20d1565` passed clean CI builds and isolated bundle smoke on macOS 15 Apple Silicon and Intel ([CI run](https://github.com/sadhiappan/t3-codex-bridge/actions/runs/34767106288)). These checks do not establish MCP health, real phone round-trips, macOS 14 compatibility or sustained production reliability.

## Optional operational features

`bridge service install` writes a separate, explicitly requested login service; `bridge service start` loads it. Use `stop` before `uninstall`. It only manages the bridge/T3 child. It waits for native Codex to be started explicitly and stops recovery after three retries in ten minutes. Installation is not performed by builds or tests.

Set `T3_BRIDGE_OTLP_METRICS_URL` to your collector's full metrics endpoint to export Go goroutine/heap gauges every ten seconds. Export is off by default; remote endpoints require HTTPS, redirects are not followed, and credential-bearing URLs are rejected. Use a local collector for authenticated forwarding. This does not enable raw T3 traces or send conversation content. Export failures are recorded without blocking agent work.

## Current-session remote sharing skill

The optional [`t3` skill](../skills/t3/SKILL.md), added in `a2b2d8d`, exposes `$t3 on`, `$t3 off`, `$t3 status`, and bare `$t3` to toggle. This is a Codex skill invocation, not a native `/t3` slash command.

On registers the current native session and unarchives its T3 entry through the authenticated orchestration API when necessary. It reports success only after T3 records an attached runtime. Off prevents automatic discovery/reattachment and waits for the provider runtime to stop; it retains history and does not revoke a paired client's host access. A timeout means intent was saved but completion is unconfirmed; check status rather than repeating toggle.

Enabling requires the calling session to belong to the shared native daemon. A standalone local session must first be resumed through the shared terminal launcher (`bridge codex resume <native-id>`, or the locally configured `codex --t3 resume <native-id>`). The helper refuses to create a second execution of a standalone session.

The helper uses Python's standard library, read-only SQLite metadata queries, local process ownership checks, and T3's HTTP API. It never directly updates T3's database. Authentication uses a dedicated orchestration read/operate credential stored through the local macOS `keychain-secret` helper; credentials are not printed or committed.

This skill is installed on the deployment Mac and recognized by the running Codex daemon. It is not installed automatically by `bridge setup` or the packaged installer. Other hosts need the skill under their Codex skills directory, a `~/.local/bin/t3-session` launcher for `skills/t3/scripts/t3.py`, matching `T3_BRIDGE_HOME`/`T3_BRIDGE_PORT`, a configured `bridge` launcher, and `~/bin/keychain-secret`. Optional `T3_TOGGLE_BRIDGE` selects the bridge executable used for pairing. Machine-specific launchers and credentials remain local.

Validation: five focused helper tests passed; skill validation passed; a live archived session was enabled and attached, then disabled and detached while its native conversation continued. Sharing was left off after the test. Native daemon identity/start time stayed unchanged. General multi-host installation and phone UI testing remain outstanding.

## Permission settings boundary

T3-created sessions send their initial sandbox and approval settings to Codex. Attaching or resuming an existing shared session preserves its native permissions. Subsequent shared turns omit permission overrides, so changing T3's permission selector is not yet a supported way to change an existing shared session's permissions. Explicit-change handling, native acceptance/readback, and synchronized client controls remain release gates.
