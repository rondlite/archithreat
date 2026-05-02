# Browser app

Purpose: capabilities, limits, and self-hosting guidance for [archithreat](../src/archithreat/__init__.py)'s browser shell — the static-site distribution that runs entirely client-side via Pyodide.

## Contents

- [Capabilities](#capabilities)
- [Performance and size limits](#performance-and-size-limits)
- [Offline use](#offline-use)
- [Hosting the bundle yourself](#hosting-the-bundle-yourself)
- [Verifying the privacy claim](#verifying-the-privacy-claim)

## Capabilities

The browser app exposes the same three core flows as the CLI:

- **Convert** — upload an ArchiMate XML file, pick a target (`iriusrisk` → `.drawio`, `threatdragon` → `.json`), preview the diagram inline (iriusrisk only, drawio viewer is vendored locally) or download the output.
- **Inventory** — upload an ArchiMate XML file, see a structured report of element counts, realization coverage, zone coverage, co-hosting analysis, and warnings.
- **Validate mapping** — paste or load a YAML mapping into the editor, validate it against the schema, see structured errors.

A built-in mapping editor sits beside the Convert form. The default mapping is prefilled. "Load default" repopulates it; "Validate" runs schema validation. On Convert, the editor's content is the active mapping; if empty, the bundled default is used.

All three flows execute in a Web Worker so the UI stays responsive during conversion and so a stuck conversion can be cancelled by terminating the worker.

## Performance and size limits

**Cold start: ~3–5 seconds** while Pyodide bootstraps and the core wheel installs from a same-origin path. After that, conversions run at near-CLI speed for the same input.

**File size practical ceiling: ~100 MB**, with a soft warning at 50 MB. Pyodide runs in WebAssembly with a memory budget bounded by the browser; very large models can hit that ceiling. For models in the millions of elements, run the CLI instead.

Inventory is cheaper than Convert because it terminates after the resolver stage (no emission, no output buffer).

## Offline use

Everything is vendored. Pyodide and the core wheel ship in the `dist/` bundle. Once the page has loaded, no network requests are made — for user content, for runtime dependencies, or for telemetry. The page works fully offline after first load.

A service worker for full first-visit offline use is on the roadmap; today, you need network connectivity for the first visit, then it works offline.

## Hosting the bundle yourself

The browser app is a static site. The build output (`browser/dist/` after `npm run build`) is HTML, CSS, JavaScript, the vendored Pyodide runtime, and the core Python wheel. Drop it behind any static host:

- **nginx**: copy `dist/*` into `/var/www/archithreat/` and serve it with a one-block server config. Set `Cache-Control: immutable` on hashed assets.
- **S3 + CloudFront**: sync `dist/` to a bucket (`aws s3 sync dist/ s3://your-bucket/`), point a CloudFront distribution at it. Public bucket or signed URLs, your call.
- **Azure Blob Storage** with the static-website feature, or **GCS** with the same.
- **Internal IIS** for shops with on-premise Windows: copy `dist/` to `wwwroot\archithreat\`, mark it as a static-content site.
- **GitHub Pages**: a publish workflow at `.github/workflows/pages.yaml` is included as a reference deployment.

The bundle has no backend dependency. There is nothing for the host to run beyond serving files.

If your static host or CDN sits behind a corporate proxy that injects script tags, be aware: the privacy claim ("no network requests after page load") is only true for the bundle as shipped. Injected analytics scripts violate it.

## Verifying the privacy claim

The browser app makes no network requests after page load. You can confirm this directly:

1. Open the browser app in any modern browser.
2. Open developer tools, switch to the Network tab.
3. Wait for Pyodide to finish loading (the UI becomes interactive).
4. Clear the network log.
5. Run a conversion against a real model file.
6. Observe: no entries in the network log. The file never leaves your machine.

If you see a request, that is a bug — file an issue. The browser shell uses the File API to read the upload into an `ArrayBuffer` and a Blob URL to trigger the download; neither touches the network.
