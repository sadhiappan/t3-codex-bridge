#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT/.runtime/t3/apps/server"
../../node_modules/.bin/vp test run \
  src/provider/sharedCodexLaunch.test.ts \
  src/provider/sharedCodexRegistration.test.ts \
  src/provider/sharedCodexTerminalRelay.test.ts \
  src/provider/sharedCodexTerminalState.test.ts \
  src/provider/SharedCodexDiscovery.test.ts \
  src/provider/Layers/codexSharedTransport.test.ts \
  src/provider/Layers/CodexSessionRuntime.test.ts \
  src/provider/Layers/ProviderSessionReaper.test.ts
