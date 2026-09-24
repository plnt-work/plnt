# plnt-cloud

Multi-tenant micro-agent platform built on top of [plnt](http://www.plnt.work/).

plnt is the personal-runtime substrate — sandbox ladder, two-tool RLM,
`allowed_roots` filesystem scoping, per-run blackboard audit. **plnt-cloud
adds the tenant axis:** per-tenant memory (Memori), per-tenant credentials,
per-tenant audit partitioning, plus Temporal-managed long-running sessions
and a web/WhatsApp/Google-Chat channel layer.

## Layout

```
tenancy/      TenantContext + per-tenant factory (Memori, Blackboard, Orchestrator)
memory/       Memori adapter (per-tenant SQLite/Postgres) + preload hook
workflows/    Temporal: ConversationWorkflow per session, run_microagent Activity
channels/     Inbound channels: web WebSocket (slice 1); Baileys/WhatsApp (slice 3)
microagents/  Skill bundles (skill.toml + prompt.md) shared across tenants
surface/      FastAPI app — tenant-scoped routes
tests/        End-to-end tests using Temporal's in-process WorkflowEnvironment
```

## Slice 1 — what works today

End-to-end: a user message lands on the WebSocket `/v1/ws/{tenant_id}/{session_id}`,
gets routed to `ConversationWorkflow`, classified by the `classify_intent`
micro-agent, dispatched to `resolve_business` + `check_availability`, and the
slot suggestions stream back over the same socket.

```bash
# 1. Install
pip install -e ../plnt
pip install -e .[dev]

# 2. Bring up Temporal + Postgres
docker compose up -d

# 3. Run the worker (in a second terminal)
python -m workflows.worker

# 4. Run the surface (in a third terminal)
uvicorn surface.app:app --reload --port 8080

# 5. Smoke test
wscat -c ws://localhost:8080/v1/ws/demo/sess1
> find me an appointment at Joe's Pizza tomorrow at 7pm
```

## Design notes

See `/Users/dev16/.claude/plans/harmonic-mapping-peacock.md` for the full
architecture decision record.
