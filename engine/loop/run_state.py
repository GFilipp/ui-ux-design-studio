#!/usr/bin/env python3
"""design-run state machine — the fail-loud guardrail spine (brand-agnostic).

A run may exit a gate ONLY via `pass` or `overridden(reason)`. There is no silent
third path: a gate left `halted` blocks ship. Every override carries a reason and
is surfaced in the ship summary, so degradation is always visible and chosen.

Usage:
  run_state.py init   --file design-run.json --project NAME --surface web --brand-kit PATH
  run_state.py gate   --file design-run.json --name contrast --status pass|fail [--detail '...']
  run_state.py override --file design-run.json --gate contrast --reason "deadline; ship anyway"
  run_state.py ship-check --file design-run.json     # exit 0 ship-ok, 3 blocked
  run_state.py done   --file design-run.json          # finalize: all gates pass -> remove the file
  run_state.py cancel --file design-run.json          # ABORT: remove the file so the Stop hook stops gating
  run_state.py brief-ok --file design-run.json        # exit 0 if the brief gate is locked (pass), else 3 (build blocked)
"""
import argparse
import json
import os
import sys

GATES = ["brand_kit", "brief", "references", "assets", "contrast", "orphans", "layout", "responsive", "human_pick"]


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
    state = {
        "project": a.project,
        "surface": a.surface,
        "brand_kit": a.brand_kit,
        "references": [],
        "gates": {g: {"status": "halted", "detail": None, "override_reason": None} for g in GATES},
    }
    state["gates"]["brand_kit"] = {"status": "pass", "detail": a.brand_kit, "override_reason": None}
    save(a.file, state)
    print("initialized run for '%s' (%s) with brand kit %s" % (a.project, a.surface, a.brand_kit))


def cmd_gate(a):
    state = load(a.file)
    if a.name not in state["gates"]:
        sys.stderr.write("unknown gate: %s\n" % a.name)
        sys.exit(1)
    status = "pass" if a.status == "pass" else "halted"
    state["gates"][a.name] = {"status": status, "detail": a.detail, "override_reason": None}
    save(a.file, state)
    print("%s -> %s" % (a.name, status))
    sys.exit(0 if status == "pass" else 2)


def cmd_override(a):
    state = load(a.file)
    if a.gate not in state["gates"]:
        sys.stderr.write("unknown gate: %s\n" % a.gate)
        sys.exit(1)
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
    halted = [g for g, v in state["gates"].items() if v["status"] == "halted"]
    overrides = {g: v["override_reason"] for g, v in state["gates"].items() if v["status"] == "overridden"}
    print("=== ship summary: %s (%s) ===" % (state["project"], state["surface"]))
    print("brand kit: %s" % state["brand_kit"])
    for g in GATES:
        v = state["gates"][g]
        line = "  %-12s %s" % (g, v["status"])
        if v["status"] == "overridden":
            line += "  (reason: %s)" % v["override_reason"]
        print(line)
    if overrides:
        print("SHIPPED WITH %d OVERRIDE(S): %s" % (len(overrides), ", ".join(overrides)))
    if halted:
        print("BLOCKED — halted gates: %s. Pass them or log an override." % ", ".join(halted))
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
    halted = [g for g, v in state["gates"].items() if v["status"] == "halted"]
    if halted:
        sys.stderr.write("cannot finalize: halted gate(s): %s. Pass them, log an override, or run `cancel`.\n" % ", ".join(halted))
        sys.exit(3)
    overrides = [g for g, v in state["gates"].items() if v["status"] == "overridden"]
    os.remove(a.file)
    msg = "run finalized for '%s'; %s removed." % (state.get("project"), a.file)
    if overrides:
        msg += " Shipped with override(s): %s." % ", ".join(overrides)
    print(msg)
    sys.exit(0)


def cmd_brief_ok(a):
    # Build gate: refuse to build until the human-approved brief is locked (Stage 1).
    state = load(a.file)
    if state["gates"].get("brief", {}).get("status") == "pass":
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

    p = sub.add_parser("brief-ok"); p.add_argument("--file", required=True); p.set_defaults(fn=cmd_brief_ok)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
