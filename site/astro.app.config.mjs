// @ts-check
// Builds ONLY the chat / integrations / login pages into dist-app/.
// Vendored into plnt at plnt/surface/static/app/ via `plnt vendor-chat`.
import { defineConfig } from 'astro/config';
import preact from '@astrojs/preact';

export default defineConfig({
  // Self-contained under /app — plnt FastAPI mounts dist-app/ at /app/*.
  base: '/app',
  srcDir: './src-app',
  outDir: './dist-app',
  publicDir: './public-app',
  trailingSlash: 'ignore',
  integrations: [preact({ compat: false })],
  build: {
    inlineStylesheets: 'auto',
    assetsPrefix: undefined,
  },
});
