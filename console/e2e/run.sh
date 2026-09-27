#!/usr/bin/env bash
# Start a fake model + `plnt dev` with the developer bundles, then drive the
# console. Usage (from repo root, console already built): bash console/e2e/run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$here/../.."
export PLNT_HOME="$(mktemp -d)"
export SHOT_DIR="${SHOT_DIR:-$root/console/e2e-shots}"
mkdir -p "$SHOT_DIR"

python "$root/site/e2e/fake_model.py" 11555 &
fake=$!
export PLNT_LOCAL_URL=http://127.0.0.1:11555 PLNT_PLANNER_MODEL=fake:1b
plnt tenants create dev >/dev/null
plnt install code-reviewer --tenant dev --config focus=bugs >/dev/null
plnt install test-writer --tenant dev >/dev/null
plnt dev repo-explainer --port 8791 --config audience=reviewer &
dev=$!
trap 'kill $fake $dev 2>/dev/null || true' EXIT
for _ in $(seq 50); do curl -sf http://127.0.0.1:8791/v1/health >/dev/null && break; sleep 0.2; done
node "$here/drive.mjs"
