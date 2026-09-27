---
title: Quickstart
description: Install plnt, point it at a model, and run a parent session on your own repository.
---

## 1. Install

plnt needs Python 3.11 or newer.

```bash
pip install "git+https://github.com/plnt-work/plnt"
plnt --version
```

Once v0.1.0 is on PyPI this becomes `pip install plnt`.

## 2. Pick a model

Choose **one** of these.

**Local, with Ollama.** Nothing leaves your machine.

```bash
ollama pull qwen2.5:7b
export PLNT_PLANNER_MODEL=qwen2.5:7b
```

**Hosted, with any OpenAI-compatible API.** Gemini is shown here; OpenAI, Groq and OpenRouter work the same way.

```bash
export PLNT_CLOUD_URL=https://generativelanguage.googleapis.com/v1beta/openai
export PLNT_CLOUD_API_KEY=...
export PLNT_CLOUD_SMALL_MODEL=gemini-2.5-flash
```

Then check that the model can do what an agent needs:

```bash
plnt models doctor
```

The doctor checks that the server is reachable, the model is pulled, it calls tools, and it returns JSON. For anything that fails, it prints the fix. See [Local models](/docs/guides/local-models/).

## 3. Run one agent on a repo

`code-reviewer` ships with plnt. It reads files and reports findings with `path:line` citations.

```bash
cd ~/src/my-project
plnt run code-reviewer "review src/auth.py for bugs" --workspace .
```

`--workspace .` copies the folder into the session's working directory first (ignoring `.git`, `node_modules` and the like). You see each step as it happens: `list_files`, `read_file`, the model calls, and the answer. Try `repo-explainer`, `test-writer` and `changelog-writer` the same way.

## 4. A parent session

The parent decides which agents a task needs. Start the local server with the bundles installed:

```bash
plnt install code-reviewer --tenant dev --config focus=bugs
plnt install test-writer --tenant dev
plnt dev repo-explainer --workspace ~/src/my-project
```

Open `http://127.0.0.1:8787/console`, go to **Sessions**, click **New session**, enter the workspace path, keep **Parent (all agents)**, and give it a task:

> Audit src/auth.py for bugs and write tests for it.

The Run tab shows the parent's decision and its reason, the plan, one card per agent as it works (spec, tool calls, files), and the merged reply. The Agents, Files and Events tabs show the same run from the other sides.

`plnt dev` turns invented roles on: if no installed bundle fits part of the task, the parent may create a single-purpose role with the built-in file tools.

Over HTTP it is the same thing:

```bash
API=http://127.0.0.1:8787/v1
SID=$(curl -s -X POST $API/tenants/dev/sessions -H 'content-type: application/json' \
  -d '{"workspace": "'$HOME'/src/my-project"}' | jq -r .session_id)
curl -s -X POST $API/tenants/dev/sessions/$SID/messages -H 'content-type: application/json' \
  -d '{"text": "Audit src/auth.py for bugs and write tests for it."}'
curl -N "$API/tenants/dev/sessions/$SID/stream?until_idle=1"
curl -s $API/tenants/dev/sessions/$SID/transcript | jq .turns[0].parent
```

## 5. Serve it for real

```bash
export PLNT_ADMIN_TOKEN=$(openssl rand -hex 24)
plnt serve --port 8787
```

`plnt serve` has auth on, invented roles off, and local folders allowed as workspaces; git URLs need `PLNT_WORKSPACE_GIT=1`. See [Serve many tenants](/docs/guides/multi-tenant/) and [Workspaces](/docs/guides/workspaces/).

## 6. Write your own bundle

```bash
plnt init my-agent
plnt run ./my-agent "do the thing" --workspace .
```

Next: [Write a bundle](/docs/guides/bundles/).
