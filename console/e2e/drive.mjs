// Browser end-to-end for the console. Expects `plnt dev` running against the
// fake model from site/e2e/fake_model.py (see run.sh).
import { chromium } from "playwright";
const base = process.env.CONSOLE_URL ?? "http://127.0.0.1:8791/console";
const browser = await chromium.launch(
  process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {},
);
const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));
const outDir = process.env.SHOT_DIR ?? "e2e-shots";
const shot = (n, full = true) => page.screenshot({ path: `${outDir}/${n}.png`, fullPage: full });

await page.goto(base + "/");
await page.getByRole("link", { name: "dev" }).click();
await page.getByRole("heading", { name: "dev" }).waitFor();
await shot("1-overview");

// A parent session on a demo workspace: the parent spawns two agents, the
// second depending on the first, and merges their answers.
await page.getByRole("tab", { name: "Sessions" }).click();
await page.getByRole("button", { name: "New session" }).click();
await page.getByRole("dialog").getByLabel("Workspace").fill("demo:notes-api");
await page.getByRole("dialog").getByRole("button", { name: "Start" }).click();
await page.getByText("No messages yet").waitFor();
await page.getByLabel("Message").fill("Audit app/store.py for bugs and write tests for it");
await page.getByRole("button", { name: "Send" }).click();
await page.locator('[data-parent="agents"]').waitFor({ timeout: 15000 });
await page.locator('[data-agent="code-reviewer"]').getByText("done").waitFor({ timeout: 20000 });
await page.locator('[data-agent="test-writer"]').getByText("done").waitFor({ timeout: 20000 });
await page.getByText("merged by the parent").waitFor({ timeout: 15000 });
await page.getByText(/ok · \d+ tokens/).waitFor({ timeout: 15000 });
// The session list shows the task as the title and the workspace.
await page.getByRole("button", { name: /Audit app\/store\.py/ }).first().waitFor();
await shot("2-session-run");

// The session's own tabs live inside its card; the page tabs are outside it.
const inner = page.locator("section");
await inner.getByRole("tab", { name: "Agents" }).click();
if ((await page.locator("[data-agents-tab] [data-agent]").count()) !== 2) throw new Error("agents tab");
await shot("3-session-agents");
await inner.getByRole("tab", { name: "Files" }).click();
await page.locator('[data-file="README.md"]').waitFor();
await inner.getByRole("tab", { name: "Events" }).click();
await page.locator('[data-events-tab] [data-kind="parent_decision"]').waitFor();
await page.locator('[data-events-tab] [data-kind="agent_spawned"]').first().waitFor();

// A single-agent session goes straight to that bundle.
await page.getByRole("button", { name: "New session" }).click();
await page.getByRole("dialog").getByLabel("Workspace").fill("demo:cli-tool");
await page.getByRole("dialog").getByLabel("Who answers").selectOption("repo-explainer");
await page.getByRole("dialog").getByRole("button", { name: "Start" }).click();
await page.getByText("No messages yet").waitFor();
await page.getByLabel("Message").fill("What does this tool do?");
await page.getByRole("button", { name: "Send" }).click();
await page.getByText("This project is # todo", { exact: false }).last().waitFor({ timeout: 15000 });
if (await page.locator('[data-parent]').count()) throw new Error("single-agent session showed a parent decision");

// Per-tenant settings for an installed bundle are edited from a schema-driven form.
await page.getByRole("tab", { name: "Agents", exact: true }).first().click();
await page.getByRole("heading", { name: "Installed" }).waitFor().catch(() => undefined);
await page.locator('[data-install="code-reviewer"]').getByRole("button", { name: "Settings" }).click();
await page.getByRole("dialog").getByText("Focus").waitFor();
await page.getByRole("dialog").getByLabel(/Max findings/).fill("5");
await shot("4-agent-settings", false);
await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
await page.getByRole("dialog").waitFor({ state: "hidden" });

await page.getByRole("tab", { name: "Overview" }).click();
await page.getByText("Usage by agent and model").waitFor();
await page.getByText("fake:1b").first().waitFor({ timeout: 15000 });
await page.getByRole("cell", { name: "parent" }).waitFor();
await shot("5-overview-usage");
await page.getByRole("tab", { name: "Settings" }).click();
await shot("6-settings");
await page.getByRole("tab", { name: "Audit log" }).click();
await page.getByText("bundle.updated").first().waitFor();
await shot("7-audit");

await page.setViewportSize({ width: 390, height: 800 });
await page.getByRole("tab", { name: "Sessions" }).click();
await shot("8-mobile");
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ errors, mobileHorizontalOverflow: overflow }));
await browser.close();
if (errors.length || overflow) process.exit(1);
