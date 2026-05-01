// archithreat browser shell — main thread.
//
// Responsibilities:
//   * Boot the Web Worker that hosts Pyodide and the core wheel.
//   * Wire up file inputs, tab navigation, status panel, mapping editor.
//   * Marshal bytes/strings between DOM and worker via postMessage.
//   * Wrap convert results in a Blob and trigger a download.
//
// The main thread never imports Pyodide; it stays interactive at all times.

import {
  $,
  initTabs,
  statusPanel,
  readFileBytes,
  triggerDownload,
  renderResult,
  replaceExtension,
  getTarget,
} from './ui.js';

const status = statusPanel();
let worker = null;
let nextRequestId = 1;
const pending = new Map();
let ready = false;

function newRequestId() {
  return `req-${nextRequestId++}`;
}

function callWorker(method, payload, transfer = []) {
  if (!worker) return Promise.reject(new Error('Worker not ready.'));
  const id = newRequestId();
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, method, payload }, transfer);
  });
}

function bootWorker() {
  worker = new Worker('./worker.js');
  worker.addEventListener('message', (ev) => {
    const msg = ev.data || {};
    if (msg.kind === 'progress') {
      status.set('boot', msg.message || 'Loading…', msg.percent);
      return;
    }
    if (msg.kind === 'ready') {
      ready = true;
      status.set('ready', 'Pyodide ready');
      // Reveal that we're ready in a way the smoke test can detect.
      document.body.dataset.pyodide = 'ready';
      enableActionButtons(true);
      return;
    }
    if (msg.kind === 'error-fatal') {
      status.set('error', `Runtime error: ${msg.message}`);
      document.body.dataset.pyodide = 'error';
      return;
    }
    if (msg.kind === 'response') {
      const handler = pending.get(msg.id);
      if (!handler) return;
      pending.delete(msg.id);
      if (msg.ok) handler.resolve(msg.result);
      else handler.reject(new Error(msg.error || 'Worker error'));
    }
  });
  worker.addEventListener('error', (ev) => {
    status.set('error', `Worker crashed: ${ev.message || 'unknown'}`);
    document.body.dataset.pyodide = 'error';
  });
}

function enableActionButtons(enabled) {
  for (const id of ['btn-convert', 'btn-inventory', 'btn-validate-run']) {
    const b = document.getElementById(id);
    if (b) b.disabled = !enabled;
  }
}

// ---------- Convert ----------

async function onConvertSubmit(ev) {
  ev.preventDefault();
  if (!ready) return;
  const fileInput = $('#file-convert');
  const mappingText = ($('#mapping-text').value || '').trim();
  const target = getTarget('target');
  const statusEl = $('#convert-status');
  try {
    statusEl.textContent = 'Reading file…';
    const { name, bytes } = await readFileBytes(fileInput);
    status.set('busy', `Converting ${name}…`);
    statusEl.textContent = 'Converting…';
    const result = await callWorker('convert', {
      bytes,
      mapping: mappingText || null,
      sourceName: name,
      target,
    });
    statusEl.textContent = 'Done.';
    status.set('ready', 'Pyodide ready');
    triggerDownload(result.bytes, replaceExtension(name, result.extension), result.mediaType);
  } catch (err) {
    statusEl.textContent = '';
    status.set('error', `Convert failed: ${err.message}`);
    renderResult('convert-result', String(err.message || err), 'error');
  }
}

// ---------- Inventory ----------

async function onInventorySubmit(ev) {
  ev.preventDefault();
  if (!ready) return;
  const fileInput = $('#file-inventory');
  const target = getTarget('target');
  const statusEl = $('#inventory-status');
  try {
    statusEl.textContent = 'Reading file…';
    const { name, bytes } = await readFileBytes(fileInput);
    status.set('busy', `Inventorying ${name}…`);
    statusEl.textContent = 'Running inventory…';
    const text = await callWorker('inventory', { bytes, target });
    statusEl.textContent = 'Done.';
    status.set('ready', 'Pyodide ready');
    const out = document.getElementById('inventory-result');
    out.textContent = text;
    out.classList.remove('is-error');
    out.classList.add('is-ok');
  } catch (err) {
    statusEl.textContent = '';
    status.set('error', `Inventory failed: ${err.message}`);
    renderResult('inventory-result', String(err.message || err), 'error');
  }
}

// ---------- Validate mapping ----------

async function onValidateSubmit(ev) {
  ev.preventDefault();
  if (!ready) return;
  const text = $('#validate-text').value || '';
  const target = getTarget('mapping-target');
  const statusEl = $('#validate-status');
  try {
    statusEl.textContent = 'Validating…';
    const errors = await callWorker('validateMapping', { text, target });
    statusEl.textContent = '';
    if (errors.length === 0) {
      renderResult('validate-result', 'Mapping is valid.', 'ok');
    } else {
      renderResult(
        'validate-result',
        errors.map((e) => `• ${e.loc || ''}: ${e.message}`).join('\n'),
        'error',
      );
    }
  } catch (err) {
    statusEl.textContent = '';
    renderResult('validate-result', String(err.message || err), 'error');
  }
}

async function onValidateMappingInline() {
  const text = ($('#mapping-text').value || '').trim();
  const target = getTarget('mapping-target');
  const out = document.getElementById('mapping-validate-result');
  if (!text) {
    out.textContent = 'Empty: the default mapping will be used.';
    out.classList.remove('is-error');
    out.classList.add('is-ok');
    return;
  }
  try {
    const errors = await callWorker('validateMapping', { text, target });
    out.classList.remove('is-error', 'is-ok');
    if (errors.length === 0) {
      out.textContent = 'Mapping is valid.';
      out.classList.add('is-ok');
    } else {
      out.textContent = errors.map((e) => `• ${e.loc || ''}: ${e.message}`).join('\n');
      out.classList.add('is-error');
    }
  } catch (err) {
    out.textContent = String(err.message || err);
    out.classList.remove('is-ok');
    out.classList.add('is-error');
  }
}

async function loadDefaultInto(elementId, targetSelectId = 'mapping-target') {
  const target = getTarget(targetSelectId);
  const text = await callWorker('defaultMapping', { target });
  const el = document.getElementById(elementId);
  if (el) el.value = text;
}

// ---------- Boot ----------

function init() {
  initTabs();
  bootWorker();

  document.getElementById('form-convert').addEventListener('submit', onConvertSubmit);
  document.getElementById('form-inventory').addEventListener('submit', onInventorySubmit);
  document.getElementById('form-validate').addEventListener('submit', onValidateSubmit);

  document
    .getElementById('btn-load-default')
    .addEventListener('click', () => loadDefaultInto('mapping-text').catch((e) => alert(e.message)));
  document
    .getElementById('btn-validate-mapping')
    .addEventListener('click', onValidateMappingInline);
  document
    .getElementById('btn-validate-load-default')
    .addEventListener('click', () => loadDefaultInto('validate-text').catch((e) => alert(e.message)));

  enableActionButtons(false);
  status.set('boot', 'Loading runtime…', 5);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
