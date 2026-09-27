---
title: What plnt is
description: An open-source runtime where a parent agent takes a task, spawns micro-agents on a workspace, and merges the result, with every step on the record.
---

plnt runs a **parent agent** in front of a task. The parent reads the task, decides which **micro-agents** to create and what each one should do, runs them in isolation on a private copy of the **workspace** (a repository or folder), and merges their answers into one reply.

Everything is recorded as it happens: the parent's decision and its reason, each agent's spec (bundle, tools, model, budget, what it depends on), every model call, tool call and file it touched, and the usage per agent. A console and a playground render that record as a run view; an HTTP API streams it.

## The pieces

- **Bundle**: an agent as a folder (`skill.toml`, `prompt.md`, `config_schema.json`, optional `tools/*.py`). plnt ships four for developer tasks: `code-reviewer`, `test-writer`, `repo-explainer`, `changelog-writer`.
- **Tenant**: whoever the agents work for (you, a team, a client). Each tenant has its own installs and config, secrets, model, sessions, usage and audit log.
- **Session**: one task and its follow-ups, bound to a workspace. A session with no bundle is run by the parent; a session with a bundle goes straight to that agent.
- **Workspace**: what the session works on. A private copy is made per session; the source is never touched.

## Who it's for

Developers and teams who want agents to do real work on repositories and documents, and want to see exactly what each agent did. Platform teams who run that for many tenants, each isolated, on the model of their choice, local or hosted.

## What it is not

- **Not a chat framework.** If you want one assistant with one prompt, a client library is simpler.
- **Not a sandbox for untrusted code, yet.** Bundle tools run inside the server process; `execute` runs programs as the server user. Only install bundles you trust, and keep the public playground read-only (it is, by default).
- **Not production-proven.** Version 0.1, pre-alpha. SQLite and files on one machine.

## Next

- [Quickstart](/docs/getting-started/quickstart/): a parent session on your own repo in five minutes.
- [Concepts](/docs/getting-started/concepts/): parent, agents, workspaces, sessions, events.
- [Playground](/playground): the same thing on a demo repo, in your browser.
