"""Slice-2 booking-saga smoke test (live WebSocket).

Sends two messages:
  1. A booking request (triggers classify → resolve → check_availability)
  2. "yes" (confirm → booking saga commits)

Then asserts the final reply is role=booking_saga with status=confirmed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

import websockets


async def run(url: str, book_msg: str, confirm_msg: str, collect_seconds: float) -> int:
    print(f"→ connecting: {url}")
    async with websockets.connect(url) as ws:
        opener = json.loads(await ws.recv())
        print(f"  session_started: workflow_id={opener.get('workflow_id')}")

        saga_seen = False

        async def collect_until(target_role: str, timeout: float) -> dict | None:
            try:
                async with asyncio.timeout(timeout):
                    while True:
                        evt = json.loads(await ws.recv())
                        if evt.get("event") != "reply":
                            print(f"  ← {evt.get('event')}")
                            continue
                        print(f"  ← reply seq={evt['seq']} role={evt['role']}: "
                              f"{json.dumps(evt['content'])[:140]}")
                        if evt["role"] == target_role:
                            return evt
            except (asyncio.TimeoutError, TimeoutError):
                return None

        # Round 1 — booking offer
        await ws.send(book_msg)
        print(f"→ sent: {book_msg!r}")
        avail = await collect_until("check_availability", collect_seconds)
        if not avail:
            print("✗ no check_availability reply")
            return 1
        slots = avail["content"].get("slots", [])
        if not slots:
            print(f"✗ no slots offered: {avail['content']}")
            return 1
        print(f"✓ slot offered: {slots[0]}")

        # Round 2 — confirm
        await ws.send(confirm_msg)
        print(f"→ sent: {confirm_msg!r}")
        saga = await collect_until("booking_saga", collect_seconds)
        if not saga:
            print("✗ saga did not produce a booking_saga reply")
            return 1
        status = saga["content"].get("status")
        booking_id = saga["content"].get("booking_id")
        print(f"  booking_id={booking_id} status={status}")
        if status != "confirmed":
            print(f"✗ saga did not commit: {saga['content']}")
            return 1
        saga_seen = True

    print("✓ slice-2 booking saga commits end-to-end" if saga_seen else "✗ no saga seen")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost:8080")
    ap.add_argument("--tenant", default="saga-demo")
    ap.add_argument("--session", default=None,
                    help="default: random — avoids re-using a session with a stale pending offer")
    ap.add_argument("--user", default="alice")
    ap.add_argument("--book",
                    default="book a table at Joe's Pizza tomorrow at 7pm")
    ap.add_argument("--confirm", default="yes book it")
    ap.add_argument("--seconds", type=float, default=15.0)
    args = ap.parse_args()
    session = args.session or f"smoke-{uuid.uuid4().hex[:8]}"
    url = f"ws://{args.host}/v1/ws/{args.tenant}/{session}?user_id={args.user}"
    return asyncio.run(run(url, args.book, args.confirm, args.seconds))


if __name__ == "__main__":
    sys.exit(main())
