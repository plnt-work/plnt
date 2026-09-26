#!/usr/bin/env bash
# Build the site, start `plnt serve --playground` against a fake model, and
# drive /playground in a browser. Usage (from repo root): bash site/e2e/run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
site="$here/.."
export PLNT_HOME="$(mktemp -d)"
export SHOT_DIR="${SHOT_DIR:-$site/e2e-shots}"
mkdir -p "$SHOT_DIR"

python "$here/fake_model.py" 11556 &
fake=$!
PLNT_LOCAL_URL=http://127.0.0.1:11556 PLNT_PLANNER_MODEL=fake:1b \
  plnt serve --port 8787 --playground &
server=$!
(cd "$site" && npx astro preview --port 4321 --host 127.0.0.1) &
preview=$!
trap 'kill $fake $server $preview 2>/dev/null || true' EXIT

for _ in $(seq 60); do
  curl -sf http://127.0.0.1:8787/v1/playground >/dev/null && \
    curl -sf http://127.0.0.1:4321/ >/dev/null && break
  sleep 0.5
done
(cd "$site" && node e2e/playground.mjs)
