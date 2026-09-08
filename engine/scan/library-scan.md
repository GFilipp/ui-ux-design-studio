# Library-discovery scan

Runs **quarterly** (cron, via the `schedule` skill) AND **on demand at the start of any new major build**.
Keeps the component / reference-library catalog fresh without hardcoding it (per no-hardcoded-rotting-values).

## What it does (research-only; NEVER auto-installs)
1. Read the currently-wired MCP servers: `claude mcp list` (+ `~/.claude.json` mcpServers).
2. Research the current landscape of design libraries that expose an MCP connector (web search +
   the tools' docs). Categories: component-code libraries, reference/inspiration libraries,
   design-tool bridges (Figma / Storybook), image generation.
3. Diff against what's wired and produce, sorted most → least relevant:
   - **New FREE** (zero-setup or free key) not yet wired → recommend wiring; include the exact
     `claude mcp add -s user …` command.
   - **New or known PAID** not wired → list with price + what it adds; flag for an explicit user decision.
   - **Wired-but-now-broken / deprecated** → flag for removal.
4. Output a short report to `engine/scan/reports/report-YYYY-MM-DD.md` (committed; it is our own
   research, no third-party content). Do NOT install anything. Do NOT enable paid without the user.
5. VERIFY before recommending. Scans repeat vendor marketing. Check each load-bearing claim against a
   primary page and label anything unchecked "unverified". Two claims that failed verification on
   2026-09-07: "21st free tier gives ~5 AI generations/month" (it gives ZERO; the 5 is a paid-plan
   trial of a different feature) and "Lazyweb is free" (the screen library is $39/mo; the free token
   buys partial reports). Price and free-tier claims are the ones that flip decisions, so check those first.

## Propagation checklist (the scan does not update code by itself)
When a scan CHANGES the wired library set, hand-update all four or the change silently half-lands:
1. `engine/floor/drawing_check.py` -> `VENDORED_SUBPATHS`, but ONLY if the library vendors into its
   own directory. Libraries that install through the shadcn registry land in `aliases.ui`
   (already exempt), and npm-imported libraries live in `node_modules` (already excluded).
   Verify where it actually writes (`files[].path` in its registry JSON); never add a guessed dir.
2. `agents/component-scout.md` -> the illustrative list and any per-library tool caveat.
3. Memory `ui-ux-design-studio.md` -> the wired set, plus WHY anything was rejected so a later scan
   does not re-recommend it.
4. `learnings.md` -> one dated entry.

## Cadence + delivery
- **Quarterly cron** (`schedule` skill) → emits the report (email / task notification) for the user.
- **New major build** → invoke this scan inline first; surface free adds + ask before any paid.

## Guardrail
Free, zero-setup libraries may be recommended for immediate wiring. Paid libraries are ALWAYS an
explicit user decision (ask, never silently enable) — matches the locked free-default / paid-optional rule.
