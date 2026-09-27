from todo import store


def test_add_and_done(tmp_path, monkeypatch):
    monkeypatch.setenv("TODO_FILE", str(tmp_path / "t.json"))
    t = store.add("write tests")
    assert t.id == 1 and not t.done
    assert store.mark_done(1).done is True
    assert store.load()[0].done is True
