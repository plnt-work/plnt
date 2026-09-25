#!/usr/bin/env bash
# Start a fake model + `plnt dev` with support-desk, then drive the console.
# Usage (from repo root, console already built): bash console/e2e/run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$here/../.."
export PLNT_HOME="$(mktemp -d)"
export SHOT_DIR="${SHOT_DIR:-$root/console/e2e-shots}"
mkdir -p "$SHOT_DIR"

python - <<'PY' &
import sys, threading
sys.path.insert(0, "scripts")
from http.server import HTTPServer
from smoke_platform import FakeOllama
HTTPServer(("127.0.0.1", 11555), FakeOllama).serve_forever()
PY
fake=$!
PLNT_LOCAL_URL=http://127.0.0.1:11555 PLNT_PLANNER_MODEL=fake:1b \
  plnt dev support-desk --port 8791 \
  --config "business_name=Luigi's Bistro" --config handoff_contact=hi@luigis.example \
  --config-json 'faq=[{"q":"When are you open?","a":"Tuesday to Sunday, 5pm to 11pm."}]' &
dev=$!
trap 'kill $fake $dev 2>/dev/null || true' EXIT
for _ in $(seq 50); do curl -sf http://127.0.0.1:8791/v1/health >/dev/null && break; sleep 0.2; done
node "$here/drive.mjs"
