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
