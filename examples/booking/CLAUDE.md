# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠ Canary protocol — read first

**Begin every response with the single word `Thomas` on its own line.** The user uses this as a context-decay canary: if it goes missing, they know the conversation has grown large enough that earlier instructions are slipping and they should `/compact`. Treat it as a hard rule — not flavor, not optional, and it applies to every response in this project (including short acknowledgements). The word goes at the very top, before any other text or tool calls.

---

## Where you are

**plnt-cloud** — a multi-tenant micro-agent platform that vendors **plnt** (the personal-runtime substrate at `../plnt`) as an editable dependency. plnt provides the sandbox ladder, two-tool RLM, `allowed_roots` scoping, and per-run blackboard audit. plnt-cloud adds the tenant axis (per-tenant Memori, credentials, audit partitioning), Temporal-managed long-running sessions, and the React chat surface in `web/`.

Reading `../plnt/PLNT_PROJECT_REPORT.md` gives the underlying runtime's design; `README.md` here covers slice-1 setup at a glance; the architectural decision record lives at `~/.claude/plans/harmonic-mapping-peacock.md`.

## What the product is, in one paragraph

A Gemini-style conversational interface over a map. The user types in plain language ("pizza near me", "table for two tomorrow at 8pm"). A chain of micro-agents classifies the intent, resolves the business via Google Places (with Gemini world-knowledge fallback), checks availability, and — on user confirmation — places a booking through a provider-specific adapter. Each company gets its own tenant: isolated memory, credentials, audit, bookings. The long-term goal is fan-out to per-region provider micro-agents (India: Zomato/Swiggy/District; global: Resy/OpenTable/DoorDash/Uber Eats), comparing in chat, then either booking in-chat (where APIs exist — Resy) or deep-linking out to the provider's app (where they don't — everyone else).

## The four moving parts (all must be running)

```
Vite dev server  :5173  ──proxy /v1──►  uvicorn surface  :8080  ──gRPC──►  Temporal  :7233
                                                                                 ▲
                                              python -m workflows.worker ───────┘
                                                  (polls task queue)
```

`web/vite.config.ts` proxies `/v1/*` (including WebSockets) from 5173 to 8080, so the React app talks same-origin in dev. The api + worker now run inside `docker-compose.yml` by default (MA-P7), with the host source bind-mounted so edits are picked up live. A bare-metal fallback (uvicorn + worker on the host) is kept for fast Python iteration without container reload churn.

`cloudflared` is an optional service in the same compose file: when `CLOUDFLARE_TUNNEL_TOKEN` is set in `.env`, it brings up a named tunnel whose Public Hostnames in the Cloudflare Zero Trust dashboard route `api.dev.<zone>` → `api:8080` and `ws.dev.<zone>` → `api:8080/ws`. Those two URLs are what the mobile app's `EXPO_PUBLIC_API_BASE` / `EXPO_PUBLIC_WS_BASE` point at (see `mobile/.env.development.example`).

## Commands

All from `plnt-cloud/` unless noted.

```bash
# ─── Default flow — full stack in Docker (MA-P7) ────────────────────
# Brings up: postgres, temporal, temporal-ui, api, worker,
#            cloudflared (if CLOUDFLARE_TUNNEL_TOKEN is set in .env).
docker compose up -d --build           # rebuild api/worker image after deps change
docker compose logs -f worker          # tail the worker (replaces /tmp/plnt-cloud-worker.log)
docker compose logs -f api             # tail uvicorn

# CORS for the surface is driven by CORS_ORIGINS (comma-separated).
# Add the cloudflared hostname here when you wire mobile:
#     CORS_ORIGINS=http://localhost:5173,https://api.dev.<your-zone>

# ─── Bare-metal fallback — when iterating fast on Python ────────────
# Skip the api+worker containers, run them on the host instead.
pip install -e ../plnt
pip install -e .[dev]
docker compose up -d postgres temporal temporal-ui
# Worker — MUST have .env sourced or it falls back to local Ollama and 400s.
# This is the #1 cause of "chat returns nothing".
set -a; . ./.env; set +a
nohup .venv/bin/python -m workflows.worker > /tmp/plnt-cloud-worker.log 2>&1 &
disown
uvicorn surface.app:app --reload --port 8080

# ─── Frontend (always on the host) ──────────────────────────────────
cd web && npm run dev                 # http://localhost:5173/atlas
cd web && npm run build               # tsc + vite build, both must pass
cd web && npm run lint

# ─── Tests — in-process WorkflowEnvironment, no Docker needed ───────
pytest                                # all
pytest tests/test_slice1_e2e.py -k "happy_path" -v
pytest tests/test_slice2_saga.py::test_compensation_path

# ─── Live smoke (needs the stack running, either flow) ──────────────
python scripts/smoke_ws.py
python scripts/smoke_saga.py
```

Worker log lives at `/tmp/plnt-cloud-worker.log`. The runner emits structured JSON events (`model_call`, `tool_call`, `tool_result`, `model_result`) and httpx logs every Gemini/Ollama hit. `tail -f` it when debugging silent latency.

## How a turn flows

`channels/web_ws.py:ws_handler` accepts a connection at `/v1/ws/{tenant_id}/{session_id}?user_id=X`. It:

1. Calls `verify_tenant_key()` — open by default; gated by `PLNT_CLOUD_REQUIRE_AUTH=1`.
2. Starts-or-attaches a `ConversationWorkflow` with a **deterministic workflow ID** `session:{tenant}:{user}:{session}`. Reconnects re-attach to the same workflow → replies replay via `replies_since(0)`. **But** stale state from a prior workflow ID will also resurface; the "+ new" button in the UI rotates `sessionStorage["atlas_session_id"]` to escape.
3. Runs two coroutines: inbound forwards each WS frame to `handle.signal("user_message", text)`; outbound polls `handle.query("replies_since", last_seq)` every 250ms.

`workflows/session.py:ConversationWorkflow._handle_message` then drives the chain:

```
user_message → classify_intent → (system "Looking up X…")
             → resolve_business → (system "Checking availability at Y…")
             → check_availability → synthesize_response → say  ← only user-facing reply
```

Each step pushes its raw output as a `Reply` on the workflow with an incrementing `seq`. Only `say` and `system` roles render in the consumer chat; the others are visible in the operator console's debug pane (`/console`).

The synthesizer turns the whole turn-trace into ONE reply with an optional `action` payload (`offer_slots` / `show_candidates` / `booking_confirmed` / `booking_failed`) that the client renders as inline action cards in the chat **and** in the floating `PlaceCard` over the map.

## Workflow code is sandboxed — passthrough is mandatory

`workflows/worker.py` configures `SandboxedWorkflowRunner` with an explicit passthrough list:

```python
restrictions = SandboxRestrictions.default.with_passthrough_modules(
    "httpx", "httpcore", "h11", "h2", "hpack", "anyio", "sniffio",
    "openai", "sqlite3",
    "plnt", "workflows.activities", "workflows.bookings_store",
    "services", "services.places", "tenancy", "tenancy.factory",
    "memory", "memory.memori_adapter",
)
```

If you add an Activity module that imports anything new (a new HTTP client, a new SDK), you almost certainly need to add it here. **Symptom of forgetting**: every workflow activation crashes with `RestrictedWorkflowAccessError: Cannot access urllib.request.Request from inside a workflow`, the worker process stays alive, acks still arrive on the WS, but no replies ever come back. This is the #2 cause of "chat returns nothing" (after a missing `.env`).

## Speed contract: one-shot skills

Every skill prompt ends with `Respond with exactly "FINAL: <json>" and nothing else`. The activity dispatcher (`workflows/activities.py:_build_spec`) sets `spec.inputs["max_steps"] = 1` and every `skill.toml` declares `tools = []`. Together this forces plnt's RLM into a single Gemini call per skill — without it, the model wastes 2–3 seconds per step on speculative `search`/`execute` tool rounds.

**Belt-and-suspenders:** all three (prompt rule + `tools=[]` + `max_steps=1`) are required. Removing any one regresses latency. The prompts already enforce FINAL; `tools=[]` strips the tool schema from the OpenAI-compatible call; `max_steps=1` is the runner-side ceiling.

A turn that goes through the full chain (classify → resolve → check_availability → synth) is currently ~10s wall-clock: four sequential Gemini Flash calls at ~2.5s each. The interim `system` status bubbles pushed between steps (see `_handle_message`) are the perceived-latency mitigation, not a real speedup. Real speedup needs fan-out, but the deps are serial: `classify.business_query` feeds `resolve`, `resolve.best_match` feeds `availability`.

## Per-tenant data layout at `~/.plnt-cloud/`

```
~/.plnt-cloud/
├── places_cache.db              shared across tenants (Places data is public)
└── tenants/<tid>/
    ├── tenant.json              display name + hashed api_key
    ├── memori.db                SQLite turns table, scoped (user_id, process_id=role)
    ├── bookings.db              idempotency-keyed booking ledger
    └── audit.jsonl              every Activity invocation
```

`tenancy/factory.py:for_tenant(tid)` (lru_cached) builds the per-tenant bundle. Memori is `_SqliteStub` by default; `pip install memorisdk` enables real semantic recall (currently disabled — the stub is recency-only).

**Memori is scoped by skill role** (`process_id=spec.role`). `synthesize_response` only recalls prior synth outputs, not the user's raw messages. The within-session conversation continuity layer is the workflow's own `_history` rolling 12-turn buffer (not Memori). Don't change the scoping without understanding both layers — within-session goes through `_history`, cross-session through Memori.

## Frontend conventions worth knowing

- **Routes**: `/` → `/atlas` (map + scoped chat in a right rail), `/console` (operator dashboard). **No sign-in pages**; backend is open by default. The earlier SignIn / AdminSignIn / route guards / `lib/session.ts` were explicitly cut as vibe code — don't bring them back unless the user asks.
- **State persistence**: `useWsChat` hydrates `items[]` from `localStorage[atlas_timeline:{tenant}:{session}]` on mount so nav-back from `/console` shows the chat immediately. The WS reconnect's `replies_since(0)` replay backfills via seq-dedup.
- **Geolocation**: Atlas requests it on mount, appends `[@lat,lng]` to every outgoing message. The status pill in the right-rail `SessionBar` lets the user retry if originally blocked. **Backend does not yet parse this into a Places `locationBias`** — TODO in `_ground_resolve_business`.
- **Google Maps**: default look (no `disableDefaultUI: true`, no custom paper restyle). Rendered via `@vis.gl/react-google-maps` (`<Map mapId={...}>` + `<AdvancedMarker>` + `<Pin>` colored by vertical from `features/places/verticals.ts`). Selected pin gets a soft 24px CSS accent ring layered inside the marker DOM so the highlight tracks pans/zooms. The user's location is a small blue dot via a custom `<AdvancedMarker>`. When `VITE_GOOGLE_MAPS_KEY` is unset, `MapSurface` renders a "set the key" fallback panel; the floating MapSearch + filter chips above still work.
- **Action cards**: the scoped `ChatPanel` inside the right rail is the **single** surface for `offer_slots` / `booking_confirmed` / `booking_failed`. There is no floating `PlaceCard` anymore — the rail replaces it. If you add a new `action.kind`, you only have to wire it in one place.
- **Outgoing envelope**: every user message from `features/chat/ChatPanel` is prefixed with `[biz:<place_id> agent:<slug>] <user text>` before hitting the WS. The current Gemini synth doesn't parse it; it just lands in the prompt context. The MA stream parses it later. Geolocation `[@lat,lng]` is appended after that envelope in `Atlas.onSendRaw`.
- **Feature folders**: app surfaces (Atlas / Console) compose primitives from `web/src/features/{places,agents,chat,console}/`. `places/` owns the map, search, business header, sample seed and vertical registry; `agents/` owns the agent registry + AgentStrip; `chat/` owns the WS hook, scoped ChatPanel, DisconnectSkeleton, and SessionBar; `console/` owns the FE-Console-v2 admin shell (`ConsoleShell.tsx` + the 6 `tabs/*.tsx`). Reusable UI primitives stay in `web/src/components/ui/`. New work goes into a feature folder; the bare `components/` tree is for shadcn-style primitives only.
- **Console v2 data layer**: every poll on `/console` goes through `@tanstack/react-query` via hooks in `web/src/lib/queries/admin.ts`. Hooks dispatch to either `lib/api/admin-v2.ts` (live) or `lib/api/admin-mocks.ts` (deterministic in-memory store seeded off `features/places/sample-businesses.ts` + `features/agents/registry.ts`). Toggle the mock/live source with the single `LIVE_MODE` const at the top of `lib/queries/admin.ts` (or `VITE_ADMIN_LIVE=1`). The mocks intentionally match the v8 endpoint shapes the MA stream is building, so swapping is one-line per hook with no component edits.
- **Console tabs**: `?tab=overview|reservations|conversations|users|agents|settings` is the URL contract; `?session=<sid>` deep-links straight into the Conversations transcript drawer; `?tenant=<tid>` clamps the project picker. Anything that should outlive a refresh goes into the URL, not local state. The old setInterval-based polling, three-pane split, and TenantRail+MetricGrid+DebugChat components are gone — don't bring them back.
- **Styling**: hybrid setup as of FE-P1.
  - Tokens live at `web/src/styles/tokens.css` (`--space-*`, `--color-{paper,ink,coal}-{50..900}`, `--radius-*`, `--shadow-*`, `--motion-*`). One source of truth; both Tailwind and the legacy CSS consume them.
  - Tailwind v4 is wired via `@tailwindcss/vite` and is the layer for **new components**. The same tokens are mirrored into `web/src/styles/tailwind.css` `@theme {...}` so `bg-paper-100`, `text-ink-700`, `shadow-md`, etc. all resolve.
  - The 1500-line `web/src/styles.css` is intentionally NOT bulk-migrated — it now reads tokens via the legacy aliases at the bottom of `tokens.css`. Migrate per-component as those components get touched for another reason; don't open a Tailwind PR just to flip classes.
  - shadcn-style Radix primitives live in `web/src/components/ui/` (Button, Dialog, AlertDialog, Tooltip, Skeleton, Field, Icon). New surfaces compose these; don't re-roll dialogs/buttons from scratch.
  - Other libs: `motion` (motion.dev) for transitions, `lucide-react` for icons, `@fontsource-variable/geist` for body type, `@tanstack/react-query` for any new server-state polling (existing setInterval hooks stay until rewritten), `@vis.gl/react-google-maps` for the `<Map>` + `<AdvancedMarker>` + `<Pin>` stack on `/atlas`.
  - The `theme-console` class still scopes the dark operator theme.

## Env contracts

- `plnt-cloud/.env` (gitignored): `PLNT_FORCE=cloud`, `PLNT_CLOUD_URL=https://generativelanguage.googleapis.com/v1beta/openai`, `PLNT_CLOUD_API_KEY=...`, `PLNT_CLOUD_SMALL_MODEL=gemini-2.5-flash`, `PLNT_CLOUD_DEEP_MODEL=gemini-2.5-pro`. The worker reads these via `os.environ` — you **must** `set -a; . ./.env; set +a` before launching it (the dockerised worker does this in `scripts/worker-entrypoint.sh` after the file is bind-mounted at `/env/.env`; the bare-metal recipe does it inline). Optional: `CORS_ORIGINS` (comma-separated; defaults to the Vite dev origin) and `CLOUDFLARE_TUNNEL_TOKEN` (enables the `cloudflared` compose service).
- `plnt-cloud/web/.env.local` (gitignored): `VITE_GOOGLE_MAPS_KEY`, `VITE_DEFAULT_TENANT=demo`, optional `VITE_ADMIN_TOKEN` when `PLNT_CLOUD_REQUIRE_AUTH=1`.
- Optional: `PLNT_CLOUD_STUB_ACTIVITY=1` swaps `run_microagent` for the deterministic stub in `workflows/stub_activities.py` (tests use this; lets you exercise the channel + workflow layer without Gemini).
- Optional: `PLNT_CLOUD_PLACES_KEY` (falls back to `PLNT_CLOUD_API_KEY`) enables real Places Text Search; activities silently fall back to Gemini world-knowledge when disabled or 403'd.

## Things that look like bugs but aren't

- **Worker process exists but chat returns no replies** → check `/tmp/plnt-cloud-worker.log` for `RestrictedWorkflowAccessError`. The worker stays alive but every activation crashes. Add the offending module to the passthrough list in `workflows/worker.py` and restart the worker.
- **Worker hits Ollama (`127.0.0.1:11434`) instead of Gemini, returning HTTP 400** → `.env` wasn't sourced before `python -m workflows.worker`. Kill it and restart with `set -a; . ./.env; set +a` first.
- **"hi" elicits a reply from yesterday's conversation** → workflow IDs are deterministic per `(tenant, user, session)`. Click "+ new" in the chat header or clear `sessionStorage["atlas_session_id"]`.
- **Pin positions don't match a real place** → as of FE-P2 pins come from the local seed in `features/places/sample-businesses.ts`. Real coords are read straight from each `Business.{lat, lng}` and dropped via `<AdvancedMarker>`; if a real address looks wrong, edit the seed. Backend-driven pins land when MA-P3's `/v1/places/area` ships and `_ground_resolve_business` returns lat/lng on the `Candidate` type.
- **Memori shows the same 5 turns regardless of query** → `_SqliteStub` is recency-only. `pip install memorisdk` and unset `PLNT_CLOUD_MEMORY_BACKEND` for real recall.
- **Map doesn't look like Google Maps** → someone has re-introduced `disableDefaultUI: true` or a custom `styles` array (the original "paper" restyle). Drop both — default Google look is the contract.
- **History wipes after navigating /atlas → /console → /atlas** → `useWsChat` was previously calling `setItems([])` on every reconnect. It now hydrates from `localStorage[atlas_timeline:...]`. If you regress this, the symptom returns.

## Outstanding work the user has asked about or queued

These are real TODOs the user has either mentioned or implied:

- **Backend `[@lat,lng]` parsing** — frontend appends coords to every message; `_ground_resolve_business` should strip the trailing `[@x,y]`, parse it, and pass to Places as `locationBias.circle`. ~5 lines.
- **Real `lat/lng` from Places → `MapPin`** — make pins drop at the addresses Google actually returned, not the deterministic SVG positions. Requires plumbing `lat`/`lng` through the `Candidate` type and `GoogleMapHost`.
- **Provider micro-agents** — Zomato / Swiggy / District / Resy / OpenTable adapters per the deep-research output. Discovery layer already supports a `platform` tag on candidates and the UI renders a `platform-badge`. Pattern follows `restaurant-mcp`: each result tagged `resy-12345` / `opentable-67890` / etc., downstream availability/booking dispatches to the right adapter.
- **Real Memori** — install `memorisdk`, swap `_RealMemori` in. Mostly a config flip.
- **Cross-channel user identity** — same user on web + WhatsApp should converge to one `user_id`. Not built; needed before WhatsApp slice.
- **Per-tenant Temporal namespaces** — currently everyone shares `default`. Slice 5.
- **MA-stream admin v2 endpoints** — the FE-Console-v2 UI ships against mocks in `web/src/lib/api/admin-mocks.ts`. Backend needs to implement, with these exact shapes (already typed in `web/src/lib/api/admin-v2.ts`):
  - `GET    /v1/admin/tenants/:tid/bookings?status=&user_id=&since=&limit=` → `{ bookings: Booking[], total }`
  - `GET    /v1/admin/tenants/:tid/sessions?user_id=&limit=` → `{ sessions: SessionRow[], total }`
  - `GET    /v1/admin/tenants/:tid/sessions/:sid/transcript` → `{ transcript: TranscriptEntry[] }`
  - `GET    /v1/admin/tenants/:tid/users` → `{ users: UserSummary[] }`
  - `GET    /v1/admin/tenants/:tid/users/:uid` → `{ user_id, bookings, sessions }`
  - `GET    /v1/marketplace/agents?vertical=` → `{ agents: MarketplaceAgent[] }`
  - `GET    /v1/admin/tenants/:tid/agents` → `{ agents: InstalledAgent[] }`
  - `POST   /v1/admin/tenants/:tid/agents/:slug` (install)
  - `PATCH  /v1/admin/tenants/:tid/agents/:slug` (toggle enabled / patch config)
  - `DELETE /v1/admin/tenants/:tid/agents/:slug` (uninstall)
  When backend ships, flip `LIVE_MODE` in `web/src/lib/queries/admin.ts` or set `VITE_ADMIN_LIVE=1`. If a field name changes, that's one edit in `admin-v2.ts` — components consume the typed hook return.

## Patterns and tradeoffs to preserve

- **Vendor plnt as a library, don't fork.** ~80% of what plnt-cloud needs is already there. The only mods to plnt itself in slice 1 are extracting `runner.run_spec()` from `main()` and tenant-prefixing the workdir.
- **Tenant data in `inputs`, not a new field on `AgentSpec`.** The open `inputs` dict carries `tenant_id`, `user_id`, `session_id`, `memory_context`. Don't widen the spec schema.
- **One synthesizer, not a multi-bubble trace.** The user explicitly rejected leaking raw trace replies into the chat. `synthesize_response` is the single user-facing voice. Trace bubbles are admin-only.
- **Confirm-before-mutate** — every booking action requires an explicit user tap (slot chip or "yes book X"), never auto-confirmed. Per GPT-5 prompting guidance referenced in the deep-research output.
- **Discovery-first, deep-link-dominant.** Most providers don't expose third-party booking APIs (only Resy via an unofficial reverse-engineered surface). The realistic UX is compare-in-chat → complete-in-provider-app. Don't build elaborate in-app checkout flows until there's a partner contract.

## User collaboration preferences (durable)

- **Concise > exhaustive.** Short tight summaries beat long structured ones. End-of-turn: one or two sentences max.
- **No vibe code.** Don't add decorative SVG compasses, fake star ratings, "Try saying" example chips that aren't wired, paper-restyle Google Maps, sign-in pages for an open backend, route guards for sessions that don't exist. The user has explicitly ripped each of these out at least once. When in doubt, ask before adding.
- **Don't ask before doing read-only investigation.** If they say "fix X", spend a minute grepping/probing before clarifying — most questions are answerable from the code.
- **End-to-end probes beat speculation.** When the chat is "broken", write a one-off `websockets` probe and time the round-trip. Don't theorize.
- **Don't hide failures behind try/except.** If a synth call fails, surface it; the workflow's `_fallback_reply` is the explicit fallback, not silent swallow.
- **Honest about plnt's gaps.** When the user asks "is X done", the answer should distinguish "shipped", "scaffolded but not active", and "deferred to slice N".

## Security notes — keys the user has pasted in conversation

The user has shared two Google API keys in prior chat. Both should be rotated and restricted before any production use:

- A Gemini key (in `plnt-cloud/.env` as `PLNT_CLOUD_API_KEY`).
- A Maps JS API key (in `plnt-cloud/web/.env.local` as `VITE_GOOGLE_MAPS_KEY`).

The Maps key in particular ships in the browser bundle — restrict it to HTTP referrers (`http://localhost:5173/*` and the eventual prod domain) via the Cloud Console. The Gemini key should be regenerated since it sat in chat logs.

## Worth knowing about the broader product landscape

The user ran a deep-research workflow on the multi-provider booking architecture. Key findings worth carrying forward:

- **Only Resy** has a usable third-party booking surface (unofficial, reverse-engineered, ToS-fragile).
- **OpenTable** API returns availability but cannot complete a booking — has to deep-link out.
- **DoorDash Drive / Marketplace** APIs are partner-gated; no path for an ad-hoc agent.
- **Uber Eats Marketplace** is merchant-side only; needs written approval + 4–8 week onboarding.
- **Reserve with Google E2E** requires per-merchant contractual relationships; not a general aggregator path.
- **A2UI** (Google's open agent-UI protocol, Dec 2025) is the emerging best practice for rendering booking flows as declarative UI components rather than chat back-and-forth. The current `ChatPanel` action cards are an in-house approximation; A2UI is the standard to converge on if it gains adoption.

The realistic architecture is therefore: Places Text Search as universal discovery → fan-out to platform-tagged candidates → Resy direct-book OR deep-link handoff for everyone else. The codebase is shaped for this: `Candidate.platform` exists, action cards exist, the saga compensation pattern is in place.

## Repo identity

`plnt-cloud/` is its own git repository (its `.git` lives here, not in the umbrella `../den-agent/`). The remote is `https://github.com/plnt-work/google-business`. The initial commit (`3742a49`) bundled the whole working tree — 69 files including both backend (Python) and frontend (`web/`). Future work commits and pushes from inside `plnt-cloud/`, not from the umbrella.

## Multi-agent caveat

This codebase has been edited concurrently by multiple Claude instances. Concrete consequences:

- Always `Read` a file fresh immediately before `Edit`/`Write`. Stale view → `File has been modified since read` errors. The harness tracks this per file; one stale read invalidates the next write.
- Prefer small surgical edits over file rewrites. A linter or sibling agent may have introduced fields you'd otherwise blow away — e.g. the `platform` field on `Candidate`, the `LocStatus`/`onRequestLocation` props on `ChatPanel`, the `userLoc` geolocation flow on `Atlas`.
- If you see an unfamiliar prop or type, search the codebase before deleting it — it probably belongs to another agent's slice.

## Frontend layout invariants

Hard-earned rules — break these and the chat stops working visually:

- `Atlas` is a 2-column CSS grid (`1fr 420px`) — **map left** (dominant) with a **floating `MapSearch` panel** pinned top-left 16px inset, **right rail** (fixed 420px) on the right. The rail stacks vertically: `BusinessHeader` → `AgentStrip` → `ChatPanel` → `SessionBar`. When nothing is selected the rail shows `EmptyState` + the vertical legend. (Previous invariant — `var(--sidebar-w) 1fr` with chat on the left and map on the right — is **superseded** as of FE-P2.)
- `features/chat/ChatPanel.tsx` is the single source of truth for the consumer chat UI, scoped to one `(business, agent)` pair. Earlier versions had separate `Sidebar.tsx` / `Conversation.tsx` / `AskBar.tsx` components and a floating `PlaceCard` overlay — they were consolidated, then re-scoped into the rail. Resurrecting any of them fragments the chat and makes it visually disappear.
- Any decorative `::before` / `::after` pseudo that overlays an interactive surface **must** carry `pointer-events: none`, or the underlying input/button becomes unclickable. The composer's iridescent focus ring was previously a `::before` hack with this caveat; FE-P1 replaced it with a clean `box-shadow` ring, but the rule still applies to anything new.
- The right rail composer uses Tailwind's `focus-within:` to drive a ring focus state on `border-color` + `box-shadow`. Don't reintroduce a position-absolute pseudo for the focus ring.

## What renders where (visibility rule)

The same `Reply` stream feeds both surfaces; rendering policy differs:

| Reply role           | `/atlas` (consumer)                       | `/console` (DebugChat) |
|----------------------|:-----------------------------------------:|:----------------------:|
| `say` (synthesizer)  | ✓ as agent bubble in the rail ChatPanel   | ✓ |
| `system` (status)    | ✓ as faint italic line in the rail        | ✓ |
| `classify_intent`    | hidden                                    | ✓ raw JSON |
| `resolve_business`   | (FE-P2) ignored — pin set is local seed    | ✓ |
| `check_availability` | drives the inline `offer_slots` card      | ✓ |
| `booking_saga`       | drives the inline `booking_*` card        | ✓ |

If a future role doesn't appear in `/atlas`, that's the `turns.filter(...)` at the top of `features/chat/ChatPanel.tsx` — extend it intentionally, not by accident. As of FE-P2 action cards live **only** in `ChatPanel`; there is no floating PlaceCard to keep in sync.

## Session-storage keys (don't collide)

- `sessionStorage["atlas_session_id"]` — current ConversationWorkflow id for this tab. Rotated by the `SessionBar` "+ new" button. Also clears the rail's selected business.
- `sessionStorage["atlas_user_id"]` — stable per-tab user id; promote to `localStorage` if you want it to persist across tabs.
- `localStorage["atlas_timeline:<tenant>:<session>"]` — cached `items[]` so navigating away to `/console` and back doesn't show an empty chat before the WS replay finishes.

## Frontend failure-mode triage

When a user reports "the chat is broken", in rough order of likelihood:

1. **"Connected" pill stays grey** → worker isn't running. The proxy hops through uvicorn, but the WS reply loop needs the worker too. Restart with `docker compose restart worker` (default flow) or the env-sourced `python -m workflows.worker` line (bare-metal fallback). If the worker exited with `worker-entrypoint: /env/.env not found`, you ran the dockerised worker without bind-mounting `.env`; fix the compose `volumes:` block.
2. **Can't type in the composer** → an iridescent `::before` lost its `pointer-events: none`. DevTools-inspect; the offender will be the topmost element under the cursor when hovering the input.
3. **Pill turns green, message sends, but no reply** → `RestrictedWorkflowAccessError` in `/tmp/plnt-cloud-worker.log`. Add the offending module to the passthrough list in `workflows/worker.py` and restart.
4. **Reply arrives but `say` is empty** → synthesizer hit Gemini's safety filter or returned non-JSON. Check `model_result` events in the worker log.
5. **Pins land at random spots, not the candidate's real address** → projected from synthetic 0..100 SVG space, not real lat/lng. Wire real coords through `_ground_resolve_business` → `MapPin` to fix.
