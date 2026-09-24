from microagents.agent_loop import _parse_content, _strip_code_fence


def test_strips_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert _parse_content(raw, expect_json=True) == {"a": 1}


def test_strips_bare_fence():
    raw = '```\n{"b": 2}\n```'
    assert _parse_content(raw, expect_json=True) == {"b": 2}


def test_plain_json_unaffected():
    assert _parse_content('{"c": 3}', expect_json=True) == {"c": 3}


def test_non_json_still_errors():
    out = _parse_content("sorry, no idea", expect_json=True)
    assert "error" in out


def test_strip_helper_idempotent_on_plain():
    assert _strip_code_fence('{"x": 1}') == '{"x": 1}'
