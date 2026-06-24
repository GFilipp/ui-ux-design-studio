// render.mjs — headless renderer for the FLOOR loop. Mobile-first.
// Emulates a REAL mobile device (iPhone 13: 390x844, DPR 3, touch) plus desktop,
// runs extract.js in-page via page.evaluate (no MCP output-cap truncation),
// and writes one extract JSON + one screenshot per breakpoint.
//
// Usage:  node engine/floor/render.mjs <url-or-file> [outDir]
//   url-or-file: http(s):// URL or an absolute path to a local .html file (file:// is auto-added)
//   outDir:      where to write extract-<bp>.json + shot-<bp>.png   (default /tmp/floor)
//
// Then gate each breakpoint with engine/floor/floor_check.py, MOBILE FIRST.
//
// Browser: uses the system Chrome (channel:'chrome') so no Chromium download is needed;
// falls back to Playwright's bundled Chromium (`npx playwright install chromium`) if absent.
import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const arg = process.argv[2];
const outDir = process.argv[3] || "/tmp/floor";
if (!arg) {
  console.error("usage: node render.mjs <url-or-file> [outDir]");
  process.exit(1);
}
const url = /^https?:\/\//.test(arg) ? arg : "file://" + arg;
mkdirSync(outDir, { recursive: true });

const extractSrc = readFileSync(new URL("./extract.js", import.meta.url), "utf8");

const targets = [
  // Explicit mobile viewport — emulation must be deterministic, not tied to a device-descriptor name.
  { bp: "mobile", opts: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true } },
  { bp: "desktop", opts: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 } },
];

let browser;
try {
  browser = await chromium.launch(); // bundled chromium = faithful device emulation
} catch {
  browser = await chromium.launch({ channel: "chrome" }); // fallback to system Chrome
}

const results = [];
for (const t of targets) {
  const ctx = await browser.newContext(t.opts);
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(400); // let fonts / reveal-on-scroll settle
  const json = await page.evaluate(extractSrc); // extract.js is a self-invoking expression
  const extractPath = join(outDir, `extract-${t.bp}.json`);
  writeFileSync(extractPath, typeof json === "string" ? json : JSON.stringify(json));
  const shotPath = join(outDir, `shot-${t.bp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true });
  let vp = null;
  try { vp = JSON.parse(typeof json === "string" ? json : "{}").viewport; } catch {}
  results.push({ bp: t.bp, extract: extractPath, shot: shotPath, viewport: vp });
  await ctx.close();
}
await browser.close();
console.log(JSON.stringify(results, null, 2));
