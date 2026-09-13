# Go bridge product requirements

Continue the same native Codex conversation between a Mac terminal and stock T3 on iPhone. Keep ordinary Codex local, sharing opt-in, and Micro entirely separate. Target macOS 14+ on Apple Silicon and Intel.

## Architecture

Go owns the launcher, terminal WebSocket relay, and bounded supervision of its T3 child. T3 retains authentication, clients, orchestration, and its privately bundled Node runtime. Native Codex owns execution, session storage, permissions and MCP processes. The bridge never automatically restarts native Codex.

Preserve `setup`, `login`, `daemon-start`, `serve`, `pair`, `codex`, `codex resume`, `codex unshare`, existing data paths, symlink launching, configurable bind addresses and native argument forwarding. Add health, logs, safe diagnostics, optional login service and manually activated updates. Default to authenticated loopback/Tailscale access; explicit LAN binding remains supported.

## Session and settings contract

Attaching to an existing session must not alter native configuration. Submitting a T3 turn forwards that turn's selected model, effort, service tier and interaction mode. Missing settings must not acquire invented overrides. Native approval and sandbox settings remain unchanged on shared turns. Only acknowledge a setting after native acceptance; never retry a prompt or approval whose acknowledgement was lost.

Persistent cross-client configuration synchronization is a separate release gate: an unmodified native terminal can retain its own settings. A successful per-turn mapping test is not proof that every client's controls stay synchronized. Unsupported permission changes, browser-tool injection, rollback and approval forms need clear capability errors/UI states before production.

Stable native IDs must survive discovery, resume, disconnect and phone-first creation. Pending imports survive failed RPCs and T3 restart. Active turns are not idle. Unshare detaches this bridge without deleting history or interrupting another client. Native MCP retention is measured independently of relay cleanup.

## Diagnostics and privacy

Structured local metadata logs, protocol-aware health, bounded retention and safe support reports are required. No prompts, attachments, tool output, authentication files, session databases or pairing tokens belong in exported diagnostics. Automatic analytics/export are off. OTLP export is opt-in to the user's endpoint only, after redaction validation. Log failures must not block agent execution.

Use captured child identities, inherited host PATH, and a 10,240 soft descriptor limit where supported. Never use `launchctl submit`, pattern-based process termination, or an automatic native-daemon restart. Stop T3 recovery after three retries in ten minutes.

## Delivery sequence

1. Regression fixtures and capability baseline.
2. Discovery, registration, settings and approval correctness.
3. Go launcher and relay with race/resource testing.
4. Operational diagnostics, optional service and failure injection.
5. Prebuilt bundles, installer, versioned manual updates and migration tests.
6. Real-client qualification, independent review and signed public release.

Each increment must pass its focused checks before promotion. Development uses isolated data and synthetic sessions. Do not migrate the working installation as part of a build.

## Production gates

- Native Mac installation on both architectures without Go or Node prerequisites.
- Stock iPhone pairing; bidirectional continuation; phone-first creation; supported settings, approvals, interruptions and recovery.
- 20 loaded sessions: discovery p95 <=3s and reconnect <=10s after services become available.
- 72-hour soak, 1,000 reconnect cycles, no duplicate prompts, wrong-session approvals, owned process leaks or sustained descriptor/memory growth.
- Native MCP cleanup measured after the actual idle grace period.
- Privacy canaries, authenticated network boundary checks, signed/notarized packages, dependency/license inventory, interrupted-update and data-rollback verification.
- Independent security/reliability review.

These are release criteria, not a statement that the preview already meets them.
