# Go preview

This development branch is not a production release. It does not modify or migrate an existing T3 installation.

Build with Go 1.27.1 or later:

```sh
./scripts/build-go.sh
./bin/bridge help
```

For a source build, install the Node 24 version specified in `versions.json`, put it on PATH, and use `./bin/bridge setup`. The preview workflow builds platform-specific unsigned bundles with a private Node runtime. Use a new `T3_BRIDGE_HOME` and `CODEX_HOME` for isolated testing; configure authentication/MCPs there explicitly.

The root `./bridge` remains the alpha launcher while this native entry point is qualified. No automatic replacement of an existing installation occurs.

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
- Opt-in redacted OTLP export; richer correlated health/resource reporting.
- Independent review, real Mac/iPhone workflow tests, both architecture tests, 72-hour soak and native MCP lifecycle verification.

A passing synthetic relay test does not prove native MCP cleanup or phone behavior. See [PRD](PRD.md) for acceptance criteria.

## Current validation (September 13, 2026)

- 89 focused T3 tests passed; scoped server typecheck passed (upstream suggestions remain).
- Go race suite includes 1,000 reconnects; descriptors returned from 4 to 4 in the synthetic Unix-WebSocket test.
- Unsigned Apple Silicon bundle smoke passed with child PATH restricted to system directories: native initialize, Go doctor, built HTML/JS, HTTP 401 for an unauthenticated WebSocket, private pairing link generation.
- No shared daemon restart, LaunchAgent installation, or live data migration was performed.

These checks do not establish MCP health, real phone round-trips, Intel compatibility or sustained production reliability.
