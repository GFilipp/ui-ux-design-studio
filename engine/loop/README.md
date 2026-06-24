# The floor loop

Render → screenshot → extract → floor-check → fix → repeat until the floor passes.
The machine owns this floor; the human owns the taste call (pick from candidates).

## One iteration
1. **Render + extract** in one headless pass, mobile-first:
   `node engine/floor/render.mjs <url-or-file> [outDir]`
   Emulates a real mobile device (390x844, DPR 3 — the PRIMARY gate) and desktop (1440), runs
   `engine/floor/extract.js` via `page.evaluate` (writes JSON to disk — no output-cap truncation),
   and saves `shot-<bp>.png` + `extract-<bp>.json`. Bundled Chromium for faithful emulation
   (falls back to system Chrome). `file://` is auto-added for local paths.
2. **Check, MOBILE FIRST**:
   `python3 engine/floor/floor_check.py <outDir>/extract-mobile.json --breakpoint mobile [--require-assets]`
   then the same for `extract-desktop.json`. Exit 2 = floor failed; a mobile failure fails the build.
3. **Fix** the flagged issues (contrast, orphan, layout, broken assets) and loop. Cap at K=3
   auto-fix rounds; if still failing, halt and ask (never ship a degraded default).
4. **Record** each gate with `engine/loop/run_state.py gate ...`. Contrast `indeterminate`
   (text over a background image) is not auto-pass; surface it for explicit review.
   (For ad-hoc visual review you can still screenshot via Chrome MCP; the *gate* uses render.mjs.)

## Gates → state
`run_state.py` enforces the contract: a gate is `pass`, or `overridden(reason)`, or it stays
`halted` and blocks ship. `ship-check` prints the summary and lists every override.

## Brand-agnostic
`extract.js` and `floor_check.py` know nothing about any brand. The brand kit only informs the
builder (constraints) and the human's taste judgment, not the objective floor.

## Resolved limitations
- **Output truncation:** `render.mjs` runs `extract.js` via `page.evaluate` and writes the JSON to
  disk, so the MCP output cap no longer truncates large pages.
- **Mobile viewport:** `render.mjs` uses bundled-Chromium device emulation at an explicit 390x844,
  so the mobile gate is a true mobile viewport. (Window-resize via the browser bridge could not
  force this — it clamped to ~443/1512; that approach is retired.)
