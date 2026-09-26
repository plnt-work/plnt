#!/usr/bin/env bash
# Install the built wheel into a clean venv, outside the checkout, and check it
# works on its own: version, bundled catalog, console, and one real run
# against a fake model. Usage: bash scripts/check_dist.sh dist/plnt-*.whl
set -euo pipefail
wheel="$(realpath "$1")"
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'kill $fake 2>/dev/null || true; rm -rf "$tmp"' EXIT
python -m venv "$tmp/venv"
"$tmp/venv/bin/pip" install -q "$wheel"
cd "$tmp"  # nothing from the checkout on the path
export PLNT_HOME="$tmp/home"

"$tmp/venv/bin/python" - <<'PY'
import plnt
from importlib.metadata import version
from pathlib import Path
from plnt.bundles import catalog
from plnt.server.app import CONSOLE_DIR

assert plnt.__version__ == version("plnt"), (plnt.__version__, version("plnt"))
found, errors = catalog.available()
assert {"support-desk", "booking-desk"} <= set(found), (sorted(found), errors)
assert all("_bundles" in str(b.path) for b in found.values()), "catalog read the checkout"
assert (CONSOLE_DIR / "index.html").is_file(), "console missing from wheel"
print("wheel ok:", plnt.__version__, sorted(found))
PY

python "$root/site/e2e/fake_model.py" 11557 &
fake=$!
sleep 1
PLNT_LOCAL_URL=http://127.0.0.1:11557 PLNT_PLANNER_MODEL=fake:1b \
  "$tmp/venv/bin/plnt" run support-desk "when are you open?" \
  --config business_name=Acme --config handoff_contact=a@acme.example \
  --config-json faq='[{"q":"When are you open?","a":"Mon-Fri 9-5."}]' | tee "$tmp/run.log"
grep -q "Mon-Fri 9-5" "$tmp/run.log"
echo "check_dist: ok"
