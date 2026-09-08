#!/usr/bin/env python3
"""drawing_check.py — provenance-aware anti-hand-drawing scanner (brand-agnostic).

The design studio forces Claude to source visuals from real component libraries,
generated imagery, brand assets, or clean type. This scanner is the objective
backstop against Claude HAND-DRAWING instead: raw inline <svg> illustrations,
<canvas> 2D drawing, and large inline data-URI SVG in files IT authored.

PROVENANCE FIRST, shape second. Component libraries like Aceternity and MagicUI
are copy-paste: their sanctioned effects (Background Beams, Meteors, dot grids)
land in source as raw <svg>/<canvas>, byte-identical to hand-drawing. Shape alone
cannot tell them apart. So vendored/library/brand-asset files are EXEMPT (skipped
entirely); only Claude-authored composition files are shape-checked.

Scope (honest): catches raw <svg>/<canvas>/data-URI primitives in authored files.
Does NOT catch styled-div "fake charts/dashboards" (no svg/canvas to see) or fully
rastered images; those are the human's Stage-3 brief-conformance call. A determined
author who deliberately moves hand-drawn art INTO a vendored dir (components/ui, ...)
evades by construction; the goal is to stop the lazy default, not an adversary who
edits provenance. The Stop hook + `done` enforce the canvas hard-block independently.

Modes:
  drawing_check.py <path> [<path> ...]        # explicit files/dirs
  drawing_check.py --git-diff [--base SHA]    # changed + untracked in the cwd repo
  (both honor --run-file design-run.json for base_sha / vendored[] / brand-kit logo)

Exit: 0 clean (warns allowed) | 2 block-soft (illustration SVG, overridable)
      | 3 block-hard (canvas 2D drawing, non-overridable) | 4 usage error (distinct from 2 on
      purpose: a scanner that never RAN must not read as a scanned-and-waived soft finding)
      | 5 degraded: no usable baseline, so committed work was not scanned — "cannot verify",
      never "clean" (one `git commit` used to empty the scan silently).
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse

SCAN_EXT = {".tsx", ".jsx", ".ts", ".js", ".mjs", ".cjs", ".mdx", ".html", ".htm",
            ".vue", ".svelte", ".astro", ".css", ".svg"}

# Directory segments never scanned (build output, deps, VCS).
EXCLUDE_SEGMENTS = {"node_modules", ".next", ".nuxt", "dist", "build", "out",
                    ".astro", ".git", ".turbo", ".vercel", ".output", "coverage"}

# Vendored/library component dirs are EXEMPT: raw svg/canvas there is the sanctioned
# copy-paste path (shadcn/aceternity/magicui/motion-primitives), not hand-drawing.
# Every entry is >=2 segments on purpose: a single generic segment like ("components",)
# would exempt authored page compositions under components/ (a real bypass).
#
# Only libraries that vendor into their OWN directory need an entry here:
#   - shadcn-registry installs (kibo-ui, and aceternity via its @aceternity namespace) land in
#     `aliases.ui`, covered by ("components","ui") + extra_vendored_from_components_json.
#   - npm-imported libraries (heroui via @heroui/react) live in node_modules, already excluded.
#   - flowbite is deliberately NOT here: its figma-to-code output is emitted INTO authored files,
#     so exempting it would be a bypass. Its emitted icons sit under the icon ceiling; a genuine
#     illustration-scale paste is a soft block you override with a reason.
# eldoraui / cult are speculative but harmless: they exempt only paths that must already exist.
VENDORED_SUBPATHS = [
    ("components", "ui"), ("components", "magicui"), ("components", "aceternity"),
    ("components", "motion-primitives"), ("components", "eldoraui"), ("components", "cult"),
]

MAX_BYTES = 256 * 1024

SHAPE_TAGS = ("path", "rect", "circle", "polygon", "polyline", "ellipse", "line")
# Canvas 2D drawing methods. getContext('2d') + any of these (or a Path2D) in an authored
# file = hand-drawing. Paired with getContext('2d') so a stray Array.fill()/.rect() is unlikely.
DRAW_PRIMS = ("fillRect", "strokeRect", "clearRect", "fillText", "strokeText", "beginPath",
              "closePath", "moveTo", "lineTo", "arcTo", "arc", "bezierCurveTo", "quadraticCurveTo",
              "roundRect", "rect", "ellipse", "drawImage", "putImageData", "fill", "stroke", "clip")

# Thresholds (applied only AFTER the provenance allowlist).
ICON_MAX_SHAPES = 4
ICON_MAX_D = 1200
ICON_MAX_VIEWBOX = 32
ILLUS_MIN_SHAPES = 8
ILLUS_MIN_TOTAL_D = 4000
ILLUS_MIN_SINGLE_D = 2500
DATAURI_WARN_BYTES, DATAURI_WARN_SHAPES = 2048, 6
DATAURI_BLOCK_BYTES, DATAURI_BLOCK_SHAPES = 4096, 12
DATAURI_BLOCK_BYTES_ANY = 8192  # a big inline svg data-URI is an illustration regardless of shape count

BOX_CHARS = set("░▒▓█▄▀│─┌┐└┘├┤┼╭╮╯╰═║╔╗╚╝╬╠╣╦╩")
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF\U00002190-\U000021FF\U00002B00-\U00002BFF]"
)

SEVERITY_RANK = {"warn": 0, "soft": 1, "hard": 2}
EXIT_FOR = {"warn": 0, "soft": 2, "hard": 3}


def run_git(args, cwd):
    try:
        p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "git not found"


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def path_parts(p):
    return [seg for seg in os.path.normpath(p).split(os.sep) if seg not in ("", ".")]


def rel_parts(abspath, root):
    # Path segments RELATIVE to the scan root. Matching exclusions/vendored dirs against the
    # ABSOLUTE path meant a repo living under any dir named build/out/dist/.next excluded every
    # file and voided the whole scan, invisibly (2026-09-08 audit).
    try:
        rel = os.path.relpath(os.path.abspath(abspath), os.path.abspath(root))
    except ValueError:  # different drive on Windows
        rel = os.path.abspath(abspath)
    return [seg for seg in rel.split(os.sep) if seg not in ("", ".")]


def is_excluded(parts):
    return any(seg in EXCLUDE_SEGMENTS for seg in parts)


def subpath_matches(parts, sub):
    # True if the consecutive segments `sub` appear anywhere in `parts`.
    n = len(sub)
    for i in range(len(parts) - n + 1):
        if tuple(parts[i:i + n]) == sub:
            return True
    return False


def load_run_config(run_file):
    # Pull base_sha, vendored[], and the brand-kit logo asset from a design-run.json.
    cfg = {"base": None, "vendored": [], "brand_assets": []}
    if not run_file or not os.path.exists(run_file):
        return cfg
    try:
        state = json.load(open(run_file))
    except Exception:
        return cfg
    cfg["base"] = state.get("base_sha")
    cfg["vendored"] = [v for v in (state.get("vendored", []) or []) if isinstance(v, str)]
    bk = state.get("brand_kit")
    if bk and os.path.exists(bk):
        try:
            kit = json.load(open(bk))
            asset = (kit.get("logo") or {}).get("asset")
            if asset:
                cfg["brand_assets"].append(
                    asset if os.path.isabs(asset) else os.path.normpath(os.path.join(os.path.dirname(bk), asset)))
        except Exception:
            pass
    return cfg


def extra_vendored_from_components_json(root):
    # Honor shadcn's components.json aliases.ui as an extra vendored subpath. Only the `ui`
    # alias, and only if it is >=2 segments — the generic `components` alias ("@/components")
    # would exempt authored page compositions, a real bypass, so we do NOT honor it.
    subs = []
    cj = os.path.join(root, "components.json")
    if os.path.exists(cj):
        try:
            data = json.load(open(cj))
            alias = (data.get("aliases") or {}).get("ui")
            if alias:
                parts = tuple(s for s in alias.lstrip("@~").lstrip("/").split("/") if s and s != ".")
                if len(parts) >= 2:
                    subs.append(parts)
        except Exception:
            pass
    return subs


def sanitize_vendored(abs_paths, root):
    # The run file is model-owned JSON and these entries exempt by PATH PREFIX, so an unvalidated
    # "." or ".." disabled the scanner entirely. Validated HERE (at consumption) rather than only
    # in run_state's writer, which the model can bypass by editing the JSON directly.
    rootr = os.path.realpath(root)
    kept, dropped = [], []
    for p in abs_paths:
        rp = os.path.realpath(p)
        if not os.path.exists(rp) or rp == rootr or not rp.startswith(rootr + os.sep):
            dropped.append(p)
        else:
            kept.append(rp)
    return kept, dropped


def is_vendored(abspath, vendored_abs, brand_abs, extra_subs, root="."):
    # Provenance allowlist. Path-prefix matching only (no basename fallback — matching by
    # basename would exempt every file of that name repo-wide). Segments are matched RELATIVE
    # to root so a repo living under e.g. /Users/x/components/ui/... is not blanket-exempt.
    parts = rel_parts(abspath, root)
    for sub in VENDORED_SUBPATHS + extra_subs:
        if subpath_matches(parts, sub):
            return "vendored-dir"
    norm = os.path.realpath(abspath)
    for v in vendored_abs:
        if norm == v or norm.startswith(v + os.sep):
            return "install-manifest"
    for b in brand_abs:
        if norm == b:
            return "brand-asset"
    return None


# ---- shape analysis ----

def analyze_svg_block(block):
    shapes = 0
    for tag in SHAPE_TAGS:
        shapes += len(re.findall(r"<%s\b" % tag, block, re.I))
    # Measurable string d attributes (double/single quoted). Negative lookbehind stops `data-d=`,
    # `stroke-d=` etc. from matching.
    dvals = re.findall(r'(?<![\w-])d\s*=\s*"([^"]*)"', block) + re.findall(r"(?<![\w-])d\s*=\s*'([^']*)'", block)
    # JSX expression d attributes: d={"..."} / d={'...'} / d={`...`} are measurable; d={expr} is not.
    d_expr_unmeasured = 0
    for m in re.finditer(r"(?<![\w-])d\s*=\s*\{", block):
        tail = block[m.end():m.end() + 4000]
        lit = re.match(r"\s*(['\"`])(.*?)\1", tail, re.S)
        if lit:
            dvals.append(lit.group(2))
        else:
            d_expr_unmeasured += 1
    total_d = sum(len(d) for d in dvals)
    max_d = max((len(d) for d in dvals), default=0)
    vw = vh = None
    m = re.search(r'viewBox\s*=\s*["\']?\s*[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)', block)
    if m:
        try:
            vw, vh = float(m.group(1)), float(m.group(2))
        except ValueError:
            vw = vh = None
    return shapes, total_d, max_d, vw, vh, d_expr_unmeasured


def classify_svg(shapes, total_d, max_d, vw, vh, d_expr):
    big = shapes >= ILLUS_MIN_SHAPES or total_d >= ILLUS_MIN_TOTAL_D or max_d >= ILLUS_MIN_SINGLE_D
    if big:  # illustration-scale always wins, even inside a small viewBox (anti-bypass)
        return "soft", "svg-illustration"
    tiny_viewbox = vw is not None and vh is not None and vw <= ICON_MAX_VIEWBOX and vh <= ICON_MAX_VIEWBOX
    if tiny_viewbox:
        return None, None  # explicitly icon-sized canvas
    if d_expr > 0:  # unmeasurable JSX d expression outside a tiny viewBox -> cannot certify an icon
        return "soft", "svg-illustration"
    if shapes <= ICON_MAX_SHAPES and total_d <= ICON_MAX_D:
        return None, None  # measured small icon
    return "warn", "svg-logo"  # logo band: surface, never block on shape alone


def decode_datauri(rest):
    # `rest` is everything after `data:image/svg+xml`, e.g. ";base64,XXXX" or ";charset=utf-8,%3C.."
    # or ",%3C..". Split media-type params from the data at the first comma; base64 ONLY if the
    # params contain `base64` (a bare `;` is a charset param, NOT base64).
    params, data = (rest.split(",", 1) + [""])[:2] if "," in rest else (rest, "")
    try:
        if "base64" in params.lower():
            return base64.b64decode(data + "===").decode("utf-8", "replace")
        return urllib.parse.unquote(data)
    except Exception:
        return data


def strip_comments(text):
    # Comments are not code. A doc comment mentioning getContext("2d") beside an unrelated
    # Array.fill() produced a soft block on a file that draws nothing.
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?m)//[^\n]*", " ", text)


def find_canvas2d_draw(text):
    text = strip_comments(text)
    # LAYERED, because both extremes are wrong:
    #   - matching getContext('2d') and ANY `.prim(` independently made `ctx.measureText()`
    #     beside an unrelated `Array(12).fill(0)` a NON-OVERRIDABLE block that wedged the run;
    #   - requiring the primitive on the bound identifier let real drawing escape entirely,
    #     e.g. `const c = el.getContext('2d'); paint(c)` with `ctx.arc()` inside the helper,
    #     or a simple alias `const d = g`. Verified false negatives, worse than over-blocking.
    # So: PROVABLE binding -> hard (non-overridable). Unprovable coexistence of a 2D context
    # and draw primitives -> soft (blocks, but a human can override with a reason).
    # Returns (line, why, severity) or None.
    prims = "|".join(DRAW_PRIMS)
    m = re.search(r"\bnew\s+Path2D\b", text)
    if m:
        return line_of(text, m.start()), "new Path2D", "hard"
    ctx2d = re.search(r"getContext\(\s*[\"'`]2d[\"'`]", text)
    if not ctx2d:
        return None
    # Chained straight off the call: getContext('2d')!.beginPath()
    m = re.search(r"getContext\(\s*[\"'`]2d[\"'`]\s*\)\s*[!?]?\s*\.\s*(%s)\s*\(" % prims, text)
    if m:
        return line_of(text, m.start()), m.group(1), "hard"
    # Bound to an identifier: const ctx = el.getContext('2d')  ->  ctx.fill(...)
    # Scan BACKWARD in a BOUNDED window. A forward pattern like `[^;\n=]*getContext\(`
    # backtracks catastrophically on one very long line (a 300KB padded line hung the
    # scanner for minutes), so the window is capped.
    ids = set()
    for gm in re.finditer(r"getContext\(\s*[\"'`]2d[\"'`]", text):
        head = text[max(0, gm.start() - 400):gm.start()]
        # Only the assignment whose RIGHT-HAND SIDE contains THIS getContext call counts. Taking
        # the last `X =` anywhere in the window bound unrelated locals: `const rows = new Array(12)`
        # before a getContext call made `rows.fill(0)` look like canvas drawing and produced a
        # NON-OVERRIDABLE false block. So cut back to the current statement first.
        frag = re.split(r"[;{}\n]", head)[-1]
        am = re.search(r"([A-Za-z_$][\w$.]*)\s*(?:!|\?)?\s*(?::[^=]{0,120})?"
                       r"(?<![!<>=+\-*/%&|^])=(?![=>])[^=]*$", frag)
        if am:
            ids.add(am.group(1).split(".")[-1])
    for ident in sorted(ids):
        m = re.search(r"\b%s\s*[!?]?\s*\.\s*(%s)\s*\(" % (re.escape(ident), prims), text)
        if m:
            return line_of(text, m.start()), m.group(1), "hard"
    # Cannot prove the binding, but a 2D context and draw primitives coexist in one authored
    # file. Too suspicious to pass, too unproven to be non-overridable.
    m = re.search(r"\.(%s)\s*\(" % prims, text)
    if m:
        return line_of(text, m.start()), m.group(1) + " (context binding unproven)", "soft"
    return None


def scan_text(rel, text):
    findings = []

    # 1) Canvas 2D drawing (highest precision -> hard). WebGL -> warn (three/shaders, not the threat).
    ctx2d = re.search(r"getContext\(\s*[\"'`]2d[\"'`]", text)
    hit = find_canvas2d_draw(text)
    if hit:
        line, why, sev = hit
        detail = ("getContext('2d') + draw primitive (%s) called on the context" % why) if sev == "hard" \
            else ("getContext('2d') and draw primitive (%s) in one authored file; could not prove "
                  "the primitive is called on the context, so this blocks softly — override with a "
                  "reason if it is genuinely not hand-drawing" % why)
        findings.append({"file": rel, "line": line, "kind": "canvas-2d", "severity": sev,
                         "detail": detail})
    else:
        webgl = re.search(r"getContext\(\s*[\"'`]webgl2?[\"'`]", text)
        if webgl:
            findings.append({"file": rel, "line": line_of(text, webgl.start()),
                             "kind": "canvas-webgl", "severity": "warn",
                             "detail": "getContext(webgl) — usually library/shader, confirm not hand-drawn"})

    # 2) Raw SVG injected via dangerouslySetInnerHTML (self-closing or not) -> hand-authored markup.
    for m in re.finditer(r"<svg\b[^>]*dangerouslySetInnerHTML", text, re.I):
        findings.append({"file": rel, "line": line_of(text, m.start()), "kind": "svg-injected", "severity": "soft",
                         "detail": "raw svg injected via dangerouslySetInnerHTML"})

    # 3) Inline <svg> blocks (or whole-file for .svg).
    is_svg_file = rel.lower().endswith(".svg")
    blocks = [(0, text)] if is_svg_file else [(m.start(), m.group(0))
                                              for m in re.finditer(r"<svg\b[^>]{0,2000}>.*?</svg>", text, re.S | re.I)]
    for start, block in blocks:
        shapes, total_d, max_d, vw, vh, d_expr = analyze_svg_block(block)
        sev, kind = classify_svg(shapes, total_d, max_d, vw, vh, d_expr)
        if sev:
            findings.append({"file": rel, "line": line_of(text, start), "kind": kind, "severity": sev,
                             "detail": "inline svg: %d shapes, total d=%d, max d=%d, d-exprs=%d, viewBox=%s"
                                       % (shapes, total_d, max_d, d_expr, ("%gx%g" % (vw, vh)) if vw else "n/a")})

    # 4) Inline data-URI SVG (CSS/JSX).
    for m in re.finditer(r"data:image/svg\+xml([^\"')\s]*)", text, re.I):
        decoded = decode_datauri(m.group(1))
        size = len(decoded)
        shapes = sum(len(re.findall(r"<%s\b" % t, decoded, re.I)) for t in SHAPE_TAGS)
        if (size >= DATAURI_BLOCK_BYTES and shapes >= DATAURI_BLOCK_SHAPES) or size >= DATAURI_BLOCK_BYTES_ANY:
            findings.append({"file": rel, "line": line_of(text, m.start()), "kind": "svg-datauri", "severity": "soft",
                             "detail": "data-URI svg: %dB, %d shapes" % (size, shapes)})
        elif size >= DATAURI_WARN_BYTES and shapes >= DATAURI_WARN_SHAPES:
            findings.append({"file": rel, "line": line_of(text, m.start()), "kind": "svg-datauri", "severity": "warn",
                             "detail": "data-URI svg: %dB, %d shapes" % (size, shapes)})

    # 5) ASCII / emoji art (warn only).
    lines = text.splitlines()
    run = 0
    for i, ln in enumerate(lines):
        if sum(1 for ch in ln if ch in BOX_CHARS) >= 8:
            run += 1
            if run == 4:
                findings.append({"file": rel, "line": i - 2, "kind": "ascii-art", "severity": "warn",
                                 "detail": "box-drawing block (>=4 lines)"})
        else:
            run = 0
    for m in re.finditer(r"(?:%s\s*){6,}" % EMOJI_RE.pattern, text):
        findings.append({"file": rel, "line": line_of(text, m.start()), "kind": "emoji-art", "severity": "warn",
                         "detail": "emoji used as a visual block (>=6)"})
        break
    return findings


def gather_git_diff(root, base):
    rc, out, _ = run_git(["rev-parse", "--show-toplevel"], root)
    if rc != 0:
        return None, False  # not a git repo -> caller falls back to full-tree
    top = out.strip()
    files = set()

    def add(args):
        rc, out, _ = run_git(args, top)
        if rc == 0:
            for ln in out.split("\0"):  # -z: NUL-separated, safe for odd filenames
                if ln.strip():
                    files.add(os.path.join(top, ln))
            return True
        return False

    add(["diff", "--name-only", "-z", "HEAD"])
    add(["diff", "--name-only", "-z", "--cached"])
    add(["ls-files", "--others", "--exclude-standard", "-z"])
    base_ok = add(["diff", "--name-only", "-z", "%s" % base, "HEAD"]) if base else False
    degraded = not base or not base_ok
    # NOTE: with no usable baseline we deliberately do NOT widen to `ls-files` (all tracked).
    # That fallback made pre-existing code the run never touched block `done` permanently and
    # non-overridably (2026-09-08 audit reproduced it in this very repo). Narrow coverage that
    # the operator is TOLD about beats a scan that wedges every run.
    # Bound to `root`: git commands run at the repo toplevel, so in a monorepo an unrelated
    # package's canvas code was blocking a run scoped to a sibling package.
    rootr = os.path.realpath(root)
    files = {f for f in files
             if os.path.realpath(f) == rootr or os.path.realpath(f).startswith(rootr + os.sep)}
    return sorted(files), degraded


def walk_tree(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_SEGMENTS]
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    return out


def eligible(abspath, root="."):
    if is_excluded(rel_parts(abspath, root)):
        return False
    base = os.path.basename(abspath)
    _, ext = os.path.splitext(abspath)
    if ext.lower() not in SCAN_EXT:
        return False
    # Skip only genuinely minified ASSETS (.min.js/.min.css), not authored .tsx named "*.min.*".
    if ext.lower() in (".js", ".css", ".mjs", ".cjs") and ".min." in base:
        return False
    return True


def collect_paths(explicit):
    out = []
    for p in explicit:
        if os.path.isdir(p):
            out.extend(walk_tree(p))
        else:
            out.append(p)
    return out


def resolve(root, items):
    return [p if os.path.isabs(p) else os.path.normpath(os.path.join(root, p)) for p in items]


class _UsageExit4(argparse.ArgumentParser):
    # argparse exits 2 on a usage error, which COLLIDES with our exit 2 = "soft finding".
    # The Stop hook read a scanner that never ran as a scanned-and-waived result
    # (2026-09-08 audit). Usage errors get their own code.
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        sys.exit(4)


def main():
    ap = _UsageExit4(description="Provenance-aware anti-hand-drawing scanner.")
    ap.add_argument("paths", nargs="*", help="explicit files/dirs to scan")
    ap.add_argument("--git-diff", action="store_true", help="scan changed + untracked web-source in the cwd repo")
    ap.add_argument("--base", default=None, help="baseline SHA for the git-diff (else HEAD + working tree + all tracked)")
    ap.add_argument("--root", default=".", help="repo/tree root for --git-diff (default cwd)")
    ap.add_argument("--run-file", default=None, help="design-run.json to read base_sha / vendored[] / brand kit from")
    ap.add_argument("--vendored", nargs="*", default=[], help="extra exempt paths (install manifest)")
    ap.add_argument("--brand-asset", nargs="*", default=[], help="extra exempt brand-asset paths")
    ap.add_argument("--out", default=None, help="write the JSON report here")
    ap.add_argument("--json", action="store_true", help="print JSON to stdout instead of the human summary")
    a = ap.parse_args()
    if not a.git_diff and not a.paths:
        ap.error("nothing to scan: pass paths or --git-diff")

    root = os.path.abspath(a.root)
    cfg = load_run_config(a.run_file)
    base = a.base or cfg["base"]
    vendored_abs, vendored_dropped = sanitize_vendored(resolve(root, list(a.vendored) + cfg["vendored"]), root)
    brand_abs = resolve(root, list(a.brand_asset) + cfg["brand_assets"])
    extra_subs = extra_vendored_from_components_json(root)

    fallback_note = None
    if a.git_diff:
        gathered, degraded = gather_git_diff(root, base)
        if gathered is None:
            fallback_note = "not a git repo; scanned the tree by extension"
            candidates = walk_tree(root)
        else:
            candidates = gathered
            if degraded:
                fallback_note = ("NO USABLE BASELINE (base_sha missing or unresolvable): scanned only "
                                 "working-tree changes + untracked files. Committed work was NOT "
                                 "re-scanned. Re-run `run_state.py init` inside the git repo for full coverage.")
    else:
        candidates = collect_paths(a.paths)

    findings, scanned, exempt = [], [], []
    for p in candidates:
        ap_ = os.path.abspath(p)
        if not os.path.isfile(ap_) or not eligible(ap_, root):
            continue
        reason = is_vendored(ap_, vendored_abs, brand_abs, extra_subs, root)
        rel = os.path.relpath(ap_, root)
        if reason:
            exempt.append({"file": rel, "reason": reason})
            continue
        try:
            size = os.path.getsize(ap_)
        except OSError:
            continue
        # Oversized files are SCANNED to the cap, not skipped. Skipping with severity "warn"
        # mapped to exit 0, so appending 256KB of padding downgraded the NON-OVERRIDABLE canvas
        # block to a clean pass (2026-09-08 audit). Scan the head, then block on the unscanned
        # remainder so the truncation itself can never be a silent pass.
        truncated = size > MAX_BYTES
        try:
            if truncated:
                # HEAD **and** TAIL: reading only the head meant padding PREPENDED to the file
                # pushed the drawing out of view and downgraded the hard block to soft.
                half = MAX_BYTES // 2
                with open(ap_, "rb") as fb:
                    head = fb.read(half)
                    fb.seek(max(half, size - half))
                    tail = fb.read()
                text = head.decode("utf-8", "replace") + "\n" + tail.decode("utf-8", "replace")
            else:
                with open(ap_, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
        except OSError:
            continue
        scanned.append(rel)
        findings.extend(scan_text(rel, text))
        if truncated:
            findings.append({"file": rel, "line": 1, "kind": "oversized-truncated", "severity": "soft",
                             "detail": "%dB > %dB: only the first and last %dB were scanned; the middle is "
                                       "unverified. Split the file or confirm it is not hand-drawn."
                                       % (size, MAX_BYTES, MAX_BYTES // 2)})

    counts = {"hard": 0, "soft": 0, "warn": 0}
    for f in findings:
        counts[f["severity"]] += 1
    code = 3 if counts["hard"] else (2 if counts["soft"] else 0)
    if code == 0 and fallback_note and fallback_note.startswith("NO USABLE BASELINE"):
        code = 5  # cannot verify committed work -> fail closed (run_state blocks on anything outside 0/2/3)

    report = {"exit": code, "scanned": len(scanned), "exempt": len(exempt),
              "counts": counts, "findings": findings, "exempt_files": exempt}
    if fallback_note:
        report["note"] = fallback_note
    if vendored_dropped:
        report["vendored_dropped"] = vendored_dropped

    if a.out:
        with open(a.out, "w") as f:
            f.write(json.dumps(report, indent=2))

    if a.json:
        print(json.dumps(report, indent=2))
    else:
        if fallback_note:
            print("note: %s" % fallback_note)
        print("drawing_check: scanned %d authored file(s), %d exempt (vendored/brand). hard=%d soft=%d warn=%d"
              % (len(scanned), len(exempt), counts["hard"], counts["soft"], counts["warn"]))
        for f in findings:
            print("  [%s] %s:%s  %s — %s" % (f["severity"].upper(), f["file"], f["line"], f["kind"], f["detail"]))
        if code == 3:
            print("BLOCK (hard): canvas 2D drawing in authored source. Use a real component "
                  "(aceternity/magicui background), generated imagery (mcp-image), or clean type. NOT overridable.")
        elif code == 2:
            print("BLOCK (soft): hand-authored illustration-scale SVG in authored source. Source it from a "
                  "component library, mcp-image, or a real brand asset. Override only with a logged reason.")
        elif counts["warn"]:
            print("OK with warnings: confirm the flagged items are library/generated, not hand-drawn.")
        else:
            print("OK: no hand-drawing detected.")
    sys.exit(code)


if __name__ == "__main__":
    main()
