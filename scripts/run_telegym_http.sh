#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TELEGYM_ROOT="${TELEGYM_ROOT:-$HOME/telegym}"
TOKEN="${TELEGYM_BOT_TOKEN:-1234567890:telegym_test_token_xxxxxxxx}"
export BOT_TOKEN="$TOKEN"
export TELEGRAM_API_URL="${TELEGRAM_API_URL:-http://127.0.0.1:5678}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres@localhost:5434/academic}"
export POSTGRES_SCHEMA="${POSTGRES_SCHEMA:-student_platform}"
export ADMIN_TELEGRAM_IDS="${ADMIN_TELEGRAM_IDS:-93000001}"
export TELEGYM_MOCK_DEFAULT_WEBHOOK="http://127.0.0.1:8089/telegym/update"
export TELEGYM_MOCK_URL="http://127.0.0.1:5678"
export TELEGYM_BOT_TOKEN="$TOKEN"
cleanup() {
  [[ -n "${BRIDGE_PID:-}" ]] && kill "$BRIDGE_PID" 2>/dev/null || true
  [[ -n "${MOCK_PID:-}" ]] && kill "$MOCK_PID" 2>/dev/null || true
}
trap cleanup EXIT

if [[ ! -x "$TELEGYM_ROOT/bin/telegym-mock" ]]; then
  echo "خطأ: telegym-mock غير موجود في المسار: $TELEGYM_ROOT/bin/telegym-mock" >&2
  echo "قم بتثبيته عبر: git clone https://github.com/kolomiichenko/telegym.git $TELEGYM_ROOT && cd $TELEGYM_ROOT && PATH=/usr/local/go/bin:\$PATH make build" >&2
  exit 1
fi

fuser -k 5678/tcp 8089/tcp 2>/dev/null || true
sleep 0.3
"$TELEGYM_ROOT/bin/telegym-mock" -quiet >/tmp/talib-telegym-mock.log 2>&1 &
MOCK_PID=$!
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:5678/health >/dev/null 2>&1 && break; sleep 0.2; done
uv run python tests/telegym_bridge.py >/tmp/talib-telegym-bridge.log 2>&1 &
BRIDGE_PID=$!
for _ in $(seq 1 50); do
  grep -q 'telegym bridge ready' /tmp/talib-telegym-bridge.log 2>/dev/null && break
  sleep 0.2
done
grep -q 'telegym bridge ready' /tmp/talib-telegym-bridge.log || { cat /tmp/talib-telegym-bridge.log >&2; exit 1; }
uv run python tests/run_telegym_http.py
