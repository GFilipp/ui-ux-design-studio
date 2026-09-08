#!/usr/bin/env bash
# run-selftests.sh — the engine's regression suite.
#
# README claimed "self-tests in samples/" for months while NOTHING executed them, which is how a
# batch of integrity bypasses accumulated unnoticed (2026-09-08 audit). Every finding from that
# audit is a named case here so it cannot silently come back.
#
# Usage: bash engine/test/run-selftests.sh            (exit 0 = all green)
# Run from anywhere; paths resolve against the repo root.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && cd .. && pwd)"
cd "$ROOT"
RS="engine/loop/run_state.py"
export RSPATH="$ROOT/engine/loop/run_state.py"
DC="engine/floor/drawing_check.py"
FC="engine/floor/floor_check.py"
KIT="brand-kits/example-rocketminds/brand-kit.json"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
chk() { # chk <label> <got> <want>
  if [ "$2" = "$3" ]; then pass=$((pass+1)); printf "  ok    %-62s %s\n" "$1" "$2"
  else fail=$((fail+1)); printf "  FAIL  %-62s got=%s want=%s\n" "$1" "$2" "$3"; fi
}
dc() { python3 "$DC" "$@" >/dev/null 2>&1; echo $?; }
rs() { python3 "$RS" "$@" >/dev/null 2>&1; echo $?; }

# A fresh run dir with 3 real reference FILES and every gate passed.
newrun() { # newrun <dir>
  local d="$1"; mkdir -p "$d/refs"
  for i in 1 2 3; do printf 'PNGDATA' > "$d/refs/r$i.png"; done
  python3 "$RS" init --file "$d/design-run.json" --project t --surface web --brand-kit "$KIT" >/dev/null 2>&1
  python3 "$RS" references --file "$d/design-run.json" --add refs/r1.png refs/r2.png refs/r3.png >/dev/null 2>&1
  for g in brief references assets no_drawing contrast orphans layout console targets type_size measure responsive; do
    python3 "$RS" gate --file "$d/design-run.json" --name "$g" --status pass >/dev/null 2>&1
  done
  python3 "$RS" pick --file "$d/design-run.json" --candidate A >/dev/null 2>&1
}
refcount() { # refcount <runfile> <json-array-of-refs> -> counted value
  python3 - "$1" "$2" <<'PY'
import json,os,sys,importlib.util
spec=importlib.util.spec_from_file_location("rs","engine/loop/run_state.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
run=sys.argv[1]; refs=json.loads(sys.argv[2])
s=json.load(open(run)); s["references"]=refs; json.dump(s,open(run,"w"))
print(m.references_count(s, os.path.dirname(os.path.abspath(run))))
PY
}

echo "=== 1. floor_check fixtures ==="
chk "floor good"                 "$(python3 "$FC" samples/_selftest_good.json >/dev/null 2>&1; echo $?)" 0
chk "floor bad"                  "$(python3 "$FC" samples/_selftest_bad.json  >/dev/null 2>&1; echo $?)" 2

echo "=== 2. drawing_check fixtures (tiered 0/2/3) ==="
chk "authored canvas -> hard"     "$(dc samples/drawing/authored_canvas.tsx --root .)" 3
chk "authored Path2D -> hard"     "$(dc samples/drawing/authored_canvas_path2d.tsx --root .)" 3
chk "authored illustration -> soft" "$(dc samples/drawing/authored_illustration.tsx --root .)" 2
chk "authored jsx d-expr -> soft" "$(dc samples/drawing/authored_jsx_dexpr.tsx --root .)" 2
chk "authored icon -> clean"      "$(dc samples/drawing/authored_icon.tsx --root .)" 0
chk "clean components -> clean"   "$(dc samples/drawing/clean_components.tsx --root .)" 0
chk "vendored aceternity -> exempt" "$(dc samples/drawing/vendored/components/aceternity/background-beams.tsx --root .)" 0
chk "vendored ui-alias (kibo) -> exempt" "$(dc samples/drawing/vendored/components/ui/kibo-gantt/index.tsx --root .)" 0

echo "=== 3. AUDIT A: integrity bypasses ==="
# A1: `vendored --add .` must not exempt the whole repo.
V="$TMP/a1"; newrun "$V"; cp samples/drawing/authored_canvas.tsx "$V/hero.tsx"
chk "A1 vendored --add '.' rejected"  "$(rs vendored --file "$V/design-run.json" --add .)" 3
chk "A1 vendored --add '..' rejected" "$(rs vendored --file "$V/design-run.json" --add ..)" 3
chk "A1 vendored nonexistent rejected" "$(rs vendored --file "$V/design-run.json" --add nope/zzz)" 3
chk "A1 canvas still hard after attempts" "$(dc "$V/hero.tsx" --root "$V" --run-file "$V/design-run.json")" 3
chk "A1 legit vendored path accepted" "$(mkdir -p "$V/components/ui" && printf 'x' > "$V/components/ui/x.tsx" && rs vendored --file "$V/design-run.json" --add components/ui)" 0

# A2: exclusion must be relative to root, not the absolute path.
B="$TMP/build/site"; mkdir -p "$B/app"; cp samples/drawing/authored_canvas.tsx "$B/app/hero.tsx"
chk "A2 repo under a 'build' dir still scanned" "$(dc --git-diff --root "$B")" 3
O="$TMP/out/proj"; mkdir -p "$O/app"; cp samples/drawing/authored_canvas.tsx "$O/app/page.tsx"
chk "A2 repo under an 'out' dir still scanned"  "$(dc "$O/app/page.tsx" --root "$O")" 3
# ...while a real build dir INSIDE the root stays excluded.
mkdir -p "$B/dist"; cp samples/drawing/authored_canvas.tsx "$B/dist/bundle.tsx"
chk "A2 in-root dist/ still excluded"           "$(dc "$B/dist/bundle.tsx" --root "$B")" 0

# A3: padding past MAX_BYTES must not downgrade the hard block.
P="$TMP/a3"; mkdir -p "$P"
cp samples/drawing/authored_canvas.tsx "$P/big.tsx"
python3 -c "open('$P/big.tsx','a').write('\n// '+('p'*300000))"
chk "A3 oversized canvas (padding appended)"   "$(dc "$P/big.tsx" --root "$P")" 3
cp samples/drawing/authored_canvas.tsx "$P/pre.tsx"
python3 -c "src=open('$P/pre.tsx').read(); open('$P/pre.tsx','w').write('// '+('p'*300000)+chr(10)+src)"
chk "A3 oversized canvas (padding PREPENDED)"  "$(dc "$P/pre.tsx" --root "$P")" 3

# A4: references padding vectors must NOT reach 3.
R="$TMP/a4"; newrun "$R"; RF="$R/design-run.json"
chk "A4 schemeless urls not counted"  "$(refcount "$RF" '["https://","https://a","http://"]')" 0
chk "A4 dot paths not counted"        "$(refcount "$RF" '[".","..","./"]')" 0
mkdir -p "$R/d1" "$R/d2" "$R/d3"; printf 'x' > "$R/notes.txt"
chk "A4 real directories not counted" "$(refcount "$RF" '["d1","d2","d3"]')" 0
chk "A4 non-image files not counted"  "$(refcount "$RF" '["notes.txt","notes.txt","notes.txt"]')" 0
chk "A4 case aliases dedupe to 1"     "$(refcount "$RF" '["refs/r1.png","refs/R1.PNG","refs/r1.PNG"]')" 1
chk "A4 same-host urls dedupe to 1"   "$(refcount "$RF" '["https://linear.app/a","https://linear.app/b","https://linear.app/c"]')" 1
chk "A4 path aliases dedupe to 1"     "$(refcount "$RF" '["refs/r1.png","./refs/r1.png","refs/../refs/r1.png"]')" 1
chk "A4 real files count"             "$(refcount "$RF" '["refs/r1.png","refs/r2.png","refs/r3.png"]')" 3
chk "A4 real https counts"            "$(refcount "$RF" '["https://linear.app","refs/r2.png","refs/r3.png"]')" 3

# A5: the canvas hard-block must fire at ship-check, BEFORE the documented deploy.
S="$TMP/a5"; newrun "$S"; cp samples/drawing/authored_canvas.tsx "$S/hero.tsx"
chk "A5 ship-check blocks on canvas"  "$(cd "$S" && python3 "$ROOT/$RS" ship-check --file design-run.json 2>&1 | grep -c 'hand-drawn <canvas>')" 1

# A6: `done` must fail CLOSED when the scan cannot be verified. Exercised through cmd_done
# ITSELF — the old A6 called a helper that production never calls, so it stayed green even if
# cmd_done's check was deleted.
U6="$TMP/a6"; newrun "$U6"
chk "A6 done refuses an unverifiable scan" "$(cd "$U6" && python3 - <<'PYEOF' 2>&1 | tail -1
import importlib.util, os
spec = importlib.util.spec_from_file_location("rs", os.environ["RSPATH"])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.drawing_scan_code = lambda _f: 1   # scanner crashed -> must NOT read as clean
try:
    m.cmd_done(type("A", (), {"file": "design-run.json"})())
    print("no-exit")
except SystemExit as e:
    print("exit:%s" % e.code)
PYEOF
)" "exit:3"

# A7: human_pick is the one gate with no override path.
H="$TMP/a7"; newrun "$H"
chk "A7 override human_pick refused"  "$(rs override --file "$H/design-run.json" --gate human_pick --reason "self-authorizing")" 3
chk "A7 override other gate allowed"  "$(rs override --file "$H/design-run.json" --gate contrast --reason "deadline")" 0

# A8: a usage error must not read as a soft finding.
chk "A8 no-args usage error != 2"     "$(dc)" 4
chk "A8 bad-flag usage error != 2"    "$(dc --nope)" 4


echo "=== 3b. AUDIT round 2: bypasses that reopened ==="
# vendored[] injected straight into the run file (the CLI guard did not cover this)
VJ="$TMP/vj"; newrun "$VJ"; cp samples/drawing/authored_canvas.tsx "$VJ/hero.tsx"
python3 - "$VJ/design-run.json" <<'PYEOF'
import json,sys
s=json.load(open(sys.argv[1])); s["vendored"]=["."]; json.dump(s,open(sys.argv[1],"w"))
PYEOF
chk "R1 vendored['.'] in the JSON is ignored" "$(cd "$VJ" && python3 "$ROOT/$DC" --git-diff --root . --run-file design-run.json >/dev/null 2>&1; echo $?)" 3
chk "R1 ship-check still blocks"              "$(cd "$VJ" && python3 "$ROOT/$RS" ship-check --file design-run.json 2>&1 | grep -c 'hand-drawn <canvas>')" 1

# soft findings must block ship-check and done unless no_drawing is overridden
SF="$TMP/sf"; newrun "$SF"; cp samples/drawing/authored_illustration.tsx "$SF/art.tsx"
chk "R2 soft finding blocks ship-check"       "$(cd "$SF" && python3 "$ROOT/$RS" ship-check --file design-run.json >/dev/null 2>&1; echo $?)" 3
chk "R2 soft finding blocks done"             "$(cd "$SF" && python3 "$ROOT/$RS" done --file design-run.json >/dev/null 2>&1; echo $?)" 3
python3 "$RS" override --file "$SF/design-run.json" --gate no_drawing --reason "intentional brand motif" >/dev/null 2>&1
chk "R2 overridden soft finding may ship"     "$(cd "$SF" && python3 "$ROOT/$RS" ship-check --file design-run.json >/dev/null 2>&1; echo $?)" 0

# human_pick cannot be granted by the model
HP="$TMP/hp"; newrun "$HP"
chk "R3 gate --name human_pick refused"       "$(rs gate --file "$HP/design-run.json" --name human_pick --status pass)" 3
chk "R3 pick records the candidate"           "$(python3 "$RS" pick --file "$HP/design-run.json" --candidate C 2>&1 | grep -c 'candidate: C')" 1
chk "R3 candidate persisted in the run file"  "$(python3 -c "import json;print(json.load(open('$HP/design-run.json')).get('picked_candidate'))")" "C"

# degraded baseline must not read as clean
DG="$TMP/dg"; mkdir -p "$DG/app"
( cd "$DG" && git init -q && git config user.email t@t && git config user.name t )
cp samples/drawing/authored_canvas.tsx "$DG/app/legacy.tsx"
( cd "$DG" && git add -A >/dev/null 2>&1 && git commit -qm legacy )
chk "R4 committed canvas + no baseline != clean" "$(dc --git-diff --root "$DG")" 5

# cancel and brief-ok were untested entirely
CB="$TMP/cb"; newrun "$CB"
python3 "$RS" cancel --file "$CB/design-run.json" >/dev/null 2>&1
chk "R5 cancel removes the run file"          "$([ -f "$CB/design-run.json" ] && echo present || echo gone)" "gone"
CB2="$TMP/cb2"; mkdir -p "$CB2"
python3 "$RS" init --file "$CB2/design-run.json" --project cb2 --surface web --brand-kit "$KIT" >/dev/null 2>&1
chk "R5 brief-ok blocks before the brief"     "$(rs brief-ok --file "$CB2/design-run.json")" 3

echo "=== 4. AUDIT B: false positives that wedge runs ==="
# B9: canvas primitive must be called on the getContext identifier.
N="$TMP/b9"; mkdir -p "$N"
cat > "$N/measure.tsx" <<'EOF'
export function Measure(label: string, data: number[]) {
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d");
  const w = ctx ? ctx.measureText(label).width : 0;
  const zeros = new Array(12).fill(0);
  const box = data.rect(1);
  return { w, zeros, box };
}
EOF
# Soft (2), not hard (3): it no longer WEDGES the run (the audit's complaint), but a 2D context
# beside draw primitives is not waved through either — it blocks overridably.
chk "B9 measureText + Array.fill not HARD" "$(dc "$N/measure.tsx" --root "$N")" 2
cat > "$N/cmp.tsx" <<'EOF'
const rows = new Array(12);
if (rows != null) { document.querySelector("canvas").getContext("2d"); }
rows.fill(0);
EOF
cat > "$N/cmt.tsx" <<'EOF'
// canvas.getContext("2d") appears only in this comment
const a = new Array(3).fill(0);
export { a };
EOF
chk "B9 comparison operand not HARD"       "$(dc "$N/cmp.tsx" --root "$N")" 2
chk "B9 comment-only mention is clean"     "$(dc "$N/cmt.tsx" --root "$N")" 0
cat > "$N/real.tsx" <<'EOF'
export function Draw() {
  const ctx = document.querySelector("canvas")!.getContext("2d")!;
  ctx.beginPath(); ctx.arc(50, 50, 20, 0, Math.PI * 2); ctx.fill();
}
EOF
chk "B9 real ctx drawing still hard"       "$(dc "$N/real.tsx" --root "$N")" 3
# FALSE-NEGATIVE guards: requiring the primitive on the bound identifier let real hand-drawn
# canvas escape entirely. Both of these were verified to return 0 before the layered fix.
cat > "$N/helper.tsx" <<'EOF'
function paint(ctx: CanvasRenderingContext2D) { ctx.beginPath(); ctx.arc(60,60,40,0,Math.PI*2); ctx.fill(); }
export function Hero() { const c = document.querySelector("canvas")!.getContext("2d")!; paint(c); }
EOF
cat > "$N/alias.tsx" <<'EOF'
export function Hero() {
  const g = document.querySelector("canvas")!.getContext("2d")!;
  const d = g;
  d.fillRect(0, 0, 10, 10);
}
EOF
# Both block (2 = soft) rather than passing. Soft, not hard, is the honest call: the primitive
# is on a function parameter / an alias, so the binding to the 2D context is not provable.
# The property under test is "not silently missed", which is what a 0 here would mean.
chk "B9 drawing via helper param blocks"     "$(dc "$N/helper.tsx" --root "$N")" 2
chk "B9 drawing via alias blocks"            "$(dc "$N/alias.tsx" --root "$N")" 2

# B10: no baseline must not widen the scan to every tracked file.
G="$TMP/b10"; mkdir -p "$G/app"
( cd "$G" && git init -q && git config user.email t@t && git config user.name t )
cp samples/drawing/authored_canvas.tsx "$G/app/legacy.tsx"
( cd "$G" && git add -A >/dev/null 2>&1 && git commit -qm legacy )
chk "B10 no baseline = cannot verify, not clean" "$(dc --git-diff --root "$G")" 5
cp samples/drawing/authored_canvas.tsx "$G/app/new.tsx"
chk "B10 newly added file IS scanned"         "$(dc --git-diff --root "$G")" 3

# B11: --root must bound the scan in a monorepo.
M="$TMP/b11"; mkdir -p "$M/pkg-a/app" "$M/pkg-b/app"
( cd "$M" && git init -q && git config user.email t@t && git config user.name t )
cp samples/drawing/authored_canvas.tsx "$M/pkg-a/app/hero.tsx"
# Commit and pass an explicit --base so this isolates root-bounding from the degraded-baseline
# path (no baseline is now exit 5, which would otherwise mask the result).
( cd "$M" && git add -A >/dev/null 2>&1 && git commit -qm init )
chk "B11 --root excludes a sibling package"   "$(dc --git-diff --base HEAD --root "$M/pkg-b")" 0
cp samples/drawing/authored_canvas.tsx "$M/pkg-b/app/own.tsx"
chk "B11 control: own package IS scanned"     "$(dc --git-diff --base HEAD --root "$M/pkg-b")" 3

echo "=== 5. references gate contract ==="
C="$TMP/refs"; mkdir -p "$C/refs"; for i in 1 2 3; do printf 'PNGDATA' > "$C/refs/r$i.png"; done
python3 "$RS" init --file "$C/design-run.json" --project r --surface web --brand-kit "$KIT" >/dev/null 2>&1
chk "assertion refused at 0 refs"     "$(rs gate --file "$C/design-run.json" --name references --status pass)" 3
chk "bare names refused"              "$(rs references --file "$C/design-run.json" --add Linear Zed Stripe)" 3
chk "directory refused"               "$(rs references --file "$C/design-run.json" --add refs)" 3
chk "batch duplicate counts once"     "$(python3 "$RS" references --file "$C/design-run.json" --add refs/r1.png refs/r1.png refs/r1.png 2>&1 | grep -c 'total 1 of 3')" 1
chk "still refused at 1 ref"          "$(rs gate --file "$C/design-run.json" --name references --status pass)" 3
python3 "$RS" references --file "$C/design-run.json" --add refs/r2.png refs/r3.png >/dev/null 2>&1
chk "passes at 3 real refs"           "$(rs gate --file "$C/design-run.json" --name references --status pass)" 0

echo "=== 6. unresolved_gates (fail-closed) ==="
U="$TMP/u"; newrun "$U"
chk "clean run ships"                 "$(rs ship-check --file "$U/design-run.json")" 0
python3 - "$U/design-run.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1])); s["gates"]["contrast"]={"status":"approved"}; json.dump(s,open(sys.argv[1],"w"))
PY
chk "unknown status blocks"           "$(rs ship-check --file "$U/design-run.json")" 3
U2="$TMP/u2"; newrun "$U2"
python3 - "$U2/design-run.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1])); del s["gates"]["layout"]; json.dump(s,open(sys.argv[1],"w"))
PY
chk "missing gate blocks, no crash"   "$(rs ship-check --file "$U2/design-run.json")" 3

echo "=== 7. Stop hook ==="
export DESIGN_STUDIO_HOME="$ROOT"
K="$TMP/hook"; newrun "$K"
chk "hook allows a clean resolved run" "$(cd "$K" && bash "$ROOT/hooks/design-gate.sh" >/dev/null 2>&1; echo $?)" 0
python3 "$RS" gate --file "$K/design-run.json" --name contrast --status fail >/dev/null 2>&1
chk "hook blocks mid-loop"             "$(cd "$K" && bash "$ROOT/hooks/design-gate.sh" >/dev/null 2>&1; echo $?)" 2
K2="$TMP/hook2"; newrun "$K2"
python3 "$RS" gate --file "$K2/design-run.json" --name human_pick --status fail >/dev/null 2>&1
chk "hook allows human_pick resting"   "$(cd "$K2" && bash "$ROOT/hooks/design-gate.sh" >/dev/null 2>&1; echo $?)" 0
K3="$TMP/hook3"; newrun "$K3"; cp samples/drawing/authored_canvas.tsx "$K3/hero.tsx"
python3 "$RS" override --file "$K3/design-run.json" --gate no_drawing --reason "trying to waive canvas" >/dev/null 2>&1
chk "hook blocks canvas despite override" "$(cd "$K3" && bash "$ROOT/hooks/design-gate.sh" 2>&1 | grep -c 'HAND-DRAWING detected')" 1

echo "=== 8. orphan gate measures headings with inline children (real browser render) ==="
# Renders through render.mjs -> extract.js, so this exercises the actual producer, not a
# hand-written JSON fixture that would assume the very values the bug got wrong.
if node engine/floor/render.mjs "$ROOT/samples/orphan/inline-child-heading.html" "$TMP/orphan" >/dev/null 2>&1; then
  read -r OTOT OLAST <<<"$(python3 - "$TMP/orphan/extract-mobile.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
h=[n for n in d["textNodes"] if n["tag"]=="h1"]
print(h[0]["totalWords"] if h else -1, h[0]["lastLineWords"] if h else -1)
PY
)"
  chk "h1 owns its full inline text (was 1)" "$OTOT" 5
  chk "h1 last line is measured (was null)"  "$OLAST" 1
  python3 "$FC" "$TMP/orphan/extract-mobile.json" --breakpoint mobile --out "$TMP/orphan/r.json" >/dev/null 2>&1
  chk "orphan fails the ORPHANS gate specifically" "$(python3 -c "import json;print(json.load(open('$TMP/orphan/r.json'))['gates']['orphans']['status'])")" "fail"
  # A parent whose text lives in an inline child must NOT be judged with the PARENT's color.
  # Mutation-checked: reverting the ownsDirectText guard turns this red.
  node engine/floor/render.mjs "$ROOT/samples/contrast/inline-child-color.html" "$TMP/ctr" >/dev/null 2>&1
  python3 "$FC" "$TMP/ctr/extract-mobile.json" --breakpoint mobile --out "$TMP/ctr/r.json" >/dev/null 2>&1
  chk "inline-child color: no false contrast fail" "$(python3 -c "import json;print(json.load(open('$TMP/ctr/r.json'))['gates']['contrast']['status'])")" "pass"
  chk "inline-child color: zero failures listed"   "$(python3 -c "import json;print(len(json.load(open('$TMP/ctr/r.json'))['gates']['contrast']['failures']))")" 0
  chk "contrast does NOT false-fail on it"         "$(python3 -c "import json;print(json.load(open('$TMP/orphan/r.json'))['gates']['contrast']['status'])")" "pass"
else
  chk "orphan render (playwright available?)" "render-failed" "ok"
fi


echo "=== 9. UX-law gates (Fitts / type size / measure / choice load) ==="
node engine/floor/render.mjs "$ROOT/samples/uxlaws/small-targets.html" "$TMP/tap" >/dev/null 2>&1
python3 "$FC" "$TMP/tap/extract-mobile.json" --breakpoint mobile --out "$TMP/tap/m.json" >/dev/null 2>&1
python3 "$FC" "$TMP/tap/extract-desktop.json" --breakpoint desktop --out "$TMP/tap/d.json" >/dev/null 2>&1
gate() { python3 -c "import json;print(json.load(open('$1'))['gates']['$2']['status'])"; }
cnt() { python3 -c "import json;print(len(json.load(open('$1'))['gates']['$2']['$3']))"; }
chk "Fitts: small taps BLOCK on mobile"        "$(gate "$TMP/tap/m.json" targets)" "fail"
chk "Fitts: flags exactly the 2 small controls" "$(cnt "$TMP/tap/m.json" targets small)" 2
chk "Fitts: inline prose link NOT flagged"     "$(python3 -c "import json;print(sum(1 for s in json.load(open('$TMP/tap/m.json'))['gates']['targets']['small'] if 'comparison' in (s.get('label') or '')))")" 0
chk "Fitts: 24px pointer floor on desktop"     "$(python3 -c "import json;print(json.load(open('$TMP/tap/d.json'))['gates']['targets']['minimum'])")" 24
node engine/floor/render.mjs "$ROOT/samples/uxlaws/wide-measure.html" "$TMP/wm" >/dev/null 2>&1
python3 "$FC" "$TMP/wm/extract-mobile.json" --breakpoint mobile --out "$TMP/wm/m.json" >/dev/null 2>&1
chk "type_size: 9px body BLOCKS on mobile"     "$(gate "$TMP/wm/m.json" type_size)" "fail"
chk "measure: 130+ CPL BLOCKS"                 "$(gate "$TMP/wm/m.json" measure)" "fail"
chk "the reference sample still clears it all" "$(node engine/floor/render.mjs "$ROOT/samples/good.html" "$TMP/gd" >/dev/null 2>&1; python3 "$FC" "$TMP/gd/extract-mobile.json" --breakpoint mobile >/dev/null 2>&1; echo $?)" 0
chk "controls are captured at all (was zero)"  "$(python3 -c "import json;print(1 if len(json.load(open('$TMP/gd/extract-mobile.json'))['controls'])>0 else 0)")" 1
chk "groups are captured at all (was zero)"    "$(python3 -c "import json;print(1 if len(json.load(open('$TMP/gd/extract-mobile.json'))['groups'])>0 else 0)")" 1
chk "legacy fixtures without controls still 0" "$(python3 "$FC" samples/_selftest_good.json >/dev/null 2>&1; echo $?)" 0

echo
echo "================ $pass passed, $fail failed ================"
[ "$fail" -eq 0 ] || exit 1
