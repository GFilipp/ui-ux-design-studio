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

0. **Ground** — load the brand kit + real sources. No kit or no real sources -> halt and ask. No fabrication.
1. **Brief lock** — produce the one-page brief (`engine/brief/brief-template.md`): value in CUSTOMER-OUTCOME terms (profit, growth, time, money), the story spine, the visual direction, the DON'TS. Human approves ONCE. No build until `run_state.py brief-ok` exits 0.
2. **Build with real components** — the component-scout pulls real components (Aceternity / 21st / shadcn / Flowbite); build in the asset's real repo with real motion. Never hand-coded HTML, never amateur graphics.
3. **Floor + brief-conformance + pick** — mobile-first floor (`engine/floor/render.mjs` then `engine/floor/floor_check.py`, 390 then 1440); confirm the brief is met and no DON'TS broken; present candidates; the human picks one.
4. **Ship** — `run_state.py ship-check`, integrate, deploy by git push, `run_state.py done`.

## Inputs (halt and ask if missing)
brand kit (path); the asset + audience; real source material.

## Hard rules (RULES.md, non-negotiable)
No going rogue; brief before pixels; real components not hand-coded; no fabrication; lead with value not features; tell a story; never neg the customer; em dashes rarely; no walls of text; the human owns the taste pick.
