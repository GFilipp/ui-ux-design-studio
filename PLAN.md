# Plan: a repeatable tool that forces beautiful marketing assets

Status: rebuilt 2026-06-24 after the first live test failed; post-rebuild audit fixes landed same day (console gate, brief-ok override parity, hook message, schema, doc sync). RULES.md is the hard-rules companion to this plan.

## Context: what this is, and why we rebuilt

Goal: a scalable, repeatable TOOL (one installed skill plus enforcement) that forces Claude to produce beautiful, on-brand marketing assets (landing pages, sites, social, ads, one-pagers, decks) for ANY brand. A system used over and over, not a one-off page.

The first real test failed. The failure is the spec. What broke, and what the tool therefore FORCES:

1. Bypassable, so the agent went rogue. The "engine" was a repo of scripts, never an installed skill, so it hand-cranked one-off HTML mockups instead of running the flow. FIX: one installed command is the only path, and a hook blocks any design "done" that did not run through it.
2. No brief front-end, so endless correction. It jumped straight to building with only an objective floor. Nothing locked the value prop, the story, or the hard rules. FIX: the tool forces a one-page brief, approved once, before any pixels.
3. Hand-coded HTML, so never beautiful. It never used the wired component libraries (they are React; standalone HTML cannot use them). FIX: build with real components, never hand-coded.
4. Fabricated content. It staged invented output and metrics as if real. FIX: hard no-fabrication rule; real source material only.
5. Babysitting. Every step needed correcting. FIX: front-load everything into one brief approval plus one pick from genuinely good candidates.

## The tool (brand- and asset-agnostic, non-bypassable)

One installed skill (`/design-studio`) that, for any marketing asset, runs five stages:

- Stage 0, Ground. Load real sources only: brand kit, positioning, ICP, messaging, existing assets, real transcripts. Never invent metrics, testimonials, or product output. Ensure `design-run.json` is gitignored in the target repo before init.
- Stage 1, Brief lock (human approves once). One page: the asset and audience; the value prop in CUSTOMER-OUTCOME terms (profit, growth, time, money), never features or tech; the story spine; the visual direction (references plus brand DNA plus the bar); the hard DON'TS. No build until `run_state.py brief-ok` exits 0 (pass, or a loud logged override).
- Stage 2, Build with real components. The component-scout pulls the best real components across enabled libraries (Aceternity, 21st, shadcn, Flowbite) and composes in the asset's real build with real motion. Never hand-coded HTML mockups.
- Stage 3, Floor plus brief-conformance plus pick. Objective floor mobile-first (contrast, orphans, overflow, console errors) PLUS a check that the output hits the brief and breaks no DON'TS. Present genuinely good candidates; human makes one taste pick.
- Stage 4, Ship. `ship-check`, integrate, deploy by git push to the connected host, `done` to finalize (removes the run file). `cancel` aborts at any point.

Repeatable: same flow every time, any brand kit, any asset type. The human approves a brief and picks a winner. The human never line-edits.

## Architecture map (where things live)

- `RULES.md`: the hard rules every stage loads.
- `skills/design-studio/SKILL.md`: the installed command (source of truth; installed copy at `~/.claude/skills/design-studio/`).
- `agents/design-pod.md` + `agents/component-scout.md`: the orchestrator and the origin-agnostic component selector (installed copies at `~/.claude/agents/`).
- `engine/brief/brief-template.md`: the Stage 1 artifact.
- `engine/loop/run_state.py`: fail-loud state machine (gates incl. `brief`; `brief-ok`, `ship-check`, `done`, `cancel`).
- `engine/floor/render.mjs` + `extract.js` + `floor_check.py`: headless mobile-first render (390 then 1440), deterministic checks (contrast incl. alpha compositing, heading orphans, layout overflow, console errors; warn-only em-dash pileup note).
- `hooks/design-gate.sh`: global Stop hook; no-ops without a `design-run.json`, otherwise blocks turn-end until the floor passes, an override is logged, or the run is cancelled.
- `brand-kits/`: the profile format + example kits (real kits stay external).
- `exemplars/`: the taste corpus (captures local-only).
- `engine/scan/library-scan.md`: quarterly library-discovery scan (scheduled task `design-library-scan`).

## Verification (does it force beauty, repeatably, without babysitting)

- Run the tool cold on a fresh asset for an arbitrary brand kit. It must: refuse to build until the brief is locked; build with real components, not hand-coded; contain zero fabricated content; pass the floor mobile-first with no console errors; present candidates for one pick. Count line-edits required (target: zero).
- Repeatability: run it on a second brand kit and a second asset type. Same flow, on-brand output, no hardcoded brand.
- Anti-rogue: attempt a hand-coded design build outside the tool. The hook blocks it.

## Risks

- Taste ceiling: beautiful is subjective, so the human owns the final pick. The tool's job is to make every candidate on-brief, real-component, fabrication-free, and floor-clean, so the pick is between good options, not a rescue.
- Over-engineering: hold to the five stages. Do not re-bloat.
