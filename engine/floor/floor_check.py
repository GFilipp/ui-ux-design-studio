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


def check_contrast(nodes):
    fails, indeterminate = [], []
    for n in nodes:
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


def evaluate(data, require_assets=False):
    nodes = data.get("textNodes", [])
    cfails, cindet = check_contrast(nodes)
    orphans = check_orphans(nodes)
    layout = check_layout(data.get("overflow", {}))
    broken = check_assets(data.get("images", []))
    blocking = bool(cfails or orphans or layout or (require_assets and broken))
    return {
        "passed": not blocking,
        "gates": {
            "contrast": {"status": "fail" if cfails else "pass",
                         "failures": cfails, "indeterminate": cindet},
            "orphans": {"status": "fail" if orphans else "pass", "failures": orphans},
            "layout": {"status": "fail" if layout else "pass", "issues": layout},
            "assets": {"status": "fail" if (require_assets and broken) else "pass",
                       "broken": broken},
        },
        "summary": {
            "contrast_failures": len(cfails),
            "contrast_indeterminate": len(cindet),
            "orphans": len(orphans),
            "layout_issues": len(layout),
            "broken_assets": len(broken),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Deterministic floor checks.")
    ap.add_argument("extract_json", help="path to extract.js output JSON")
    ap.add_argument("--breakpoint", default="desktop")
    ap.add_argument("--require-assets", action="store_true",
                    help="fail if any visible img slot is empty/broken")
    ap.add_argument("--out", help="write result JSON to this path")
    a = ap.parse_args()
    with open(a.extract_json) as f:
        data = json.load(f)
    result = evaluate(data, require_assets=a.require_assets)
    result["breakpoint"] = a.breakpoint
    out = json.dumps(result, indent=2)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out)
    print(out)
    sys.exit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
