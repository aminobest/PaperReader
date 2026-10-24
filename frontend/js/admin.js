// US-11 — admin: model & settings, prompt templates (edit / reset), AI call log.
import { api, confirmDialog, errorToast, toast } from './api.js';
import { esc } from './util.mjs';

export async function renderAdmin(root, me) {
  if (me.role !== 'admin') { root.innerHTML = '<div class="page"><div class="empty">Administrator access required. <a href="/">Back</a></div></div>'; return; }
  let settings, prompts, logs;
  try {
    [settings, prompts, logs] = await Promise.all([api('/admin/settings'), api('/admin/prompts'), api('/admin/logs?limit=100')]);
  } catch (e) { return errorToast(e); }
  const v = settings.values;
  root.innerHTML = `<div class="page admin">
    <header class="page-top"><a class="btn ghost" href="/">‹ Sessions</a><h1>Admin</h1></header>
    <section class="card"><h2>Model &amp; settings</h2><form class="settings grid2">
      <label>OpenRouter model<input name="model" list="presets" value="${esc(v.model)}" required></label>
      <datalist id="presets">${settings.presets.map((p) => `<option value="${esc(p)}">`).join('')}</datalist>
      <label>Temperature<input name="temperature" type="number" min="0" max="2" step="0.1" value="${v.temperature}"></label>
      <label>Grounding retries<input name="grounding_retries" type="number" min="0" max="5" value="${v.grounding_retries}"></label>
      <label>Minimum map depth (0 = off)<input name="min_map_depth" type="number" min="0" max="6" value="${v.min_map_depth}"></label>
      <label>AI-chat trace color<input name="chat_color" type="color" value="${v.chat_color}"></label>
      <label>Map-quote color<input name="map_color" type="color" value="${v.map_color}"></label>
      <div><button class="btn primary">Save settings</button></div></form>
      <p class="muted small">Presets: ${settings.presets.map(esc).join(' · ')} — any OpenRouter model id works.</p></section>
    <section class="card"><h2>Prompt templates</h2>
      ${prompts.map((p) => `<details class="prompt" data-key="${p.key}"><summary><b>${esc(p.name)}</b> <span class="muted small">${esc(p.key)}${p.is_default ? '' : ' · edited'}</span></summary>
        <p class="muted small">${esc(p.description)}${p.required.length ? ` Required: ${p.required.map((r) => `<code>{{${r}}}</code>`).join(' ')}` : ''}</p>
        <textarea rows="14" spellcheck="false">${esc(p.template)}</textarea>
        <div class="actions"><button class="btn primary" data-save>Save</button><button class="btn" data-reset>Reset to default</button></div></details>`).join('')}</section>
    <section class="card"><h2>AI call log <span class="muted small">(latest 100)</span></h2>
      <div class="actions"><button class="btn danger" data-clear>Clear log</button></div>
      <table class="log"><thead><tr><th>When</th><th>Kind</th><th>Model</th><th>ms</th><th>Status</th></tr></thead><tbody>
      ${logs.map((l) => `<tr data-log="${l.id}"><td>${esc(new Date(l.ts).toLocaleString())}</td><td>${esc(l.kind)}</td><td>${esc(l.model)}</td><td>${l.duration_ms}</td><td>${l.error ? `<span class="error-text">${esc(l.error.slice(0, 80))}</span>` : 'ok'}</td></tr>
        <tr class="log-detail" hidden><td colspan="5"><pre>${esc(JSON.stringify(l.messages, null, 1).slice(0, 20000))}</pre><h4>Response</h4><pre>${esc(l.response || '')}</pre></td></tr>`).join('')}</tbody></table></section></div>`;

  root.querySelector('.settings').onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target.elements;
    try {
      await api('/admin/settings', { method: 'PUT', body: { model: f.model.value, temperature: Number(f.temperature.value), grounding_retries: Number(f.grounding_retries.value), min_map_depth: Number(f.min_map_depth.value), chat_color: f.chat_color.value, map_color: f.map_color.value } });
      toast('Settings saved', 'ok');
    } catch (err) { errorToast(err); }
  };
  root.querySelector('.admin').addEventListener('click', async (e) => {
    const d = e.target.closest('details.prompt');
    try {
      if (e.target.matches('[data-save]')) {
        await api(`/admin/prompts/${d.dataset.key}`, { method: 'PUT', body: { template: d.querySelector('textarea').value } });
        toast('Prompt saved', 'ok');
      } else if (e.target.matches('[data-reset]')) {
        const p = await api(`/admin/prompts/${d.dataset.key}/reset`, { method: 'POST' });
        d.querySelector('textarea').value = p.template;
        toast('Prompt reset to default', 'ok');
      } else if (e.target.matches('[data-clear]')) {
        if (await confirmDialog('Clear AI log?', 'All logged prompts and responses are deleted.', 'Clear')) { await api('/admin/logs', { method: 'DELETE' }); renderAdmin(root, me); }
      } else if (e.target.closest('tr[data-log]')) {
        const det = e.target.closest('tr[data-log]').nextElementSibling;
        det.hidden = !det.hidden;
      }
    } catch (err) { errorToast(err); }
  });
}
