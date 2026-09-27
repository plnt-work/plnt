// Browser end-to-end for /playground. Expects the built site on SITE_URL and
// `plnt serve --playground` on :8787 with the fake model (see e2e/run.sh).
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
await page.getByLabel('Workspace').waitFor();

// 1. A parent session on notes-api: one task, two agents, the second after the
//    first, one merged reply, and every tab filled from the same run.
await page.getByLabel('Workspace').selectOption('notes-api');
await page.getByLabel('Message').fill('Audit app/store.py for bugs and write tests for it');
await page.getByRole('button', { name: 'Send' }).click();
await page.locator('.run-parent[data-parent="agents"]').waitFor({ timeout: 15000 });
await page.locator('.run-agent[data-agent="code-reviewer"].done').waitFor({ timeout: 20000 });
await page.locator('.run-agent[data-agent="test-writer"].done').waitFor({ timeout: 20000 });
await page.locator('.reply .msg.agent', { hasText: 'Findings' }).waitFor({ timeout: 20000 });
await page.getByText('merged by the parent').waitFor();
await page.locator('.pg-head h1', { hasText: 'Audit app/store.py' }).waitFor();
await page.locator('.pg-list .row', { hasText: 'Audit app/store.py' }).waitFor();
await page.screenshot({ path: `${outDir}/playground-run.png` });

await page.getByRole('tab', { name: 'Agents' }).click();
if ((await page.locator('[data-agents-tab] [data-agent]').count()) !== 2) await fail('agents tab should list 2 agents');
await page.screenshot({ path: `${outDir}/playground-agents.png` });
await page.getByRole('tab', { name: 'Files' }).click();
await page.locator('[data-file="README.md"]').waitFor();
await page.getByRole('tab', { name: 'Events' }).click();
for (const kind of ['user_message', 'run_started', 'parent_decision', 'agent_spawned', 'tool_call', 'agent_finished', 'assistant_message', 'run_finished']) {
  if (!(await page.locator(`.pg-trace li.k-${kind}`).count())) await fail(`trace is missing ${kind}`);
}
await page.screenshot({ path: `${outDir}/playground-events.png` });
await page.getByRole('tab', { name: 'Run' }).click();

// 2. Restart: a new session on the other workspace, isolated from the first.
await page.getByRole('button', { name: 'Restart' }).click();
await page.getByLabel('Workspace').selectOption('cli-tool');
if (await page.locator('.msg.user').count()) await fail('new session shows the old messages');
await page.getByLabel('Message').fill('What does this tool do?');
await page.getByRole('button', { name: 'Send' }).click();
await page.locator('.reply .msg.agent', { hasText: '# todo' }).waitFor({ timeout: 20000 });

// 3. Switching back keeps the first session.
await page.locator('.pg-list .row', { hasText: 'Audit app/store.py' }).click();
await page.locator('.reply .msg.agent', { hasText: 'Findings' }).waitFor();

// 4. Kill a slow run.
await page.getByLabel('Message').fill('slow question please');
await page.getByRole('button', { name: 'Send' }).click();
await page.getByRole('button', { name: 'Kill run' }).click({ timeout: 5000 });
await page.locator('.msg.note.killed').waitFor({ timeout: 15000 });
await page.getByRole('button', { name: 'Send' }).waitFor();
await page.screenshot({ path: `${outDir}/playground-killed.png` });

// 5. A preset from the URL (use-cases page links here).
await page.goto(`${site}/playground?tenant=cli-tool&task=${encodeURIComponent('Find the bug in the date handling.')}`);
await page.getByLabel('Message').waitFor();
if ((await page.getByLabel('Message').inputValue()) !== 'Find the bug in the date handling.') await fail('task preset not applied');

// 6. Mobile layout renders without horizontal scroll.
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
await mobile.goto(`${site}/playground`);
await mobile.getByLabel('Workspace').waitFor();
const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
if (overflow > 1) await fail(`mobile horizontal overflow ${overflow}px`);
await mobile.screenshot({ path: `${outDir}/playground-mobile.png`, fullPage: true });

// 7. Offline state is honest when the server is unreachable.
const off = await browser.newPage();
await off.goto(`${site}/playground?api=http://127.0.0.1:9`);
await off.getByText('The playground server is offline').waitFor();
await off.screenshot({ path: `${outDir}/playground-offline.png` });

// 7b. A reachable server without playground mode says so, and names the fix.
await off.goto(`${site}/playground?api=http://127.0.0.1:8788`);
await off.getByText('The playground is not enabled on this server').waitFor();
await off.getByText('PLNT_PLAYGROUND=1').waitFor();

// 8. Landing and docs render.
await page.goto(`${site}/`);
await page.locator('.hero h1').waitFor();
await page.screenshot({ path: `${outDir}/home.png`, fullPage: true });
await page.goto(`${site}/docs/getting-started/quickstart/`);
await page.getByRole('heading', { name: 'Quickstart' }).first().waitFor();
await page.screenshot({ path: `${outDir}/docs-quickstart.png` });

console.log(JSON.stringify({ errors }));
await browser.close();
if (errors.length) process.exit(1);
console.log('site e2e: ok');
