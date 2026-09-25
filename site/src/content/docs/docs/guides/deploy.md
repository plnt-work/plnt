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

The [playground](/playground) on this site is a normal plnt server started with `--playground`:

```bash
PLNT_TRUST_PROXY=1 PLNT_PLAYGROUND_ORIGINS=https://plnt.work \
  plnt serve --host 0.0.0.0 --port 8787 --playground
```

It seeds two demo tenants and opens an anonymous API limited to them, with per-IP rate limits and a daily token cap (`PLNT_PLAYGROUND_*`, see [Environment variables](/docs/reference/env/)). Don't enable it on a server with real customers. Point the site at it with `PUBLIC_PLNT_PLAYGROUND_URL` at build time.
