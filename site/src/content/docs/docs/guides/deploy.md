---
title: Deploy
description: Run plnt serve on a server, with Docker or without.
---

plnt 0.1 is a single process with its state on local disk (`$PLNT_HOME`). Deploy it like any small stateful service: one instance, one persistent volume, backups of that volume.

## Docker

The repo's `Dockerfile` builds the server with the console included. Each release is also published as `ghcr.io/plnt-work/plnt:<version>`.

```bash
docker build -t plnt .       # or: docker pull ghcr.io/plnt-work/plnt:v0.1.0
docker run -d --name plnt -p 8787:8787 \
  -v plnt-data:/data \
  -e PLNT_ADMIN_TOKEN=... \
  -e PLNT_CLOUD_URL=https://generativelanguage.googleapis.com/v1beta/openai \
  -e PLNT_CLOUD_API_KEY=... \
  -e PLNT_CLOUD_SMALL_MODEL=gemini-2.5-flash \
  plnt
```

Inside the image, `PLNT_HOME=/data` and the server runs as a non-root user (uid 10001). Mount a volume there or you lose every tenant on restart.

To add your own bundles, mount them and point `PLNT_BUNDLE_PATH` at them:

```bash
  -v ./bundles:/bundles:ro -e PLNT_BUNDLE_PATH=/bundles
```

With Ollama on the Docker host, add `--add-host=host.docker.internal:host-gateway -e PLNT_LOCAL_URL=http://host.docker.internal:11434`.

## Without Docker

```bash
pip install "git+https://github.com/plnt-work/plnt"
PLNT_HOME=/var/lib/plnt PLNT_ADMIN_TOKEN=... plnt serve --host 0.0.0.0 --port 8787
```

Run it under systemd or another supervisor.

## In front of it

- Terminate TLS in a reverse proxy (Caddy, nginx, a load balancer). Never send tokens over plain HTTP.
- Disable proxy buffering for `/v1/tenants/*/sessions/*/stream` so SSE events arrive live (nginx: `proxy_buffering off;`).
- Keep one instance. Two processes on the same `$PLNT_HOME` do not coordinate runs in 0.1.

## Backups

Everything is under `$PLNT_HOME`: SQLite files, JSON and JSONL. Back up the directory. Use `sqlite3 data.db .backup` for a consistent copy of a database that's in use. `secrets.json` files contain plaintext credentials, so encrypt your backups.

## Hosting the public playground

The [playground](/playground) on this site is a normal plnt server with `PLNT_PLAYGROUND=1` (or `--playground`). It seeds two demo tenants, each bound to a sample workspace (`notes-api`, `cli-tool`) with the four developer bundles installed, and opens an anonymous API limited to them: every visitor session gets its own copy of the workspace, the executor is read-only (no `write_file`, no `execute`) unless `PLNT_PLAYGROUND_EXECUTE=1`, invented roles are on, and there are per-IP rate limits and a daily token cap (`PLNT_PLAYGROUND_*`, see [Environment variables](/docs/reference/env/)). Copies older than 24 hours are swept. Don't enable it on a server with real tenants.

### On Render

The repo has a Render Blueprint, `render.yaml`:

1. In the Render dashboard, choose **New → Blueprint** and pick the repository.
2. When asked for `PLNT_CLOUD_API_KEY`, paste a Gemini API key made only for the playground. Set a budget alert on it in Google Cloud.
3. Deploy. Check `https://<service>.onrender.com/v1/playground` returns the two demo workspaces with a `file_count`.
4. In the site's hosting (Vercel), set `PUBLIC_PLNT_PLAYGROUND_URL=https://<service>.onrender.com` and redeploy the site. The Vercel project's **Root Directory** must be `site` with the **Astro** preset. From the repository root, Vercel finds the Python code and tries to deploy it as a FastAPI app, which fails.

Opening the service's bare URL returns a small JSON map of its endpoints; the playground API is under `/v1/playground`.

The blueprint:

- runs the repo's `Dockerfile` on a Starter instance. Free instances sleep when idle, so the first visitor would wait about a minute.
- uses Gemini 2.5 Flash with a cap of 3M tokens a day across all visitors (agents that read files use more than chat).
- allows only `plnt.work` origins and the site's Vercel preview deployments (`https://plnt-site*.vercel.app`). If you created the service by hand rather than from the blueprint, set `PLNT_PLAYGROUND_ORIGINS` to the same value in the Render dashboard.
- leaves `PLNT_ADMIN_TOKEN` unset, so operator routes answer 503.
- has no disk. Sessions and workspace copies are thrown away on each deploy, and the demo tenants are seeded again on start.
- keeps `PLNT_PLAYGROUND_EXECUTE` unset: visitors never run programs on the server.
- redeploys only after CI passes, and only when server code changes.

### Anywhere else

```bash
docker run -d -p 8787:8787 -e PLNT_PLAYGROUND=1 -e PLNT_TRUST_PROXY=1 \
  -e PLNT_PLAYGROUND_ORIGINS=https://your-site.example \
  -e PLNT_CLOUD_URL=... -e PLNT_CLOUD_API_KEY=... -e PLNT_CLOUD_SMALL_MODEL=... plnt
```

Only set `PLNT_TRUST_PROXY=1` behind a proxy that puts the real client IP first in `X-Forwarded-For` (Render does). Otherwise a visitor can fake the header and get past the rate limits.
