# Creative brief: <asset> for <brand>

Fill this from REAL sources only (Stage 0). No fabrication. The human approves this ONCE before any build. This is the gate: no pixels until it is locked.

## 1. Asset + audience
- Asset: <landing page / hero / social ad / one-pager / deck / email>
- Audience (the protagonist): <who they are and their situation, in their words>

## 2. Value prop (CUSTOMER OUTCOME, never features or tech)
- The outcome they get: <profit / growth / time saved / money saved>. One sentence.
- The stakes / why now: <one line>
- NOTE: the mechanism (how it works, the architecture) is supporting detail, never the headline.

## 3. Story spine (problem to outcome)
- <2 to 4 beats forming a narrative: the situation, the turn, the outcome>. Not a feature list.

## 4. Visual direction
- References (the bar): <3 or more exemplars, one line each on why. Record each with `run_state.py references --file design-run.json --add <path-or-url>`. The gate COUNTS these and refuses to pass below 3; each must resolve (an existing screenshot file, or an http(s) URL with a real host), so a bare name does not count.>
- Brand DNA (from the kit): <tokens, type, motion appetite, do and do-not>
- The bar in one phrase: <e.g. concept-car, product-as-hero, editorial-minimal>
- Visual sourcing plan (every planned visual maps to a real source; NO hand-drawing):
    - <visual / section> -> <library:component | mcp-image | asset:path | type-only>
    - <one line per hero and section visual; if a source is unknown, resolve it via the component-scout before building>

## 5. Hard DON'TS (from RULES.md, confirm each)
- [ ] No negging the customer (no "you can't afford")
- [ ] Em dashes rarely, never the default connector
- [ ] No feature-tile lists
- [ ] No fabricated content, metrics, or output
- [ ] No walls of text
- [ ] No hand-drawn svg / canvas / CSS-art / ASCII-emoji art; visuals come from components, mcp-image, assets, or type
- [ ] No hand-built charts / dashboards / fake data-graphics (real chart component or real screenshot only)

## 6. Sources used (real only)
- <files / repos / transcripts cited>

## Approval
Locked by <human> on <date>. On approval, run:
`run_state.py gate --file design-run.json --name brief --status pass --detail <path to this brief>`
