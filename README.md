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
engine/floor/floor_check.py  # BLOCKING: contrast, orphans, layout, assets, console, targets (Fitts), type_size, measure; WARN: style, density, choices, drawing
engine/loop/run_state.py     # fail-loud state machine: pass | overridden(reason) | halted; + slate discipline (cheap slate -> direction -> built -> pick)
engine/loop/README.md        # the render → screenshot → check → fix loop
engine/preflight.sh          # tool preflight: checks (and with --install, installs) everything in TOOLS.md
TOOLS.md                     # every machine-level tool the engine needs: why, how installed, how checked
engine/schema/               # design-run.json schema
brand-kits/SCHEMA.md         # the brand-kit profile format (the only brand-specific input)
brand-kits/example-*/        # one example profile documenting the format
exemplars/INDEX.md           # curated references + distilled DNA (the floor rubric source)
agents/design-pod.md         # the build orchestrator sub-agent
skills/design-studio/        # the /design-studio on-ramp command
hooks/                       # the Stop-hook gate + wiring
engine/test/                 # run-selftests.sh — the regression suite (166 cases)
engine/floor/UX-LAWS.md      # UX laws: enforced vs judged vs rejected, with reasons
engine/floor/capture-refs.mjs    # headless capture of the exemplar corpus
engine/floor/capture-sections.mjs # section-level capture util
learnings.md                 # compounding memory of wins/kills
```

## Quickstart
```bash
# 0. tools (installs what is missing: Playwright + Chromium, GNU timeout, the target repo's package manager),
#    then the self-tests (everything below is covered by these)
bash engine/preflight.sh --install
bash engine/test/run-selftests.sh

# 1. start a run against a brand kit (halts if none)
python3 engine/loop/run_state.py init --file design-run.json \
  --project my-landing --surface web \
  --brand-kit brand-kits/example-rocketminds/brand-kit.json

# 2. record the vision references — the gate COUNTS these and refuses to pass below 3
python3 engine/loop/run_state.py references --file design-run.json \
  --add https://linear.app https://zed.dev https://ui.aceternity.com   # or existing screenshot paths; one per host

# 3. lock the human-approved brief, then confirm the build is unblocked
python3 engine/loop/run_state.py gate --file design-run.json --name brief --status pass
python3 engine/loop/run_state.py brief-ok --file design-run.json

# 4. cheapest choice first: a CHEAP, DIVERGENT slate (3-4 from different wells), the human's DIRECTION, then build ONLY that.
#    One-well or derivative slates and a fifth candidate are refused; a `built` candidate is refused before a direction exists.
python3 engine/loop/run_state.py candidate --file design-run.json --add A --source aceternity --archetype motion-led         --fidelity cheap
python3 engine/loop/run_state.py candidate --file design-run.json --add B --source magicui    --archetype type-led           --fidelity cheap
python3 engine/loop/run_state.py candidate --file design-run.json --add C --source mcp-image  --archetype generated-imagery  --fidelity cheap
python3 engine/loop/run_state.py direction --file design-run.json --candidate B    # or: direction --given "<the human's words>" when they named it up front

# 5. build ONLY B, then render + check MOBILE FIRST (render.mjs writes extract-<bp>.json + shot-<bp>.png)
node engine/floor/render.mjs http://localhost:3000 /tmp/floor
python3 engine/floor/floor_check.py /tmp/floor/extract-mobile.json  --breakpoint mobile  --require-assets --out /tmp/floor/mobile.json
python3 engine/floor/floor_check.py /tmp/floor/extract-desktop.json --breakpoint desktop --require-assets --out /tmp/floor/desktop.json

# 6. anti-hand-drawing scan, then record the gates it and the floor cover
python3 engine/floor/drawing_check.py --git-diff --run-file design-run.json
for g in references assets no_drawing contrast orphans layout console targets type_size measure responsive; do
  python3 engine/loop/run_state.py gate --file design-run.json --name $g --status pass
done

# 7. register what was built, then the human picks; `pick` is the ONLY way to resolve human_pick and refuses anything unregistered
python3 engine/loop/run_state.py candidate --file design-run.json --add B1 --source magicui --archetype type-led --fidelity built
python3 engine/loop/run_state.py pick --file design-run.json --candidate B1

# 8. ship-check re-runs the drawing scan itself, so a canvas blocks BEFORE you deploy
python3 engine/loop/run_state.py ship-check --file design-run.json
python3 engine/loop/run_state.py done --file design-run.json
```

## Status
Phase 1 (lean core): deterministic floor + fail-loud state machine + design-pod + /design-studio
command + Stop-hook gate. Self-tests: `bash engine/test/run-selftests.sh` (166 cases; fixtures in `samples/`). Every 2026-09-08 audit finding has a named regression case, and the repaired cases are MUTATION-CHECKED: reverting a fix must turn its test red. Since shipped: image-gen (`mcp-image`), 21st.dev
components, the provenance-based anti-drawing scanner (`engine/floor/drawing_check.py`), and a
counted references gate. Deferred: divergent-direction automation, multi-surface expansion, Vercel
audit skills. Rejected: Lazyweb on price (the screen library is $39/mo; Mobbin covers the category for less),
the Figma MCP on fit (it only pays off if work originates in Figma; its "free during beta" applies
to write-to-canvas, not the server). kibo-ui was wired 2026-09-08 and dropped the same day: its
MCP endpoint returns HTTP 500 on initialize.
