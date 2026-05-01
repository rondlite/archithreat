// Small UI helpers: tab switching, status panel, file reading. Vanilla JS,
// factored out only enough to keep main.js readable. No framework, no state
// container — DOM is the source of truth.

export function $(sel, root = document) {
  return root.querySelector(sel);
}

/** Wire up tab buttons that toggle role=tabpanel siblings via aria-controls. */
export function initTabs(tabSelector = '[role="tab"]') {
  const tabs = Array.from(document.querySelectorAll(tabSelector));
  const panels = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')));

  function activate(idx) {
    tabs.forEach((t, i) => {
      const active = i === idx;
      t.classList.toggle('is-active', active);
      t.setAttribute('aria-selected', active ? 'true' : 'false');
      t.tabIndex = active ? 0 : -1;
      const panel = panels[i];
      if (!panel) return;
      panel.hidden = !active;
      panel.classList.toggle('is-active', active);
    });
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => activate(i));
    tab.addEventListener('keydown', (ev) => {
      if (ev.key === 'ArrowRight') {
        ev.preventDefault();
        activate((i + 1) % tabs.length);
        tabs[(i + 1) % tabs.length].focus();
      } else if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        activate((i - 1 + tabs.length) % tabs.length);
        tabs[(i - 1 + tabs.length) % tabs.length].focus();
      } else if (ev.key === 'Home') {
        ev.preventDefault();
        activate(0);
        tabs[0].focus();
      } else if (ev.key === 'End') {
        ev.preventDefault();
        activate(tabs.length - 1);
        tabs[tabs.length - 1].focus();
      }
    });
  });

  activate(0);
}

/** Status panel controller. */
export function statusPanel(dotId = 'status-dot', textId = 'status-text', progressId = 'status-progress') {
  const dot = document.getElementById(dotId);
  const text = document.getElementById(textId);
  const progress = document.getElementById(progressId);
  return {
    set(state, message, pct) {
      if (dot) dot.dataset.state = state;
      if (text) text.textContent = message;
      if (progress) {
        if (typeof pct === 'number') {
          progress.value = Math.max(0, Math.min(100, pct));
          progress.style.display = '';
        } else if (state === 'ready') {
          progress.value = 100;
          progress.style.display = 'none';
        }
      }
    },
  };
}

/** Read a File from an <input type="file"> as Uint8Array. */
export async function readFileBytes(input) {
  const file = input.files && input.files[0];
  if (!file) throw new Error('No file selected.');
  const buf = await file.arrayBuffer();
  return { name: file.name, bytes: new Uint8Array(buf) };
}

/** Trigger a download by wrapping bytes in a Blob and clicking an <a>. */
export function triggerDownload(bytes, filename, mediaType = 'application/octet-stream') {
  const blob = new Blob([bytes], { type: mediaType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.className = 'download-link';
  a.textContent = `Download ${filename}`;
  // Append to result box so the user can re-click; also auto-click once.
  const target = document.getElementById('convert-result');
  if (target) {
    target.classList.remove('is-error');
    target.classList.add('is-ok');
    target.replaceChildren(a);
  }
  // Auto-trigger so smoke tests see the download event.
  a.click();
  // Free the URL after a tick.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return url;
}

/** Render a result box with text content and an ok/err class. */
export function renderResult(elementId, message, kind = 'ok') {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.classList.remove('is-ok', 'is-error');
  el.classList.add(kind === 'error' ? 'is-error' : 'is-ok');
  el.textContent = message;
}

/** Replace the suffix of a filename. */
export function replaceExtension(name, ext) {
  const dot = name.lastIndexOf('.');
  const stem = dot > 0 ? name.slice(0, dot) : name;
  return `${stem}.${ext}`;
}

/**
 * Read a target dropdown's value, defaulting to drawio-iriusrisk if the
 * element is missing or unset. The Convert tab uses #target; the mapping
 * editor uses #mapping-target.
 */
export function getTarget(elementId = 'target', fallback = 'drawio-iriusrisk') {
  const el = document.getElementById(elementId);
  const value = el && el.value ? el.value.trim() : '';
  return value || fallback;
}
