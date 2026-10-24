// API client + job polling + DOM helpers (toast, modal dialogs) used by every view.
import { esc } from './util.mjs';

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const opts = { method, credentials: 'same-origin', headers: {} };
  if (form) opts.body = form;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
  const res = await fetch(`/api${path}`, opts);
  if (res.status === 401 && !path.startsWith('/auth/')) {
    window.dispatchEvent(new CustomEvent('pr:unauthorized'));
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = await res.json();
      msg = typeof d.detail === 'string' ? d.detail : (d.detail || []).map((e) => e.msg).join('; ') || msg;
    } catch { /* not JSON */ }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? null : res.json();
}

/** Poll a job until done/failed. onTick(job, seconds) for progress UI. */
export async function waitJob(job, onTick) {
  const start = Date.now();
  for (;;) {
    const j = await api(`/jobs/${job.id}`);
    onTick?.(j, Math.round((Date.now() - start) / 1000));
    if (j.status === 'done') return j;
    if (j.status === 'failed') throw new ApiError(500, j.error || 'job failed');
    await new Promise((r) => setTimeout(r, 1500));
  }
}

export function h(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function toast(msg, kind = 'info', ms = 3500) {
  let box = document.getElementById('toasts');
  if (!box) { box = h('<div id="toasts" aria-live="polite"></div>'); document.body.append(box); }
  const el = h(`<div class="toast ${kind}">${esc(msg)}</div>`);
  box.append(el);
  setTimeout(() => el.remove(), ms);
}

export function errorToast(e) { toast(e.message || String(e), 'error', 6000); }

/**
 * Modal form. fields: [{name,label,type:'text'|'textarea'|'select'|'checkbox'|'checks'|'color',value,options:[{value,label}]}]
 * Resolves to an object of values, or null if cancelled.
 */
export function dialog({ title, message = '', fields = [], ok = 'Save', danger = false }) {
  return new Promise((resolve) => {
    const body = fields.map((f) => {
      const id = `f_${f.name}`;
      if (f.type === 'textarea') return `<label for="${id}">${esc(f.label)}</label><textarea id="${id}" name="${f.name}" rows="${f.rows || 5}">${esc(f.value ?? '')}</textarea>`;
      if (f.type === 'select') return `<label for="${id}">${esc(f.label)}</label><select id="${id}" name="${f.name}">${f.options.map((o) => `<option value="${esc(o.value)}" ${o.value === f.value ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
      if (f.type === 'checkbox') return `<label class="check"><input type="checkbox" name="${f.name}" ${f.value ? 'checked' : ''}> ${esc(f.label)}</label>`;
      if (f.type === 'checks') return `<fieldset><legend>${esc(f.label)}</legend>${f.options.map((o) => `<label class="check"><input type="checkbox" name="${f.name}" value="${esc(o.value)}" ${(f.value || []).includes(o.value) ? 'checked' : ''}> ${esc(o.label)}</label>`).join('')}</fieldset>`;
      return `<label for="${id}">${esc(f.label)}</label><input id="${id}" name="${f.name}" type="${f.type || 'text'}" value="${esc(f.value ?? '')}" ${f.placeholder ? `placeholder="${esc(f.placeholder)}"` : ''} autocomplete="off">`;
    }).join('');
    const el = h(`<div class="modal-back"><form class="modal" role="dialog" aria-modal="true">
      <h3>${esc(title)}</h3>${message ? `<p class="muted">${esc(message)}</p>` : ''}${body}
      <div class="modal-actions"><button type="button" class="btn ghost" data-cancel>Cancel</button>
      <button type="submit" class="btn ${danger ? 'danger' : 'primary'}">${esc(ok)}</button></div></form></div>`);
    const form = el.querySelector('form');
    const close = (v) => { el.remove(); resolve(v); };
    el.addEventListener('click', (e) => { if (e.target === el) close(null); });
    el.querySelector('[data-cancel]').onclick = () => close(null);
    form.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(null); });
    form.onsubmit = (e) => {
      e.preventDefault();
      const out = {};
      for (const f of fields) {
        if (f.type === 'checkbox') out[f.name] = form.elements[f.name].checked;
        else if (f.type === 'checks') out[f.name] = [...form.querySelectorAll(`input[name="${f.name}"]:checked`)].map((i) => i.value);
        else out[f.name] = form.elements[f.name].value;
      }
      close(out);
    };
    document.body.append(el);
    (form.querySelector('input:not([type=checkbox]),textarea,select') || form.querySelector('button[type=submit]')).focus();
  });
}

export async function confirmDialog(title, message, ok = 'Delete') {
  return (await dialog({ title, message, ok, danger: true })) !== null;
}
