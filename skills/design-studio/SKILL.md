---
name: design-studio
description: Build a beautiful, on-brand marketing asset (landing page, site, hero, social ad, one-pager, deck) for ANY brand through one enforced flow. Triggers on "build/design a landing page/site/hero/ad/social/one-pager/deck", "marketing asset", "design studio", "make this beautiful / on-brand". Forces a human-approved brief before any build, builds with real component libraries (never hand-coded), never fabricates content, and ends on a human pick. Not for copy-only work (use brand-voice) or strategy.
---

# design-studio

The ONE path to a beautiful marketing asset. Not bypassable: no hand-cranked mockups, no fabricated content, no leading with features. This is what makes the output good and repeatable instead of a 15-round hand-cranking session.

Engine root: `/Users/garyfilipp/Documents/Claude/ui-ux-design-studio`
**FIRST read `RULES.md` at the engine root and obey it. It overrides convenience.**

## How to run
Hand off to the **design-pod** subagent (`agents/design-pod.md` at the engine root) and run its five stages in order:

0. **Ground** — preflight (`engine/preflight.sh --install --target <repo>`; a `FAIL` halts, see `TOOLS.md`), then load the brand kit + real sources. No kit or no real sources -> halt and ask. No fabrication.
1. **Brief lock** — produce the one-page brief (`engine/brief/brief-template.md`): value in CUSTOMER-OUTCOME terms (profit, growth, time, money), the story spine, the visual direction, the DON'TS. Human approves ONCE. No build until `run_state.py brief-ok` exits 0.
2. **Direction slate, then build ONLY the pick** — cheapest choice first: the scout returns a SPREAD of 3 to 4 cheap candidates from different libraries and archetypes (`run_state.py candidate --add ... --fidelity cheap`; one-well or derivative slates and a fifth candidate are refused), the human picks a direction from ONE contact sheet (`direction --candidate`), and only that direction is built, with real components from whatever component-library MCPs are enabled this session (enumerated live, never a fixed list), in the asset's real repo with real motion. Nothing nobody chose gets built; a dead direction is dropped in one line, not repaired. Every visual comes from a real source in priority order: components > brand asset > `mcp-image` generated imagery > clean type > real icons. Never hand-drawn (`<svg>`/`<canvas>`/CSS-art/fake charts); `drawing_check.py` + the Stop hook block it, canvas non-overridably.
3. **Floor + brief-conformance + pick** — mobile-first floor (`engine/floor/render.mjs` then `engine/floor/floor_check.py`, 390 then 1440); confirm the brief is met and no DON'TS broken; present the BUILT candidates (registered `--fidelity built`, at most 4); the human picks one (`pick`, which refuses anything unregistered).
4. **Ship** — `run_state.py ship-check`, integrate, deploy by git push, `run_state.py done`.

## Inputs (halt and ask if missing)
brand kit (path); the asset + audience; real source material.

## Hard rules (RULES.md, non-negotiable)
No going rogue; brief before pixels; real components not hand-coded; never hand-drawn visuals (source from components / mcp-image / assets / type); no fabrication; lead with value not features; tell a story; never neg the customer; em dashes rarely; no walls of text; the human owns the taste pick; cheapest choice first and build only the pick; divergent slates, never derivatives from one well.
