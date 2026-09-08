# RULES (hard, always loaded)

These are the non-negotiable rules for the design tool. They are the distilled failures from the first real test. Every stage loads this file. Breaking any of these is a stop, not a style choice.

## Process
1. **One path only. Never go rogue.** Build only through this tool: ground, brief-lock, scout, build-with-components, floor, pick. Never hand-crank one-off mockups outside the flow.
2. **Brief before pixels.** No build starts until the human approves the one-page brief (Stage 1). If there is no locked brief, stop and produce the brief first.
3. **Front-load, do not babysit.** The human approves a brief once and picks a winner once. Do not seek line-by-line correction. Get the brief right, then execute to it.

## Build
4. **Real components, never hand-drawn.** Every visual comes from a real source, never Claude's own hand. Source priority: (1) real components from whatever component-library MCPs are enabled this session (enumerated live by the scout, never a hardcoded list), with real motion; (2) a real brand asset (the kit's logo, provided imagery); (3) generated imagery via the `mcp-image` MCP; (4) clean type + brand tokens + layout; (5) small icons from a real icon set. BANNED, this is "drawing": hand-authored inline `<svg>` illustrations, `<canvas>` 2D drawing, CSS-art pictures, ASCII/emoji art, and hand-built charts/dashboards/fake data-graphics. If no component fits, use `mcp-image` or clean type; hand-code is for trivial layout scaffolding only, never a graphic. Never ship a hand-coded standalone HTML mockup.
   - ENFORCEMENT + SCOPE: `engine/floor/drawing_check.py` blocks raw svg/canvas drawing in Claude-authored files (canvas is non-overridable; illustration-scale svg is overridable with a logged reason); vendored library files and brand assets are exempt by provenance. It CANNOT see styled-div "fake charts" (no svg to detect) or rastered fakes; those stay the human's Stage-3 brief-conformance call. Do not hand-build a chart or dashboard and read the scanner's silence as a pass.
5. **Visual-first.** The visual carries the asset. Minimal words. No walls of text. PARTLY ENFORCED now: `floor_check.py` blocks body type under 12px and a measure over ~130 characters per line, and warns on small type, wide measure, and any single text block over 120 words. The judgment half ("does the visual carry it?") is still yours at the pick.
   - **Respect the reader's hit area and choice load.** Tap targets are at least 44px on touch breakpoints (Fitts's law; Apple HIG 44pt, Material 48dp, WCAG 2.5.5) — BLOCKING. Choice sets of 10 or more siblings and primary nav over 7 links are surfaced as warnings (Hick's and Miller's laws): sometimes a 12-logo wall is right, so the machine flags the load and you decide.

## Content
6. **No fabrication, ever.** Never invent metrics, testimonials, customer names, or product output. Use real source material only. If real proof does not exist, stay at value or positioning level. Do not stage fake "output" as if real.
7. **Lead with VALUE, not features or tech.** Sell the customer outcome: profit, growth, time saved, money saved. The mechanism (how it works, the architecture, the "orchestration") is supporting detail, never the hero.
8. **Tell a story.** Problem to outcome. Never list features or stuff tiles onto a page.
9. **Never neg the customer.** No "you can't afford it," no poverty framing. Frame the customer as capable and ambitious; the asset is their edge.

## Style
10. **Em dashes rarely, never as the default connector.** An occasional em dash is fine; a pileup is the AI tell. Prefer periods, commas, semicolons, colons.
11. **Honest, plain, no hype.** No buzzwords, no fake urgency, no unsupported claims.

## Quality
12. **The taste pick is the human's.** `human_pick` cannot be set with `gate` and cannot be overridden; it resolves only via `run_state.py pick --candidate <id>`, which records WHICH candidate was chosen. Honest limit: nothing in a CLI the model drives can PROVE a human chose. The mechanism makes usurping the pick deliberate and visible in the run file, not impossible. **Floor is the floor, not the bar.** The objective floor (mobile-first contrast, orphans, overflow) is a minimum. Passing it does not mean beautiful. The brief and the human pick set the bar.
