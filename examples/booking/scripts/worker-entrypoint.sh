#!/usr/bin/env sh
# plnt-cloud worker entrypoint.
#
# CLAUDE.md invariant: the worker MUST be launched with .env sourced via
# `set -a`, otherwise PLNT_CLOUD_URL/PLNT_CLOUD_API_KEY are missing and
# the plnt router silently falls back to local Ollama (HTTP 400 ⇒ chat
# returns no replies). This script reproduces the bare-metal recipe.
#
# Mount the host .env at /env/.env:
#     volumes:
#       - ./.env:/env/.env:ro
# We deliberately do NOT add fallback environment defaults — failing
# loudly is the contract.

set -eu

ENV_FILE="${PLNT_ENV_FILE:-/env/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "worker-entrypoint: $ENV_FILE not found." >&2
  echo "  Mount your plnt-cloud .env at $ENV_FILE (or set PLNT_ENV_FILE)." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

exec python -m workflows.worker
