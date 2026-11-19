import {present, render} from './presentation.mjs';

const el = id => document.getElementById(id);
const api = '/api/v1';
let webReady = false;
let conversation, job, textReady = false, visionReady = false, busy = false;
let sources = [];

function element(tag, text) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  return node;
}
function link(label, path) {
  const node = element('a', label);
  node.href = path;
  if (path.startsWith(api + '/')) { node.target = '_blank'; node.rel = 'noopener'; }
  return node;
}
function details(label, text) {
  const node = element('details');
  node.append(element('summary', label), element('pre', text));
  return node;
}
async function request(path, body) {
  const options = body instanceof FormData ? {method: 'POST', body} :
    body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
  const response = await fetch(api + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || 'HTTP ' + response.status);
  return data;
}
function controls() {
  el('inspect').disabled = busy;
  el('files').disabled = busy;
  el('run').disabled = busy || !textReady || !sources.length ||
    (!visionReady && sources.some(s => s.kind === 'image'));
  el('cancel').hidden = !job;
}
async function readiness() {
  try {
    const [h, providers] = await Promise.all([request('/health'), request('/providers')]);
    webReady = h.web_ready === true;
    el('workspace').hidden = !webReady;
    const matches = providers.reference_digest_matches ?? {};
    textReady = h.text_ready === true && matches[providers.configured_text] === true;
    visionReady = h.vision_ready === true && matches[providers.configured_vision] === true;
    el('provider').textContent = 'Backend ' + h.status + ' · Text model ' + (textReady ? 'verified' : 'missing or unverified') +
      ' · Vision model ' + (visionReady ? 'verified' : 'missing or unverified') + '. Source inspection works independently.';
  } catch (err) {
    textReady = visionReady = false;
    el('provider').textContent = err.message;
  }
  controls();
}
const show = n => n == null ? 'undefined' : Number(n.toPrecision(8)).toString();
async function profile(card, source) {
  const report = await request('/intelligence/execute', {tool_id: 'measurements.profile',
    arguments: {conversation_id: conversation, attachment_id: source.id}});
  const table = element('table');
  const head = table.createTHead().insertRow();
  for (const field of ['Asset / channel','Unit','First','Last','Full mean','Change','Change (%)','First 24 mean','Last 6 mean','Source']) {
    head.append(element('th', field));
  }
  const rows = table.createTBody();
  for (const g of report.result.groups) {
    const row = rows.insertRow();
    for (const value of [g.asset_id + ' / ' + g.channel, g.unit, ...[g.first_value, g.last_value, g.full_mean,
      g.endpoint_delta, g.endpoint_percent_delta, g.baseline_mean, g.recent_mean].map(show)]) row.insertCell().textContent = value;
    row.insertCell().append(link('Source rows', api + '/evidence/' + encodeURIComponent(g.evidence_id)));
  }
  const wrapper = element('div'); wrapper.className = 'scroll'; wrapper.append(table); card.append(wrapper);
  card.append(element('small','First and last are the earliest and latest good readings. Change (%) uses the first reading as denominator. Windows can overlap on short series.'));
  for (const m of report.result.missing_cells) card.append(element('p', m.asset_id + ' · ' + m.source_field + ' · blank cells: ' + m.blank_count));
  card.append(link('Execution trace', api + '/runs/' + encodeURIComponent(report.run_id) + '/trace'));
}
el('upload').onsubmit = async event => {
  event.preventDefault();
  const files = Array.from(el('files').files);
  if (!files.length || files.length > 6) { el('status').textContent = 'Choose one to six source files.'; return; }
  busy = true; controls(); sources = []; el('records').replaceChildren(); el('answer').replaceChildren();
  el('progress').textContent = ''; el('status').textContent = 'Uploading to a new local conversation…'; el('observations').hidden = false;
  let issues = 0;
  try {
    conversation = (await request('/conversations', {title: 'Engineering evidence review'})).id;
    const cards = new Map();
    for (const file of files) {
      const card = element('article'); card.append(element('h3', file.name)); el('records').append(card);
      try {
        const form = new FormData(); form.set('conversation_id', conversation); form.set('file', file);
        const source = await request('/attachments', form);
        if (source.ingestion_status === 'failed') throw new Error(source.metadata?.media_error?.message || 'Media extraction failed');
        if (!sources.some(item => item.id === source.id)) sources.push(source);
        cards.set(source.id, card);
        card.append(element('small','Original SHA-256 · ' + source.metadata.original_sha256),
          link('Inspect attachment record', api + '/evidence/' + encodeURIComponent(source.id)));
        const content = api + '/attachments/' + encodeURIComponent(source.id) + '/content';
        card.append(element('br'), link(source.kind === 'image' ? 'Inspect stored image' : 'Open stored file', content));
        if (source.metadata.measurement_schema) await profile(card, source);
        else if (file.name.toLowerCase().endsWith('.csv')) card.append(element('p','CSV accepted. No supported typed measurement schema was identified.'));
      } catch (err) { issues++; card.append(element('p', err.message)); }
    }
    const knowledge = await request('/knowledge/sources?conversation_id=' + encodeURIComponent(conversation));
    for (const chunk of knowledge.chunks) cards.get(chunk.attachment_id)?.append(details(chunk.locator, chunk.text));
    el('status').textContent = sources.length + ' distinct source files available · ' + issues + ' processing errors.';
    await readiness();
  } catch (err) { el('status').textContent = err.message; }
  finally { busy = false; controls(); }
};
el('investigate').onsubmit = async event => {
  event.preventDefault(); if (el('run').disabled) return;
  busy = true; controls(); el('answer').replaceChildren(); el('progress').textContent = 'Submitting investigation…';
  try {
    job = await request('/investigation-jobs', {conversation_id: conversation, content: el('question').value,
      attachment_ids: sources.map(s => s.id)});
    controls();
    const path = '/investigation-jobs/' + encodeURIComponent(job.id) + '?conversation_id=' + encodeURIComponent(conversation);
    while (['queued','running'].includes(job.status)) {
      el('progress').textContent = 'Execution: ' + job.status;
      await new Promise(resolve => setTimeout(resolve, 1000));
      job = await request(path);
    }
    el('progress').textContent = 'Execution: ' + job.status + (job.error ? ' · ' + job.error.message : '');
    const state = await request('/conversations/' + encodeURIComponent(conversation));
    const message = state.messages.find(m => m.id === job.assistant_message_id);
    render(el('answer'), present(job, message));
    if (webReady) el('answer').append(link('Open conversation and investigation details', '/chat/' + encodeURIComponent(conversation)));
    if (job.run_id) el('answer').append(element('br'), link('Inspect execution trace', api + '/runs/' + encodeURIComponent(job.run_id) + '/trace'));
  } catch (err) {
    el('progress').textContent = err.message;
    if (job) el('answer').append(link('Recover saved job status', api + '/investigation-jobs/' + encodeURIComponent(job.id) + '?conversation_id=' + encodeURIComponent(conversation)));
  }
  finally { job = undefined; busy = false; controls(); }
};
el('cancel').onclick = async () => {
  if (!job) return;
  try { await request('/investigation-jobs/' + encodeURIComponent(job.id) + '/cancel?conversation_id=' + encodeURIComponent(conversation), {}); }
  catch (err) { el('progress').textContent = err.message; }
};
readiness();
