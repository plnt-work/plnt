from __future__ import annotations

from pathlib import Path

import pytest

from plnt.bundles import load_bundle
from plnt.executors import LocalExecutor, SessionError
from plnt.models import ChatResult, ScriptedProvider, ToolCall, Usage
from plnt.tenancy import TenantStore, installs

FIXTURE = Path(__file__).parent / "fixtures" / "bundles" / "order-desk"


class Scripts:
    """Per-tenant scripted models so tests can tell tenants' traffic apart."""

    def __init__(self):
        self.by_model: dict[str, ScriptedProvider] = {}
        self.default: ScriptedProvider | None = None

    def factory(self, profile):
        return self.by_model.get(profile.model) or self.default


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")  # server default if a tenant has no model
    store = TenantStore(tmp_path / "tenants")
    scripts = Scripts()
    ex = LocalExecutor(store, provider_factory=scripts.factory)
    t, _ = store.create("acme")
    t.set_secret("SHOP_API_KEY", "sk-acme-9999")
    installs.install(t, load_bundle(FIXTURE), {"shop_name": "Acme"})
    return store, ex, scripts, t


def _kinds(events):
    return [e["kind"] for e in events]


def test_turn_uses_tenant_config_secret_and_records_usage(env):
    store, ex, scripts, t = env
    scripts.default = ScriptedProvider(
        [
            ChatResult(
                tool_calls=[ToolCall("c1", "lookup_order", {"order_id": "42"})],
                usage=Usage(100, 10),
                cost_usd=0.001,
            ),
            ChatResult(content="Order 42 has shipped.", usage=Usage(150, 12), cost_usd=0.002),
        ]
    )
    sid = ex.start_session("acme", "order-desk", user_id="u1")
    ex.send("acme", sid, "where is order 42?", wait=True)
    events = ex.events_since("acme", sid)
    kinds = _kinds(events)
    assert kinds[0] == "user_message" and kinds[-1] == "run_finished"
    assert "tool_call" in kinds and "assistant_message" in kinds
    tool_result = scripts.default.calls[1]["messages"][-1]
    assert '"shop": "Acme"' in tool_result["content"] and "9999" in tool_result["content"]
    assert "order desk for Acme" in scripts.default.calls[0]["messages"][0]["content"]
    assert events[-1]["payload"]["outcome"] == "ok"

    usage = ex.db(t).usage_summary()
    assert usage["model_calls"] == 2 and usage["prompt_tokens"] == 250
    assert usage["cost_usd"] == pytest.approx(0.003)
    assert [e["action"] for e in t.audit_events()][-1] == "run.finished"


def test_history_carries_across_turns(env):
    _, ex, scripts, _ = env
    scripts.default = ScriptedProvider(
        [ChatResult(content="Hi!"), ChatResult(content="Still here.")]
    )
    sid = ex.start_session("acme", "order-desk")
    ex.send("acme", sid, "hello", wait=True)
    ex.send("acme", sid, "you there?", wait=True)
    roles = [m["role"] for m in scripts.default.calls[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_missing_secret_fails_the_turn_clearly(env):
    store, ex, scripts, t = env
    t.delete_secret("SHOP_API_KEY")
    scripts.default = ScriptedProvider([])
    sid = ex.start_session("acme", "order-desk")
    ex.send("acme", sid, "hi", wait=True)
    err = [e for e in ex.events_since("acme", sid) if e["kind"] == "run_error"][0]
    assert "SHOP_API_KEY" in err["payload"]["error"] and not scripts.default.calls


def test_acc_kills_a_tool_loop(env):
    _, ex, scripts, _ = env
    loop = ChatResult(tool_calls=[ToolCall("c", "lookup_order", {"order_id": "1"})])
    scripts.default = ScriptedProvider(lambda m, t: ChatResult(tool_calls=list(loop.tool_calls)))
    sid = ex.start_session("acme", "order-desk")
    ex.send("acme", sid, "loop forever", wait=True)
    events = ex.events_since("acme", sid)
    killed = [e for e in events if e["kind"] == "killed"]
    assert killed and "ACC:loop" in killed[0]["payload"]["reason"]
    assert events[-1]["payload"]["outcome"] == "killed"


def test_token_budget_stops_run(env):
    _, ex, scripts, _ = env
    scripts.default = ScriptedProvider(
        lambda m, t: ChatResult(
            tool_calls=[ToolCall("c", "lookup_order", {"order_id": str(len(m))})],
            usage=Usage(4000, 1000),
        )
    )
    sid = ex.start_session("acme", "order-desk")
    ex.send("acme", sid, "go", wait=True)
    killed = [e for e in ex.events_since("acme", sid) if e["kind"] == "killed"]
    assert killed and "token budget" in killed[0]["payload"]["reason"]


def test_manual_kill(env):
    import threading

    _, ex, scripts, _ = env
    gate = threading.Event()

    def slow(messages, tools):
        gate.wait(5)
        return ChatResult(tool_calls=[ToolCall("c", "lookup_order", {"order_id": "9"})])

    scripts.default = ScriptedProvider(slow)
    sid = ex.start_session("acme", "order-desk")
    ex.send("acme", sid, "take your time")
    assert ex.kill("acme", sid)
    gate.set()
    ex.wait("acme", sid, 5)
    kinds = _kinds(ex.events_since("acme", sid))
    assert "killed" in kinds and "assistant_message" not in kinds
    assert not ex.kill("acme", sid)  # nothing running any more


def test_tenants_use_their_own_model(env, tmp_path):
    store, ex, scripts, acme = env
    other, _ = store.create("other")
    other.set_secret("SHOP_API_KEY", "sk-other")
    installs.install(other, load_bundle(FIXTURE), {"shop_name": "Other"})
    other.set_model_config(
        {"provider": "ollama", "base_url": "http://gpu-box:11434", "model": "onprem-7b"}
    )
    scripts.by_model["onprem-7b"] = ScriptedProvider([ChatResult(content="from on-prem")])
    scripts.default = ScriptedProvider([ChatResult(content="from default")])

    s1 = ex.start_session("acme", "order-desk")
    s2 = ex.start_session("other", "order-desk")
    ex.send("acme", s1, "hi", wait=True)
    ex.send("other", s2, "hi", wait=True)
    answer = lambda t, s: [e for e in ex.events_since(t, s) if e["kind"] == "assistant_message"][0]  # noqa: E731
    assert answer("acme", s1)["payload"]["text"] == "from default"
    assert answer("other", s2)["payload"]["text"] == "from on-prem"
    started = [e for e in ex.events_since("other", s2) if e["kind"] == "run_started"][0]
    assert started["payload"]["model"]["source"] == "tenant"
    with pytest.raises(SessionError):
        ex.events_since("other", s1)  # acme's session is invisible to "other"


def test_session_requires_installed_enabled_bundle(env):
    from plnt.bundles import BundleError

    _, ex, _, t = env
    with pytest.raises(BundleError):
        ex.start_session("acme", "support-desk")
    installs.update(t, "order-desk", enabled=False)
    with pytest.raises(BundleError, match="disabled"):
        ex.start_session("acme", "order-desk")
