// US-07 / US-08 — pure geometry for PDF overlays (rects normalised to the page, 0..1).

/** Client rects -> page-normalised rects, merged per visual line (AT-08.1). */
export function normalizeRects(clientRects, pageBox) {
  const out = [];
  for (const r of clientRects) {
    if (r.width < 1 || r.height < 1) continue;
    const x0 = Math.max(r.left, pageBox.left), x1 = Math.min(r.right, pageBox.right);
    const y0 = Math.max(r.top, pageBox.top), y1 = Math.min(r.bottom, pageBox.bottom);
    if (x1 <= x0 || y1 <= y0) continue;
    out.push([(x0 - pageBox.left) / pageBox.width, (y0 - pageBox.top) / pageBox.height,
      (x1 - pageBox.left) / pageBox.width, (y1 - pageBox.top) / pageBox.height]);
  }
  return mergeLines(out);
}

/** Merge rects that sit on the same line (vertical overlap > 50%) and touch horizontally. */
export function mergeLines(rects) {
  const sorted = rects.slice().sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const out = [];
  for (const r of sorted) {
    const last = out[out.length - 1];
    if (last) {
      const ov = Math.min(last[3], r[3]) - Math.max(last[1], r[1]);
      const minH = Math.min(last[3] - last[1], r[3] - r[1]);
      if (ov > 0.5 * minH && r[0] <= last[2] + 0.02) {
        last[0] = Math.min(last[0], r[0]); last[1] = Math.min(last[1], r[1]);
        last[2] = Math.max(last[2], r[2]); last[3] = Math.max(last[3], r[3]);
        continue;
      }
    }
    out.push(r.map((v) => Math.round(v * 1e5) / 1e5));
  }
  return out;
}

export function rectsOverlap(a, b) {
  return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
}

/** AT-07.2 — quotes (same paper & page) whose rects overlap the selection rects. */
export function overlappingQuotes(selection, quotes) {
  return quotes.filter((q) => q.paper_id === selection.paperId && q.page === selection.page
    && q.rects.some((qr) => selection.rects.some((sr) => rectsOverlap(qr, sr))));
}

/** AT-07.3 — items whose rects contain a normalised point (with a small tolerance). */
export function hitTest(point, items, tol = 0.004) {
  return items.filter((it) => it.rects.some((r) => point.x >= r[0] - tol && point.x <= r[2] + tol
    && point.y >= r[1] - tol && point.y <= r[3] + tol));
}
