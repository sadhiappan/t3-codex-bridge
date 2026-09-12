# Alpha validation

Release: `0.1.0-alpha.1` · September 12, 2026

## Checked for this package

- Downloaded pinned T3 source directly from its public upstream; applied the public patch.
- Installed pinned npm Codex 0.154.0 and dependencies into a fresh runtime directory.
- Built the production web client and server on macOS arm64 with Node 24.13.1.
- Companion launcher tests: 6 passed.
- Focused upstream shared-session tests: 69 passed across 8 files.
- Server TypeScript check passed after adding the missing `check-sharing` transport error operation. Upstream Effect suggestions remain informational.
- An isolated raw native app-server initialized over a Unix WebSocket.
- An isolated production T3 server served HTML and its built JavaScript asset, rejected unauthenticated WebSocket access with HTTP 401, and issued a pairing link.
- Isolated smoke-test processes were stopped and temporary data removed. The user's running daemon was not restarted.
- Public files were checked for personal host paths, hardware bridge code, and obvious credential patterns. Runtime downloads/data are Git-ignored; private fork history is not included.

Reproduce with `npm test`, `./bridge setup`, `./scripts/test-upstream.sh`, and `node scripts/smoke.mjs`. GitHub Actions repeats installation, build, server type checking, focused tests, and isolated startup. Check the Actions result for the exact commit you install.

## Earlier prototype evidence

Mac-to-phone and phone-to-Mac replies were observed in the same native conversation. Separate lifecycle fixtures showed repeated resumes reused MCP children, and native cleanup released idle sessions/MCP children after their last client detached. These checks predate the standalone installer and are supporting evidence, not certification of this package.

## Still needs tester coverage

- Fresh physical phone pairing and bidirectional conversations using this packaged release.
- Phone-first session creation followed by terminal discovery/resume.
- Multiple terminal apps, Intel Macs, Linux, and combinations of real MCP servers.
- Sleep/wake, network churn, prolonged daemon stalls, partial discovery failures, and multi-day load.
- Independent security review and full permission/approval coverage.

This release is for controlled testing, not a production-readiness or leak-free guarantee. See README alpha limits and TESTING.md.
