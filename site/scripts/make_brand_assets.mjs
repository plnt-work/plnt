// Rebuild the PNG brand assets from the one mark (site/public/mark.svg) and
// the OG layout (design/og.html). Run from site/: node scripts/make_brand_assets.mjs
// Uses headless Chrome via Playwright (CHROME_PATH to point at a local build).
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const site = resolve(here, '..');
const design = resolve(site, '..', 'design');
const sprout = readFileSync(resolve(site, 'public/mark.svg'), 'utf8');
const browser = await chromium.launch(
  process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {},
);

// Square icon: ink tile, orange sprout. Same drawing as public/favicon.svg.
async function icon(size, out) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  const inner = sprout.replace('<svg ', `<svg style="width:${size * 0.72}px;height:${size * 0.72}px" `);
  await page.setContent(
    `<html><body style="margin:0;width:${size}px;height:${size}px;display:grid;place-items:center;background:#14120f">${inner}</body></html>`,
  );
  writeFileSync(resolve(site, 'public', out), await page.screenshot({ type: 'png' }));
  await page.close();
}

await icon(180, 'apple-touch-icon.png');
await icon(32, 'favicon-32.png');

const og = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await og.goto(pathToFileURL(resolve(design, 'og.html')).href);
await og.evaluate(() => document.fonts.ready);
writeFileSync(resolve(site, 'public/og.png'), await og.screenshot({ type: 'png' }));
await browser.close();
console.log('wrote public/apple-touch-icon.png, public/favicon-32.png, public/og.png');
