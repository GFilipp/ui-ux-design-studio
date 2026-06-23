---
name: design-studio
description: Brand-agnostic UI/UX build command. Use to build a website, app UI screen, landing page, or marketing asset to a quality floor with a human taste pick. Loads a swappable brand kit, runs the render → screenshot → deterministic-floor → fix loop under a fail-loud guardrail contract, and presents divergent candidates to choose from. Triggers on "build a section/page/landing/screen", "design studio", "design this to the floor". Not for copy-only work (use brand-voice) or strategy.
---

# design-studio

The manual on-ramp to the design pod. One invocation runs the whole pipeline so you stop re-prompting each step.

## Inputs (the command will HALT and ask for any that is missing — never defaulted)
- **brand kit** — path to a brand-kit profile (see `brand-kits/SCHEMA.md`). No kit → halt.
- **surface** — web | app | marketing-asset | deck.
- **references** — ≥3 exemplar screenshots. Fewer → halt.
- **brief** — what to build (section/page/asset + intent).

## What it does
1. `engine/loop/run_state.py init --file design-run.json --project <name> --surface <surface> --brand-kit <path>`.
2. Hands off to the **design-pod** sub-agent, which builds 2-3 divergent directions within the brand tokens, runs the floor loop (desktop + mobile) until `engine/floor/floor_check.py` passes, and records each gate.
3. Presents the floor-passing candidates as screenshots; **you pick** (the machine never auto-ships taste).
4. `run_state.py ship-check` gates the finish and surfaces any logged overrides.

## Defaults / rules
- **Clean type first.** Imagery is generated only when it beats type-only and matches the kit. No slop.
- **Brand-agnostic.** Swap the kit, get a different brand. RocketMinds is just one profile.
- **Models** auto-discovered per task; never hardcoded.
- **Fail loud.** Any missing input or failed gate halts and asks; the only way past is a logged override with a reason.

## Compose, don't rebuild
Uses installed skills: `web-artifacts-builder` / `canvas-design` / `rocketminds-slide-generator` (build), `design:design-critique` + `design:accessibility-review` (floor corroboration), `rocketminds-brand-voice` or the kit's voice skill (copy). Hosted on the `a-biz-d-delivery` / off-ramp spine.
