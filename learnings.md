# Learnings (compounding memory)

Only human-confirmed wins and explicit kills go here, so the library stays clean (a mediocre
"win" reused as a template propagates mediocrity). One line per entry.

Format: `YYYY-MM-DD | brand | surface | WIN/KILL | what + why`

---
<!-- entries below -->
2026-06-23 | RocketMinds (example) | web | WIN | Product-as-hero from styled divs (a mock "today's shortlist" panel), zero images. Satisfies clean-type-first and passes the assets gate with no generated imagery; balances the hero so there is no dead zone.
2026-06-23 | RocketMinds (example) | web | WIN | Two-line headline: force the second clause onto its own line (accent span `display:block`) so the last line keeps >=2 words. The floor caught "call." orphaned on v1; the fix passed. The loop works: flag -> fix -> pass.
2026-06-23 | Aperture + RocketMinds (examples) | web | WIN | Brand-agnostic proven: the same hero section under two kits (RM dark/serif/orange vs Aperture light/sans/blue) renders as two different on-brand designs, both pass the floor, zero hardcoded brand.
2026-06-23 | engine | web | KILL | Browser-bridge window resize does NOT force a true mobile viewport (innerWidth stayed 1512 at a 390 request). Mobile-breakpoint floor checks need headless device emulation, not window resize.
2026-06-23 | engine | web | WIN | Mobile-first headless floor shipped: engine/floor/render.mjs (Playwright, bundled Chromium, explicit 390x844 + desktop 1440) runs extract.js via page.evaluate (kills the output-truncation limit) and writes screenshot + extract JSON per breakpoint. Replaces window-resize.
2026-06-23 | RocketMinds + Aperture (examples) | web | WIN | Mobile-first loop proven end-to-end: good.html FAILED the mobile gate (non-responsive 2-col grid → layout overflow + cramped panel), added a stack media query, re-ran → both kits pass mobile AND desktop. Flag → fix → pass.
2026-06-23 | engine | web | FIX | Orphan gate over-flagged body-paragraph rag on mobile (11 false orphans). Now flags only heading-like text (large/bold display OR <=6 words); long paragraphs exempt. The mobile gate caught a bug in the gate itself.
2026-06-23 | engine | web | WIN | Wired 4 FREE component MCPs at user scope (Claude Code), all health-check ✓: shadcn (`npx shadcn@latest mcp`), aceternity (`npx aceternityui-mcp`), flowbite (`npx flowbite-mcp`), 21st magic (`npx @21st-dev/magic@latest`, API key in ~/.claude.json — gitignored). Gotcha: `claude mcp add` variadic `-e` eats the next token; put the server NAME before `-e`. Built the origin-agnostic component-scout subagent (agents/component-scout.md) + the library-scan playbook (engine/scan/library-scan.md). Paid (Mobbin/Refero) remain opt-in.
2026-07-03 | engine | wiring | FIX | Trailing carriage return (\r) in a credentials file silently breaks an MCP env key. `$(cat keyfile)` strips trailing \n but NOT \r, so the stored GEMINI_API_KEY was 54 chars (53-char key + \r) and would fail auth on the first render. Fix: wire with `tr -d '\r\n' < keyfile` AND clean the source file; always sanity-check a pasted key by comparing stored length vs stripped length. Separately: wired free component set expanded to six (shadcn / aceternity / flowbite / magic(21st) / magicui / heroui) + mcp-image (Nano Banana) for image gen, all user scope. De-hardcoded the library name-lists in RULES/design-pod/SKILL/component-scout so they enumerate enabled MCPs live (per no-hardcoded-rotting-values); the scout was already dynamic, the lists were stale illustration. Honest nuance: flowbite's MCP is figma-to-code + theme-gen, not component search, so it is not a browsable component source like the other five.
2026-06-24 | engine | audit | FIX | Post-rebuild fresh-eyes audit (Fable): closed 3 real defects: (1) "no console errors" was promised but unchecked; render.mjs now captures pageerror + console.error per breakpoint and floor_check blocks on them (older extracts without the key report "not-captured"); (2) brief-ok now honors an overridden brief gate (contract parity: pass OR loud logged override), previously override was meaningless; (3) em-dash rule corrected per Gary: RARE is fine, pileup is the AI tell; RULES reworded + warn-only style note at 3+ em dashes (never blocks). Plus: hook message names the three exits (brief-lock / override / cancel), SCHEMA documents optional kit fields (status, motifs, border/faint/accent2, type.mono), PLAN.md replaced with the rebuild plan, render.mjs falls back networkidle -> domcontentloaded on live-site timeout, pod ensures design-run.json is gitignored in TARGET repos.
2026-06-24 | engine | marketing-assets | FAIL then REBUILD | First live test (Tegy rebuild) failed entirely. Five root causes, each now structurally fixed: (1) the tool was a repo of scripts, never an installed skill, so I went rogue and hand-cranked HTML mockups (v1-v4); FIX: install as a real /design-studio skill, one path only. (2) no brief/value/story front-end, so endless correction; FIX: mandatory `brief` gate (run_state brief-ok) + engine/brief/brief-template.md, human approves once before any build. (3) hand-coded HTML cannot use the React component libraries, so never beautiful; FIX: RULES.md requires building with real components (Aceternity/21st/shadcn/Flowbite), never hand-coded. (4) fabricated product output presented as real; FIX: RULES.md forbids fabrication, real sources only. (5) constant babysitting; FIX: front-load to one brief approval + one pick. All hard rules in RULES.md, loaded by design-pod + skill. Tegy was the test case, not the subject; the tool is brand- and asset-agnostic.

## 2026-07-07 — Stop-hook deadlock at the human-pick gate
The design-gate Stop hook blocked EVERY turn-end while `human_pick` was the only
halted gate. But RULES 12 + design-pod forbid the model from passing or
overriding that gate — so a run legitimately parked at "candidates presented,
awaiting the human's pick" deadlocked the loop (hook demands progress the rules
forbid). Fix: design-gate.sh now allows the stop when brief has passed and the
ONLY unresolved gate is human_pick, with a stderr note. ship-check is untouched,
so Stage 4 still cannot ship without the pick. Lesson: state machines with
human-only gates need an explicit awaiting-human resting state, or their
enforcement hooks turn into infinite nags.

## 2026-07-07 — Decoration is not design (RM homepage redo)
First pass layered registry animations (border beams, dot patterns, hover
dimming, scroll timeline) onto unchanged layouts. Human verdict: gimmicky slop
that distracts a professional audience. Root cause: skipped Stage-0 grounding in
exemplars/INDEX.md and the DNA rubric ("zero decorative noise"), then let the
component-scout drive the design. The corpus already encoded the answer:
Tesla (type+space only), Exat (motion reveals one idea then pauses; my infinite
loops violated it), Tresmares (capital-firm premium-minimal = composition).
Redo that passed: stepped display hero, numbered index / ledger rows, unboxed
blockquotes, once-only reveals, fast hovers. Rule for the engine: exemplars and
rubric BEFORE the scout; the scout serves the composition, never replaces it.
