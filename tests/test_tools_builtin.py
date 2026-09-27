"""The built-in file tools stay inside the workdir and behave as documented."""

from __future__ import annotations

from plnt.agent import filesystem_tools
from plnt.bundles import BUILTIN_TOOLS, READ_ONLY_TOOLS


def _tools(tmp_path):
    wd = tmp_path / "wd"
    (wd / "src").mkdir(parents=True)
    (wd / "src" / "a.py").write_text("line1\nline2\nline3\n")
    (wd / "src" / "__pycache__").mkdir()
    (wd / "README.md").write_text("# hi\n")
    (tmp_path / "outside.txt").write_text("secret\n")
    return wd, filesystem_tools(wd, [wd])


def test_names_match_the_bundle_contract(tmp_path):
    _, tools = _tools(tmp_path)
    assert set(tools) == set(BUILTIN_TOOLS)
    assert READ_ONLY_TOOLS < BUILTIN_TOOLS
    for t in tools.values():
        assert t.spec()["function"]["name"] == t.name


def test_list_files(tmp_path):
    _, tools = _tools(tmp_path)
    out = tools["list_files"].fn({})
    paths = [e["path"] for e in out["entries"]]
    assert paths == ["src/", "src/a.py", "README.md"]
    assert out["root"] == "." and out["truncated"] is False
    assert tools["list_files"].fn({"path": "src", "depth": 1})["entries"][0]["path"] == "a.py"
    assert "error" in tools["list_files"].fn({"path": "README.md"})


def test_read_file_ranges_and_confinement(tmp_path):
    _, tools = _tools(tmp_path)
    r = tools["read_file"].fn({"path": "src/a.py", "start": 2})
    assert r["content"] == "2: line2\n3: line3" and r["lines"] == 3 and r["end"] == 3
    r = tools["read_file"].fn({"path": "src/a.py", "start": 1, "end": 1})
    assert r["content"] == "1: line1"
    assert "error" in tools["read_file"].fn({"path": "src"})
    try:
        tools["read_file"].fn({"path": "../outside.txt"})
    except Exception as e:  # noqa: BLE001
        assert "not inside" in str(e)
    else:
        raise AssertionError("read outside the workdir was allowed")


def test_write_file_creates_parents_and_stays_inside(tmp_path):
    wd, tools = _tools(tmp_path)
    r = tools["write_file"].fn({"path": "tests/test_a.py", "content": "def test(): pass\n"})
    assert r["created"] is True and (wd / "tests" / "test_a.py").is_file()
    r = tools["write_file"].fn({"path": "tests/test_a.py", "content": "x"})
    assert r["created"] is False and r["bytes"] == 1
    try:
        tools["write_file"].fn({"path": "/etc/evil", "content": "x"})
    except Exception as e:  # noqa: BLE001
        assert "not inside" in str(e)
    else:
        raise AssertionError("write outside the workdir was allowed")
