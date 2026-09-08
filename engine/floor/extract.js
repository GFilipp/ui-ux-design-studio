// extract.js — run inside the rendered page (Chrome MCP execute_javascript / preview_eval).
// Returns a JSON string of deterministic inputs for the floor checks:
// text nodes (color, effective background, size, weight, rect, last-line word count),
// images / asset slots, and layout overflow signals. Brand-agnostic; no dependencies.
(function () {
  function rgbToArr(s) {
    if (!s) return null;
    var m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(",").map(function (x) { return parseFloat(x.trim()); });
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  // Walk ancestors to the first opaque background-color; note any background-image en route.
  function effectiveBg(el) {
    // Collect background layers from the element outward, then COMPOSITE semi-transparent
    // layers over the first opaque ancestor (or white). Without this, a tint like
    // rgba(254,108,45,.06) over a dark page reads as solid orange -> false contrast fails.
    var node = el, hadImage = false, layers = [];
    while (node && node.nodeType === 1) {
      var cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== "none") hadImage = true;
      var bg = rgbToArr(cs.backgroundColor);
      if (bg && bg.a > 0) {
        layers.push(bg);
        if (bg.a >= 0.999) break; // opaque base reached
      }
      node = node.parentElement;
    }
    var base = (layers.length && layers[layers.length - 1].a >= 0.999)
      ? layers.pop() : { r: 255, g: 255, b: 255, a: 1 };
    for (var i = layers.length - 1; i >= 0; i--) { // composite nearest-last, over the base
      var s = layers[i], a = s.a;
      base = { r: s.r * a + base.r * (1 - a), g: s.g * a + base.g * (1 - a), b: s.b * a + base.b * (1 - a), a: 1 };
    }
    return { bg: { r: base.r, g: base.g, b: base.b, a: 1 }, hadImage: hadImage };
  }
  function isVisible(el) {
    var cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function directText(el) {
    var t = "";
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) t += n.nodeValue;
    }
    return t.trim();
  }
  // Pure inline wrappers: an element whose children are all these still owns ONE line of text.
  var INLINE_WRAPPERS = { SPAN: 1, EM: 1, B: 1, STRONG: 1, I: 1, A: 1, MARK: 1, SMALL: 1,
                          CODE: 1, U: 1, S: 1, SUP: 1, SUB: 1, ABBR: 1, BR: 1, WBR: 1 };
  function onlyInlineChildren(el) {
    for (var i = 0; i < el.children.length; i++) {
      if (!INLINE_WRAPPERS[el.children[i].tagName]) return false;
    }
    return true;
  }
  // The text this element is responsible for. Normally its DIRECT text, but when every element
  // child is a pure inline wrapper the whole textContent belongs to it:
  // `<h1>Build <span>faster</span></h1>` is ONE headline. Attributing only "Build" to the h1
  // made the orphan gate skip it as totalWords<=1 while reporting pass.
  function ownText(el) {
    if (el.children.length && onlyInlineChildren(el)) return (el.textContent || "").trim();
    return directText(el);
  }
  function collectTextNodes(el) {
    var out = [], walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), n;
    while ((n = walker.nextNode())) { if (n.nodeValue && n.nodeValue.trim()) out.push(n); }
    return out;
  }
  // Count words sharing the top of the last visual line. 1 word alone => orphan.
  // Measures ACROSS inline element children. Previously it bailed out (returned null) on any
  // element child, so the dominant marketing-headline shape was never measured at all.
  function lastLineWordCount(el) {
    // Comment stripping + normalize() happen ONCE for the whole document below, before this
    // loop runs, so this function no longer mutates the DOM per element.
    if (el.children.length && !onlyInlineChildren(el)) return null; // block children: not one line
    var tns = collectTextNodes(el);
    if (!tns.length) return null;
    var ranges = [];
    for (var i = 0; i < tns.length; i++) {
      var tn = tns[i], txt = tn.nodeValue, re = /\S+/g, m;
      while ((m = re.exec(txt)) !== null) {
        var r = document.createRange();
        r.setStart(tn, m.index);
        r.setEnd(tn, m.index + m[0].length);
        ranges.push(r);
      }
    }
    if (ranges.length < 2) return ranges.length;
    var full = document.createRange();
    full.selectNodeContents(el);
    var rects = full.getClientRects();
    if (!rects.length) return ranges.length;
    var lastTop = rects[rects.length - 1].top;
    var count = 0;
    for (var j = 0; j < ranges.length; j++) {
      // A word broken across lines (soft hyphen break) renders partly on the
      // last line; attribute it to its LAST rect, not its bounding top.
      var wrects = ranges[j].getClientRects();
      var wtop = wrects.length ? wrects[wrects.length - 1].top : ranges[j].getBoundingClientRect().top;
      if (Math.abs(wtop - lastTop) <= 2) count++;
    }
    return count;
  }
  // Visual line count for the element's own text: the number of distinct line boxes.
  function lineCount(el) {
    if (el.children.length && !onlyInlineChildren(el)) return null;
    var r = document.createRange();
    r.selectNodeContents(el);
    var rects = r.getClientRects(), tops = [];
    for (var i = 0; i < rects.length; i++) {
      var t = Math.round(rects[i].top);
      var seen = false;
      for (var j = 0; j < tops.length; j++) if (Math.abs(tops[j] - t) <= 2) { seen = true; break; }
      if (!seen) tops.push(t);
    }
    return tops.length || null;
  }
  // Accessible-ish label, only to make a finding readable.
  function labelOf(el) {
    // a <select>'s textContent is every option concatenated ("MonthlyYearly"); use the chosen one.
    var sel = (el.tagName === "SELECT" && el.options && el.selectedIndex >= 0) ? el.options[el.selectedIndex].text : "";
    var t = (el.getAttribute("aria-label") || sel || el.textContent || el.getAttribute("title")
             || el.getAttribute("alt") || el.getAttribute("placeholder")
             || ((el.type === "checkbox" || el.type === "radio") ? "" : (el.value || "")) || "").trim();
    return t.slice(0, 60);
  }
  // Strip React SSR comment markers ONCE. Doing it per-element mutated the live DOM during the
  // measurement loop and forced a layout pass per element; render.mjs now also screenshots BEFORE
  // this runs, so the human's pick image is the untouched page.
  (function (root) {
    var w = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT, null), cs = [], n;
    while ((n = w.nextNode())) cs.push(n);
    for (var i = 0; i < cs.length; i++) if (cs[i].parentNode) cs[i].parentNode.removeChild(cs[i]);
  })(document.body);
  document.body.normalize();
  var report = {
    viewport: { w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio },
    textNodes: [], images: [], overflow: {}, controls: [], groups: []
  };
  var all = document.querySelectorAll("body *");
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var txt = ownText(el);
    if (!txt || !isVisible(el)) continue;
    var cs = getComputedStyle(el);
    var eb = effectiveBg(el);
    var rect = el.getBoundingClientRect();
    report.textNodes.push({
      tag: el.tagName.toLowerCase(),
      text: txt.slice(0, 120),
      color: rgbToArr(cs.color),
      bg: eb.bg,
      bgImage: eb.hadImage,
      fontSize: parseFloat(cs.fontSize),
      fontWeight: parseInt(cs.fontWeight) || 400,
      display: cs.display,
      ownsDirectText: directText(el).length > 0,
      rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
      lastLineWords: lastLineWordCount(el),
      totalWords: txt.split(/\s+/).length,
      // Line metrics for MEASURE (characters per line). `text` is truncated to 120 for payload
      // size, so chars/lineCount are computed on the FULL string.
      chars: txt.length,
      lineCount: lineCount(el),
      lineHeight: parseFloat(cs.lineHeight) || null
    });
  }
  var imgs = document.querySelectorAll("img");
  for (var k = 0; k < imgs.length; k++) {
    var im = imgs[k];
    report.images.push({
      src: im.currentSrc || im.src || "",
      naturalWidth: im.naturalWidth,
      alt: im.alt || "",
      visible: isVisible(im)
    });
  }
  // --- interactive controls (Fitts: tap-target size) ---
  // Captured as a FIRST-CLASS list. Previously interactivity was incidental to text, so an
  // icon-only <button> or any <input> was invisible to every check.
  // disabled controls have no hit area; flagging them produced unfixable findings.
  var CTRL_SEL = 'a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),' +
                 'select:not([disabled]),textarea:not([disabled]),summary,' +
                 '[role=button],[role=link],[role=checkbox],[role=tab],[onclick]';
  var ctrls = document.querySelectorAll(CTRL_SEL);
  for (var ci2 = 0; ci2 < ctrls.length; ci2++) {
    var c = ctrls[ci2];
    if (!isVisible(c)) continue;
    var cr = c.getBoundingClientRect();
    var ccs = getComputedStyle(c);
    // An inline link inside a paragraph is text, not a tap target with its own hit area;
    // judging it by 44px would flag every prose link on the page.
    // Exempt ONLY a link inside prose: the parent must carry its own text around it. A bare
    // <li><a> in a non-flex nav is display:inline too, and nine 18px nav links were slipping
    // through as "prose" (flex-item anchors get blockified, so those were caught).
    var pt = c.parentElement ? directText(c.parentElement) : "";
    var inlineInProse = ccs.display === "inline" && c.tagName === "A" && pt.length > 0;
    report.controls.push({
      tag: c.tagName.toLowerCase(),
      type: (c.getAttribute("type") || c.getAttribute("role") || "").toLowerCase(),
      label: labelOf(c),
      display: ccs.display,
      inlineInProse: inlineInProse,
      rect: { x: Math.round(cr.x), y: Math.round(cr.y), w: Math.round(cr.width), h: Math.round(cr.height) }
    });
  }
  // --- sibling-group sizes (Hick/Miller: choice-set size) ---
  // Flex/grid containers are where a design presents a set of choices.
  for (var gi = 0; gi < all.length; gi++) {
    var g = all[gi];
    if (!isVisible(g)) continue;
    var gcs = getComputedStyle(g);
    var isTrack = gcs.display === "flex" || gcs.display === "grid" ||
                  gcs.display === "inline-flex" || gcs.display === "inline-grid";
    var isList = g.tagName === "UL" || g.tagName === "OL" || g.tagName === "NAV";
    if (!isTrack && !isList) continue;
    var kids = 0;
    for (var ki = 0; ki < g.children.length; ki++) if (isVisible(g.children[ki])) kids++;
    // The <nav> itself is always reported (even with one child, e.g. <nav><ul>…</ul></nav>, the
    // canonical shape) and carries navLinks; inner lists report their own sibling count only,
    // so a nav is never double-counted. `g.closest("nav") === g` was identical to the tagName
    // test, which is why the nav rule never fired on the most common markup.
    var isNav = g.tagName === "NAV";
    var navLinks = isNav ? g.querySelectorAll('a[href],[role=link]').length : null;
    if (kids < 2 && !isNav) continue;
    report.groups.push({
      tag: g.tagName.toLowerCase(), display: gcs.display, children: kids, navLinks: navLinks
    });
  }
  var de = document.documentElement;
  var off = 0;
  function insideClip(el) {
    // A node whose ancestor clips horizontally (overflow hidden/clip) cannot
    // widen the page; masked marquees and clipped decorations are legal.
    for (var a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      var ox = getComputedStyle(a).overflowX;
      if (ox === "hidden" || ox === "clip") return true;
    }
    return false;
  }
  for (var b = 0; b < all.length; b++) {
    var rr = all[b].getBoundingClientRect();
    if (rr.width > 0 && rr.left > window.innerWidth + 1 && !insideClip(all[b])) off++;
  }
  report.overflow = {
    docScrollW: de.scrollWidth,
    clientW: de.clientWidth,
    horizontal: de.scrollWidth - de.clientWidth > 1,
    offscreenRight: off
  };
  // Graphics census — WARN-ONLY signal for the human pick. At runtime a library's animated-SVG
  // background is indistinguishable from a hand-drawn one (no import info in the DOM), so this
  // NEVER blocks; source-level provenance enforcement lives in drawing_check.py. It surfaces
  // "confirm these large SVGs / canvases are library or generated, not hand-drawn" at Stage 3.
  var vpArea = window.innerWidth * window.innerHeight;
  var svgs = [], canvases = [];
  var svgEls = document.querySelectorAll("svg");
  for (var s = 0; s < svgEls.length; s++) {
    var sv = svgEls[s];
    if (!isVisible(sv)) continue;
    if (sv.parentNode && sv.parentNode.nodeType === 1 && sv.parentNode.closest && sv.parentNode.closest("svg")) continue; // outermost only
    var sr = sv.getBoundingClientRect();
    svgs.push({
      w: Math.round(sr.width), h: Math.round(sr.height),
      areaPct: vpArea ? Math.round((sr.width * sr.height) / vpArea * 100) : 0,
      shapes: sv.querySelectorAll("path,rect,circle,polygon,polyline,ellipse,line").length
    });
  }
  var canvasEls = document.querySelectorAll("canvas");
  for (var c = 0; c < canvasEls.length; c++) {
    var cv = canvasEls[c];
    if (!isVisible(cv)) continue;
    var cr = cv.getBoundingClientRect();
    canvases.push({ w: Math.round(cr.width), h: Math.round(cr.height),
      areaPct: vpArea ? Math.round((cr.width * cr.height) / vpArea * 100) : 0 });
  }
  report.graphics = { svgs: svgs, canvases: canvases };
  return JSON.stringify(report);
})();
