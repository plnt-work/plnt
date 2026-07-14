#!/usr/bin/env bash
# Regenerate the pitch PDFs from source markdown.
#
# Requires: pandoc + Google Chrome (headless).
#
# Usage:
#   ./docs/build-pdfs.sh
#
# Output:
#   docs/pdf/one-pager.pdf
#   docs/pdf/full-pitch.pdf

set -euo pipefail

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if [ ! -x "$CHROME" ]; then
  echo "Chrome not found at: $CHROME"
  echo "Set CHROME env var to the correct path and retry."
  exit 1
fi

if ! command -v pandoc >/dev/null 2>&1; then
  echo "pandoc not found — install with: brew install pandoc"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p docs/pdf

build_one() {
  local src="$1"
  local out_stem="$2"
  local title="$3"
  shift 3
  local extra_pandoc_args=("$@")

  echo ">> $src -> docs/pdf/${out_stem}.pdf"

  pandoc "$src" \
    --standalone \
    --embed-resources \
    --css=docs/pdf-style.css \
    --metadata pagetitle="$title" \
    ${extra_pandoc_args[@]+"${extra_pandoc_args[@]}"} \
    -o "docs/pdf/${out_stem}.html"

  "$CHROME" \
    --headless \
    --disable-gpu \
    --no-pdf-header-footer \
    --print-to-pdf="$ROOT/docs/pdf/${out_stem}.pdf" \
    "file://$ROOT/docs/pdf/${out_stem}.html" 2>/dev/null
}

build_one docs/ONE-PAGER.md  one-pager  "plnt — one-pager"
build_one docs/FULL-PITCH.md full-pitch "plnt — pitch" --toc --toc-depth=2

echo
echo "Done. PDFs in docs/pdf/:"
ls -lh docs/pdf/*.pdf
