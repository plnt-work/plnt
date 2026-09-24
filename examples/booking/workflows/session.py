"""ConversationWorkflow — one Temporal Workflow per (tenant, user, session).

Long-lived. Awaits `user_message` signals. For each message:
  1. Collect an internal **trace** by calling micro-agents (classify_intent,
     optionally resolve_business + check_availability, optionally booking_saga).
  2. Run `synthesize_response` over the trace to produce ONE user-facing reply
     with a structured `action` payload the client can render.
  3. Push both the raw trace entries (for audit + admin debug) AND a final
     `say` reply (the user-facing one) to the replies queue.

The Maps surface renders only `say` replies → no more "CLASSIFY · BOOK"
bubbles leaking into the user's chat. The admin debug pane (showDebug=true)
keeps the full trace visible.

Workflow code is deterministic — no Date.now(), no random, no direct I/O.
All side effects live in Activities (workflows/activities.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from workflows.saga_booking import SagaInput, run_booking_saga


# Candidate platform → booking provider adapter. Google Places can't take
# bookings, so "google"-sourced candidates fall back to house_rules; future
# adapters are one entry each.
_PLATFORM_TO_PROVIDER = {"resy": "resy"}


def provider_for_platform(platform: str) -> str:
    return _PLATFORM_TO_PROVIDER.get(platform, "house_rules")


@dataclass
class SessionInput:
    """Workflow start argument — identifies the tenant + user + session triple."""

    tenant_id: str
    user_id: str
    session_id: str
    # Test hook: override which compute backend the micro-agents use.
    force_backend: str | None = None
    # Test hook: force a saga step (e.g. "notify") to fail so the
    # compensation path can be verified end-to-end.
    force_fail_step: str | None = None
    # Optional contact info attached to bookings created in this session.
    user_contact: str = ""


@dataclass
class Reply:
    seq: int
    role: str       # the micro-agent that produced it; "say" = synthesized user-facing
    content: dict[str, Any]


@workflow.defn(name="ConversationWorkflow")
class ConversationWorkflow:
    """Driven by user_message signals; replies are collected on the workflow."""

    def __init__(self) -> None:
        self._inbox: list[str] = []
        self._replies: list[Reply] = []
        self._reply_seq: int = 0
        self._closed: bool = False
        self._input: SessionInput | None = None
        # Pending booking state — populated after check_availability,
        # consumed by the confirm-intent path. None when no offer is open.
        self._pending: dict[str, Any] | None = None
        # Test hook flowed through to the saga so compensation paths are testable.
        self._force_fail_step: str | None = None
        # Rolling conversation history passed into classify_intent +
        # synthesize_response so the LLM has context. Bounded to last 6
        # turns to keep prompts cheap.
        self._history: list[dict[str, str]] = []
        # Candidates from the most recent show_candidates synthesizer action.
        # Used to resolve ordinal refs ("the second one") into a concrete pick.
        self._last_candidates: list[dict[str, Any]] = []
        # Most recent geolocation parsed from the trailing "[@lat,lng]" marker
        # the frontend appends to each user message.
        self._user_location: dict[str, float] | None = None
        # Best-match business from the most recent resolve — the enquiry
        # skill's profile grounding. Empty until a lookup lands.
        self._business_profile: dict[str, Any] = {}

    # ─────────────────────────────────────────────────── signals & queries

    @workflow.signal
    def user_message(self, text: str) -> None:
        if self._closed:
            return
        # Persist the user message as a reply too so reconnecting clients
        # can replay the full bidirectional history via replies_since.
        # Without this, navigating away + back leaves user bubbles missing
        # (only agent replies survive).
        self._push_reply("user", {"text": text})
        self._inbox.append(text)

    @workflow.signal
    def close(self) -> None:
        self._closed = True

    @workflow.query
    def replies_since(self, seq: int) -> list[dict[str, Any]]:
        """Return all replies with seq > the given value (long-poll style)."""
        return [
            {"seq": r.seq, "role": r.role, "content": r.content}
            for r in self._replies if r.seq > seq
        ]

    @workflow.query
    def state(self) -> dict[str, Any]:
        return {
            "inbox_pending": len(self._inbox),
            "replies_total": len(self._replies),
            "closed": self._closed,
            "has_pending_offer": self._pending is not None,
        }

    # ─────────────────────────────────────────────────── main loop

    @workflow.run
    async def run(self, inp: SessionInput) -> int:
        self._input = inp
        self._force_fail_step = inp.force_fail_step
        while not self._closed:
            try:
                await workflow.wait_condition(
                    lambda: bool(self._inbox) or self._closed,
                    timeout=timedelta(hours=24),
                )
            except TimeoutError:
                self._closed = True
                break

            if self._closed:
                break
            if not self._inbox:
                continue

            text = self._inbox.pop(0)
            await self._handle_message(text)
        return len(self._replies)

    # ─────────────────────────────────────────────────── handler

    async def _handle_message(self, text: str) -> None:
        """Drive a single user turn: run upstream micro-agents, collect their
        outputs into a turn-trace, synthesize one user-facing reply."""
        assert self._input is not None
        today_iso = workflow.now().date().isoformat()
        trace: list[dict[str, Any]] = []

        # Strip the frontend's trailing "[@lat,lng]" geolocation marker so it
        # doesn't leak into the LLM prompt, and stash the coords for the
        # downstream resolve_business step.
        text, user_location = _extract_geolocation(text)

        # Expand ordinal references to concrete candidate names so the LLM
        # has something to resolve. "the second one" → "book {candidate[1].name}".
        text = _expand_ordinal(text, self._last_candidates)
        self._user_location = user_location

        # Record this user turn before classification so the LLM sees it as
        # the latest in the history window.
        self._history.append({"role": "user", "content": text})
        self._history = self._history[-12:]  # keep last 6 turns (user + agent)

        # 1. classify_intent — what does the user want? History is passed so
        # follow-ups like "near mumbai" carry the prior topic forward.
        cls = await self._call_agent("classify_intent", {
            "text": text,
            "today": today_iso,
            "history": self._history[:-1],  # everything before the current msg
            "pending": self._pending_summary(),
        })
        cls_out = cls.get("output", {})
        trace.append({"role": "classify_intent", "output": cls_out})
        self._push_reply("classify_intent", cls_out)
        kind = str(cls_out.get("kind", "smalltalk"))

        # Override: when a slot is on offer and the user message explicitly
        # references one of those slots' ISO datetimes, treat as confirm
        # regardless of classifier output. Frontend slot-button clicks send
        # "yes book <iso>" which the LLM sometimes reads as `book`.
        if self._pending and self._pending.get("slots"):
            chosen = _pick_slot(text, list(self._pending["slots"]))
            iso_present = bool(_ISO_DT_RE.search(text))
            if iso_present and chosen in self._pending["slots"]:
                kind = "confirm"

        # 2. Branch on intent kind, but keep collecting the trace.
        # Push interim status replies so the user sees progress before the
        # synthesizer lands (each LLM call is ~2-3s).
        if kind in ("book", "query"):
            bq = str(cls_out.get("business_query") or "").strip() or text
            self._push_reply("system", {"note": f"Looking up {bq}…"})
            await self._handle_lookup(text, cls_out, today_iso, trace)
        elif kind == "question":
            self._push_reply("system", {"note": "Checking that for you…"})
            if await self._handle_question(text, today_iso, trace):
                return  # enquiry reply IS the user-facing say; skip the synthesizer
        elif kind == "confirm":
            biz = (self._pending or {}).get("business_name", "your booking")
            self._push_reply("system", {"note": f"Confirming {biz}…"})
            await self._handle_confirm_with_trace(trace, text)
        elif kind == "cancel":
            self._handle_cancel(trace)
        # else: smalltalk → trace is just classify_intent; synthesizer ad-libs

        # 3. Synthesize the user-facing reply over the full trace.
        await self._emit_synthesized_reply(text, trace, today_iso)

    async def _handle_lookup(
        self, text: str, cls_out: dict[str, Any],
        today_iso: str, trace: list[dict[str, Any]],
    ) -> None:
        """Resolve a business and (when a single match is found) offer slots."""
        business_query = str(cls_out.get("business_query") or "").strip()
        # When the classifier strips too much (e.g. "pizza places in mumbai"
        # → business_query="Mumbai"), the original user text carries the
        # category + location together. Pass both so resolve_business can
        # pick the richer signal.
        if not business_query:
            business_query = text

        resolve_inputs: dict[str, Any] = {
            "business_query": business_query,
            "user_text": text,
            "today": today_iso,
        }
        if self._user_location is not None:
            resolve_inputs["user_location"] = dict(self._user_location)
        resolved = await self._call_agent("resolve_business", resolve_inputs)
        r_out = resolved.get("output", {})
        trace.append({"role": "resolve_business", "output": r_out})
        self._push_reply("resolve_business", r_out)

        # Only run availability when we have a single confident match.
        best = r_out.get("best_match")
        if not isinstance(best, dict):
            return
        business_name = str(best.get("name") or "")
        if not business_name:
            return
        self._business_profile = dict(best)

        self._push_reply("system", {"note": f"Checking availability at {business_name}…"})

        slots = await self._call_agent(
            "check_availability",
            {
                "business_name": business_name,
                "category": str(best.get("category") or ""),
                "date_hint": str(cls_out.get("date_hint") or ""),
                "today": today_iso,
            },
        )
        s_out = slots.get("output", {})
        trace.append({"role": "check_availability", "output": s_out})
        self._push_reply("check_availability", s_out)

        slot_list = s_out.get("slots") or []
        if isinstance(slot_list, list) and slot_list:
            # Internal business_id used by the saga's idempotency key. Derived
            # from name+neighborhood so retries hit the same row.
            biz_key = f"{business_name}|{best.get('neighborhood') or ''}".lower()
            self._pending = {
                "business_id": biz_key,
                "business_name": business_name,
                "slots": [str(s) for s in slot_list],
                "provider": provider_for_platform(str(best.get("platform") or "")),
            }

    async def _handle_question(
        self, text: str, today_iso: str, trace: list[dict[str, Any]],
    ) -> bool:
        """Run the enquiry skill; emit its answer directly as the `say` reply.

        Retrieval (doc_context) is injected activity-side — the workflow only
        passes the question + whatever business profile it has. Returns False
        when the skill produced no answer, so the synthesizer can fall back.
        """
        enq = await self._call_agent("enquiry-generic", {
            "question": text,
            "business_profile": dict(self._business_profile),
            "today": today_iso,
        })
        e_out = enq.get("output", {}) or {}
        trace.append({"role": "enquiry-generic", "output": e_out})
        self._push_reply("enquiry-generic", e_out)
        say = str(e_out.get("say") or "").strip()
        if not say:
            return False
        self._finalize_say(say, None)
        return True

    def _handle_cancel(self, trace: list[dict[str, Any]]) -> None:
        if self._pending:
            self._pending = None
            trace.append({"role": "system", "output": {"note": "cleared pending offer"}})
        else:
            trace.append({"role": "system", "output": {"note": "no pending offer"}})

    async def _handle_confirm_with_trace(self, trace: list[dict[str, Any]], text: str) -> None:
        assert self._input is not None
        if not self._pending or not self._pending.get("slots"):
            trace.append({"role": "system", "output": {"note": "no pending offer"}})
            return

        # User may have clicked a specific slot button (frontend sends
        # "yes book 2026-06-22T19:30:00") — match it against pending. Falls
        # back to the first offered slot only when no datetime is present.
        chosen_slot = _pick_slot(text, list(self._pending["slots"]))

        saga_in = SagaInput(
            tenant_id=self._input.tenant_id,
            user_id=self._input.user_id,
            session_id=self._input.session_id,
            business_id=str(self._pending["business_id"]),
            slot=chosen_slot,
            provider=str(self._pending.get("provider") or "house_rules"),
            business_name=str(self._pending.get("business_name") or ""),
            user_contact=self._input.user_contact or self._input.user_id,
            force_fail_step=self._force_fail_step,
            force_backend=self._input.force_backend,
        )
        result = await run_booking_saga(saga_in)
        saga_out = {
            "booking_id": result.booking_id,
            "status": result.status,
            "note": result.note,
            "business_name": self._pending.get("business_name", ""),
            "slot": chosen_slot,
        }
        trace.append({"role": "booking_saga", "output": saga_out})
        self._push_reply("booking_saga", saga_out)
        if result.status == "confirmed":
            self._pending = None

    async def _emit_synthesized_reply(
        self, text: str, trace: list[dict[str, Any]], today_iso: str,
    ) -> None:
        """Run synthesize_response over the turn-trace; push the result as
        the single user-facing `say` reply."""
        # On synthesizer failure, fall back to a hand-shaped reply so the
        # user always sees SOMETHING.
        try:
            synth = await self._call_agent(
                "synthesize_response",
                {
                    "user_message": text,
                    "trace": trace,
                    "today": today_iso,
                    "history": self._history[:-1],
                    "pending": self._pending_summary(),
                },
            )
            s_out = synth.get("output", {}) or {}
            say = str(s_out.get("say") or "").strip()
            action = s_out.get("action")
        except Exception:  # noqa: BLE001 — never let synth break the turn
            say = ""
            action = None

        if not say:
            say, action = _fallback_reply(trace, self._pending)
        self._finalize_say(say, action)

    def _finalize_say(self, say: str, action: Any) -> None:
        """Push the single user-facing reply + do end-of-turn bookkeeping."""
        self._push_reply("say", {"say": say, "action": action})
        # Record agent turn so it joins the next prompt's history.
        self._history.append({"role": "assistant", "content": say})
        self._history = self._history[-12:]
        # If we just offered candidates, remember them for ordinal resolution
        # on the next turn. Otherwise clear so stale ordinals don't fire.
        if isinstance(action, dict) and action.get("kind") == "show_candidates":
            cands = action.get("candidates") or []
            self._last_candidates = [c for c in cands if isinstance(c, dict)]
        else:
            self._last_candidates = []

    def _pending_summary(self) -> dict[str, Any] | None:
        """Compact form of the pending offer for prompts. Hides internal IDs."""
        if not self._pending:
            return None
        return {
            "business_name": self._pending.get("business_name", ""),
            "slots": list(self._pending.get("slots") or [])[:5],
        }

    # ─────────────────────────────────────────────────── plumbing

    async def _call_agent(self, role: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._input is not None
        return await workflow.execute_activity(
            "run_microagent",
            args=[self._req(role, inputs)],
            start_to_close_timeout=timedelta(seconds=25),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=3,
            ),
        )

    def _req(self, role: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._input is not None
        return {
            "tenant_id": self._input.tenant_id,
            "user_id": self._input.user_id,
            "session_id": self._input.session_id,
            "role": role,
            "inputs": inputs,
            "force_backend": self._input.force_backend,
        }

    def _push_reply(self, role: str, content: dict[str, Any]) -> None:
        self._reply_seq += 1
        self._replies.append(Reply(seq=self._reply_seq, role=role, content=content))


def _fallback_reply(
    trace: list[dict[str, Any]], pending: dict[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Last-resort reply when the synthesizer doesn't produce a valid output.

    Scans the trace for the dominant signal and emits a hand-shaped say+action.
    This keeps the UX from ever showing a blank turn.
    """
    last = trace[-1] if trace else None
    if last and last["role"] == "booking_saga":
        out = last["output"]
        if out.get("status") == "confirmed":
            return (
                f"Booked — {out.get('business_name', 'your reservation')} for "
                f"{_human_time(out.get('slot', ''))}.",
                {"kind": "booking_confirmed", **{k: out[k] for k in ("business_name", "slot", "booking_id")}},
            )
        return f"Booking didn't complete: {out.get('note', 'unknown error')}.", {
            "kind": "booking_failed", "reason": out.get("note", ""),
        }
    if last and last["role"] == "check_availability":
        slots = last["output"].get("slots") or []
        if slots and pending:
            return (
                f"{pending.get('business_name', 'That place')} has slots — tap one to book.",
                {"kind": "offer_slots",
                 "business_name": pending.get("business_name", ""),
                 "slots": slots},
            )
    if last and last["role"] == "resolve_business":
        out = last["output"]
        cands = out.get("candidates") or []
        if out.get("needs_disambiguation") and cands:
            return ("I found a few options — which one?", {"kind": "show_candidates", "candidates": cands})
        if not cands:
            return ("I couldn't find a real business matching that. Try a specific name?", None)
    # smalltalk / classify-only
    return ("Hi! I can help find and book a business. What are you looking for?", None)


_ISO_DT_RE = __import__("re").compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?")

_GEO_RE = __import__("re").compile(
    r"\s*\[@\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*$"
)


def _extract_geolocation(text: str) -> tuple[str, dict[str, float] | None]:
    """Strip a trailing "[@lat,lng]" marker off `text` and return the parsed
    coords. Returns (text, None) when the marker is absent or malformed."""
    if not text:
        return text, None
    m = _GEO_RE.search(text)
    if not m:
        return text, None
    try:
        lat = float(m.group(1)); lng = float(m.group(2))
    except ValueError:
        return text, None
    return text[: m.start()].rstrip(), {"lat": lat, "lng": lng}

_ORDINALS = {
    "first": 0, "1st": 0, "one": 0,
    "second": 1, "2nd": 1, "two": 1,
    "third": 2, "3rd": 2, "three": 2,
    "fourth": 3, "4th": 3, "four": 3,
    "fifth": 4, "5th": 4, "five": 4,
    "last": -1,
}


def _expand_ordinal(text: str, candidates: list[dict[str, Any]]) -> str:
    """When the user says "the second one" after we showed a candidate list,
    expand it into a concrete pick the LLM can actually resolve.

    Examples (with 3 candidates Joey's / Ray's / PizzaExpress):
      "the second one"        → "book Ray's"
      "first"                 → "book Joey's"
      "I'll take the last"    → "book PizzaExpress"

    Returns the original text when no candidates remembered, or no ordinal
    detected, or the index is out of range.
    """
    if not candidates:
        return text
    lowered = text.lower()
    tokens = __import__("re").findall(r"[a-zA-Z0-9]+", lowered)
    if not tokens:
        return text
    pick: int | None = None
    for tok in tokens:
        if tok in _ORDINALS:
            pick = _ORDINALS[tok]
            break
    if pick is None:
        return text
    if pick == -1:
        pick = len(candidates) - 1
    if pick < 0 or pick >= len(candidates):
        return text
    name = str(candidates[pick].get("name") or "")
    nb = str(candidates[pick].get("neighborhood") or "")
    if not name:
        return text
    expanded = f"book {name}" + (f" in {nb}" if nb else "")
    return f"{text} (→ {expanded})"


def _pick_slot(user_text: str, offered: list[str]) -> str:
    """Honor the user's chosen slot. Frontend buttons send the ISO datetime
    inline ("yes book 2026-06-22T19:30:00") — match the longest ISO prefix
    in the user message against the offered list. Default to offered[0]
    when nothing matches (handles plain "yes" / "confirm")."""
    if not offered:
        return ""
    match = _ISO_DT_RE.search(user_text or "")
    if not match:
        return offered[0]
    requested = match.group(0)
    # Allow either "2026-06-22T19:30" or full "...:00" — match by prefix.
    for s in offered:
        if s.startswith(requested) or requested.startswith(s):
            return s
    return offered[0]


def _human_time(iso: str) -> str:
    # Best-effort cosmetic — Workflow code is deterministic so we don't
    # call datetime parsing helpers that touch tzinfo. Plain string slice.
    if "T" in iso:
        date, t = iso.split("T", 1)
        return f"{date} at {t[:5]}"
    return iso
