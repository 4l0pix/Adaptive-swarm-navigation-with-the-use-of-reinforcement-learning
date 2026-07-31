#!/usr/bin/env node

import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const playwrightModule = process.env.PLAYWRIGHT_MODULE_PATH ?? "playwright";
const { chromium } = require(playwrightModule);

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "..");
const outputDirectory = path.join(repositoryRoot, "assets", "screenshots");
const target = process.env.SWARM_SCREENSHOT_URL ?? "http://127.0.0.1:5000";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1600, height: 1000 },
  deviceScaleFactor: 1,
});

const browserErrors = [];
page.on("pageerror", (error) => browserErrors.push(`page: ${error.message}`));
page.on("requestfailed", (request) => {
  browserErrors.push(
    `request: ${request.url()} (${request.failure()?.errorText ?? "unknown"})`,
  );
});

await page.goto(target, { waitUntil: "networkidle", timeout: 60_000 });
await page.locator("#welcome-screen").waitFor({ state: "visible" });
await page.screenshot({
  path: path.join(outputDirectory, "sandbox-entry.png"),
  fullPage: true,
});

await page.locator("#num-experiments").fill("1");
await page.locator("#paths-per-test").fill("10");
await page.locator("#btn-start-session").click();
await page.locator("#dashboard").waitFor({ state: "visible" });
await page.locator("#view-3d canvas").waitFor({ state: "visible", timeout: 30_000 });
await page.waitForTimeout(4_000);

// Hide the unexplored-volume veil so the agent and obstacle geometry reads
// clearly in the repository overview screenshot.
await page.locator("#btn-fog-toggle").click();
await page.waitForTimeout(1_000);
await page.screenshot({
  path: path.join(outputDirectory, "command-center.png"),
  fullPage: true,
});

const summary = {
  title: await page.title(),
  status: await page.locator("#sim-status-text").textContent(),
  agents: await page.locator("#stat-total").textContent(),
  exploration: await page.locator("#stat-exploration").textContent(),
  browserErrors,
};
console.log(JSON.stringify(summary, null, 2));

await browser.close();

if (browserErrors.length > 0) {
  process.exitCode = 1;
}
