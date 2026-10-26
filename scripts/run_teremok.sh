#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export BOT_TOKEN="${BOT_TOKEN:-123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890}"
exec uv run pytest -q tests/test_teremok_blackbox.py \
  -o asyncio_default_test_loop_scope=session \
  -o asyncio_default_fixture_loop_scope=session "$@"
