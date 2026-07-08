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
  // Only headings/simple single-text-node elements get reliable line analysis.
  function singleTextNode(el) {
    var tn = null, elemChildren = 0;
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 1) elemChildren++;
      else if (n.nodeType === 3 && n.nodeValue.trim()) tn = n;
    }
    return elemChildren === 0 && tn ? tn : null;
  }
  // Count words sharing the top of the last visual line. 1 word alone => orphan.
  function lastLineWordCount(el) {
    // React SSR separates adjacent text parts with comment nodes; strip them so
    // normalize() can merge the parts back into one measurable text node.
    for (var ci = el.childNodes.length - 1; ci >= 0; ci--) {
      if (el.childNodes[ci].nodeType === 8) el.removeChild(el.childNodes[ci]);
    }
    el.normalize(); // merge adjacent text nodes (React splits {a}{'\u00A0'}{b} into 3)
    var tn = singleTextNode(el);
    if (!tn) return null;
    var text = tn.nodeValue;
    var words = text.trim().split(/\s+/);
    if (words.length < 2) return words.length;
    var full = document.createRange();
    full.selectNodeContents(tn);
    var rects = full.getClientRects();
    if (rects.length < 2) return words.length;
    var lastTop = rects[rects.length - 1].top;
    var count = 0, re = /\S+/g, m;
    while ((m = re.exec(text)) !== null) {
      var r = document.createRange();
      r.setStart(tn, m.index);
      r.setEnd(tn, m.index + m[0].length);
      if (Math.abs(r.getBoundingClientRect().top - lastTop) <= 2) count++;
    }
    return count;
  }
  var report = {
    viewport: { w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio },
    textNodes: [], images: [], overflow: {}
  };
  var all = document.querySelectorAll("body *");
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var txt = directText(el);
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
      rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
      lastLineWords: lastLineWordCount(el),
      totalWords: txt.split(/\s+/).length
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
  var de = document.documentElement;
  var off = 0;
  for (var b = 0; b < all.length; b++) {
    var rr = all[b].getBoundingClientRect();
    if (rr.width > 0 && rr.left > window.innerWidth + 1) off++;
  }
  report.overflow = {
    docScrollW: de.scrollWidth,
    clientW: de.clientWidth,
    horizontal: de.scrollWidth - de.clientWidth > 1,
    offscreenRight: off
  };
  return JSON.stringify(report);
})();
