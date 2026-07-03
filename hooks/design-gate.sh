#!/usr/bin/env bash
# design-gate.sh — Stop hook. Refuses to let a turn end "done" while a design run is
# active and its floor has not passed. SAFE BY DESIGN: if no ./design-run.json exists in
# the project, it does nothing, so it never interferes with non-design work.
#
# Wire as a Stop hook in ~/.claude/settings.json (see hooks/README.md). Set
# DESIGN_STUDIO_HOME to this repo so it can find run_state.py.
#
# Exit 0 = allow stop. Exit 2 = block stop, stderr is shown to the model so it continues
# the loop (passes the floor or logs an override) instead of ending on a degraded result.
set -euo pipefail

HOME_DIR="${DESIGN_STUDIO_HOME:-}"
RUN_FILE="./design-run.json"

# No active design run -> no-op (do not interfere with unrelated sessions).
[ -f "$RUN_FILE" ] || exit 0

# Locate run_state.py.
if [ -n "$HOME_DIR" ] && [ -f "$HOME_DIR/engine/loop/run_state.py" ]; then
  STATE="$HOME_DIR/engine/loop/run_state.py"
elif [ -f "$(dirname "$0")/../engine/loop/run_state.py" ]; then
  STATE="$(dirname "$0")/../engine/loop/run_state.py"
else
  # Cannot verify; fail loud rather than silently allow.
  echo "design-gate: design-run.json present but run_state.py not found; set DESIGN_STUDIO_HOME. Blocking to avoid silent ship." >&2
  exit 2
fi

if python3 "$STATE" ship-check --file "$RUN_FILE" >/tmp/design-gate.out 2>&1; then
  exit 0
fi

echo "design-gate: floor not passed. Do not finish this build yet." >&2
cat /tmp/design-gate.out >&2
echo "Three exits: (1) if 'brief' is halted, lock the human-approved brief first (Stage 1; run_state.py gate --name brief --status pass); (2) pass the failing gates via the floor loop or log an explicit override (run_state.py override --gate <g> --reason '...'); (3) abort the run entirely (run_state.py cancel --file design-run.json)." >&2
exit 2
