// Browser end-to-end for the console. Expects `plnt dev support-desk` running
// against the fake model from scripts/smoke_platform.py (see run.sh).
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

await page.getByRole("tab", { name: "Conversations" }).click();
await page.getByRole("button", { name: "New conversation" }).click();
await page.getByRole("dialog").getByRole("button", { name: "Start" }).click();
await page.getByPlaceholder("Message as this tenant’s customer…").fill("When are you open?");
await page.getByRole("button", { name: "Send" }).click();
await page.getByText("Tuesday to Sunday, 5pm to 11pm.", { exact: false }).last().waitFor({ timeout: 15000 });
await page.getByText(/ok · \d+ tokens/).waitFor({ timeout: 15000 });
await shot("2-conversation");

await page.getByRole("tab", { name: "Agents" }).click();
await page.getByRole("button", { name: "Settings" }).first().click();
await page.getByRole("dialog").getByText("Business name").waitFor();
await page.getByRole("dialog").getByRole("button", { name: "Add" }).click();
const rows = page.getByRole("dialog").getByLabel(/^Question 2$/);
await rows.fill("Do you have parking?");
await page.getByRole("dialog").getByLabel(/^Answer 2$/).fill("Yes, free parking behind the restaurant.");
await shot("3-agent-settings", false);
await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
await page.getByRole("dialog").waitFor({ state: "hidden" });

await page.getByRole("tab", { name: "Conversations" }).click();
await page.getByRole("button", { name: "New conversation" }).click();
await page.getByRole("dialog").getByRole("button", { name: "Start" }).click();
await page.getByPlaceholder("Message as this tenant’s customer…").fill("Is there parking?");
await page.getByRole("button", { name: "Send" }).click();
await page.getByText("Yes, free parking behind the restaurant.").last().waitFor({ timeout: 15000 });

await page.getByRole("tab", { name: "Overview" }).click();
await page.getByText("Usage by agent and model").waitFor();
await page.getByText("fake:1b").waitFor({ timeout: 15000 });
await shot("4-overview-usage");
await page.getByRole("tab", { name: "Settings" }).click();
await shot("5-settings");
await page.getByRole("tab", { name: "Audit log" }).click();
await page.getByText("bundle.updated").first().waitFor();
await shot("6-audit");

await page.setViewportSize({ width: 390, height: 800 });
await page.getByRole("tab", { name: "Conversations" }).click();
await shot("7-mobile");
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ errors, mobileHorizontalOverflow: overflow }));
await browser.close();
if (errors.length || overflow) process.exit(1);
