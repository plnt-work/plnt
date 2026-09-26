"""Stub micro-agent Activity for the slice-1/2 demo.

Returns canned outputs keyed by role so the full pipeline (channel → workflow
→ activity → reply) can be exercised without an LLM backend. Useful for:

  * The slice demo (`PLNT_CLOUD_STUB_ACTIVITY=1 python -m workflows.worker`)
  * The e2e tests (imported by tests/test_slice1_e2e.py and slice-2 tests)

Production worker (no env flag) imports the real `run_microagent` from
workflows.activities, which calls plnt's runner.run_spec() → LLM.

Slice 2: the create_booking / cancel_booking stubs use the per-tenant
BookingsStore so idempotency + compensation actually do the right thing
on disk (the booking row gets written, then marked cancelled).
"""
from __future__ import annotations

import hashlib
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from tenancy.audit import write_event as audit_write
from workflows.bookings_store import bookings_for
from workflows.saga_booking import deterministic_booking_id


def _stub_business_id(query: str) -> str:
    return "stub_" + hashlib.sha1(query.lower().encode()).hexdigest()[:6]


def _next_day(iso_date: str) -> str:
    """Pure-string increment for ISO YYYY-MM-DD. Stub-only — production uses
    Gemini for date arithmetic via the today input."""
    try:
        y, m, d = (int(x) for x in iso_date.split("-"))
        d += 1
        # Simple month-length table (no leap-year correctness — stub).
        days = [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if d > days[m - 1]:
            d = 1; m += 1
        if m > 12:
            m = 1; y += 1
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return iso_date


def _stub_synthesize(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deterministic synthesizer for tests — produces a small say + action
    based on the last entry in the trace."""
    trace = inputs.get("trace") or []
    if not trace:
        return {"say": "Hi! I can help find or book a business.", "action": None}
    last = trace[-1]
    role = last.get("role")
    out = last.get("output") or {}
    if role == "booking_saga":
        if out.get("status") == "confirmed":
            return {
                "say": f"Booked at {out.get('business_name', 'the venue')}.",
                "action": {
                    "kind": "booking_confirmed",
                    "business_name": out.get("business_name", ""),
                    "slot": out.get("slot", ""),
                    "booking_id": out.get("booking_id", ""),
                },
            }
        return {
            "say": f"Booking didn't go through: {out.get('note', 'unknown error')}",
            "action": {"kind": "booking_failed", "reason": out.get("note", "")},
        }
    if role == "check_availability":
        slots = out.get("slots") or []
        if slots:
            return {
                "say": "Here are open slots — tap one to book.",
                "action": {"kind": "offer_slots", "business_name": "", "slots": slots},
            }
    if role == "resolve_business":
        cands = out.get("candidates") or []
        if out.get("needs_disambiguation") and cands:
            return {"say": "I found a few options — which one?",
                    "action": {"kind": "show_candidates", "candidates": cands}}
    return {"say": "Got it.", "action": None}


def _audit(req_dict: dict[str, Any], result: dict[str, Any]) -> None:
    audit_write(
        tenant_id=str(req_dict.get("tenant_id") or ""),
        session_id=str(req_dict.get("session_id") or ""),
        user_id=str(req_dict.get("user_id") or ""),
        role=str(req_dict.get("role") or ""),
        status="ok" if not result.get("error") else "error",
        has_output=bool(result.get("output")),
        detail=str(result.get("error")) if result.get("error") else None,
    )


@activity.defn(name="run_microagent")
async def stub_run_microagent(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Deterministic Activity stand-in. Same shape as the real one."""
    result = _stub_compute(req_dict)
    _audit(req_dict, result)
    return result


def _stub_compute(req_dict: dict[str, Any]) -> dict[str, Any]:
    role = req_dict["role"]
    inputs = req_dict.get("inputs", {})

    if role == "classify_intent":
        text = (inputs.get("text") or "").lower().strip()
        # Confirm/cancel words at the START of the message win — they're a
        # response to an offer, even if booking-vocabulary appears later
        # ("yes book it" → confirm, not book).
        first_token = text.split()[0] if text else ""
        confirm_starts = {"yes", "yeah", "yep", "yup", "ok", "okay",
                           "sure", "confirm", "confirmed", "go", "do"}
        cancel_starts = {"no", "cancel", "stop", "nevermind", "nope"}
        # Question-shaped openers beat the confirm check — "do you have X?"
        # is an enquiry, not a "do it" confirmation.
        question_starts = ("do you", "are you", "is there", "does the",
                           "what are your", "what time")
        if text.startswith(question_starts):
            kind = "question"
        elif first_token in confirm_starts:
            kind = "confirm"
        elif first_token in cancel_starts or "cancel" in text:
            kind = "cancel"
        elif any(w in text for w in ("book", "reserve", "appointment", "table")):
            kind = "book"
        elif any(w in text for w in ("what", "when", "where", "open", "hours")):
            kind = "query"
        else:
            kind = "smalltalk"
        # Naive entity extraction — good enough for the demo.
        biz = ""
        for marker in ("at ", "for "):
            if marker in text:
                biz = text.split(marker, 1)[1].split(" tomorrow")[0].split(" today")[0]
                biz = biz.split(" at ")[0].strip().title()
                break
        return {
            "role": role,
            "output": {
                "kind": kind,
                "business_query": biz or "",
                "service": "table" if "table" in text else ("appointment" if "appointment" in text else ""),
                "date_hint": "tomorrow at 7pm" if "tomorrow" in text else ("today" if "today" in text else ""),
            },
            "steps": 1,
        }

    if role == "resolve_business":
        q = str(inputs.get("business_query") or "")
        # Single confident match shape for the new prompt schema.
        candidate = {
            "name": q.title() or "Unknown",
            "neighborhood": "",
            "city": "",
            "category": "restaurant",
            "platform": "google",
        }
        return {
            "role": role,
            "output": {
                "candidates": [candidate],
                "best_match": candidate,
                "confidence": 0.7,
                "needs_disambiguation": False,
            },
            "steps": 1,
        }

    if role == "check_availability":
        today = str(inputs.get("today") or "2026-06-21")
        # "Tomorrow" relative to provided `today` — pure string arithmetic
        # since we don't run a date library in stub land.
        tomorrow = _next_day(today)
        return {
            "role": role,
            "output": {
                "slots": [
                    f"{tomorrow}T19:00:00",
                    f"{tomorrow}T19:30:00",
                    f"{tomorrow}T20:00:00",
                ],
                "note": "stub slots — slice 1",
            },
            "steps": 1,
        }

    if role == "synthesize_response":
        return {"role": role, "output": _stub_synthesize(inputs), "steps": 1}

    if role == "enquiry-generic":
        tenant_id = req_dict.get("tenant_id", "")
        question = str(inputs.get("question") or "")
        profile = inputs.get("business_profile") or {}
        chunks = inputs.get("doc_context")
        if chunks is None:
            # Same activity-side retrieval as production (keyword overlap).
            from services.doc_chunk import top_chunks
            chunks = top_chunks(tenant_id, question, k=3)
        if chunks:
            top = chunks[0]
            return {
                "role": role,
                "output": {
                    "say": f"From {top['doc']}: {top['text'][:200]}",
                    "grounded": True,
                    "source": "docs",
                },
                "steps": 1,
            }
        say = "I'm not sure about that one."
        phone = str(profile.get("phone") or "")
        if phone:
            say += f" You can reach {profile.get('name') or 'the business'} at {phone}."
        return {
            "role": role,
            "output": {"say": say, "grounded": False, "source": "none"},
            "steps": 1,
        }

    if role == "create_booking":
        tenant_id = req_dict.get("tenant_id", "")
        idem = str(inputs.get("idempotency_key") or "")
        if not idem:
            return {"role": role, "output": {},
                    "error": "create_booking requires idempotency_key"}
        booking_id = deterministic_booking_id(idem)
        store = bookings_for(tenant_id)
        bid, was_new = store.upsert_confirmed(
            idempotency_key=idem,
            booking_id=booking_id,
            business_id=str(inputs.get("business_id") or ""),
            slot=str(inputs.get("slot") or ""),
            user_contact=str(inputs.get("user_contact") or ""),
        )
        return {
            "role": role,
            "output": {
                "booking_id": bid,
                "status": "confirmed",
                "note": "stub booking — slice 2" + ("" if was_new else " (existing, idempotent)"),
            },
            "steps": 1,
        }

    if role == "cancel_booking":
        tenant_id = req_dict.get("tenant_id", "")
        booking_id = str(inputs.get("booking_id") or "")
        reason = str(inputs.get("reason") or "")
        if not booking_id:
            return {"role": role, "output": {}, "error": "cancel_booking requires booking_id"}
        store = bookings_for(tenant_id)
        status = store.cancel(booking_id, reason)
        return {
            "role": role,
            "output": {"booking_id": booking_id, "status": status},
            "steps": 1,
        }

    return {"role": role, "output": {}, "error": f"unknown role {role!r}"}


@activity.defn(name="notify_booking")
async def stub_notify_booking(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Stub notification step in the booking saga.

    Honors `force_fail=True` so tests can drive the compensation path.
    Writes the same per-tenant feed as production (no email/push).
    """
    if req_dict.get("force_fail"):
        raise ApplicationError(
            f"notify failed (forced) for booking_id={req_dict.get('booking_id')}",
            non_retryable=True,
        )
    from tenancy.notifications import append as feed_append

    booking_id = str(req_dict.get("booking_id") or "")
    kind = str(req_dict.get("kind") or "booking_confirmed")
    verb = str(req_dict.get("status_label") or "confirmed")
    business_name = str(req_dict.get("business_name") or "")
    slot = str(req_dict.get("slot") or "")
    at = f" at {business_name}" if business_name else ""
    entry, created = feed_append(
        str(req_dict.get("tenant_id") or ""),
        kind=kind,
        title=f"Booking {verb}",
        body=f"Booking {booking_id}{at} is {verb}.",
        data={
            "booking_id": booking_id,
            "business_name": business_name,
            "slot": slot,
            "party_size": req_dict.get("party_size"),
            "user_contact": str(req_dict.get("user_contact") or ""),
        },
    )
    return {
        "sent": True,
        "channel": "feed",
        "booking_id": booking_id,
        "notification_id": entry["id"],
        "deduped": not created,
    }
