# The floor loop

Render → screenshot → extract → floor-check → fix → repeat until the floor passes.
The machine owns this floor; the human owns the taste call (pick from candidates).

## One iteration
1. **Render** the candidate on a dev server (web-artifacts-builder output, or a static sample).
2. **Screenshot** desktop (1440w) and mobile (390w) via Chrome MCP (`computer` action `screenshot`) or `preview_screenshot`.
3. **Extract** deterministic facts: run `engine/floor/extract.js` in the page
   (Chrome MCP `execute_javascript`, or `preview_eval`). Save the returned JSON.
4. **Check**: `python3 engine/floor/floor_check.py <extract.json> --breakpoint desktop [--require-assets] --out floor.desktop.json`
   Repeat for mobile. Exit code 2 = floor failed.
5. **Fix** the flagged issues (contrast, orphan, layout, broken assets) and loop. Cap at K=3
   auto-fix rounds; if still failing, halt and ask (never ship a degraded default).
6. **Record** each gate with `engine/loop/run_state.py gate ...`. Contrast `indeterminate`
   (text over a background image) is not auto-pass; surface it for explicit review.

## Gates → state
`run_state.py` enforces the contract: a gate is `pass`, or `overridden(reason)`, or it stays
`halted` and blocks ship. `ship-check` prints the summary and lists every override.

## Brand-agnostic
`extract.js` and `floor_check.py` know nothing about any brand. The brand kit only informs the
builder (constraints) and the human's taste judgment, not the objective floor.

## Known limitation
When `extract.js` is run through an MCP `execute_javascript` bridge, the returned string can be
truncated by the tool's output cap on large pages. Mitigations: keep `text` slices short (done),
and for big pages run extract per-section, or write the JSON to a local writable sink rather than
returning it inline. Validate the captured JSON parses before running `floor_check.py`.

A second limitation: resizing the browser window via the MCP bridge does not reliably force a
true mobile viewport (desktop Chrome clamps the minimum width; `innerWidth` stayed 1512 at a 390
request). The mobile-breakpoint floor check therefore needs **headless device emulation**
(Playwright/Puppeteer or CDP `Emulation.setDeviceMetricsOverride` at 390x844), not window resize.
