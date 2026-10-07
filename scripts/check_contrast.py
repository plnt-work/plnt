#!/usr/bin/env python3
"""Fail if any text colour in design/tokens.css is under WCAG AA on the
backgrounds it is used on. Run in CI so the contrast rules are enforced,
not a suggestion. Usage: python scripts/check_contrast.py [tokens.css]"""
from __future__ import annotations

import re
import sys
from pathlib import Path

AA = 4.5

# (text token, background tokens it may sit on)
PAIRS: list[tuple[str, tuple[str, ...]]] = [
    ("ink", ("bg", "panel", "sunken", "accent-soft")),
    ("ink-2", ("bg", "panel", "sunken", "accent-soft")),
    ("muted", ("bg", "panel", "sunken")),
    ("accent-text", ("bg", "panel", "sunken", "accent-soft")),
    ("accent-ink", ("accent",)),
    ("ok", ("ok-soft", "bg", "panel", "sunken")),
    ("warn", ("warn-soft", "bg", "panel", "sunken")),
    ("danger", ("danger-soft", "bg", "panel", "sunken")),
    ("code-ink", ("code-bg",)),
    ("code-dim", ("code-bg",)),
]


def luminance(hex_: str) -> float:
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    chans = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def tokens(path: Path) -> dict[str, str]:
    text = path.read_text()
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,6})\s*;", text))


def main() -> int:
    default = Path(__file__).parent.parent / "design" / "tokens.css"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    t = tokens(path)
    failed = 0
    for fg, bgs in PAIRS:
        for bg in bgs:
            if fg not in t or bg not in t:
                print(f"MISSING  --{fg} on --{bg}")
                failed += 1
                continue
            r = ratio(t[fg], t[bg])
            ok = r >= AA
            failed += not ok
            print(f"{'ok  ' if ok else 'FAIL'}  {r:5.2f}  --{fg} {t[fg]} on --{bg} {t[bg]}")
    if failed:
        print(f"\n{failed} pair(s) under {AA}:1. Fix design/tokens.css (see design/README.md).")
        return 1
    print(f"\nAll text pairs pass {AA}:1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
