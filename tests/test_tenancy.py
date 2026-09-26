from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from plnt.bundles import BundleError, load_bundle
from plnt.tenancy import TenantError, TenantNotFound, TenantStore, installs

FIXTURE = Path(__file__).parent / "fixtures" / "bundles" / "order-desk"


@pytest.fixture
def store(tmp_path) -> TenantStore:
    return TenantStore(tmp_path / "tenants")


def test_create_and_keys(store):
    t, key = store.create("acme", "Acme Inc")
    assert key.startswith("pk_") and t.verify_key(key) and not t.verify_key("pk_wrong")
    assert "api_key_hash" in t.meta and key not in (t.home / "tenant.json").read_text()
    new = t.rotate_key()
    assert t.verify_key(new) and not t.verify_key(key)
    assert store.find_by_key(new).id == "acme"
    with pytest.raises(TenantError, match="exists"):
        store.create("acme")
    for bad in ("A", "../x", "a/b", "x"):
        with pytest.raises(TenantError):
            store.create(bad)
    with pytest.raises(TenantNotFound):
        store.get("ghost")


def test_secrets_are_private_and_named(store):
    t, _ = store.create("acme")
    t.set_secret("SHOP_API_KEY", "sk-1")
    assert t.secret_names() == ["SHOP_API_KEY"]
    mode = stat.S_IMODE(os.stat(t.home / "secrets.json").st_mode)
    assert mode == 0o600
    with pytest.raises(TenantError):
        t.set_secret("lowercase", "x")
    assert t.delete_secret("SHOP_API_KEY") and t.secret_names() == []


def test_model_config_per_tenant(store, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    t, _ = store.create("acme")
    assert t.model_profile().provider == "offline"  # server default
    with pytest.raises(TenantError, match="provider"):
        t.set_model_config({"provider": "magic", "base_url": "x", "model": "m"})
    with pytest.raises(TenantError, match="unknown"):
        t.set_model_config({"provider": "ollama", "base_url": "x", "model": "m", "api_key": "raw"})
    t.set_model_config(
        {
            "provider": "openai",
            "base_url": "https://llm.example/v1",
            "model": "m1",
            "api_key_secret": "LLM_KEY",
            "num_ctx": 4096,
        }
    )
    with pytest.raises(TenantError, match="LLM_KEY"):
        t.model_profile()
    t.set_secret("LLM_KEY", "sk-tenant")
    p = t.model_profile()
    assert (p.provider, p.model, p.api_key, p.num_ctx, p.source) == (
        "openai",
        "m1",
        "sk-tenant",
        4096,
        "tenant",
    )
    assert "sk-tenant" not in str(p.to_event())


def test_install_lifecycle(store):
    t, _ = store.create("acme")
    b = load_bundle(FIXTURE)
    with pytest.raises(BundleError):
        installs.install(t, b, {})  # shop_name required
    inst = installs.install(t, b, {"shop_name": "Acme"})
    assert inst.config == {"shop_name": "Acme", "tone": "friendly"}
    assert inst.path.parent == t.bundles_dir and inst.digest == b.digest()
    assert installs.active(t, "order-desk").version == "1.2.0"

    installs.update(t, "order-desk", config={"shop_name": "Acme 2", "tone": "formal"})
    assert installs.active(t, "order-desk").config["tone"] == "formal"
    with pytest.raises(BundleError):
        installs.update(t, "order-desk", config={"shop_name": ""})

    installs.update(t, "order-desk", enabled=False)
    with pytest.raises(BundleError, match="disabled"):
        installs.active(t, "order-desk")
    installs.update(t, "order-desk", enabled=True)

    installs.uninstall(t, "order-desk")
    with pytest.raises(BundleError, match="not installed"):
        installs.active(t, "order-desk")
    actions = [e["action"] for e in t.audit_events()]
    assert actions == [
        "tenant.created",
        "bundle.installed",
        "bundle.updated",
        "bundle.updated",
        "bundle.updated",
        "bundle.uninstalled",
    ]


def test_highest_enabled_version_wins(store, tmp_path):
    import shutil

    t, _ = store.create("acme")
    v2 = tmp_path / "v2"
    shutil.copytree(FIXTURE, v2)
    (v2 / "skill.toml").write_text((v2 / "skill.toml").read_text().replace('"1.2.0"', '"1.10.0"'))
    installs.install(t, load_bundle(FIXTURE), {"shop_name": "A"})
    installs.install(t, load_bundle(v2), {"shop_name": "A"})
    assert installs.active(t, "order-desk").version == "1.10.0"  # semver, not string order


def test_installed_copy_is_frozen(store, tmp_path):
    import shutil

    src = tmp_path / "src"
    shutil.copytree(FIXTURE, src)
    t, _ = store.create("acme")
    installs.install(t, load_bundle(src), {"shop_name": "A"})
    (src / "prompt.md").write_text("changed upstream")
    assert "order desk" in installs.active(t, "order-desk").load().prompt_template


def test_tenants_are_isolated(store):
    a, _ = store.create("tenant-a")
    b, _ = store.create("tenant-b")
    bundle = load_bundle(FIXTURE)
    installs.install(a, bundle, {"shop_name": "A shop"})
    installs.install(b, bundle, {"shop_name": "B shop", "tone": "formal"})
    a.set_secret("SHOP_API_KEY", "sk-aaaa")
    assert b.secret_names() == []
    assert installs.active(a, "order-desk").config["shop_name"] == "A shop"
    assert installs.active(b, "order-desk").config["shop_name"] == "B shop"
    assert not set(a.home.rglob("*")) & set(b.home.rglob("*"))
    store.delete("tenant-a")
    assert not a.home.exists() and installs.active(b, "order-desk")
