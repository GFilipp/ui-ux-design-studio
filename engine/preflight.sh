#!/usr/bin/env bash
# preflight.sh — verifies (and with --install, installs) every machine-level tool the design
# studio needs, so a run never hits "command not found" mid-build.
#
# Why this exists (2026-09-08): a /design-studio run reported four reference renders as
# failures because the pod wrapped `node render.mjs` in GNU `timeout`, which macOS does not
# ship. Nothing in this repo called `timeout`, and nothing checked for it either. This script
# is that check. The registry below is derived from what the engine actually invokes;
# TOOLS.md must list exactly the same names (the self-test suite asserts it).
#
# Usage: bash engine/preflight.sh [--install] [--target <repo-dir>] [--list]
#   (no flags)   check only. exit 0 = every REQUIRED tool present (WARN lines allowed)
#   --install    install what is missing where a package manager exists (Homebrew on macOS;
#                npm for the Playwright module and browser), then re-check
#   --target d   also require the package manager the TARGET repo's lockfile implies
#                (bun.lock -> bun, pnpm-lock.yaml -> pnpm, yarn.lock -> yarn,
#                package-lock.json -> npm; a `packageManager` field in package.json wins)
#   --list       print the registry (name | tier | why) and exit 0
# Exit: 0 ok | 1 a REQUIRED tool is missing (still missing after --install) | 2 usage error
#
# Portable to the bash 3.2 that macOS ships: no associative arrays, no mapfile.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL=0; TARGET=""; LIST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --install) INSTALL=1 ;;
    --target)  [ $# -ge 2 ] || { echo "preflight: --target needs a directory" >&2; exit 2; }
               TARGET="$2"; shift ;;
    --list)    LIST=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "preflight: unknown argument '$1' (see --help)" >&2; exit 2 ;;
  esac
  shift
done

# ---- registry: name|tier|homebrew formula (- = not a brew package)|why -----------------------
# tier: required = the engine cannot run without it; recommended = runs hit noise without it.
REGISTRY='python3|required|python3|run_state.py, floor_check.py, drawing_check.py (stdlib only)
node|required|node|render.mjs, extract.js, capture-*.mjs; version floor read from node_modules/playwright engines
npm|required|node|installs the Playwright module (package.json devDependency)
npx|required|node|`npx playwright install chromium` fetches the render browser
git|required|git|run_state.py init records base_sha; drawing_check.py --git-diff scopes the scan to it
playwright|required|-|the node module, resolvable from the engine root (npm ci)
browser|required|-|render.mjs needs Playwright bundled Chromium, else system Chrome (channel "chrome")
timeout|recommended|coreutils|the pod wraps long renders in GNU timeout; macOS ships none (the 2026-09-08 false failures)
stop-hook|recommended|-|~/.claude/settings.json: env.DESIGN_STUDIO_HOME + a Stop hook running hooks/design-gate.sh'

if [ "$LIST" = 1 ]; then
  printf '%-11s %-12s %s\n' name tier why
  printf '%s\n' "$REGISTRY" | while IFS='|' read -r n t _b w; do printf '%-11s %-12s %s\n' "$n" "$t" "$w"; done
  echo "(--target adds the package manager the target repo's lockfile implies)"
  exit 0
fi

REQ_MISSING=0; WARNINGS=0
say() { printf '  %-5s %-11s %s\n' "$1" "$2" "$3"; }
have_brew() { command -v brew >/dev/null 2>&1; }

brew_install() { # <formula> -> 0 installed, 1 not attempted/failed (message printed)
  if ! have_brew; then say info "$2" "no Homebrew here; install '$1' with your package manager"; return 1; fi
  say info "$2" "installing '$1' via Homebrew..."
  if brew install "$1" >/dev/null 2>&1; then return 0; fi
  say info "$2" "brew install $1 FAILED; run it by hand to see why"; return 1
}

# ---- individual checks: print nothing, return 0 present / 1 missing; DETAIL carries a note ----
DETAIL=""
check_bin() { local p; p=$(command -v "$1" 2>/dev/null) || { DETAIL="not on PATH"; return 1; }; DETAIL="$p"; return 0; }

check_python3() {
  check_bin python3 || return 1
  python3 -c 'import argparse,base64,json,os,re,subprocess,sys,urllib' 2>/dev/null || { DETAIL="python3 present but the stdlib import failed"; return 1; }
  DETAIL="$DETAIL ($(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])'))"
}

check_node() {
  check_bin node || return 1
  local pj="$ROOT/node_modules/playwright/package.json" out
  # Version floor is whatever the installed Playwright declares, never a number typed here.
  if [ -f "$pj" ]; then
    out=$(node -e '
const fs=require("fs"); let eng;
try { eng=(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).engines||{}).node; } catch (e) { process.exit(0); }
if (!eng) process.exit(0);
const m=/(\d+)/.exec(eng); if (!m) { console.log("engines.node unparsed: "+eng); process.exit(0); }
const have=+process.versions.node.split(".")[0];
console.log("v"+process.versions.node+" (playwright wants "+eng+")");
process.exit(have>=+m[1]?0:1);' "$pj" 2>&1) || { DETAIL="$out: too old for the installed Playwright"; return 1; }
    DETAIL="$DETAIL $out"
  else
    DETAIL="$DETAIL ($(node --version 2>/dev/null))"
  fi
}

check_playwright() {
  (cd "$ROOT" && node -e 'require("playwright")' >/dev/null 2>&1) || { DETAIL="not resolvable from $ROOT (run: npm ci)"; return 1; }
  DETAIL="$(cd "$ROOT" && node -p 'require("playwright/package.json").version' 2>/dev/null)"
}

check_browser() {
  local out
  out=$(cd "$ROOT" && node -e '
const { chromium } = require("playwright");
(async () => {
  try { const b = await chromium.launch(); await b.close(); console.log("bundled chromium " + b.version()); return; } catch (e) {}
  try { const b = await chromium.launch({ channel: "chrome" }); await b.close(); console.log("system Chrome (bundled chromium absent)"); return; } catch (e) {}
  console.log("no launchable browser"); process.exit(1);
})();' 2>&1) || { DETAIL="$out (run: npx playwright install chromium)"; return 1; }
  DETAIL="$out"
}

check_timeout() {
  if check_bin timeout; then return 0; fi
  if command -v gtimeout >/dev/null 2>&1; then DETAIL="only gtimeout on PATH; the pod calls 'timeout'"; return 1; fi
  DETAIL="not on PATH (GNU coreutils)"; return 1
}

check_stop_hook() {
  local s="$HOME/.claude/settings.json"
  [ -f "$s" ] || { DETAIL="no $s; wire per hooks/README.md"; return 1; }
  DETAIL=$(python3 - "$s" <<'PY'
import json, sys
try:
    s = json.load(open(sys.argv[1]))
except Exception as e:
    print("settings.json unreadable: %s" % e); sys.exit(1)
home = (s.get("env") or {}).get("DESIGN_STUDIO_HOME")
wired = any("design-gate.sh" in (h.get("command") or "")
            for grp in (s.get("hooks") or {}).get("Stop", []) for h in grp.get("hooks", []))
if home and wired: print("DESIGN_STUDIO_HOME set, Stop hook runs design-gate.sh"); sys.exit(0)
missing = [x for x, ok in (("env.DESIGN_STUDIO_HOME", home), ("Stop hook -> design-gate.sh", wired)) if not ok]
print("not wired: " + ", ".join(missing) + " (hooks/README.md)"); sys.exit(1)
PY
) || return 1
}

# ---- installers: return 0 when something was installed and should be re-checked -------------
install_one() { # <name>
  case "$1" in
    python3) brew_install python3 "$1" ;;
    node)    if [ -d "${NVM_DIR:-$HOME/.nvm}" ]; then say info node "nvm is installed; run: nvm install --lts"; return 1; fi
             brew_install node "$1" ;;
    npm|npx) say info "$1" "ships with node; install node first"; return 1 ;;
    git)     brew_install git "$1" ;;
    playwright)
             say info playwright "installing the node module from $ROOT/package.json..."
             if [ -f "$ROOT/package-lock.json" ]; then (cd "$ROOT" && npm ci --no-audit --no-fund >/dev/null 2>&1)
             else (cd "$ROOT" && npm install --no-audit --no-fund >/dev/null 2>&1); fi ;;
    browser) say info browser "downloading Playwright's bundled Chromium..."
             (cd "$ROOT" && npx playwright install chromium >/dev/null 2>&1) ;;
    timeout) if command -v gtimeout >/dev/null 2>&1; then
               local g; g=$(command -v gtimeout); ln -s "$g" "$(dirname "$g")/timeout" 2>/dev/null && { say info timeout "linked timeout -> $g"; return 0; }
             fi
             brew_install coreutils "$1" ;;
    stop-hook) say info stop-hook "wiring is a settings.json edit: follow hooks/README.md (update-config skill)"; return 1 ;;
    bun)     brew_install oven-sh/bun/bun "$1" ;;
    pnpm)    brew_install pnpm "$1" ;;
    yarn)    brew_install yarn "$1" ;;
    *)       return 1 ;;
  esac
}

run_check() { # <name> -> 0/1, DETAIL set
  case "$1" in
    python3)    check_python3 ;;
    node)       check_node ;;
    playwright) check_playwright ;;
    browser)    check_browser ;;
    timeout)    check_timeout ;;
    stop-hook)  check_stop_hook ;;
    *)          check_bin "$1" ;;
  esac
}

report() { # <name> <tier> <why>
  local name="$1" tier="$2" why="$3"
  if run_check "$name"; then say ok "$name" "$DETAIL"; return; fi
  local before="$DETAIL"
  if [ "$INSTALL" = 1 ] && install_one "$name" && run_check "$name"; then say FIXED "$name" "$DETAIL"; return; fi
  if [ "$tier" = required ]; then REQ_MISSING=$((REQ_MISSING+1)); say FAIL "$name" "$before. Needed for: $why"
  else WARNINGS=$((WARNINGS+1)); say WARN "$name" "$before. Needed for: $why"; fi
}

echo "design-studio preflight ($ROOT)"
printf '%s\n' "$REGISTRY" > "${TMPDIR:-/tmp}/preflight-registry.$$"
while IFS='|' read -r name tier _formula why; do
  report "$name" "$tier" "$why"
done < "${TMPDIR:-/tmp}/preflight-registry.$$"
rm -f "${TMPDIR:-/tmp}/preflight-registry.$$"

# ---- target repo: the package manager its lockfile implies ----------------------------------
if [ -n "$TARGET" ]; then
  [ -d "$TARGET" ] || { echo "preflight: --target '$TARGET' is not a directory" >&2; exit 2; }
  declared=""
  if [ -f "$TARGET/package.json" ]; then
    declared=$(python3 -c 'import json,sys
try: print((json.load(open(sys.argv[1])).get("packageManager") or "").split("@")[0])
except Exception: print("")' "$TARGET/package.json")
  fi
  found=""
  { [ -f "$TARGET/bun.lock" ] || [ -f "$TARGET/bun.lockb" ]; } && found="$found bun"
  [ -f "$TARGET/pnpm-lock.yaml" ] && found="$found pnpm"
  [ -f "$TARGET/yarn.lock" ] && found="$found yarn"
  { [ -f "$TARGET/package-lock.json" ] || [ -f "$TARGET/npm-shrinkwrap.json" ]; } && found="$found npm"
  found="${found# }"
  if [ -n "$declared" ]; then primary="$declared"; reason="package.json packageManager"
  elif [ -z "$found" ]; then primary=""; reason="no lockfile"
  else
    case " $found " in *" npm "*) primary=npm ;; *) primary="${found%% *}" ;; esac
    reason="lockfile(s): $found"
  fi
  echo "target $TARGET ($reason)"
  if [ -z "$primary" ]; then say info target "no package manager implied; nothing extra required"
  else
    report "$primary" required "installing the target repo's dependencies"
    for pm in $found; do
      [ "$pm" = "$primary" ] && continue
      if run_check "$pm"; then say ok "$pm" "$DETAIL (secondary lockfile)"
      else WARNINGS=$((WARNINGS+1)); say WARN "$pm" "$DETAIL; a $pm lockfile is present but $primary will be used"; fi
    done
  fi
fi

echo
if [ "$REQ_MISSING" -gt 0 ]; then
  echo "preflight: FAIL ($REQ_MISSING required missing, $WARNINGS warnings). Re-run with --install, or install by hand, before any design run."
  exit 1
fi
echo "preflight: OK ($WARNINGS warnings)"
exit 0
