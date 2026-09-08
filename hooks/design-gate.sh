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
OUT_DIR="$(mktemp -d)"
trap 'rm -rf "$OUT_DIR"' EXIT

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

# Anti-hand-drawing backstop. Runs an INDEPENDENT source scan of the target repo's changed
# files, regardless of the gate statuses the model set (reconcile, do not trust). A build that
# hand-drew cannot park at human_pick or ship on a green gate it set itself.
DCHECK="$(dirname "$STATE")/../floor/drawing_check.py"
if [ ! -f "$DCHECK" ]; then
  echo "design-gate: WARNING — drawing_check.py not found next to run_state.py; the anti-drawing backstop did NOT run this turn." >&2
fi
if [ -f "$DCHECK" ]; then
  # `|| DRC=$?` keeps the non-zero scan exit from tripping `set -e` before we branch on it.
  DRC=0
  # Timeout via python (macOS ships no `timeout`). A wedged scanner must not hang every turn-end.
  python3 -c 'import subprocess,sys
try:
    sys.exit(subprocess.run(sys.argv[1:], timeout=120).returncode)
except subprocess.TimeoutExpired:
    print("drawing_check timed out after 120s", file=sys.stderr); sys.exit(6)' \
    python3 "$DCHECK" --git-diff --root . --run-file "$RUN_FILE" >$OUT_DIR/drawing.out 2>&1 || DRC=$?
  if [ "$DRC" = "3" ]; then
    echo "design-gate: HAND-DRAWING detected — canvas 2D drawing in authored source. This is NOT overridable." >&2
    cat $OUT_DIR/drawing.out >&2
    echo "Replace it with a real component (e.g. an aceternity/magicui background), generated imagery (mcp-image), or clean type + tokens, then continue." >&2
    exit 2
  elif [ "$DRC" = "2" ]; then
    # Soft finding (illustration-scale SVG). Allowed ONLY if no_drawing is explicitly overridden with a reason.
    OVR=$(python3 - "$RUN_FILE" <<'PY'
import json, sys
try:
    g = json.load(open(sys.argv[1])).get("gates", {}).get("no_drawing", {})
    print("yes" if (g.get("status") if isinstance(g, dict) else g) == "overridden" else "no")
except Exception:
    print("no")
PY
)
    if [ "$OVR" != "yes" ]; then
      echo "design-gate: hand-authored illustration-scale SVG in authored source (the no_drawing gate reads clean or is stale; the scan is authoritative)." >&2
      cat $OUT_DIR/drawing.out >&2
      echo "Source it from a component library, mcp-image, or a real brand asset. If genuinely intentional, log: run_state.py override --file design-run.json --gate no_drawing --reason '...'." >&2
      exit 2
    fi
  elif [ "$DRC" = "5" ]; then
    # Degraded: no usable baseline, so committed work was NOT scanned. One `git commit` used to
    # empty the scan and report clean, which is how a canvas could reach a push unnoticed.
    echo "design-gate: the anti-drawing scan could not cover committed work (no usable base_sha). Re-run run_state.py init inside the git repo so the baseline is recorded; do not treat this as clean." >&2
    cat $OUT_DIR/drawing.out >&2
    exit 2
  elif [ "$DRC" = "4" ]; then
    # Usage error: the scanner NEVER RAN. Exit 4 exists so this cannot be mistaken for the
    # exit-2 "soft finding, overridden, proceed" path, which is what used to happen.
    echo "design-gate: drawing_check was invoked incorrectly (exit 4) — the anti-drawing scan did NOT run. Fix the invocation; do not treat this as a clean scan." >&2
    cat $OUT_DIR/drawing.out >&2
    exit 2
  elif [ "$DRC" != "0" ]; then
    # Unexpected failure (crash, timeout). FAIL CLOSED like ship-check/done do: an unverified
    # build is not a clean build. Escape hatch is `run_state.py cancel`.
    echo "design-gate: drawing_check did not run cleanly (exit $DRC); the anti-drawing scan did NOT cover this turn. Not treating it as clean." >&2
    cat $OUT_DIR/drawing.out >&2
    exit 2
  fi
fi

if python3 "$STATE" ship-check --file "$RUN_FILE" >$OUT_DIR/gate.out 2>&1; then
  exit 0
fi

# Legitimate resting state: every model-fixable gate is resolved and the ONLY
# halted gate is human_pick. The taste pick belongs to the human (RULES 12);
# the model must neither pass nor override it, so blocking the stop here would
# deadlock the loop. Allow the stop; ship-check still blocks Stage 4 until the
# human picks, so no enforcement is lost.
if python3 "$STATE" resting-ok --file "$RUN_FILE" >/dev/null 2>&1; then
  echo "design-gate: parked at human_pick (all other gates resolved). Present the candidates and get the human's pick; shipping stays blocked until then." >&2
  exit 0
fi

echo "design-gate: floor not passed. Do not finish this build yet." >&2
cat $OUT_DIR/gate.out >&2
echo "Exits: (1) if 'brief' is halted, lock the human-approved brief first (Stage 1; run_state.py gate --file design-run.json --name brief --status pass); (2) pass the failing gates via the floor loop or log an explicit override (run_state.py override --file design-run.json --gate <g> --reason '...'); (3) if 'human_pick' is the blocker, present the candidates and record the human's choice (run_state.py pick --file design-run.json --candidate <id>) — it cannot be set with 'gate' or overridden; (4) abort the run entirely (run_state.py cancel --file design-run.json)." >&2
exit 2
