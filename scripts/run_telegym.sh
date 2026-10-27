#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="${TELEGYM_ROOT:-$HOME/telegym}"
MOCK="$ROOT/bin/telegym-mock"
K6="$ROOT/bin/k6"
[[ -x "$MOCK" ]] || { echo "Missing $MOCK; build with: cd $ROOT && PATH=/usr/local/go/bin:\$PATH make build" >&2; exit 1; }
[[ -x "$K6" ]] || { echo "Missing $K6; build with: cd $ROOT && PATH=/usr/local/go/bin:\$PATH make k6" >&2; exit 1; }
export BOT_TOKEN="${BOT_TOKEN:-1234567890:telegym_test_token_xxxxxxxx}"
export TELEGRAM_API_URL="${TELEGRAM_API_URL:-http://127.0.0.1:5678}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres@localhost:5434/academic}"
export POSTGRES_SCHEMA="${POSTGRES_SCHEMA:-student_platform}"
export TELEGYM_MOCK_DEFAULT_WEBHOOK="http://127.0.0.1:8089/telegym/update"
export TELEGRAM_API_URL

cleanup() {
  [[ -n "${BRIDGE_PID:-}" ]] && kill "$BRIDGE_PID" 2>/dev/null || true
  [[ -n "${MOCK_PID:-}" ]] && kill "$MOCK_PID" 2>/dev/null || true
}
trap cleanup EXIT
"$MOCK" -quiet >/tmp/talib-telegym-mock.log 2>&1 &
MOCK_PID=$!
sleep 0.5
uv run python tests/telegym_bridge.py >/tmp/talib-telegym-bridge.log 2>&1 &
BRIDGE_PID=$!
sleep 1
TELEGYM_MOCK_URL=http://127.0.0.1:5678 \
TELEGYM_BOT_TOKEN="$BOT_TOKEN" \
  "$K6" run "${1:-tests/telegym_scenarios/public_user.js}"
