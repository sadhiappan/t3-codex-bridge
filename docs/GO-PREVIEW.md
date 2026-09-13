# Go preview

This development branch is not a production release. It does not modify or migrate an existing T3 installation.

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
- Real launchd validation of the optional service; manual update/migration implementation.
- Both-architecture clean-machine package validation, signing and notarization.
- Redacted trace export and richer native-session/MCP resource reporting. Go process metrics already support opt-in export.
- Independent review, real Mac/iPhone workflow tests, both architecture tests, 72-hour soak and native MCP lifecycle verification.

A passing synthetic relay test does not prove native MCP cleanup or phone behavior. See [PRD](PRD.md) for acceptance criteria.

## Current validation (September 13, 2026)

- 89 focused T3 tests passed; scoped server typecheck passed (upstream suggestions remain).
- Go race suite includes 1,000 reconnects; descriptors returned from 4 to 4 in the synthetic Unix-WebSocket test.
- Unsigned Apple Silicon bundle smoke passed with child PATH restricted to system directories: native initialize, Go doctor, built HTML/JS, HTTP 401 for an unauthenticated WebSocket, private pairing link generation.
- No shared daemon restart, LaunchAgent installation, or live data migration was performed.

The previous committed preview also passed clean CI builds and isolated bundle smoke on macOS 15 Apple Silicon and Intel. These checks do not establish MCP health, real phone round-trips, macOS 14 compatibility or sustained production reliability.

## Optional operational features

`bridge service install` writes a separate, explicitly requested login service; `bridge service start` loads it. Use `stop` before `uninstall`. It only manages the bridge/T3 child. It waits for native Codex to be started explicitly and stops recovery after three retries in ten minutes. Installation is not performed by builds or tests.

Set `T3_BRIDGE_OTLP_METRICS_URL` to your collector's full metrics endpoint to export Go goroutine/heap gauges every ten seconds. Export is off by default; remote endpoints require HTTPS, redirects are not followed, and credential-bearing URLs are rejected. Use a local collector for authenticated forwarding. This does not enable raw T3 traces or send conversation content. Export failures are recorded without blocking agent work.
