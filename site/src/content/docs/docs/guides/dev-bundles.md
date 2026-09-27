---
title: The shipped developer bundles
description: code-reviewer, test-writer, repo-explainer and changelog-writer, what each does and how to configure it.
---

Four bundles ship with plnt and are what the parent picks from on a fresh install. All of them work on the session's [workspace](/docs/guides/workspaces/) with the built-in file tools; none needs a secret.

| Bundle | Tools | Must call first | Config |
| --- | --- | --- | --- |
| `code-reviewer` | list_files, read_file, search | `read_file` | `focus` (bugs, security, style, all), `max_findings`, `language_hint` |
| `test-writer` | list_files, read_file, search, write_file, execute | `read_file` | `framework` (auto, pytest, unittest, jest, vitest, go), `test_dir` |
| `repo-explainer` | list_files, read_file, search | `list_files` | `audience` (new-contributor, reviewer, manager), `max_words` |
| `changelog-writer` | list_files, read_file, search, execute | none | `style` (keepachangelog, plain, release-notes), `since` |

**Must call first** is the bundle's `require_tool`: an answer given before that tool ran is withheld. A reviewer that never read a file does not get to report findings.

## In read-only mode

The public playground and any server with `PLNT_READ_ONLY=1` strip `write_file` and `execute` before the agent sees its tools. `test-writer` then returns the test file content in its answer and says it was not written or run; `changelog-writer` writes from the current code instead of git history and says so.

## Installing and tuning

```bash
plnt install code-reviewer --tenant acme --config focus=security --config max_findings=5
plnt install test-writer --tenant acme --config framework=pytest --config test_dir=tests
```

The console's **Agents** tab builds a settings form from each bundle's `config_schema.json`.

## What the parent is told

For each installed bundle the parent sees its name, description and tools. The descriptions are written for that: they say what the bundle is for, so the parent can split a task by concern ("audit" to the reviewer, "tests" to the test writer, "explain" to the explainer).

## Your own

Copy one of them as a starting point:

```bash
cp -r "$(python -c 'import plnt.bundles.catalog as c; print(c.resolve("code-reviewer").path)')" ./my-reviewer
```

then edit `skill.toml`, `prompt.md` and `config_schema.json`. See [Write a bundle](/docs/guides/bundles/).
