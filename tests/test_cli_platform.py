from __future__ import annotations

from click.testing import CliRunner

from plnt.bundles import load_bundle
from plnt.cli import cli


def test_init_scaffold_is_a_valid_bundle(tmp_path):
    r = CliRunner().invoke(cli, ["init", "hello-desk", "--dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    b = load_bundle(tmp_path / "hello-desk")
    assert b.slug == "hello-desk" and "get_business_hours" in b.tools
    assert CliRunner().invoke(cli, ["init", "hello-desk", "--dir", str(tmp_path)]).exit_code == 1


def test_run_offline_and_fail_loud(tmp_path, monkeypatch):
    runner = CliRunner()
    runner.invoke(cli, ["init", "hello-desk", "--dir", str(tmp_path)])
    bundle = str(tmp_path / "hello-desk")

    monkeypatch.setenv("PLNT_FORCE", "offline")
    r = runner.invoke(cli, ["run", bundle, "hi", "--config", "business_name=Acme"])
    assert r.exit_code == 0, r.output
    assert "[offline stub]" in r.output  # escaped, not eaten as markup

    monkeypatch.delenv("PLNT_FORCE")
    monkeypatch.delenv("PLNT_CLOUD_URL", raising=False)
    monkeypatch.setenv("PLNT_LOCAL_URL", "http://127.0.0.1:1")
    r = runner.invoke(cli, ["run", bundle, "hi", "--config", "business_name=Acme"])
    assert r.exit_code == 1
    assert r.output.count("ollama pull") == 1  # hint shown once


def test_run_rejects_bad_config(tmp_path, monkeypatch):
    monkeypatch.setenv("PLNT_FORCE", "offline")
    runner = CliRunner()
    runner.invoke(cli, ["init", "hello-desk", "--dir", str(tmp_path)])
    r = runner.invoke(cli, ["run", str(tmp_path / "hello-desk"), "hi"])
    assert r.exit_code == 1 and "business_name" in r.output


def test_tenants_and_install(tmp_path):
    runner = CliRunner()
    r = runner.invoke(cli, ["tenants", "create", "bistro"])
    assert r.exit_code == 0 and "pk_" in r.output
    r = runner.invoke(
        cli,
        [
            "install",
            "support-desk",
            "--tenant",
            "bistro",
            "--config",
            "business_name=Luigi's",
            "--config",
            "handoff_contact=x@y.z",
            "--config-json",
            'faq=[{"q": "open?", "a": "5-11pm"}]',
        ],
    )
    assert r.exit_code == 0, r.output
    assert "support-desk@0.1.0" in runner.invoke(cli, ["tenants", "list"]).output
    r = runner.invoke(cli, ["install", "support-desk", "--tenant", "ghost"])
    assert r.exit_code == 1 and "does not exist" in r.output
