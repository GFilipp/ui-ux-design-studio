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
  const ctx = await browser.newContext({ ...t.opts, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  // Capture runtime errors: the floor gates on "no console errors" (pageerror = uncaught JS,
  // console.error = logged errors). Collected per breakpoint and merged into the extract JSON.
  const consoleLog = { pageErrors: 0, consoleErrors: 0, samples: [] };
  page.on("pageerror", (err) => {
    consoleLog.pageErrors++;
    if (consoleLog.samples.length < 5) consoleLog.samples.push("pageerror: " + String(err).split("\n")[0].slice(0, 160));
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleLog.consoleErrors++;
      if (consoleLog.samples.length < 5) consoleLog.samples.push("console.error: " + msg.text().slice(0, 160));
    }
  });
  // networkidle is ideal but can time out on live sites with long-polling/analytics;
  // fall back once to domcontentloaded + a settle wait.
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
  } catch {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
    await page.waitForTimeout(1500);
  }
  await page.waitForTimeout(400); // let fonts settle
  // Scroll through to trigger IntersectionObserver reveals + JS-injected content, then return to top.
  // (Motion pages hide content until in-view; without this the floor would check an empty page.
  //  reducedMotion:'reduce' makes well-built pages show their final resting state immediately.)
  await page.evaluate(async () => {
    await new Promise((res) => {
      let y = 0;
      const step = () => {
        y += Math.max(300, window.innerHeight * 0.8);
        window.scrollTo(0, y);
        if (y < document.body.scrollHeight) setTimeout(step, 120);
        else { window.scrollTo(0, 0); setTimeout(res, 300); }
      };
      step();
    });
  });
  await page.waitForTimeout(700); // let revealed / injected content settle
  const json = await page.evaluate(extractSrc); // extract.js is a self-invoking expression
  const extractPath = join(outDir, `extract-${t.bp}.json`);
  // Merge the console capture into the extract so floor_check gates on it.
  let extractOut = typeof json === "string" ? json : JSON.stringify(json);
  try {
    const parsed = JSON.parse(extractOut);
    parsed.console = consoleLog;
    extractOut = JSON.stringify(parsed);
  } catch {}
  writeFileSync(extractPath, extractOut);
  const shotPath = join(outDir, `shot-${t.bp}.png`);
  await page.screenshot({ path: shotPath, fullPage: true });
  let vp = null;
  try { vp = JSON.parse(typeof json === "string" ? json : "{}").viewport; } catch {}
  results.push({ bp: t.bp, extract: extractPath, shot: shotPath, viewport: vp });
  await ctx.close();
}
await browser.close();
console.log(JSON.stringify(results, null, 2));
