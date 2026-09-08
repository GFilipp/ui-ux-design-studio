#!/usr/bin/env python3
"""design-run state machine — the fail-loud guardrail spine (brand-agnostic).

A run may exit a gate ONLY via `pass` or `overridden(reason)`. There is no silent
third path: a gate left `halted` blocks ship. Every override carries a reason and
is surfaced in the ship summary, so degradation is always visible and chosen.

Usage:
  run_state.py init   --file design-run.json --project NAME --surface web --brand-kit PATH
  run_state.py gate   --file design-run.json --name contrast --status pass|fail [--detail '...']
                                                      # exit 0 on pass, 2 on fail (a recorded halt, not an error)
  run_state.py override --file design-run.json --gate contrast --reason "deadline; ship anyway"
  run_state.py ship-check --file design-run.json     # exit 0 ship-ok, 3 blocked
  run_state.py done   --file design-run.json          # finalize: all gates pass -> remove the file
  run_state.py cancel --file design-run.json          # ABORT: remove the file so the Stop hook stops gating
  run_state.py candidate --file design-run.json --add A --source aceternity --archetype motion-led --fidelity cheap|built
  run_state.py candidate --file design-run.json --drop A | --list
  run_state.py direction --file design-run.json --candidate B     # pick the DIRECTION from a cheap, divergent slate (>=3, <=4)
  run_state.py direction --file design-run.json --given "the human's words"   # the human named the direction up front
  run_state.py pick     --file design-run.json --candidate B   # the ONLY way to resolve human_pick; B must be a BUILT candidate
  run_state.py brief-ok --file design-run.json        # exit 0 if the brief gate is locked (pass or overridden), else 3
  run_state.py references --file design-run.json --add PATH_OR_URL ...   # record loaded vision references (gate COUNTS these)
  run_state.py vendored   --file design-run.json --add PATH ...          # record library-install paths (drawing_check exempts them)
"""
import argparse
import json
import os
import re
import subprocess
import sys

GATES = ["brand_kit", "brief", "references", "assets", "no_drawing",
         "contrast", "orphans", "layout", "console", "targets", "type_size", "measure",
         "responsive", "human_pick"]
# console/targets/type_size/measure are BLOCKING in floor_check.py but were absent here, so a
# build with console errors or 20px tap targets could reach SHIP OK. Documented as gated in four
# places while being enforced in none (2026-09-08 audit).

# The references gate is COUNTED, not asserted: `gate --name references --status pass` is
# refused until this many real references are recorded via `references --add`, and ship-check
# and done re-verify the count. Before this, the gate passed on the model's word alone.
REFERENCES_MIN = 3

# The human's taste pick has no override path: `override --gate human_pick` let the model
# self-authorize the one decision RULES 12 reserves for the human (2026-09-08 audit).
NON_OVERRIDABLE_GATES = {"human_pick"}

# human_pick is also NOT settable via `gate`: it was non-overridable but freely passable, so one
# command still let the model grant itself the human's taste pick. It now requires `pick`, which
# records WHICH candidate was chosen. This does not prove a human acted (nothing in a CLI the
# model drives can); it makes the bypass deliberate and the audit trail honest.
PICK_ONLY_GATES = {"human_pick"}

# A reference is a vision exemplar, so it must be an image.
REFERENCE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg"}

# SLATE DISCIPLINE (2026-09-08, two sessions' learnings). A run once built EIGHT full covers, all
# Aceternity effects, before anyone had chosen anything: expensive, and one well. Two rules, both
# mechanical. (1) Cheapest choice first: a DIRECTION is picked from a slate of cheap artifacts
# (reference or demo screenshots, at most one static render each) and only the picked direction
# gets built; a `built` candidate cannot be registered before a direction exists. (2) Divergent
# slates: a direction slate needs SLATE_MIN candidates from at least two sources and two
# archetypes, with no two sharing (source, archetype); "five slightly different derivatives" is
# refused. SLATE_MAX caps any slate. `direction --given` records a direction the HUMAN named up
# front, in which case no cheap slate is needed. Honest limit, as with human_pick: a CLI the model
# drives cannot prove who chose or how cheap a "cheap" candidate really was; it makes the default
# path the disciplined one and every bypass visible in the run file.
SLATE_MIN = 3
SLATE_MAX = 4
FIDELITIES = ("cheap", "built")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


def slate(state):
    c = state.get("candidates")
    return c if isinstance(c, list) else []


def direction_of(state):
    # The chosen direction: a pick from a cheap slate, or the human's stated direction. None if neither.
    d = state.get("direction")
    if isinstance(d, dict) and (d.get("candidate") or d.get("given")):
        return d
    return None


def slate_violations(cands):
    # Why a slate is NOT a valid direction slate. Empty list = valid.
    out = []
    n = len(cands)
    if n < SLATE_MIN:
        out.append("only %d of %d directions" % (n, SLATE_MIN))
    if n > SLATE_MAX:
        out.append("%d candidates exceeds SLATE_MAX=%d" % (n, SLATE_MAX))
    not_cheap = [c.get("id") for c in cands if c.get("fidelity") != "cheap"]
    if not_cheap:
        out.append("not cheap: %s (a direction slate is cheap artifacts only)" % ", ".join(map(str, not_cheap)))
    sources = {c.get("source") for c in cands}
    if n and len(sources) < 2:
        out.append("one source for all %d (%s): go to other wells" % (n, next(iter(sources))))
    archetypes = {c.get("archetype") for c in cands}
    if n and len(archetypes) < 2:
        out.append("one archetype for all %d (%s): these are variants, not directions" % (n, next(iter(archetypes))))
    seen = {}
    for c in cands:
        k = (c.get("source"), c.get("archetype"))
        if k in seen:
            out.append("%s and %s are derivatives: same source (%s) and archetype (%s)" % (seen[k], c.get("id"), k[0], k[1]))
        else:
            seen[k] = c.get("id")
    return out


def resting_kind(state):
    # The ONLY legitimate places to end a turn with an open run, both waiting on a human choice:
    # "direction" = a valid cheap, divergent slate is registered and no direction is chosen yet;
    # "final" = a direction exists, a built slate is registered, and every gate but human_pick is
    # resolved. Anything else (including "parked" with nothing registered to choose from) is not
    # resting, so the Stop hook keeps the loop going. None = not resting.
    g = (state.get("gates") or {}).get("brief") or {}
    if (g.get("status") if isinstance(g, dict) else None) not in ("pass", "overridden"):
        return None
    cands = slate(state)
    if direction_of(state) is None:
        return "direction" if (cands and not slate_violations(cands)) else None
    if set(unresolved_gates(state)) == {"human_pick"} and cands and all(c.get("fidelity") == "built" for c in cands):
        return "final"
    return None


def pick_shortfall(state):
    # Reconcile human_pick against the slate: a pass whose candidate is not in a built slate under
    # a recorded direction is hand-edited or stale. None if consistent, else the reason.
    g = (state.get("gates") or {}).get("human_pick") or {}
    if (g.get("status") if isinstance(g, dict) else None) != "pass":
        return None
    if direction_of(state) is None:
        return "human_pick reads pass but no direction was ever recorded"
    pc = state.get("picked_candidate")
    ids = [c.get("id") for c in slate(state) if c.get("fidelity") == "built"]
    if pc not in ids:
        return "human_pick reads pass but picked_candidate %r is not in the built slate %s" % (pc, ids)
    return None


def git_head(cwd):
    # Baseline SHA for the drawing_check git-diff. None if the target is not a git repo yet.
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None
    except (FileNotFoundError, OSError):
        return None


def drawing_scan_code(run_file):
    # Run the anti-drawing scanner and return its exit code, or None if it could not run.
    # None/unexpected is NOT "clean" — see drawing_unverifiable.
    dc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "floor", "drawing_check.py")
    if not os.path.exists(dc):
        return None
    repo_dir = os.path.dirname(os.path.abspath(run_file)) or "."
    try:
        p = subprocess.run([sys.executable, dc, "--git-diff", "--root", ".",
                            "--run-file", os.path.abspath(run_file)],
                           cwd=repo_dir, capture_output=True, text=True, timeout=120)
        return p.returncode
    except subprocess.TimeoutExpired:
        return None  # treated as "cannot verify" -> fails closed
    except (FileNotFoundError, OSError):
        return None


def drawing_hard(run_file):
    # Non-overridable canvas hard-block, enforced at finalize AND ship-check (not just the Stop
    # hook): a model could override no_drawing then `done`, and the hook no-ops once the run
    # file is gone. ship-check matters because the pod deploys BETWEEN ship-check and done.
    return drawing_scan_code(run_file) == 3


def drawing_unverifiable(run_file):
    # FAIL CLOSED. A missing scanner, a crash (1), a usage error (4), or any unexpected code is
    # "cannot verify", never "clean" — previously all of these silently allowed the ship.
    code = drawing_scan_code(run_file)
    return code is None or code not in (0, 2, 3)


URL_RE = re.compile(r"^https?://([^/\s]+)", re.I)


def url_host(ref):
    # A reference URL needs a plausible host. A single-label host ("https://a") is padding,
    # not a reference; localhost is kept because local preview URLs are legitimate exemplars.
    m = URL_RE.match(ref)
    if not m:
        return None
    host = m.group(1).split("@")[-1].split(":")[0].lower()
    if host in ("localhost", "127.0.0.1"):
        return host
    return host if ("." in host and len(host) >= 4) else None


def reference_is_real(ref, base_dir):
    # A reference counts only if it resolves to an actual artifact: a URL with a real host, or
    # a local FILE that exists. Re-checked on every count, not just at write time.
    # Deliberately strict, because the 2026-09-08 audit padded the gate to 3 with "https://",
    # ".", "..", and directories — os.path.exists accepts dirs and "/", and a bare scheme is
    # not a reference. isfile + a required host closes both.
    if not isinstance(ref, str) or not ref.strip():
        return False
    r = ref.strip()
    if url_host(r):
        return True  # NOT fetched: we verify the shape, never that the page exists
    if "://" in r:
        return False  # unverifiable scheme, bare "https://", or a single-label host
    p = r if os.path.isabs(r) else os.path.join(base_dir, r)
    # Must be a non-empty IMAGE. Any three existing files used to satisfy the gate
    # (/etc/hosts counted), which is not a vision reference by any reading.
    if os.path.splitext(p)[1].lower() not in REFERENCE_EXTS:
        return False
    try:
        return os.path.isfile(p) and os.path.getsize(p) > 0
    except OSError:
        return False


def reference_key(ref, base_dir):
    # Identity for dedupe. Local paths collapse via realpath AND normcase, so refs/a.png,
    # ./refs/a.png, refs/../refs/a.png and refs/A.PNG are ONE reference — realpath alone does
    # not canonicalize case, so three spellings of one file passed the gate on APFS/NTFS.
    # URLs collapse to their HOST: three pages of one site are one exemplar, not three.
    r = ref.strip()
    host = url_host(r)
    if host:
        return "url:" + host
    p = r if os.path.isabs(r) else os.path.join(base_dir, r)
    # Identity by INODE where possible: os.path.normcase is a no-op outside Windows, so on APFS
    # (case-insensitive) refs/r1.png and refs/R1.PNG resolved to different keys and one file
    # counted twice. st_dev/st_ino also collapses hardlinks, which realpath does not.
    try:
        st = os.stat(p)
        return "ino:%s:%s" % (st.st_dev, st.st_ino)
    except OSError:
        return os.path.normcase(os.path.realpath(p))


def references_count(state, base_dir):
    refs = state.get("references")
    if not isinstance(refs, list):
        return 0
    seen = set()
    for r in refs:
        if not isinstance(r, str) or not reference_is_real(r, base_dir):
            continue
        seen.add(reference_key(r, base_dir))
    return len(seen)


def references_shortfall(state, base_dir):
    # Reconcile the gate against the array. A `pass` that is not backed by REFERENCES_MIN
    # real references is stale or asserted; an `overridden` gate is a logged human choice
    # and is honored (only the canvas hard-block is non-overridable).
    g = (state.get("gates") or {}).get("references") or {}
    if g.get("status") != "pass":
        return None
    n = references_count(state, base_dir)
    return n if n < REFERENCES_MIN else None


def run_dir(path):
    return os.path.dirname(os.path.abspath(path)) or "."


def unresolved_gates(state):
    # Fail-CLOSED: a gate is resolved ONLY by exactly "pass" or "overridden". Testing for
    # == "halted" instead let an unknown status ("approved", "ok", anything) satisfy both the
    # halted check and the shortfall reconcile, which shipped the run. Iterating GATES (not the
    # file's keys) also makes a MISSING gate unresolved instead of a KeyError crash.
    gates = state.get("gates") or {}
    out = []
    for g in GATES:
        v = gates.get(g)
        status = v.get("status") if isinstance(v, dict) else None
        if status not in ("pass", "overridden"):
            out.append(g)
    return out


def load(path):
    with open(path) as f:
        state = json.load(f)
    # Backfill gates added AFTER this run file was created. Without this a legacy file could never
    # be resolved: `gate`/`override` validated names against the FILE's keys while unresolved_gates
    # iterates the code's GATES, so "gate --name targets" said "unknown gate" and the Stop hook
    # blocked turn-end with remediation that could not work (2026-09-08 round-3 audit).
    if isinstance(state, dict):
        g = state.get("gates")
        if not isinstance(g, dict):
            g = state["gates"] = {}
        for k in GATES:
            g.setdefault(k, {"status": "halted", "detail": None, "override_reason": None})
    return state


def save(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def cmd_init(a):
    if not a.brand_kit:
        sys.stderr.write("HALT: no brand kit selected. Provide --brand-kit PATH or this run cannot start.\n")
        sys.exit(3)
    if not os.path.exists(a.brand_kit):
        sys.stderr.write("HALT: brand kit not found: %s\n" % a.brand_kit)
        sys.exit(3)
    repo_dir = os.path.dirname(os.path.abspath(a.file)) or "."
    state = {
        "project": a.project,
        "surface": a.surface,
        "brand_kit": a.brand_kit,
        "references": [],
        "base_sha": git_head(repo_dir),
        "vendored": [],
        "candidates": [],
        "direction": None,
        "gates": {g: {"status": "halted", "detail": None, "override_reason": None} for g in GATES},
    }
    state["gates"]["brand_kit"] = {"status": "pass", "detail": a.brand_kit, "override_reason": None}
    save(a.file, state)
    print("initialized run for '%s' (%s) with brand kit %s (base_sha=%s)"
          % (a.project, a.surface, a.brand_kit, state["base_sha"] or "n/a"))


def cmd_gate(a):
    state = load(a.file)
    if a.name not in GATES:
        sys.stderr.write("unknown gate: %s\n" % a.name)
        sys.exit(1)
    if a.name in PICK_ONLY_GATES:
        sys.stderr.write("HALT: '%s' cannot be set with `gate`. The taste pick belongs to the human "
                         "(RULES 12). Present the candidates, then record the human's actual choice: "
                         "`run_state.py pick --file %s --candidate <id>`.\n" % (a.name, a.file))
        sys.exit(3)
    status = "pass" if a.status == "pass" else "halted"
    # references cannot be passed by assertion: the array must actually hold REFERENCES_MIN.
    if a.name == "references" and status == "pass":
        n = references_count(state, run_dir(a.file))
        if n < REFERENCES_MIN:
            sys.stderr.write(
                "HALT: references gate needs %d recorded references, found %d. "
                "Load them and record each with `run_state.py references --file %s --add <path-or-url>`, "
                "or log an explicit override with a reason.\n" % (REFERENCES_MIN, n, a.file))
            sys.exit(3)
    state["gates"][a.name] = {"status": status, "detail": a.detail, "override_reason": None}
    save(a.file, state)
    print("%s -> %s" % (a.name, status))
    sys.exit(0 if status == "pass" else 2)


def cmd_override(a):
    state = load(a.file)
    if a.gate not in GATES:
        sys.stderr.write("unknown gate: %s\n" % a.gate)
        sys.exit(1)
    if a.gate in NON_OVERRIDABLE_GATES:
        sys.stderr.write("HALT: '%s' cannot be overridden. The taste pick belongs to the human "
                         "(RULES 12); the model may neither pass nor override it. Present the "
                         "candidates and record the human's actual choice.\n" % a.gate)
        sys.exit(3)
    if not a.reason or not a.reason.strip():
        sys.stderr.write("HALT: override requires a non-empty --reason.\n")
        sys.exit(3)
    g = state["gates"][a.gate]
    g["status"] = "overridden"
    g["override_reason"] = a.reason.strip()
    save(a.file, state)
    print("OVERRIDE logged: %s — %s" % (a.gate, a.reason.strip()))


def cmd_ship_check(a):
    state = load(a.file)
    gates = state.get("gates") or {}
    unresolved = unresolved_gates(state)
    def _g(name):
        v = gates.get(name)
        return v if isinstance(v, dict) else {}
    overrides = {g: _g(g).get("override_reason") for g in GATES if _g(g).get("status") == "overridden"}
    print("=== ship summary: %s (%s) ===" % (state.get("project"), state.get("surface")))
    print("brand kit: %s" % state.get("brand_kit"))
    for g in GATES:
        v = _g(g)
        status = v.get("status") or "MISSING"
        line = "  %-12s %s" % (g, status)
        if status == "overridden":
            line += "  (reason: %s)" % v.get("override_reason")
        elif status not in ("pass", "halted", "MISSING"):
            line += "  (INVALID status — treated as unresolved)"
        print(line)
    if overrides:
        print("SHIPPED WITH %d OVERRIDE(S): %s" % (len(overrides), ", ".join(overrides)))
    if unresolved:
        print("BLOCKED — unresolved gates: %s. Pass them or log an override." % ", ".join(unresolved))
        sys.exit(3)
    short = references_shortfall(state, run_dir(a.file))
    if short is not None:
        print("BLOCKED — references gate reads pass but only %d of %d references resolve "
              "(stale or asserted). Record them with `references --add`, or log an override."
              % (short, REFERENCES_MIN))
        sys.exit(3)
    ps = pick_shortfall(state)
    if ps is not None:
        print("BLOCKED — %s. Register the slate with `candidate --add`, record the direction, and "
              "pick again." % ps)
        sys.exit(3)
    # The canvas hard-block must fire HERE, not only at `done`: the pod integrates and
    # `git push`es between ship-check and done, so checking only at done fired post-deploy.
    code = drawing_scan_code(a.file)
    if code is None or code not in (0, 2, 3):
        print("BLOCKED — could not verify the build is free of hand-drawn canvas "
              "(drawing_check unavailable or errored, exit=%s). Refusing to report SHIP OK on an "
              "unverified build." % code)
        sys.exit(3)
    if code == 3:
        print("BLOCKED — hand-drawn <canvas> detected in the build (non-overridable). Remove it "
              "and source the visual from a component, mcp-image, or clean type.")
        sys.exit(3)
    if code == 2 and (gates.get("no_drawing") or {}).get("status") != "overridden":
        print("BLOCKED — hand-authored illustration-scale SVG in the build and no_drawing is not "
              "overridden. Source it from a component library, mcp-image, or a brand asset, or log "
              "`override --gate no_drawing --reason '...'`.")
        sys.exit(3)
    print("SHIP OK.")
    sys.exit(0)


def cmd_cancel(a):
    # Abort path: remove the live run file so the global Stop hook stops gating this directory.
    if os.path.exists(a.file):
        os.remove(a.file)
        print("run cancelled; %s removed. The Stop hook no longer gates this directory." % a.file)
    else:
        print("no active run at %s; nothing to cancel." % a.file)
    sys.exit(0)


def cmd_done(a):
    # Finalize a passing run: refuse if any gate is still halted, else remove the file (run complete).
    state = load(a.file)
    unresolved = unresolved_gates(state)
    if unresolved:
        sys.stderr.write("cannot finalize: unresolved gate(s): %s. Pass them, log an override, or run `cancel`.\n" % ", ".join(unresolved))
        sys.exit(3)
    short = references_shortfall(state, run_dir(a.file))
    if short is not None:
        sys.stderr.write("cannot finalize: references gate reads pass but only %d of %d references resolve. "
                         "Record them with `references --add`, or log an override.\n" % (short, REFERENCES_MIN))
        sys.exit(3)
    ps = pick_shortfall(state)
    if ps is not None:
        sys.stderr.write("cannot finalize: %s. Register the slate with `candidate --add`, record the "
                         "direction, and pick again.\n" % ps)
        sys.exit(3)
    code = drawing_scan_code(a.file)
    if code is None or code not in (0, 2, 3):
        sys.stderr.write("cannot finalize: could not verify the build is free of hand-drawn canvas "
                         "(drawing_check unavailable or errored, exit=%s). Fail-closed: fix the "
                         "scanner or run `cancel`.\n" % code)
        sys.exit(3)
    if code == 3:
        sys.stderr.write("cannot finalize: hand-drawn <canvas> detected in the build (non-overridable, even with a no_drawing override). Remove it and source the visual from a component, mcp-image, or clean type.\n")
        sys.exit(3)
    if code == 2 and ((state.get("gates") or {}).get("no_drawing") or {}).get("status") != "overridden":
        sys.stderr.write("cannot finalize: hand-authored illustration-scale SVG in the build and no_drawing is not overridden. Fix it or log an override with a reason.\n")
        sys.exit(3)
    overrides = [g for g, v in (state.get("gates") or {}).items()
                 if isinstance(v, dict) and v.get("status") == "overridden"]
    os.remove(a.file)
    msg = "run finalized for '%s'; %s removed." % (state.get("project"), a.file)
    if overrides:
        msg += " Shipped with override(s): %s." % ", ".join(overrides)
    print(msg)
    sys.exit(0)


def cmd_vendored(a):
    # Record files/dirs written by component-library installs so drawing_check exempts them
    # (their raw svg/canvas is sanctioned copy-paste, not hand-drawing).
    state = load(a.file)
    if not isinstance(state.get("vendored"), list):
        state["vendored"] = []
    # VALIDATE. drawing_check exempts these by path PREFIX, so an unvalidated `--add .` (or "..",
    # or "/") exempted the entire repo and silently disabled the scanner in one command
    # (2026-09-08 audit). An entry must exist and live strictly INSIDE the run directory.
    base_real = os.path.realpath(run_dir(a.file))
    bad = []
    for p in (a.add or []):
        q = p.strip() if isinstance(p, str) else ""
        if not q:
            continue
        full = os.path.realpath(q if os.path.isabs(q) else os.path.join(base_real, q))
        if not os.path.exists(full):
            bad.append("%s (does not exist)" % q)
        elif full == base_real or not full.startswith(base_real + os.sep):
            bad.append("%s (is the run dir or outside it — that would exempt everything)" % q)
    if bad:
        sys.stderr.write("HALT: refusing to record vendored path(s): %s\n" % "; ".join(bad))
        sys.exit(3)
    added = [p.strip() for p in (a.add or [])
             if isinstance(p, str) and p.strip() and p.strip() not in state["vendored"]]
    state["vendored"].extend(added)
    save(a.file, state)
    print("vendored paths recorded (+%d, total %d): %s" % (len(added), len(state["vendored"]), ", ".join(added) or "(none)"))


def cmd_references(a):
    # Record the vision references actually loaded for this run. The references gate counts
    # THIS array, so a local path that does not exist is refused: otherwise the count could be
    # padded with names and the gate would be back to passing on assertion.
    state = load(a.file)
    if not isinstance(state.get("references"), list):
        state["references"] = []
    base = run_dir(a.file)
    bad = [p for p in (a.add or []) if p and p.strip() and not reference_is_real(p, base)]
    if bad:
        sys.stderr.write("HALT: reference(s) do not resolve: %s. Record an existing screenshot path "
                         "(relative to the run file) or an http(s) URL — a bare name does not count.\n"
                         % ", ".join(bad))
        sys.exit(3)
    # Dedupe against the existing array AND within this batch (the same path passed twice
    # in one call must not count twice).
    added = []
    for p in (a.add or []):
        q = p.strip() if isinstance(p, str) else ""
        if q and q not in state["references"] and q not in added:
            added.append(q)
    state["references"].extend(added)
    save(a.file, state)
    n = references_count(state, base)
    print("references recorded (+%d, total %d of %d needed): %s"
          % (len(added), n, REFERENCES_MIN, ", ".join(added) or "(none)"))
    if n < REFERENCES_MIN:
        print("  %d more needed before the references gate can pass." % (REFERENCES_MIN - n))


def cmd_pick(a):
    # The ONLY way to resolve human_pick. Records WHICH candidate the human chose, so the run
    # file says what was picked instead of merely that something was.
    if not a.candidate or not a.candidate.strip():
        sys.stderr.write("HALT: pick requires --candidate <id> (which candidate the human chose).\n")
        sys.exit(3)
    state = load(a.file)
    if not isinstance(state.get("gates"), dict):
        sys.stderr.write("HALT: run file has no gates object.\n")
        sys.exit(3)
    cid = a.candidate.strip()
    if direction_of(state) is None:
        sys.stderr.write("HALT: no direction recorded, so there is nothing legitimate to pick from. Cheapest "
                         "choice first: register >=%d cheap candidates from different wells (`candidate --add "
                         "... --fidelity cheap`), get the human's direction (`direction --candidate <id>`), "
                         "build ONLY that, then pick. If the human named the direction up front, record it: "
                         "`direction --given '<their words>'`.\n" % SLATE_MIN)
        sys.exit(3)
    built = [c for c in slate(state) if c.get("fidelity") == "built"]
    if not built:
        sys.stderr.write("HALT: nothing built is registered. Record what the human is choosing from: "
                         "`candidate --add <id> --source <lib> --archetype <a> --fidelity built`.\n")
        sys.exit(3)
    if cid not in [c.get("id") for c in built]:
        sys.stderr.write("HALT: candidate %r is not in the built slate %s. Register it first, or pick one "
                         "of those.\n" % (cid, [c.get("id") for c in built]))
        sys.exit(3)
    state["picked_candidate"] = a.candidate.strip()
    state["gates"]["human_pick"] = {"status": "pass", "detail": a.candidate.strip(),
                                    "override_reason": None}
    save(a.file, state)
    print("human_pick -> pass (candidate: %s)" % a.candidate.strip())


def cmd_resting_ok(a):
    # ONE definition of "is this run legitimately parked on a human choice?". The Stop hook used
    # to re-implement this over the run file's own keys, so the two could disagree. Prints the
    # kind ("direction" or "final") on stdout so the hook can say what the human is being asked.
    state = load(a.file)
    kind = resting_kind(state)
    if kind:
        print(kind)
        sys.exit(0)
    sys.exit(1)


def _token(val, flag):
    v = (val or "").strip().lower()
    if not TOKEN_RE.match(v):
        sys.stderr.write("HALT: %s must be a short lowercase token (e.g. aceternity, magicui, mcp-image; "
                         "type-led, photo-led, motion-led, component-grid, generated-imagery), got %r.\n" % (flag, val))
        sys.exit(3)
    return v


def cmd_candidate(a):
    # The slate writer. Every candidate the human will choose from is registered here with its
    # provenance, so the direction rules (cheap first, divergent, capped) can be checked instead of
    # trusted. `--add` needs --source, --archetype and --fidelity; `--drop` removes; `--list` prints.
    state = load(a.file)
    cands = slate(state)
    state["candidates"] = cands
    d = direction_of(state)
    if a.list_:
        stage = "final (direction: %s)" % (d.get("candidate") or "given by the human") if d else "direction"
        print("slate (%d of %d, stage: %s)" % (len(cands), SLATE_MAX, stage))
        for c in cands:
            print("  %-8s %-14s %-18s %-6s %s" % (c.get("id"), c.get("source"), c.get("archetype"), c.get("fidelity"), c.get("note") or ""))
        if d is None:
            v = slate_violations(cands)
            print("direction slate: " + ("VALID; record the human's choice with `direction --candidate <id>`" if not v else "NOT valid: " + "; ".join(v)))
        sys.exit(0)
    if a.drop:
        keep = [c for c in cands if c.get("id") != a.drop.strip()]
        if len(keep) == len(cands):
            sys.stderr.write("HALT: no candidate %r in the slate.\n" % a.drop)
            sys.exit(3)
        state["candidates"] = keep
        save(a.file, state)
        print("candidate %s dropped (%d left)" % (a.drop.strip(), len(keep)))
        sys.exit(0)
    if not a.add:
        sys.stderr.write("HALT: candidate needs --add <id> (with --source, --archetype, --fidelity), --drop <id>, or --list.\n")
        sys.exit(3)
    cid = a.add.strip()
    if not ID_RE.match(cid):
        sys.stderr.write("HALT: --add id must be a short token like A, B, v2 (got %r).\n" % a.add)
        sys.exit(3)
    if not a.fidelity:
        sys.stderr.write("HALT: --fidelity cheap|built is required: cheap = a reference/demo screenshot or at most one "
                         "static render, no integration; built = integrated into the real repo.\n")
        sys.exit(3)
    source = _token(a.source, "--source")
    archetype = _token(a.archetype, "--archetype")
    if any(c.get("id") == cid for c in cands):
        sys.stderr.write("HALT: candidate %s is already in the slate; `candidate --drop %s` first.\n" % (cid, cid))
        sys.exit(3)
    if len(cands) >= SLATE_MAX:
        sys.stderr.write("HALT: the slate is full (SLATE_MAX=%d). Choose before making more: get the direction or the "
                         "pick, or drop one. Eight covers were once built before anyone had chosen; that is the "
                         "failure this cap exists for.\n" % SLATE_MAX)
        sys.exit(3)
    if a.fidelity == "built" and d is None:
        sys.stderr.write("HALT: a BUILT candidate before any direction is chosen. Cheapest choice first: register "
                         ">=%d cheap candidates from different wells, get the human's direction with `direction "
                         "--candidate <id>`, then build ONLY that. If the human named the direction up front, record "
                         "it: `direction --given '<their words>'`.\n" % SLATE_MIN)
        sys.exit(3)
    if a.fidelity == "cheap" and d is not None:
        sys.stderr.write("HALT: the direction is already chosen (%s); register what you BUILT for it (--fidelity "
                         "built). To go back to the direction stage, `direction --clear`.\n"
                         % (d.get("candidate") or "given by the human"))
        sys.exit(3)
    cands.append({"id": cid, "source": source, "archetype": archetype, "fidelity": a.fidelity,
                  "note": (a.note or "").strip() or None})
    save(a.file, state)
    print("candidate %s registered (%d of %d): %s / %s / %s" % (cid, len(cands), SLATE_MAX, source, archetype, a.fidelity))
    if d is None:
        v = slate_violations(cands)
        print("  direction slate " + ("VALID: show it to the human as ONE contact sheet, then `direction --candidate <id>`."
                                      if not v else "not yet valid: " + "; ".join(v)))
    sys.exit(0)


def cmd_direction(a):
    # Records WHICH direction gets built. Either the human's choice from a valid cheap slate
    # (--candidate), or the direction the human stated up front (--given). --clear returns to the
    # direction stage (drops the slate). Choosing a direction empties the slate: what follows is
    # the built slate for that direction only.
    state = load(a.file)
    if a.clear:
        state["direction"] = None
        state["candidates"] = []
        save(a.file, state)
        print("direction cleared; back to the direction stage with an empty slate.")
        sys.exit(0)
    if a.given is not None:
        if not a.given.strip():
            sys.stderr.write("HALT: --given needs the human's words (non-empty).\n")
            sys.exit(3)
        state["direction"] = {"candidate": None, "given": a.given.strip(), "slate": []}
        state["candidates"] = []
        save(a.file, state)
        print("direction recorded from the human's words: %r. Build ONLY this; register what you build with "
              "`candidate --add <id> ... --fidelity built` (at most %d)." % (a.given.strip(), SLATE_MAX))
        sys.exit(0)
    cands = slate(state)
    v = slate_violations(cands)
    if v:
        sys.stderr.write("HALT: not a valid direction slate: %s. Fix the slate (`candidate --add/--drop`) before "
                         "recording a direction.\n" % "; ".join(v))
        sys.exit(3)
    cid = (a.candidate or "").strip()
    if cid not in [c.get("id") for c in cands]:
        sys.stderr.write("HALT: %r is not in the slate %s.\n" % (cid, [c.get("id") for c in cands]))
        sys.exit(3)
    prev = direction_of(state)
    state["direction"] = {"candidate": cid, "given": None, "slate": cands}
    state["candidates"] = []
    save(a.file, state)
    chosen = next(c for c in cands if c.get("id") == cid)
    print("direction -> %s (%s / %s) from a slate of %d%s. Build ONLY this direction; register what you build "
          "with `candidate --add <id> ... --fidelity built` (at most %d, variants only if the human asked)."
          % (cid, chosen.get("source"), chosen.get("archetype"), len(cands),
             "; replaces the earlier direction" if prev else "", SLATE_MAX))
    sys.exit(0)


def cmd_brief_ok(a):
    # Build gate: refuse to build until the human-approved brief is locked (Stage 1).
    # Contract parity: a gate exits via pass OR overridden(reason), so an explicit
    # override also unblocks the build, loudly.
    state = load(a.file)
    g = state["gates"].get("brief", {})
    if g.get("status") == "pass":
        sys.exit(0)
    if g.get("status") == "overridden":
        print("WARNING: building WITHOUT a locked brief. Override reason: %s" % g.get("override_reason"))
        sys.exit(0)
    sys.stderr.write("HALT: no locked brief. Run Stage 1 brief-lock and get human approval before any build.\n")
    sys.exit(3)


def main():
    ap = argparse.ArgumentParser(description="design-run fail-loud state machine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--file", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--surface", default="web", choices=["web", "app", "marketing-asset", "deck"])
    p.add_argument("--brand-kit", dest="brand_kit", default=None); p.set_defaults(fn=cmd_init)

    p = sub.add_parser("gate"); p.add_argument("--file", required=True)
    p.add_argument("--name", required=True); p.add_argument("--status", required=True, choices=["pass", "fail"])
    p.add_argument("--detail", default=None); p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("override"); p.add_argument("--file", required=True)
    p.add_argument("--gate", required=True); p.add_argument("--reason", required=True); p.set_defaults(fn=cmd_override)

    p = sub.add_parser("ship-check"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_ship_check)

    p = sub.add_parser("done"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_done)

    p = sub.add_parser("cancel"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_cancel)

    p = sub.add_parser("vendored"); p.add_argument("--file", required=True)
    p.add_argument("--add", nargs="*", default=[]); p.set_defaults(fn=cmd_vendored)

    p = sub.add_parser("references"); p.add_argument("--file", required=True)
    p.add_argument("--add", nargs="*", default=[]); p.set_defaults(fn=cmd_references)

    p = sub.add_parser("pick"); p.add_argument("--file", required=True)
    p.add_argument("--candidate", required=True); p.set_defaults(fn=cmd_pick)

    p = sub.add_parser("candidate"); p.add_argument("--file", required=True)
    p.add_argument("--add", default=None, metavar="ID"); p.add_argument("--drop", default=None, metavar="ID")
    p.add_argument("--list", dest="list_", action="store_true")
    p.add_argument("--source", default=None); p.add_argument("--archetype", default=None)
    p.add_argument("--fidelity", default=None, choices=list(FIDELITIES)); p.add_argument("--note", default=None)
    p.set_defaults(fn=cmd_candidate)

    p = sub.add_parser("direction"); p.add_argument("--file", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--candidate", default=None); g.add_argument("--given", default=None)
    g.add_argument("--clear", action="store_true"); p.set_defaults(fn=cmd_direction)

    p = sub.add_parser("resting-ok"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_resting_ok)

    p = sub.add_parser("brief-ok"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_brief_ok)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
