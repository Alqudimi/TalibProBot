#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export REDIS_ENABLED="${REDIS_ENABLED:-true}"
export CELERY_BROKER_DB="${CELERY_BROKER_DB:-0}"
export CELERY_RESULT_DB="${CELERY_RESULT_DB:-1}"
exec uv run celery -A src.app.infrastructure.tasks.celery_app:celery_app worker \
  --loglevel="${CELERY_LOG_LEVEL:-WARNING}" \
  --concurrency="${CELERY_CONCURRENCY:-4}" \
  --pool="${CELERY_POOL:-prefork}" \
  --hostname="${CELERY_HOSTNAME:-talibprobot@%h}"
