// Per-section screenshot capture for landing-page bake-offs.
// Usage: node capture-sections.mjs <config.json> <outRoot>
//   config.json: [{ "id": "v3", "url": "http://...", "mode": "markers" | "auto" }, ...]
//   markers mode: sections = [data-section] elements, filenames from the attribute.
//   auto mode:    sections = header/main>section/section/footer in DOM order, named sNN;
//                 writes meta.json with a text snippet per section for later mapping.
// Output per candidate: <outRoot>/<id>/<section>.jpg (q60), full.png, meta.json
import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const [cfgPath, outRoot] = process.argv.slice(2);
if (!cfgPath || !outRoot) {
  console.error("usage: node capture-sections.mjs <config.json> <outRoot>");
  process.exit(1);
}
const candidates = JSON.parse(readFileSync(cfgPath, "utf8"));

const browser = await chromium.launch({ channel: "chrome" }).catch(() => chromium.launch());

for (const cand of candidates) {
  const outDir = join(outRoot, cand.id);
  mkdirSync(outDir, { recursive: true });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 0.5,
    reducedMotion: "reduce",
  });
  const page = await ctx.newPage();
  console.log(`[${cand.id}] ${cand.url}`);
  try {
    await page.goto(cand.url, { waitUntil: "networkidle", timeout: 60000 });
  } catch {
    await page.goto(cand.url, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(3000);
  }
  // Scroll through to fire once:true reveals, then settle at top.
  await page.evaluate(async () => {
    const step = window.innerHeight * 0.7;
    for (let y = 0; y <= document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 90));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(900);

  // Resolve section list.
  const sections = await page.evaluate((mode) => {
    const out = [];
    if (mode === "markers") {
      document.querySelectorAll("[data-section]").forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.height > 30) out.push({ name: el.getAttribute("data-section"), text: (el.textContent || "").trim().slice(0, 90) });
      });
    } else {
      const els = [
        ...document.querySelectorAll("header"),
        ...document.querySelectorAll("main > section, main > div > section, body section"),
        ...document.querySelectorAll("footer"),
      ];
      const seen = new Set();
      let i = 0;
      for (const el of els) {
        if (seen.has(el)) continue;
        seen.add(el);
        const r = el.getBoundingClientRect();
        if (r.height < 60) continue;
        i += 1;
        el.setAttribute("data-capture", `s${String(i).padStart(2, "0")}`);
        out.push({ name: `s${String(i).padStart(2, "0")}`, text: (el.textContent || "").trim().slice(0, 90) });
      }
    }
    return out;
  }, cand.mode);

  const meta = [];
  for (const s of sections) {
    const sel = cand.mode === "markers" ? `[data-section="${s.name}"]` : `[data-capture="${s.name}"]`;
    const loc = page.locator(sel).first();
    const file = join(outDir, `${s.name}.jpg`);
    try {
      await loc.scrollIntoViewIfNeeded({ timeout: 8000 }).catch(() => {});
      await page.waitForTimeout(250);
      await loc.screenshot({ path: file, type: "jpeg", quality: 60, timeout: 20000, animations: "disabled" });
      meta.push({ ...s, file: `${s.name}.jpg`, ok: true });
      console.log(`  ok ${s.name}`);
    } catch (e) {
      meta.push({ ...s, ok: false, err: String(e).slice(0, 120) });
      console.log(`  FAIL ${s.name}: ${String(e).slice(0, 80)}`);
    }
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: join(outDir, "full.png"), fullPage: true }).catch((e) => console.log("  full.png fail", String(e).slice(0, 80)));
  writeFileSync(join(outDir, "meta.json"), JSON.stringify(meta, null, 1));
  await ctx.close();
}
await browser.close();
console.log("done");
