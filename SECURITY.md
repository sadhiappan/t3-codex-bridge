# Security

This alpha runs coding agents with the host user's access and configured Codex permissions. Treat pairing credentials as sensitive host-access credentials. Opt-in discovery is a convenience, not isolation between paired users.

The server defaults to loopback. Phone sharing explicitly enables Tailscale Serve, not public Funnel. Use tailnet ACLs and T3 client revocation. Do not expose this server directly to the public internet.

For a suspected vulnerability, use this repository's private GitHub vulnerability reporting when available. Do not post credentials or exploit details in a public issue. Public issue reports should contain only non-sensitive summaries.

No independent security audit has been completed. Supported tester release: 0.1.0-alpha.1, pinned to the versions in versions.json. Report compatibility problems before upgrading the shared daemon; a daemon restart disconnects attached clients.
