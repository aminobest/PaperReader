// Small pure helpers shared by views (escaping, light markdown, citation chips).

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** US-10 AT-10.2 — light markdown; `[[q:<id>|n]]` becomes a clickable citation chip. */
export function renderMarkdown(text) {
  const lines = esc(text).split('\n');
  const html = [];
  let list = null;
  const inline = (s) => s
    .replace(/\[\[q:(\w+)\|(\d+)\]\]/g, '<button class="cite" data-quote="$1">$2</button>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  for (const raw of lines) {
    const line = raw.trimEnd();
    const li = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/);
    if (li) {
      const tag = /^\s*\d+\./.test(line) ? 'ol' : 'ul';
      if (list !== tag) { if (list) html.push(`</${list}>`); html.push(`<${tag}>`); list = tag; }
      html.push(`<li>${inline(li[1])}</li>`);
      continue;
    }
    if (list) { html.push(`</${list}>`); list = null; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) html.push(`<h${h[1].length + 2}>${inline(h[2])}</h${h[1].length + 2}>`);
    else if (line.trim()) html.push(`<p>${inline(line)}</p>`);
  }
  if (list) html.push(`</${list}>`);
  return html.join('');
}

export function timeAgo(iso) {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export function debounce(fn, ms) {
  let t;
  const d = (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  d.flush = (...a) => { clearTimeout(t); fn(...a); };
  return d;
}
