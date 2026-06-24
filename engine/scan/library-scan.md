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
4. Output a short report. Do NOT install anything. Do NOT enable paid without the user.

## Cadence + delivery
- **Quarterly cron** (`schedule` skill) → emits the report (email / task notification) for the user.
- **New major build** → invoke this scan inline first; surface free adds + ask before any paid.

## Guardrail
Free, zero-setup libraries may be recommended for immediate wiring. Paid libraries are ALWAYS an
explicit user decision (ask, never silently enable) — matches the locked free-default / paid-optional rule.
