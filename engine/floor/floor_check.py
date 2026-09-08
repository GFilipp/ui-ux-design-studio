#!/usr/bin/env python3
"""Deterministic FLOOR checks for the UI/UX design studio (brand-agnostic).

Reads an extraction JSON produced by engine/floor/extract.js (run in the rendered
page) and evaluates objective gates only:

  - contrast : WCAG 2.1 AA ratio per text node vs its effective background
  - orphans  : a heading/text block whose last visual line is a single word
  - layout   : horizontal overflow / off-screen elements (broken layout)
  - assets   : visible <img> slots that are empty or failed to load

These are OBJECTIVE. The machine owns this floor. Taste ("is it world-class?")
is never scored here; that is the human's call. Exits 2 if any blocking gate fails
so the loop / hook can gate on it.
"""
import argparse
import json
import sys


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    return 0.2126 * _lin(rgb["r"]) + 0.7152 * _lin(rgb["g"]) + 0.0722 * _lin(rgb["b"])


def contrast(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def is_large(font_size, font_weight):
    return font_size >= 24 or (font_size >= 18.66 and font_weight >= 700)


def owns_text(n):
    # A parent whose visible text lives entirely in an inline child reports that text paired with
    # the PARENT's color, which produced contrast "failures" on text that was perfectly readable
    # (and unfixable by recoloring). The inline child covers that text with the right color.
    return n.get("ownsDirectText", True)


def check_contrast(nodes):
    fails, indeterminate = [], []
    for n in nodes:
        if not owns_text(n):
            continue  # its inline child reports the same text with the correct color
        if not n.get("color") or not n.get("bg"):
            continue
        if n.get("bgImage"):
            indeterminate.append({"text": n["text"], "rect": n["rect"]})
            continue
        ratio = contrast(n["color"], n["bg"])
        need = 3.0 if is_large(n["fontSize"], n["fontWeight"]) else 4.5
        if ratio + 1e-6 < need:
            fails.append({
                "text": n["text"], "ratio": round(ratio, 2), "need": need,
                "fontSize": n["fontSize"], "rect": n["rect"],
            })
    return fails, indeterminate


def check_orphans(nodes):
    # An orphan (a single word alone on the last visual line) is a defect for HEADINGS and
    # short display lines, not for natural body-paragraph rag. Only flag heading-like text:
    # large/bold display type, or short blocks (<= 6 words). Long paragraphs are exempt.
    out = []
    for n in nodes:
        if n.get("lastLineWords") != 1 or n.get("totalWords", 0) <= 1:
            continue
        # Orphans apply to BLOCK-LEVEL display text (headings/standalone lines), not inline
        # emphasis (<b>/<em>/<span>) or labels inside flowing text.
        if n.get("display") == "inline":
            continue
        heading_like = is_large(n.get("fontSize", 0), n.get("fontWeight", 400)) or n.get("totalWords", 0) <= 6
        if heading_like:
            out.append({"text": n["text"], "tag": n["tag"]})
    return out


def check_layout(overflow):
    issues = []
    if overflow.get("horizontal"):
        issues.append("horizontal-scroll")
    if overflow.get("offscreenRight", 0) > 0:
        issues.append("offscreen-right:%d" % overflow["offscreenRight"])
    return issues


def check_assets(images):
    return [
        {"src": i.get("src", ""), "alt": i.get("alt", "")}
        for i in images
        if i.get("visible") and (not i.get("src") or i.get("naturalWidth", 0) == 0)
    ]


def check_console(data):
    # Runtime errors captured by render.mjs (pageerror + console.error). Blocking when captured.
    # Extracts without the key (older fixtures, extract.js run outside render.mjs) are "not-captured".
    cons = data.get("console")
    if cons is None:
        return None, []
    errors = int(cons.get("pageErrors", 0)) + int(cons.get("consoleErrors", 0))
    return errors, cons.get("samples", [])


def check_style(nodes):
    # WARN-ONLY: rare em dashes are fine; a pileup is the AI tell. Never blocks.
    n = sum(node.get("text", "").count("—") for node in nodes if owns_text(node))
    return n


def check_graphics(data):
    # WARN-ONLY runtime census. Provenance is impossible at runtime (a library's animated-SVG
    # background looks like hand-drawn art), so this NEVER blocks. Source-level enforcement is
    # drawing_check.py; here we surface a mandatory human-review line for the Stage-3 pick.
    g = data.get("graphics")
    if g is None:
        return {"status": "not-captured", "large_svgs": 0, "canvases": 0, "note": None}
    big = [s for s in g.get("svgs", []) if s.get("areaPct", 0) >= 15 and s.get("shapes", 0) >= 6]
    canvases = g.get("canvases", [])
    if not big and not canvases:
        return {"status": "pass", "large_svgs": 0, "canvases": 0, "note": None}
    note = ("runtime census: %d large on-screen SVG(s) and %d canvas(es); CONFIRM these are library "
            "components or mcp-image output, not hand-drawn (drawing_check.py enforces at source level)"
            % (len(big), len(canvases)))
    return {"status": "warn", "large_svgs": len(big), "canvases": len(canvases), "note": note}



# --- UX-law derived checks (2026-09-08) -------------------------------------------------
# Only the laws that are OBJECTIVELY measurable are gates. The judgment-level laws (attention
# order, one dominant element, Gestalt grouping) live in the brief + DNA rubric because they
# need a human; encoding them as thresholds would fake precision we do not have.
#
# Fitts's law: a tap target smaller than the platform minimum is slower and error-prone. Apple
# HIG says 44pt, Material 48dp, WCAG 2.5.5 (AAA) 44px. 44 on TOUCH breakpoints; desktop pointers
# are precise, so there it only warns.
TAP_MIN = 44
TAP_MIN_DESKTOP = 24          # WCAG 2.5.8 (AA) floor, warn-only on pointer breakpoints
TYPE_MIN_BLOCK = 12           # below this, body copy is indefensible on a phone
TYPE_MIN_WARN = 15            # 15 and under reads small on mobile; judgment, so warn
MEASURE_MAX_WARN = 100        # characters per line; comfortable body measure is ~45-75
MEASURE_MAX_BLOCK = 130       # beyond this, line tracking genuinely breaks down
BLOCK_WORDS_WARN = 120        # one text block this long is a wall of text (RULES 5)
CHOICES_WARN = 10             # Miller: a single choice set beyond ~7+-2 stops being scannable
NAV_LINKS_WARN = 7            # Hick: primary nav beyond 7 slows every decision


def is_touch(breakpoint, viewport):
    if breakpoint:
        return breakpoint.lower() in ("mobile", "phone", "touch", "tablet")
    return (viewport or {}).get("w", 9999) < 768


def check_targets(controls, touch):
    # Fitts. Inline prose links are excluded: they are text, not standalone hit areas, and
    # judging them at 44px would flag every link in a paragraph.
    minimum = TAP_MIN if touch else TAP_MIN_DESKTOP
    small = []
    for c in controls or []:
        if c.get("inlineInProse"):
            continue
        r = c.get("rect") or {}
        w, h = r.get("w", 0), r.get("h", 0)
        if w <= 0 or h <= 0:
            continue
        if min(w, h) < minimum:
            small.append({"tag": c.get("tag"), "label": c.get("label"),
                          "w": w, "h": h, "need": minimum})
    return small, minimum


def check_type_size(nodes, touch):
    # Readability floor. Only real copy, and only on touch breakpoints.
    if not touch:
        return [], []
    blocking, warn = [], []
    for n in nodes:
        if not n.get("ownsDirectText", True) or n.get("totalWords", 0) < 3:
            continue
        fs = n.get("fontSize") or 0
        if fs and fs < TYPE_MIN_BLOCK:
            blocking.append({"text": n.get("text"), "fontSize": fs, "need": TYPE_MIN_BLOCK})
        elif fs and fs <= TYPE_MIN_WARN:
            warn.append({"text": n.get("text"), "fontSize": fs})
    return blocking, warn


def check_measure(nodes):
    # Characters per line. Long measure is the readability half of "no walls of text" (RULES 5).
    blocking, warn = [], []
    for n in nodes:
        if not n.get("ownsDirectText", True):
            continue
        lines, chars = n.get("lineCount"), n.get("chars")
        if not lines or not chars or chars < MEASURE_MAX_WARN:
            continue  # short text cannot have a bad measure; a LONG single line certainly can
        if is_large(n.get("fontSize", 0), n.get("fontWeight", 400)):
            continue  # display type is set to a different measure on purpose
        cpl = chars / float(lines)
        if cpl >= MEASURE_MAX_BLOCK:
            blocking.append({"text": n.get("text"), "cpl": round(cpl), "need": MEASURE_MAX_WARN})
        elif cpl >= MEASURE_MAX_WARN:
            warn.append({"text": n.get("text"), "cpl": round(cpl)})
    return blocking, warn


def check_density(nodes):
    # The other half of RULES 5: one enormous block of prose. WARN — "visual-first" is a
    # judgment the human owns; only the extreme is worth flagging mechanically.
    return [{"text": n.get("text"), "words": n.get("totalWords")}
            for n in nodes
            if n.get("ownsDirectText", True) and n.get("totalWords", 0) >= BLOCK_WORDS_WARN]


def check_choices(groups):
    # Hick + Miller. WARN only: a 12-logo wall or a long feature grid can be right, so this
    # surfaces the choice-set size for the human rather than pretending to know the answer.
    out = []
    for g in groups or []:
        if (g.get("children") or 0) >= CHOICES_WARN:
            out.append({"tag": g.get("tag"), "children": g["children"], "kind": "group"})
        if (g.get("navLinks") or 0) > NAV_LINKS_WARN:
            out.append({"tag": g.get("tag"), "navLinks": g["navLinks"], "kind": "nav"})
    return out


def evaluate(data, require_assets=False, allow_indeterminate=False, breakpoint=None):
    nodes = data.get("textNodes", [])
    touch = is_touch(breakpoint, data.get("viewport"))
    small_targets, tap_min = check_targets(data.get("controls"), touch)
    type_block, type_warn = check_type_size(nodes, touch)
    measure_block, measure_warn = check_measure(nodes)
    density = check_density(nodes)
    choices = check_choices(data.get("groups"))
    cfails, cindet = check_contrast(nodes)
    orphans = check_orphans(nodes)
    layout = check_layout(data.get("overflow", {}))
    broken = check_assets(data.get("images", []))
    console_errors, console_samples = check_console(data)
    em_dashes = check_style(nodes)
    graphics = check_graphics(data)
    # Indeterminate = text over a background image; not a silent pass. It blocks as "review"
    # (the human overrides in run_state if the overlay is genuinely readable) unless explicitly allowed.
    if cfails:
        contrast_status = "fail"
    elif cindet and not allow_indeterminate:
        contrast_status = "review"
    else:
        contrast_status = "pass"
    console_fail = console_errors is not None and console_errors > 0
    blocking = bool(contrast_status in ("fail", "review") or orphans or layout
                    or (require_assets and broken) or console_fail
                    or small_targets or type_block or measure_block)
    return {
        "passed": not blocking,
        "gates": {
            "contrast": {"status": contrast_status,
                         "failures": cfails, "indeterminate": cindet},
            "orphans": {"status": "fail" if orphans else "pass", "failures": orphans},
            "layout": {"status": "fail" if layout else "pass", "issues": layout},
            "assets": {"status": "fail" if (require_assets and broken) else "pass",
                       "broken": broken},
            "console": {"status": ("not-captured" if console_errors is None
                                   else ("fail" if console_fail else "pass")),
                        "errors": console_errors, "samples": console_samples},
            # warn-only: never contributes to `passed`
            "style": {"status": "warn" if em_dashes >= 3 else "pass",
                      "em_dashes": em_dashes,
                      "note": ("em-dash pileup (%d); rare is fine, this reads as the AI default connector" % em_dashes)
                              if em_dashes >= 3 else None},
            # Fitts's law — BLOCKING on touch breakpoints.
            "targets": {"status": "fail" if small_targets else "pass",
                        "minimum": tap_min, "touch": touch, "small": small_targets},
            # readability floor — BLOCKING under 12px, warn to 15px (touch only)
            "type_size": {"status": "fail" if type_block else ("warn" if type_warn else "pass"),
                          "too_small": type_block, "small": type_warn},
            # measure / characters per line — the readability half of RULES 5
            "measure": {"status": "fail" if measure_block else ("warn" if measure_warn else "pass"),
                        "too_wide": measure_block, "wide": measure_warn},
            # warn-only: wall-of-text density (RULES 5); "visual-first" stays a human call
            "density": {"status": "warn" if density else "pass", "long_blocks": density},
            # warn-only: Hick/Miller choice-set size
            "choices": {"status": "warn" if choices else "pass", "oversized": choices},
            # warn-only runtime census; drawing_check.py owns the blocking source-level gate
            "drawing": graphics,
        },
        "summary": {
            "contrast_failures": len(cfails),
            "contrast_indeterminate": len(cindet),
            "orphans": len(orphans),
            "layout_issues": len(layout),
            "broken_assets": len(broken),
            "console_errors": console_errors,
            "em_dashes": em_dashes,
            "runtime_large_svgs": graphics["large_svgs"],
            "runtime_canvases": graphics["canvases"],
            "small_targets": len(small_targets),
            "type_too_small": len(type_block),
            "measure_too_wide": len(measure_block),
            "long_text_blocks": len(density),
            "oversized_choice_sets": len(choices),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Deterministic floor checks.")
    ap.add_argument("extract_json", help="path to extract.js output JSON")
    ap.add_argument("--breakpoint", default="desktop")
    ap.add_argument("--require-assets", action="store_true",
                    help="fail if any visible img slot is empty/broken")
    ap.add_argument("--allow-indeterminate", action="store_true",
                    help="treat text-over-image (indeterminate contrast) as pass instead of review")
    ap.add_argument("--out", help="write result JSON to this path")
    a = ap.parse_args()
    with open(a.extract_json) as f:
        data = json.load(f)
    result = evaluate(data, require_assets=a.require_assets,
                      allow_indeterminate=a.allow_indeterminate, breakpoint=a.breakpoint)
    result["breakpoint"] = a.breakpoint
    out = json.dumps(result, indent=2)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out)
    print(out)
    sys.exit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
