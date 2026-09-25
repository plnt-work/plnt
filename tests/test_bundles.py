from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from plnt.bundles import BundleError, load_bundle
from plnt.bundles.sdk import ToolContext, tool

FIXTURE = Path(__file__).parent / "fixtures" / "bundles" / "order-desk"


@pytest.fixture
def bundle_dir(tmp_path) -> Path:
    d = tmp_path / "order-desk"
    shutil.copytree(FIXTURE, d)
    return d


def test_loads_manifest_prompt_schema_and_tools():
    b = load_bundle(FIXTURE)
    assert (b.slug, b.version) == ("order-desk", "1.2.0")
    assert b.manifest.runtime.max_steps == 4
    assert b.manifest.secrets.required == ["SHOP_API_KEY"]
    spec = b.tools["lookup_order"]
    assert spec.description == "Look up an order's status by id."
    assert spec.parameters == {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "include_items": {"type": "boolean", "default": False},
        },
        "required": ["order_id"],
    }
    assert spec.wants_ctx


def test_config_defaults_validation_and_render():
    b = load_bundle(FIXTURE)
    cfg = b.validate_config({"shop_name": "Acme"})
    assert cfg == {"shop_name": "Acme", "tone": "friendly"}
    assert "order desk for Acme" in b.render_prompt(cfg)
    with pytest.raises(BundleError, match="shop_name"):
        b.validate_config({})
    with pytest.raises(BundleError, match="tone"):
        b.validate_config({"shop_name": "A", "tone": "rude"})
    with pytest.raises(BundleError):
        b.validate_config({"shop_name": "A", "surprise": 1})


def test_tool_call_gets_ctx():
    b = load_bundle(FIXTURE)
    ctx = ToolContext(
        tenant_id="t1",
        session_id="s",
        bundle="order-desk",
        config={"shop_name": "Acme"},
        _secrets={"SHOP_API_KEY": "sk-123456"},
    )
    out = b.tools["lookup_order"].call({"order_id": "42"}, ctx)
    assert out["shop"] == "Acme" and out["key_tail"] == "3456" and out["tenant"] == "t1"
    with pytest.raises(KeyError):
        ToolContext("t", "s", "b").secret("NOPE")


def test_prompt_referencing_undeclared_config_is_rejected(bundle_dir):
    (bundle_dir / "prompt.md").write_text("Hi {{config.shop_name}} {{config.secret_sauce}}")
    with pytest.raises(BundleError, match="secret_sauce"):
        load_bundle(bundle_dir)


def test_unknown_tool_is_rejected(bundle_dir):
    toml = (
        (bundle_dir / "skill.toml")
        .read_text()
        .replace('["lookup_order"]', '["lookup_order", "refund"]')
    )
    (bundle_dir / "skill.toml").write_text(toml)
    with pytest.raises(BundleError, match="refund"):
        load_bundle(bundle_dir)


def test_broken_tool_module_is_reported(bundle_dir):
    (bundle_dir / "tools" / "broken.py").write_text("import does_not_exist\n")
    with pytest.raises(BundleError, match="broken.py failed to import"):
        load_bundle(bundle_dir)


def test_bad_slug_and_missing_files(bundle_dir, tmp_path):
    toml = (
        (bundle_dir / "skill.toml")
        .read_text()
        .replace('name = "order-desk"', 'name = "Order Desk"')
    )
    (bundle_dir / "skill.toml").write_text(toml)
    with pytest.raises(BundleError, match="slug"):
        load_bundle(bundle_dir)
    with pytest.raises(BundleError, match="not a bundle"):
        load_bundle(tmp_path / "nothing")


def test_digest_changes_with_content(bundle_dir):
    before = load_bundle(bundle_dir).digest()
    assert before == load_bundle(bundle_dir).digest()
    (bundle_dir / "prompt.md").write_text((bundle_dir / "prompt.md").read_text() + "\nBe brief.")
    assert load_bundle(bundle_dir).digest() != before


def test_tool_decorator_rejects_varargs():
    with pytest.raises(TypeError):

        @tool
        def bad(*args):  # pragma: no cover
            pass


def test_registry_example_bundle_loads():
    b = load_bundle(Path(__file__).parents[1] / "registry" / "bundles" / "support-desk")
    assert b.slug == "support-desk" and "lookup_faq" in b.tools


def test_require_tool_must_be_listed(bundle_dir):
    toml = (bundle_dir / "skill.toml").read_text().replace(
        "max_steps = 4", 'max_steps = 4\nrequire_tool = "refund"')
    (bundle_dir / "skill.toml").write_text(toml)
    with pytest.raises(BundleError, match="require_tool"):
        load_bundle(bundle_dir)
