#!/bin/zsh
set -eu
ulimit -Sn 10240 || exit 1
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export T3_CODEX_BINARY="${T3_CODEX_BINARY:-$HOME/.codex/packages/standalone/current/bin/codex}"
if [[ "${1:-}" == --standalone ]]; then
  shift
  exec "$T3_CODEX_BINARY" "$@"
fi
export T3_CODEX_AUTO_SHARE=0
if [[ "${1:-}" == --t3 ]]; then
  shift
  export T3_CODEX_AUTO_SHARE=1
fi
if [[ "$CODEX_HOME" != "$HOME/.codex" || ! -t 0 || ! -t 1 ]]; then
  exec "$T3_CODEX_BINARY" "$@"
fi
export T3_BRIDGE_HOME="$HOME/.local/share/codex-shared-t3/go-data-20d1565"
export T3_BRIDGE_PORT=5733
export T3_CODEX_SHARED_SOCKET="$CODEX_HOME/app-server-control/app-server-control.sock"
export T3_CODEX_SHARED_REGISTRATIONS="$HOME/.local/share/codex-shared-t3/registrations"
export T3_CODEX_START_DAEMON=0
export T3_CODEX_MICRO_SOCKET="$HOME/.local/share/codex-micro-bridge/bridge.sock"
exec "${T3_NODE_BINARY:-$HOME/.local/share/codex-shared-t3/node-v24.13.1-darwin-arm64/bin/node}" \
  "${T3_TERMINAL_SOURCE:-$HOME/Projects/t3code/apps/server/src/sharedCodexTerminal.ts}" "$@"
