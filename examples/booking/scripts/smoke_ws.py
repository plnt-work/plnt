"""Slice-1 WebSocket smoke test.

Connects to ws://localhost:8080/v1/ws/<tenant>/<session>, sends one message,
collects replies for a few seconds, prints the result. Exits 0 if at least
the three expected reply roles arrived, 1 otherwise.

Usage:
    .venv/bin/python scripts/smoke_ws.py
    .venv/bin/python scripts/smoke_ws.py --tenant acme --message "book a table at Mario's tomorrow at 8pm"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets


EXPECTED_ROLES = {"classify_intent", "resolve_business", "check_availability"}


async def run(url: str, message: str, collect_seconds: float) -> int:
    print(f"→ connecting: {url}")
    async with websockets.connect(url) as ws:
        # First frame is session_started.
        opener = json.loads(await ws.recv())
        print(f"  session_started: workflow_id={opener.get('workflow_id')}")

        await ws.send(message)
        print(f"→ sent: {message!r}")

        seen_roles: set[str] = set()
        seen_events: list[dict] = []
        try:
            async with asyncio.timeout(collect_seconds):
                while True:
                    raw = await ws.recv()
                    evt = json.loads(raw)
                    seen_events.append(evt)
                    if evt.get("event") == "reply":
                        seen_roles.add(evt.get("role", ""))
                        print(f"  ← reply seq={evt['seq']} role={evt['role']}: {json.dumps(evt['content'])[:160]}")
                    elif evt.get("event") == "ack":
                        print(f"  ← ack ({evt.get('received_chars')} chars)")
                    else:
                        print(f"  ← {evt}")
                    if EXPECTED_ROLES <= seen_roles:
                        print("✓ all expected roles seen")
                        break
        except (asyncio.TimeoutError, TimeoutError):
            print(f"⏱  collection window of {collect_seconds}s elapsed")

    missing = EXPECTED_ROLES - seen_roles
    if missing:
        print(f"✗ missing roles: {sorted(missing)}")
        return 1
    print("✓ slice-1 demo pipeline works end-to-end")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost:8080")
    ap.add_argument("--tenant", default="demo")
    ap.add_argument("--session", default="sess1")
    ap.add_argument("--user", default="alice")
    ap.add_argument(
        "--message",
        default="find me an appointment at Joe's Pizza tomorrow at 7pm",
    )
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args()

    url = f"ws://{args.host}/v1/ws/{args.tenant}/{args.session}?user_id={args.user}"
    return asyncio.run(run(url, args.message, args.seconds))


if __name__ == "__main__":
    sys.exit(main())
