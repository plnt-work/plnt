# plnt site

The website and docs for [plnt](https://github.com/plnt-work/plnt), built with Astro + Starlight. Static output, deployable to any static host.

```
src/
  pages/index.astro          landing page
  pages/playground.astro     live playground (Preact island)
  pages/privacy.astro, terms.astro
  islands/Playground.tsx     talks to a real `plnt serve --playground`
  content/docs/docs/         docs at /docs/ (Starlight)
  layouts/Layout.astro
  styles/                    global.css (same tokens as the console), playground.css, starlight-overrides.css
e2e/                         browser test for the playground (run.sh, playground.mjs, fake_model.py)
```

## Develop

```bash
npm ci
npm run dev        # http://localhost:4321
npm run build      # static output in dist/
```

## Playground

The `/playground` page has no canned answers. It calls a plnt server started with `--playground`:

```bash
plnt serve --port 8787 --playground     # from the repo root, with a model configured
```

The page uses `PUBLIC_PLNT_PLAYGROUND_URL` (set at build time), then `?api=<url>` in the page URL, then `http://localhost:8787`. If the server is unreachable, it says so and shows how to run it locally. See the [deploy guide](src/content/docs/docs/guides/deploy.md#hosting-the-public-playground) for hosting it.

## Test

```bash
bash site/e2e/run.sh     # from the repo root; needs plnt installed and Chromium
```

This builds nothing itself; run `npm run build` first. It starts a fake model and `plnt serve --playground`, serves `dist/`, and drives the playground: chat, tenant isolation, kill, mobile layout, the offline state, and the landing and docs pages.
