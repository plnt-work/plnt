"""Platform commands: init, run, install, tenants, serve, dev.

Registered onto the main `plnt` click group by plnt/cli.py.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.markup import escape

console = Console()

DEFAULT_PORT = 8787


# --------------------------------------------------------------------- helpers


def _parse_config(pairs: tuple[str, ...], json_pairs: tuple[str, ...]) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    for p in pairs:
        k, sep, v = p.partition("=")
        if not sep:
            raise click.BadParameter(f"--config expects key=value, got {p!r}")
        cfg[k.strip()] = v
    for p in json_pairs:
        k, sep, v = p.partition("=")
        if not sep:
            raise click.BadParameter(f"--config-json expects key=<json>, got {p!r}")
        try:
            cfg[k.strip()] = json.loads(v)
        except json.JSONDecodeError as e:
            raise click.BadParameter(f"--config-json {k}: {e}") from None
    return cfg


def _fail(msg: str, hint: str = "") -> None:
    console.print(f"[red]✗[/red] {escape(msg)}")
    if hint:
        console.print(f"  [yellow]fix:[/yellow] {escape(hint)}")
    sys.exit(1)


def _render(evt: dict[str, Any]) -> None:
    k = evt["kind"]
    # Everything below comes from models, tools or configs: never let it be
    # interpreted as rich markup.
    p = {key: escape(v) if isinstance(v, str) else v for key, v in evt["payload"].items()}
    if k == "run_started":
        m = p.get("model", {})
        console.print(
            f"[dim]▸ {p['bundle']}@{p['version']} · {m.get('provider')} {m.get('model')}"
            f" ({m.get('source')})[/dim]"
        )
    elif k == "tool_call":
        args = escape(json.dumps(p.get("args"))[:160])
        console.print(f"[cyan]→ {p['tool']}[/cyan]([dim]{args}[/dim])")
    elif k == "tool_result":
        console.print(f"  {'[green]ok[/green]' if p.get('ok') else '[red]error[/red]'}")
    elif k == "model_result":
        console.print(
            f"[dim]  model: {p.get('prompt_tokens', 0)}+{p.get('completion_tokens', 0)} tok,"
            f" {p.get('latency_ms', 0)} ms{' (shim)' if p.get('shimmed') else ''}[/dim]"
        )
    elif k == "assistant_message":
        console.print(f"\n{p['text']}\n")
    elif k == "killed":
        console.print(f"[red]■ killed:[/red] {p.get('reason')}")
    elif k == "run_error":
        console.print(f"[red]✗ {p.get('error')}[/red]")
        if p.get("hint"):
            console.print(f"  [yellow]fix:[/yellow] {p['hint']}")
    elif k == "run_finished":
        console.print(
            f"[dim]■ {p.get('outcome')} · {p.get('tokens')} tokens · "
            f"{p.get('wall_seconds')} s[/dim]"
        )


def _store():
    from plnt.tenancy import TenantStore

    return TenantStore()


def _ensure_tenant(store, tid: str):
    from plnt.tenancy import TenantNotFound

    try:
        return store.get(tid)
    except TenantNotFound:
        t, key = store.create(tid)
        console.print(f"[dim]created tenant {tid!r}[/dim]")
        return t


# --------------------------------------------------------------------- init


_SKILL = """[meta]
name = "{slug}"
version = "0.1.0"
description = "Describe what this agent does for one customer."
tags = []

[runtime]
model_hint = "small"            # small | deep | auto
tools = ["get_business_hours"]  # built-ins: search, execute; or @tool functions in tools/
max_steps = 4

[budget]
tokens = 8000                   # per message; the run is stopped past this
wall_seconds = 60

[secrets]
required = []                   # e.g. ["CRM_API_KEY"], set per tenant
"""

_PROMPT = """You are the assistant for {{config.business_name}}.

- Use `get_business_hours` when someone asks when you are open.
- Keep answers short and friendly.
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "business_name": {"type": "string", "minLength": 1},
        "hours": {"type": "string", "default": "Mon-Fri 9am-5pm"},
    },
    "required": ["business_name"],
    "additionalProperties": False,
}

_TOOL = '''from plnt import ToolContext, tool


@tool
def get_business_hours(ctx: ToolContext) -> dict:
    """Return this business's opening hours."""
    return {"hours": ctx.config["hours"]}
'''


@click.command("init")
@click.argument("slug")
@click.option(
    "--dir",
    "parent",
    type=click.Path(file_okay=False),
    default=".",
    help="Where to create the bundle directory.",
)
def init_cmd(slug: str, parent: str) -> None:
    """Scaffold a new agent bundle."""
    from plnt.bundles import BundleError, load_bundle

    d = Path(parent) / slug
    if d.exists():
        _fail(f"{d} already exists")
    (d / "tools").mkdir(parents=True)
    (d / "skill.toml").write_text(_SKILL.format(slug=slug))
    (d / "prompt.md").write_text(_PROMPT)
    (d / "config_schema.json").write_text(json.dumps(_SCHEMA, indent=2) + "\n")
    (d / "tools" / "hours.py").write_text(_TOOL)
    try:
        load_bundle(d)
    except BundleError as e:
        _fail(f"scaffold is invalid: {e}")
    console.print(f"[green]✓[/green] created {d}/")
    console.print(f'  try it:  plnt run {d} "when are you open?" --config business_name=Acme')


# --------------------------------------------------------------------- run


@click.command("run")
@click.argument("bundle")
@click.argument("message", nargs=-1, required=True)
@click.option("--tenant", default="local", show_default=True)
@click.option("--config", "config", multiple=True, help="key=value (repeatable).")
@click.option("--config-json", "config_json", multiple=True, help="key=<json> (repeatable).")
@click.option("--secret", "secrets", multiple=True, help="NAME=value, stored for the tenant.")
def run_cmd(bundle, message, tenant, config, config_json, secrets) -> None:
    """Install BUNDLE (path or catalog slug) for a tenant and send it one message."""
    from plnt.bundles import BundleError
    from plnt.bundles.catalog import resolve
    from plnt.executors import LocalExecutor
    from plnt.tenancy import installs

    store = _store()
    t = _ensure_tenant(store, tenant)
    for s in secrets:
        name, _, value = s.partition("=")
        t.set_secret(name, value)
    try:
        b = resolve(bundle)
        installs.install(t, b, _parse_config(config, config_json))
    except BundleError as e:
        _fail(str(e))
    ex = LocalExecutor(store)
    sid = ex.start_session(t.id, b.slug, user_id="cli")
    ex.send(t.id, sid, " ".join(message))
    seen = 0
    while True:
        for e in ex.events_since(t.id, sid, seen):
            seen = e["seq"]
            _render(e)
            if e["kind"] == "run_finished":
                sys.exit(0 if e["payload"]["outcome"] == "ok" else 1)
        time.sleep(0.1)


# --------------------------------------------------------------------- install


@click.command("install")
@click.argument("bundle")
@click.option("--tenant", required=True)
@click.option("--config", "config", multiple=True, help="key=value (repeatable).")
@click.option("--config-json", "config_json", multiple=True, help="key=<json> (repeatable).")
def install_cmd(bundle, tenant, config, config_json) -> None:
    """Install BUNDLE (path or catalog slug) for one tenant with its config."""
    from plnt.bundles import BundleError
    from plnt.bundles.catalog import resolve
    from plnt.tenancy import TenantNotFound, installs

    try:
        t = _store().get(tenant)
    except TenantNotFound:
        _fail(f"tenant {tenant!r} does not exist", f"plnt tenants create {tenant}")
    try:
        inst = installs.install(t, resolve(bundle), _parse_config(config, config_json))
    except BundleError as e:
        _fail(str(e))
    console.print(f"[green]✓[/green] {inst.slug}@{inst.version} installed for {tenant}")
    console.print(f"  config: {json.dumps(inst.config)}")


# --------------------------------------------------------------------- tenants


@click.group("tenants")
def tenants_group() -> None:
    """Create, list and delete tenants."""


@tenants_group.command("create")
@click.argument("tid")
@click.option("--name", default="")
def tenants_create(tid: str, name: str) -> None:
    from plnt.tenancy import TenantError

    try:
        _, key = _store().create(tid, name)
    except TenantError as e:
        _fail(str(e))
    console.print(f"[green]✓[/green] tenant {tid} created")
    console.print(f"  api key (shown once): [bold]{key}[/bold]")


@tenants_group.command("list")
def tenants_list() -> None:
    from plnt.tenancy import installs

    for t in _store().list():
        inst = (
            ", ".join(
                f"{i.slug}@{i.version}{'' if i.enabled else ' (off)'}"
                for i in installs.list_installed(t)
            )
            or "—"
        )
        console.print(f"{t.id:<24} {inst}")


@tenants_group.command("delete")
@click.argument("tid")
@click.confirmation_option(prompt="Delete this tenant and all its data?")
def tenants_delete(tid: str) -> None:
    from plnt.tenancy import TenantNotFound

    try:
        _store().delete(tid)
    except TenantNotFound:
        _fail(f"tenant {tid!r} does not exist")
    console.print(f"[green]✓[/green] deleted {tid}")


# --------------------------------------------------------------------- serve / dev


@click.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=DEFAULT_PORT, type=int, show_default=True)
@click.option("--playground", is_flag=True,
              help="Also seed demo tenants and open the anonymous /v1/playground API.")
def serve_cmd(host: str, port: int, playground: bool) -> None:
    """Run the multi-tenant HTTP API."""
    import uvicorn

    from plnt.server import create_app

    if not os.environ.get("PLNT_ADMIN_TOKEN"):
        console.print(
            "[yellow]PLNT_ADMIN_TOKEN is not set: operator routes (create tenants, "
            "list tenants) will answer 503. Tenant API keys still work.[/yellow]"
        )
    uvicorn.run(create_app(playground=playground), host=host, port=port, log_level="info")


@click.command("dev")
@click.argument("bundle", required=False)
@click.option("--port", default=DEFAULT_PORT, type=int, show_default=True)
@click.option("--config", "config", multiple=True, help="key=value for installing BUNDLE.")
@click.option("--config-json", "config_json", multiple=True)
def dev_cmd(bundle, port, config, config_json) -> None:
    """Local development server: loopback only, no auth, tenant `dev`.

    With BUNDLE (a path or slug), installs it for `dev` first.
    """
    import uvicorn

    from plnt.bundles import BundleError
    from plnt.bundles.catalog import resolve
    from plnt.server import create_app
    from plnt.tenancy import installs

    store = _store()
    t = _ensure_tenant(store, "dev")
    if bundle:
        try:
            inst = installs.install(t, resolve(bundle), _parse_config(config, config_json))
        except BundleError as e:
            _fail(str(e))
        console.print(f"[green]✓[/green] {inst.slug}@{inst.version} installed for tenant dev")
    base = f"http://127.0.0.1:{port}/v1"
    console.print(f"[bold]plnt dev[/bold] · {base} · auth disabled (loopback only)")
    console.print(
        f"  curl -X POST {base}/tenants/dev/sessions -H 'content-type: application/json' "
        f'-d \'{{"bundle": "{bundle and resolve(bundle).slug or "<slug>"}"}}\''
    )
    uvicorn.run(create_app(store=store, dev=True), host="127.0.0.1", port=port, log_level="info")


def register(cli: click.Group) -> None:
    for cmd in (init_cmd, run_cmd, install_cmd, tenants_group, serve_cmd, dev_cmd):
        cli.add_command(cmd)
