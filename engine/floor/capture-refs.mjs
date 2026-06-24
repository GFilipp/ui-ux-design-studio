// capture-refs.mjs — headless capture of the exemplar reference corpus.
// Saves an above-the-fold desktop screenshot per site to the output dir (default exemplars/captures).
// Headless + to-disk (does not flood the agent context). Third-party captures stay LOCAL (gitignored).
//
// Usage:  node engine/floor/capture-refs.mjs [outDir]
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const OUT = process.argv[2] || "exemplars/captures";
mkdirSync(OUT, { recursive: true });

// Gary's 14 exemplars. URLs are best-effort; failures are reported for manual resolution.
const SITES = [
  { name: "linear", url: "https://linear.app" },
  { name: "zed", url: "https://zed.dev" },
  { name: "tesla", url: "https://www.tesla.com" },
  { name: "arc", url: "https://arc.net" },
  { name: "raycast", url: "https://www.raycast.com" },
  { name: "polestar", url: "https://www.polestar.com" },
  { name: "teenage-engineering", url: "https://teenage.engineering" },
  { name: "oura", url: "https://ouraring.com" },
  { name: "stripe", url: "https://stripe.com" },
  { name: "tresmares", url: "https://www.tresmarescapital.com/en/" },
  { name: "exat", url: "https://exat.studio" }, // UNRESOLVED guess — obscure Awwwards site; fix if you have the URL
  { name: "lando-norris", url: "https://www.landonorris.com" },
  { name: "dropbox-brand", url: "https://brand.dropbox.com" },
  { name: "symphony-of-vines", url: "https://symphonyofvines.com" },
];

let browser;
try { browser = await chromium.launch(); }
catch { browser = await chromium.launch({ channel: "chrome" }); }

const results = [];
for (const s of SITES) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  try {
    await page.goto(s.url, { waitUntil: "domcontentloaded", timeout: 20000 });
    await page.waitForTimeout(2500); // let hero/fonts settle
    const p = join(OUT, s.name + ".png");
    await page.screenshot({ path: p }); // viewport only = above the fold
    results.push({ name: s.name, ok: true, path: p });
  } catch (e) {
    results.push({ name: s.name, ok: false, url: s.url, error: String(e).split("\n")[0].slice(0, 90) });
  }
  await ctx.close();
}
await browser.close();
const ok = results.filter(r => r.ok).map(r => r.name);
const failed = results.filter(r => !r.ok);
console.log(JSON.stringify({ captured: ok, failed }, null, 2));
