# Deploy — plnt-site + play.plnt.work

Target topology:

- **Frontend** (this repo): Vercel, serves `plnt.work` (marketing) and `play.plnt.work` (playground).
- **Backend** (`../plnt`, Helm chart `plnt/charts/playground-api/`): Kubernetes Ingress at `playground.plnt.work`. OpenAI-shape API: `/v1/models`, `/v1/chat/completions` (SSE), `/healthz`, `/readyz`.
- Frontend fetches the backend cross-origin. Backend must allow `https://play.plnt.work` (and `https://plnt.work` if you want the marketing `/playground` route to work too).

---

## 1. First deploy (one-time)

```sh
# from /Users/dev16/Documents/den-agent/plnt-site
vercel login              # opens browser; log in as devdattatalele
vercel --yes              # links the project (scope=devdattatalele, name=plnt-site, framework=Astro) and ships a preview
```

Preview URL will be something like `https://plnt-site-<hash>-devdattatalele.vercel.app`. Open it — the `/playground` route should render with the model sidebar + chat panel. Chat will show `stub` (backend not wired yet).

## 2. Promote to production

```sh
vercel --prod
```

Prints the production URL (default: `plnt-site.vercel.app` + any custom domains you've attached).

## 3. Attach domains

```sh
# marketing site — root
vercel domains add plnt.work
vercel domains add www.plnt.work

# playground subdomain
vercel domains add play.plnt.work
```

Each command prints the DNS record it needs. Typical output for an apex domain (`plnt.work`):

```
A     @    76.76.21.21
```

For a subdomain (`play.plnt.work`, `www.plnt.work`):

```
CNAME play    cname.vercel-dns.com.
CNAME www     cname.vercel-dns.com.
```

Add these at your DNS provider (Cloudflare, Route53, registrar's default DNS, etc.). Vercel auto-issues a Let's Encrypt cert once DNS resolves.

Confirm with:

```sh
vercel domains inspect play.plnt.work
```

## 4. Wire the backend endpoint (when the backend is deployed)

Once `playground.plnt.work` is live and reachable:

```sh
vercel env add PUBLIC_PLNT_ENDPOINT production
# paste: https://playground.plnt.work
```

Then redeploy:

```sh
vercel --prod
```

The playground page will now fetch `/v1/models` on load. If the backend responds, the connection indicator flips from `stub` to `live` and Send goes through to the real inference endpoint.

If `PUBLIC_PLNT_ENDPOINT` is unset, the frontend already defaults to `https://playground.plnt.work` (baked into `src/islands/playground/api.ts`) — the env var only matters when overriding for local dev or a different backend.

## 5. Local override (for dev against a local backend)

```sh
# ephemeral, current shell only
PUBLIC_PLNT_ENDPOINT=http://localhost:8000 npm run dev
```

Or add to `.env` (gitignored) at the repo root.

## 6. Backend CORS (this needs to happen in the plnt repo)

The backend Helm chart must set `Access-Control-Allow-Origin` for the frontend hosts.
Typical ingress annotation for nginx:

```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://play.plnt.work, https://plnt.work"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "content-type, authorization"
```

Without this, browsers will block the fetch and the playground will silently fall back to stub mode.

## 7. Routing rules

- `plnt.work/` — marketing home
- `plnt.work/playground` — playground (also served here, for convenience)
- `play.plnt.work/` — playground (rewritten from `/playground` via `vercel.json`)
- `playground.plnt.work/*` — **backend only**, not the frontend. Owned by the K8s Ingress.

## 8. Rollback

```sh
vercel ls                           # list recent deploys with URLs
vercel rollback <deployment-url>    # promote a prior deploy back to production
```

## 9. Files that matter here

- `vercel.json` — host-based rewrite (`play.plnt.work/` → `/playground`)
- `.vercelignore` — excludes `src-app/`, `dist-app/`, `public-app/`, `astro.app.config.mjs`, `HANDOFF.md` from upload
- `src/islands/playground/api.ts` — `ENDPOINT` default and fetch logic
