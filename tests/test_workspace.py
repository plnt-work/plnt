"""Workspace specs: demo copies, local folder copies with a size cap, policy
refusals, and a shallow clone from a local repository."""

from __future__ import annotations

import subprocess

import pytest

from plnt.tenancy import workspace as ws


def test_parse():
    assert ws.parse("demo:notes-api") == ("demo", "notes-api")
    assert ws.parse("/tmp/x") == ("path", "/tmp/x")
    assert ws.parse("~/x") == ("path", "~/x")
    assert ws.parse("https://github.com/o/r.git") == ("git", "https://github.com/o/r.git")
    assert ws.parse("git@github.com:o/r.git")[0] == "git"
    for bad in ("", "nope", "demo:../x"):
        with pytest.raises(ws.WorkspaceError):
            ws.parse(bad) if bad != "demo:../x" else ws.demo_root("../x")


def test_path_copy_skips_junk_and_counts_files(tmp_path):
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "a.py").write_text("x = 1\n")
    (src / ".git").mkdir()
    (src / ".git" / "HEAD").write_text("ref\n")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "big.js").write_text("//\n")
    dest = tmp_path / "dest"
    info = ws.materialize(str(src), dest, allow_paths=True)
    assert info == ws.WorkspaceInfo(name="src", kind="path", source=str(src), file_count=1)
    assert (dest / "pkg" / "a.py").read_text() == "x = 1\n"
    assert not (dest / ".git").exists() and not (dest / "node_modules").exists()


def test_path_copy_refused_by_policy_or_size(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.bin").write_bytes(b"0" * (2 * 1024 * 1024))
    with pytest.raises(ws.WorkspaceError, match="not allowed"):
        ws.materialize(str(src), tmp_path / "d1", allow_paths=False)
    with pytest.raises(ws.WorkspaceError, match="limit is 1 MB"):
        ws.materialize(str(src), tmp_path / "d2", allow_paths=True, max_mb=1)
    with pytest.raises(ws.WorkspaceError, match="not a directory"):
        ws.materialize(str(tmp_path / "missing"), tmp_path / "d3", allow_paths=True)


def test_git_clone_from_a_local_repo(tmp_path):
    repo = tmp_path / "upstream"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "hello.py").write_text("print('hi')\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                   cwd=repo, check=True)
    url = "file://" + str(repo)
    with pytest.raises(ws.WorkspaceError, match="not allowed"):
        ws.materialize(url, tmp_path / "d0", allow_git=False)
    info = ws.materialize(url, tmp_path / "d1", allow_git=True)
    assert info.kind == "git" and info.name == "upstream" and info.file_count == 1
    assert (tmp_path / "d1" / "hello.py").read_text().startswith("print")
    with pytest.raises(ws.WorkspaceError, match="git clone failed"):
        ws.materialize("file:///nowhere/none.git", tmp_path / "d2", allow_git=True)


def test_demo_workspaces_list_and_copy(tmp_path, monkeypatch):
    demo = tmp_path / "demos"
    (demo / "tiny").mkdir(parents=True)
    (demo / "tiny" / "main.py").write_text("pass\n")
    monkeypatch.setattr(ws, "_DEMO_DIRS", [demo])
    assert ws.list_demos() == ["tiny"]
    info = ws.materialize("demo:tiny", tmp_path / "dest")
    assert info.kind == "demo" and info.file_count == 1 and info.source == "demo:tiny"
    with pytest.raises(ws.WorkspaceError, match="no demo workspace"):
        ws.materialize("demo:other", tmp_path / "dest2")
