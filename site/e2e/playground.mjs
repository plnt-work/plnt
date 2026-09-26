// Browser end-to-end for /playground. Expects the built site on SITE_URL and
// `plnt serve --playground` on :8787 with a fake model (see e2e/run.sh).
import { chromium } from 'playwright';

const site = process.env.SITE_URL ?? 'http://127.0.0.1:4321';
const outDir = process.env.SHOT_DIR ?? 'e2e-shots';
const browser = await chromium.launch(
  process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {},
);
const errors = [];
const fail = async (msg) => {
  console.error('FAIL:', msg, errors);
  await browser.close();
  process.exit(1);
};

const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('console', (m) => m.type() === 'error' && errors.push('console: ' + m.text()));

await page.goto(`${site}/playground`);
await page.getByText('Bright Smile Dental').first().waitFor();

// 1. Dental: ask, get the grounded answer, see the trace.
await page.locator('.pg-tenant', { hasText: 'Bright Smile Dental' }).getByRole('button', { name: 'support-desk' }).click();
await page.getByLabel('Message').fill('When are you open?');
await page.getByRole('button', { name: 'Send' }).click();
await page.locator('.msg.agent', { hasText: '8am to 4pm' }).waitFor({ timeout: 15000 });
for (const kind of ['user_message', 'run_started', 'tool_call', 'assistant_message', 'run_finished']) {
  if (!(await page.locator(`.pg-trace li.k-${kind}`).count())) await fail(`trace is missing ${kind}`);
}
await page.screenshot({ path: `${outDir}/playground-dental.png` });

// 2. Isolation: the bistro's support-desk answers from its own FAQ, in a separate conversation.
await page.locator('.pg-tenant', { hasText: "Luigi's Bistro" }).getByRole('button', { name: 'support-desk' }).click();
if (await page.locator('.msg.user').count()) await fail('bistro conversation shows dental messages');
await page.getByLabel('Message').fill('When are you open?');
await page.getByRole('button', { name: 'Send' }).click();
await page.locator('.msg.agent', { hasText: 'Closed Mondays' }).waitFor({ timeout: 15000 });

// 3. Switching back keeps the dental conversation.
await page.locator('.pg-tenant', { hasText: 'Bright Smile Dental' }).getByRole('button', { name: 'support-desk' }).click();
await page.locator('.msg.agent', { hasText: '8am to 4pm' }).waitFor();

// 4. Kill a slow run.
await page.getByLabel('Message').fill('slow question please');
await page.getByRole('button', { name: 'Send' }).click();
await page.getByRole('button', { name: 'Kill run' }).click({ timeout: 5000 });
await page.locator('.pg-trace li.k-killed').waitFor({ timeout: 15000 });
await page.locator('.pg-trace li.k-run_finished').nth(1).waitFor({ timeout: 15000 });
await page.getByRole('button', { name: 'Send' }).waitFor();
await page.screenshot({ path: `${outDir}/playground-killed.png` });

// 5. Mobile layout renders without horizontal scroll.
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto(`${site}/playground`);
await mobile.getByText('Bright Smile Dental').first().waitFor();
const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
if (overflow > 1) await fail(`mobile horizontal overflow ${overflow}px`);
await mobile.screenshot({ path: `${outDir}/playground-mobile.png`, fullPage: true });

// 6. Offline state is honest when the server is unreachable.
const off = await browser.newPage();
await off.goto(`${site}/playground?api=http://127.0.0.1:9`);
await off.getByText('The playground server is offline').waitFor();
await off.screenshot({ path: `${outDir}/playground-offline.png` });

// 7. Landing and docs render.
await page.goto(`${site}/`);
await page.getByText('Ship one agent to 1,000 customers.').waitFor();
await page.screenshot({ path: `${outDir}/home.png`, fullPage: true });
await page.goto(`${site}/docs/getting-started/quickstart/`);
await page.getByRole('heading', { name: 'Quickstart' }).first().waitFor();
await page.screenshot({ path: `${outDir}/docs-quickstart.png` });

const real = errors.filter((e) => !e.includes('127.0.0.1:9'));
if (real.length) await fail('browser errors');
console.log('site e2e: ok');
await browser.close();
