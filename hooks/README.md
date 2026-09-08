# Enforcement hook

The hook is what makes the discipline FIRE without re-prompting. It is deterministic; the
harness runs it regardless of model intent. It enforces the floor + forces the loop; it does
not judge taste.

## Primary: Stop hook (recommended)
`design-gate.sh` runs at turn-end. If a `design-run.json` exists in the project and its
floor has not passed, it blocks the finish and tells the model to keep looping (or log an
override). If no `design-run.json` exists, it does nothing, so it is safe to enable globally.

Wire into `~/.claude/settings.json` (do this via the `update-config` skill, not by hand):

```json
{
  "env": { "DESIGN_STUDIO_HOME": "/Users/garyfilipp/Documents/Claude/ui-ux-design-studio" },
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "bash \"$DESIGN_STUDIO_HOME/hooks/design-gate.sh\"" } ] }
    ]
  }
}
```

## NOT IMPLEMENTED (idea only): a PreToolUse hard gate
A stricter variant blocks Write/Edit to web design-output files (`.tsx/.jsx/.html/.css/.astro`)
while a run is active and unpassed. Stricter, but blunter (catches unrelated edits to those
file types), so start with the Stop hook and add this only if builds still slip through.

## Why a Stop hook, not "force skill invocation"
Forcing a skill to run cannot force quality (a green check on an ugly page). Gating turn-end on
the deterministic floor + a rendered screenshot is enforceable and meaningful: the build cannot
be called done until the floor passes or you consciously override.
