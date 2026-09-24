"""plnt — Click-based CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from plnt import __version__
from plnt.config import DEFAULT_SURFACE_HOST, DEFAULT_SURFACE_PORT, paths
from plnt.control.orchestrator import Orchestrator
from plnt.execution.blackboard import Blackboard

console = Console()
_paths = paths()


def _base_url() -> str:
    return f"http://{DEFAULT_SURFACE_HOST}:{DEFAULT_SURFACE_PORT}"


@click.group()
@click.version_option(__version__, prog_name="plnt")
def cli() -> None:
    """plnt — open-source runtime for shipping one agent to many isolated tenants.

    \b
      plnt up             start the local surface server
      plnt submit …       send an intent and stream the run
      plnt skills …       list / show / install agent bundles
    """


# ---------------------------------------------------------------------- server


@cli.command()
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def up(host: str | None, port: int | None) -> None:
    """Start the surface server (foreground)."""
    _paths.ensure()
    from plnt.surface.server import run

    console.print(f"[bold green]plnt[/bold green] surface starting on {host or DEFAULT_SURFACE_HOST}:{port or DEFAULT_SURFACE_PORT}")
    console.print(f"home: {_paths.home}")
    run(host=host, port=port)


@cli.command()
def status() -> None:
    """Show surface status."""
    try:
        r = httpx.get(f"{_base_url()}/v1/health", timeout=2)
        console.print_json(r.text)
    except Exception as e:
        console.print(f"[red]surface unreachable:[/red] {e}")


# ---------------------------------------------------------------------- intents


@cli.command()
@click.argument("intent", nargs=-1, required=True)
@click.option("--remote/--local", default=False, help="Submit via HTTP (remote) or run inline (local).")
def submit(intent: tuple[str, ...], remote: bool) -> None:
    """Submit an intent. Default: inline (no server needed)."""
    text = " ".join(intent)
    if remote:
        r = httpx.post(f"{_base_url()}/v1/intents", json={"text": text}, timeout=10)
        r.raise_for_status()
        console.print(r.json())
        return

    _paths.ensure()
    orch = Orchestrator()
    handle = orch.start_run(text)
    console.print(f"[green]run[/green] {handle.run_id}")
    if handle.result and handle.result.output:
        console.print_json(json.dumps(handle.result.output, default=str))
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        out = orch.write_outcome(handle, desktop)
        if out:
            console.print(f"[dim]wrote[/dim] {out}")


# ----------------------------------------------------------------------- views


@cli.command()
def runs() -> None:
    """List recent runs."""
    if not _paths.runs.exists():
        console.print("[dim]no runs yet[/dim]")
        return
    table = Table(title="runs")
    table.add_column("run_id")
    table.add_column("bytes", justify="right")
    table.add_column("mtime")
    for d in sorted(_paths.runs.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
        if not d.is_dir():
            continue
        events = d / "events.jsonl"
        size = events.stat().st_size if events.exists() else 0
        table.add_row(d.name, str(size), str(d.stat().st_mtime))
    console.print(table)


@cli.command()
@click.argument("run_id")
@click.option("--follow/--no-follow", default=False)
def tail(run_id: str, follow: bool) -> None:
    """cat or follow a run's event log."""
    bb = Blackboard(run_id, root=_paths.runs)
    if not bb.events_path.exists():
        console.print(f"[red]unknown run[/red] {run_id}")
        sys.exit(1)
    if not follow:
        for evt in bb.read_all():
            console.print_json(json.dumps(evt, default=str))
        return
    try:
        for evt in bb.tail():
            console.print_json(json.dumps(evt, default=str))
            if evt.get("kind") == "finished":
                break
    except KeyboardInterrupt:
        pass


# ----------------------------------------------------------------------- monitor


@cli.command()
@click.option("--remote/--local", default=False, help="Read /v1/system over HTTP, or compute locally.")
def monitor(remote: bool) -> None:
    """Snapshot live agents + sandbox rungs + recent runs."""
    if remote:
        try:
            r = httpx.get(f"{_base_url()}/v1/system", timeout=4)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            console.print(f"[red]surface unreachable:[/red] {e}")
            sys.exit(1)
    else:
        from plnt.surface.monitor import snapshot

        data = snapshot()

    console.print(f"[bold]sandbox rungs:[/bold] {', '.join(data.get('sandbox_rungs', []))}")
    console.print(f"[bold]cpu count:[/bold] {data.get('cpu_count')}")
    docker_agents = data.get("docker_agents", [])
    console.print(f"[bold]docker agents:[/bold] {len(docker_agents)} live")
    if docker_agents:
        table = Table(title="live agents")
        for col in ("id", "name", "image", "status"):
            table.add_column(col)
        for a in docker_agents:
            table.add_row(a["id"][:12], a["name"], a["image"], a["status"])
        console.print(table)
        stats = data.get("docker_stats", [])
        if stats:
            t2 = Table(title="resources")
            for col in ("id", "cpu", "mem", "mem_pct"):
                t2.add_column(col)
            for s in stats:
                t2.add_row(s["id"][:12], s["cpu"], s["mem"], s["mem_pct"])
            console.print(t2)
    runs = data.get("runs_recent", [])[:5]
    if runs:
        t3 = Table(title="recent runs")
        for col in ("run_id", "event_bytes"):
            t3.add_column(col)
        for r in runs:
            t3.add_row(r["run_id"], str(r["event_bytes"]))
        console.print(t3)


# ----------------------------------------------------------------------- skills


@cli.group()
def skills() -> None:
    """Skills loaded from $PLNT_HOME/skills/*.md."""


@skills.command("list")
def skills_list() -> None:
    from plnt.control.skills import SkillRegistry

    reg = SkillRegistry(_paths.skills)
    items = reg.list()
    if not items:
        console.print(f"[dim]no skills in {_paths.skills}[/dim]")
        return
    for role in items:
        sk = reg.get(role)
        if sk:
            console.print(f"[bold]{role}[/bold] · tools={sk.tools} hint={sk.model_hint}")


@skills.command("show")
@click.argument("role")
def skills_show(role: str) -> None:
    from plnt.control.skills import SkillRegistry

    sk = SkillRegistry(_paths.skills).get(role)
    if not sk:
        console.print(f"[red]no such skill[/red] {role}")
        sys.exit(1)
    console.rule(f"{role}")
    console.print(sk.prompt)


# ----------------------------------------------------------------------- auth


@cli.group()
def auth() -> None:
    """Web UI authentication — username/password store."""


@auth.command("set-password")
@click.option("--user", "username", default="admin", help="Username to set.")
@click.password_option("--password", prompt=True, confirmation_prompt=True)
def auth_set_password(username: str, password: str) -> None:
    from plnt.surface.auth import AuthStore

    _paths.ensure()
    store = AuthStore()
    store.set_password(username, password)
    console.print(f"[green]OK[/green] password set for {username!r} at {store.path}")


@auth.command("list-users")
def auth_list_users() -> None:
    from plnt.surface.auth import AuthStore

    store = AuthStore()
    users = store.list_users()
    if not users:
        console.print(f"[dim]no users in {store.path}[/dim]")
        return
    for u in users:
        console.print(u)


# ----------------------------------------------------------------------- vendor


@cli.command("vendor-chat")
@click.option(
    "--source", default=None,
    help="Path to plnt-site/dist/app/. Defaults to ../plnt-site/dist/app relative to this repo.",
)
def vendor_chat(source: str | None) -> None:
    """Copy a built chat bundle into plnt/surface/static/app/."""
    import shutil

    repo_root = Path(__file__).resolve().parent.parent
    src = Path(source).expanduser() if source else (repo_root.parent / "plnt-site" / "dist-app")
    src = src.resolve()
    if not src.exists():
        console.print(f"[red]source not found:[/red] {src}")
        console.print(f"[dim]hint: cd {src.parent.parent} && npm run build:app[/dim]")
        sys.exit(1)
    dst = repo_root / "plnt" / "surface" / "static" / "app"
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    console.print(f"[green]OK[/green] vendored {src} -> {dst}")


@skills.command("install")
@click.argument("source")
@click.option("--dry-run", is_flag=True, help="List what would be imported without writing.")
def skills_install(source: str, dry_run: bool) -> None:
    """Install skills from a public library.

    SOURCE can be a shorthand or a full git URL. Shorthands:
      anthropic           Anthropic's official skills repo
      addyosmani          addyosmani/agent-skills (24 engineering skills)
      scientific          K-Dense-AI/scientific-agent-skills (140 skills)
      antigravity         sickn33/antigravity-awesome-skills (1500+ skills)
      claude-skills-collection
      the-library

    Or pass a full URL: https://github.com/owner/repo.git
    """
    from plnt.control.skill_installer import KNOWN_SOURCES, InstallError, install

    if source == "list":
        console.print("[bold]Known shorthands:[/bold]")
        for k, v in KNOWN_SOURCES.items():
            console.print(f"  {k:30} {Subtle.render(v) if hasattr(Subtle, 'render') else v}")
        return

    try:
        result = install(source, dry_run=dry_run)
    except InstallError as e:
        console.print(f"[red]install failed:[/red] {e}")
        sys.exit(1)

    console.print(f"[green]OK[/green] imported {result['imported']} skills from {result['source']}")
    if result['skipped']:
        console.print(f"[yellow]skipped[/yellow] {result['skipped']} (already exist or malformed)")
    if result['skills']:
        for role in result['skills'][:20]:
            console.print(f"  · {role}")
        if len(result['skills']) > 20:
            console.print(f"  · ... and {len(result['skills']) - 20} more")
    console.print(f"[dim]installed to {result['target']}[/dim]")


# ----------------------------------------------------------------------- models


@cli.group()
def models() -> None:
    """Inspect and diagnose the model backends plnt will use."""


def _profiles_for(model: str | None, url: str | None, provider: str | None, force: str | None):
    from dataclasses import replace

    from plnt.models import ModelError, resolve_profile
    from plnt.models.profiles import guess_local_provider, local_profile

    if url:
        base = local_profile("small")
        p = replace(base, base_url=url, provider=provider or guess_local_provider(url),
                    model=model or base.model, source="explicit", reason="--url")
        return [p]
    out = []
    for hint in ("small", "deep"):
        try:
            p = resolve_profile(hint, force)  # type: ignore[arg-type]
        except ModelError as e:
            console.print(f"[red]✗ no model:[/red] {e}")
            sys.exit(1)
        if model:
            p = replace(p, model=model)
        if all((q.base_url, q.model) != (p.base_url, p.model) for q in out):
            out.append(p)
    return out


@models.command("doctor")
@click.option("--model", default=None, help="Model name to check (default: resolved small + deep).")
@click.option("--url", default=None, help="Check this endpoint instead of the resolved one.")
@click.option("--provider", type=click.Choice(["ollama", "openai"]), default=None)
@click.option("--force", type=click.Choice(["local", "cloud"]), default=None,
              help="Check the local or cloud slot regardless of PLNT_FORCE.")
@click.option("--no-probe", is_flag=True, help="Skip the tool-calling / JSON test prompts.")
def models_doctor(model, url, provider, force, no_probe) -> None:
    """Check reachability, pulled model, tool calling, JSON output, context size."""
    from plnt.models.doctor import diagnose

    all_ok = True
    for profile in _profiles_for(model, url, provider, force):
        console.print(
            f"\n[bold]{profile.model}[/bold]  [dim]{profile.provider} · {profile.base_url} · "
            f"{profile.source}{' — ' + profile.reason if profile.reason else ''}[/dim]"
        )
        rep = diagnose(profile, probe=not no_probe)
        for c in rep.checks:
            mark = {True: "[green]✓[/green]", False: "[red]✗[/red]", None: "[dim]–[/dim]"}[c.ok]
            console.print(f"  {mark} {c.name:<15} {c.detail}")
            if c.hint and c.ok is False:
                console.print(f"      [yellow]fix:[/yellow] {c.hint}")
        all_ok = all_ok and rep.ok
    sys.exit(0 if all_ok else 1)


@models.command("list")
@click.option("--url", default=None, help="Endpoint to list (default: resolved small model's).")
@click.option("--provider", type=click.Choice(["ollama", "openai"]), default=None)
def models_list(url, provider) -> None:
    """List the models an endpoint serves."""
    from plnt.models import ModelError, get_provider

    for profile in _profiles_for(None, url, provider, None)[:1]:
        try:
            names = get_provider(profile).list_models()
        except ModelError as e:
            console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        console.print(f"[dim]{profile.provider} · {profile.base_url}[/dim]")
        for n in names:
            console.print(f"  {'[green]●[/green]' if n == profile.model else '·'} {n}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
