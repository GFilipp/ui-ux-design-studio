# UI/UX Design Studio

A **brand-agnostic** engine that makes an AI coding agent produce visual UI to an objective
quality floor, with a human owning the taste call. Swap the brand kit, get a different brand
from the same pipeline. No brand is hardcoded.

## The idea
The machine owns the **floor** (clean, on-brand, high-contrast, no orphans, real components,
responsive). The human owns the **ceiling** (which direction is actually great). Enforcement is
deterministic and fail-loud: missing inputs or failed gates HALT and ask; the only way past is a
logged override with a reason. Nothing ships silently degraded.

## Why it exists
Design skills exist but get skipped under build pressure, and the agent designs blind (no
render → see → fix loop, no asset generation). The result is text-heavy, low-contrast, asset-less
output that takes many manual correction rounds. This engine fixes the firing problem (a hook),
closes the loop (render/screenshot/check/fix), and keeps taste with the human.

## Layout
```
engine/floor/extract.js      # run in the page: dump text/color/bg/size/rect/lines, images, overflow
engine/floor/floor_check.py  # deterministic gates: contrast (WCAG AA), orphans, layout, assets
engine/loop/run_state.py     # fail-loud state machine: pass | overridden(reason) | halted
engine/loop/README.md        # the render → screenshot → check → fix loop
engine/schema/               # design-run.json schema
brand-kits/SCHEMA.md         # the brand-kit profile format (the only brand-specific input)
brand-kits/example-*/        # one example profile documenting the format
exemplars/INDEX.md           # curated references + distilled DNA (the floor rubric source)
agents/design-pod.md         # the build orchestrator sub-agent
skills/design-studio/        # the /design-studio on-ramp command
hooks/                       # the Stop-hook gate + wiring
learnings.md                 # compounding memory of wins/kills
```

## Quickstart
```bash
# 1. start a run against a brand kit (halts if none)
python3 engine/loop/run_state.py init --file design-run.json \
  --project my-landing --surface web \
  --brand-kit brand-kits/example-rocketminds/brand-kit.json

# 2. build + render a candidate, then extract + check (desktop and mobile)
#    (run engine/floor/extract.js in the page, save JSON, then:)
python3 engine/floor/floor_check.py page.desktop.extract.json --breakpoint desktop --out floor.desktop.json

# 3. record gates, present candidates for the human pick, then gate the finish
python3 engine/loop/run_state.py ship-check --file design-run.json
```

## Status
Phase 1 (lean core): deterministic floor + fail-loud state machine + design-pod + /design-studio
command + Stop-hook gate. Self-tests in `samples/`. Deferred: image-gen MCP, 21st.dev components,
divergent-direction automation, multi-surface expansion, Vercel audit skills.
