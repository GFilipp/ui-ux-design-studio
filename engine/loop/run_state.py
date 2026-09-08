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
  run_state.py pick     --file design-run.json --candidate B   # the ONLY way to resolve human_pick
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
        return json.load(f)


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
        "gates": {g: {"status": "halted", "detail": None, "override_reason": None} for g in GATES},
    }
    state["gates"]["brand_kit"] = {"status": "pass", "detail": a.brand_kit, "override_reason": None}
    save(a.file, state)
    print("initialized run for '%s' (%s) with brand kit %s (base_sha=%s)"
          % (a.project, a.surface, a.brand_kit, state["base_sha"] or "n/a"))


def cmd_gate(a):
    state = load(a.file)
    if not isinstance(state.get("gates"), dict) or a.name not in state["gates"]:
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
    if not isinstance(state.get("gates"), dict) or a.gate not in state["gates"]:
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
    state["picked_candidate"] = a.candidate.strip()
    state["gates"]["human_pick"] = {"status": "pass", "detail": a.candidate.strip(),
                                    "override_reason": None}
    save(a.file, state)
    print("human_pick -> pass (candidate: %s)" % a.candidate.strip())


def cmd_resting_ok(a):
    # ONE definition of "is this run legitimately parked at the human pick?". The Stop hook used
    # to re-implement this over the run file's own keys, so the two could disagree.
    state = load(a.file)
    unresolved = set(unresolved_gates(state))
    g = (state.get("gates") or {}).get("brief") or {}
    brief_ok = (g.get("status") if isinstance(g, dict) else g) in ("pass", "overridden")
    sys.exit(0 if (brief_ok and unresolved == {"human_pick"}) else 1)


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
    p.add_argument("--project", required=True); p.add_argument("--surface", default="web")
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

    p = sub.add_parser("resting-ok"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_resting_ok)

    p = sub.add_parser("brief-ok"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_brief_ok)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
