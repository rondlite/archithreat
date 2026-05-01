// archithreat browser shell — Web Worker.
//
// Hosts Pyodide and the archithreat core wheel. All heavy work happens here so
// the main thread stays responsive.
//
// Pyodide is loaded from a same-origin vendored path (./pyodide/). The wheel
// is installed from a same-origin /wheels/ directory. No PyPI access at
// runtime, no CDN.
//
// Message protocol:
//   in:  { id, method: 'convert'|'inventory'|'validateMapping'|'defaultMapping', payload }
//        payload.target selects the output target (e.g. 'drawio-iriusrisk',
//        'threatdragon'); empty/missing falls back to the Python DEFAULT_TARGET.
//   out: { kind: 'progress'|'ready'|'response'|'error-fatal', ... }

/* global importScripts, loadPyodide */

importScripts('./pyodide/pyodide.js');

let pyodide = null;
let bootPromise = null;

function postProgress(message, percent) {
  self.postMessage({ kind: 'progress', message, percent });
}

function postReady() {
  self.postMessage({ kind: 'ready' });
}

function postFatal(message) {
  self.postMessage({ kind: 'error-fatal', message });
}

function respond(id, ok, payload) {
  if (ok) {
    self.postMessage({ kind: 'response', id, ok: true, result: payload });
  } else {
    self.postMessage({ kind: 'response', id, ok: false, error: String(payload) });
  }
}

async function findWheelUrl() {
  // We don't get a directory listing from a static host. The build script
  // copies exactly one wheel into dist/wheels/, named archithreat-<ver>-*.whl.
  // Try a manifest first; fall back to a versioned guess via fetch HEAD.
  try {
    const r = await fetch('./wheels/index.json', { cache: 'no-store' });
    if (r.ok) {
      const j = await r.json();
      if (j.wheel) return `./wheels/${j.wheel}`;
    }
  } catch (_) { /* ignore */ }
  // Fallback: try the current pinned package version. CI writes
  // ./wheels/index.json with the actual filename so this fallback is only
  // hit during local dev when you forgot the index step.
  const candidates = [
    'archithreat-2.0.0-py3-none-any.whl',
  ];
  for (const c of candidates) {
    try {
      const head = await fetch(`./wheels/${c}`, { method: 'HEAD' });
      if (head.ok) return `./wheels/${c}`;
    } catch (_) { /* ignore */ }
  }
  throw new Error('No wheel found under ./wheels/. Run `npm run build:wheel`.');
}

async function bootstrap() {
  if (bootPromise) return bootPromise;
  bootPromise = (async () => {
    postProgress('Loading Pyodide…', 10);
    pyodide = await loadPyodide({
      indexURL: './pyodide/',
      stdout: (s) => console.log('[py]', s),
      stderr: (s) => console.warn('[py]', s),
    });
    postProgress('Loading core dependencies…', 40);
    // archithreat's runtime deps: lxml, pydantic, pyyaml. All shipped as
    // Pyodide packages — no PyPI fetch needed.
    await pyodide.loadPackage(['lxml', 'pydantic', 'pyyaml', 'micropip']);

    postProgress('Installing archithreat core…', 70);
    const wheelUrl = await findWheelUrl();
    const micropip = pyodide.pyimport('micropip');
    // Install local wheel from same origin, with deps already satisfied.
    await micropip.install(wheelUrl, { deps: false });

    postProgress('Initializing…', 90);
    await pyodide.runPythonAsync(`
import archithreat
from archithreat import (
    convert_bytes,
    inventory_bytes,
    validate_mapping,
    load_default_mapping,
    DEFAULT_TARGET,
    get_emitter,
)
from archithreat.core.mappings import default_mapping_text

def _resolve_target(target):
    return target or DEFAULT_TARGET

def _do_convert(model_bytes, mapping_text, source_name, target):
    target = _resolve_target(target)
    mapping = mapping_text if mapping_text else None
    out = convert_bytes(
        model_bytes,
        mapping_source=mapping,
        target=target,
        source_name=source_name or "",
    )
    em = get_emitter(target)
    return out, em.output_extension, em.output_media_type

def _do_inventory(model_bytes, target):
    target = _resolve_target(target)
    rep = inventory_bytes(model_bytes, mapping=load_default_mapping(target=target))
    return rep.to_text()

def _do_validate(text, target):
    target = _resolve_target(target)
    try:
        errs = validate_mapping(text, target=target)
    except Exception as exc:
        return [{"loc": "", "message": str(exc)}]
    return [
        {"loc": ".".join(str(p) for p in (e.get("loc") or [])), "message": e.get("msg") or e.get("message") or str(e)}
        for e in errs
    ]

def _do_default_mapping(target):
    target = _resolve_target(target)
    return default_mapping_text(target=target)
`);
    postReady();
  })().catch((err) => {
    postFatal(err && err.message ? err.message : String(err));
    throw err;
  });
  return bootPromise;
}

async function handle(method, payload) {
  await bootstrap();
  switch (method) {
    case 'convert': {
      const fn = pyodide.globals.get('_do_convert');
      try {
        const tuple = fn(
          payload.bytes,
          payload.mapping || '',
          payload.sourceName || '',
          payload.target || '',
        );
        const arr = tuple.toJs({ create_proxies: false });
        // arr = [bytes, ext, media_type]
        const [data, extension, mediaType] = arr;
        return {
          bytes: data instanceof Uint8Array ? data : new Uint8Array(data),
          extension,
          mediaType,
        };
      } finally {
        fn.destroy();
      }
    }
    case 'inventory': {
      const fn = pyodide.globals.get('_do_inventory');
      try {
        return fn(payload.bytes, payload.target || '');
      } finally {
        fn.destroy();
      }
    }
    case 'validateMapping': {
      const fn = pyodide.globals.get('_do_validate');
      try {
        const result = fn(payload.text || '', payload.target || '');
        return result.toJs({ dict_converter: Object.fromEntries });
      } finally {
        fn.destroy();
      }
    }
    case 'defaultMapping': {
      const fn = pyodide.globals.get('_do_default_mapping');
      try {
        return fn(payload.target || '');
      } finally {
        fn.destroy();
      }
    }
    default:
      throw new Error(`Unknown method: ${method}`);
  }
}

self.addEventListener('message', async (ev) => {
  const { id, method, payload } = ev.data || {};
  try {
    const result = await handle(method, payload || {});
    respond(id, true, result);
  } catch (err) {
    respond(id, false, err && err.message ? err.message : String(err));
  }
});

// Kick off bootstrap eagerly so the user sees progress without a click.
bootstrap().catch(() => { /* already reported */ });
