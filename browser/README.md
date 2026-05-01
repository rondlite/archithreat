# archithreat — browser shell

A static site that runs the `archithreat` conversion core entirely in the
user's browser via [Pyodide](https://pyodide.org/). No backend; nothing
leaves the user's machine after page load.

This directory builds into a self-contained `dist/` you can drop behind any
static host (GitHub Pages, S3, an internal nginx, anything).

## Output target

The Convert tab and the Mapping editor each carry an "Output target" dropdown.
Pick `IriusRisk (draw.io)` to emit a `.drawio` XML file consumable by
IriusRisk, or `OWASP Threat Dragon (JSON)` to emit a Threat Dragon v2 `.json`
model. The selection drives both the Python emitter (via `convert_bytes(..., 
target=...)`) and the mapping schema used when validating or loading a
default mapping — the two targets ship distinct mapping schemas, so the
editor's dropdown should match the schema you intend to author.

## Stack

- **Vanilla JS** — no React/Vue/Svelte/etc. (spec §6.8)
- **Pyodide 0.26.4** — vendored locally; not loaded from a CDN at runtime
  (spec §10.7)
- **Web Worker** — Pyodide runs off the main thread (spec §6.9)
- **esbuild** — build-only dependency for JS bundling

## Prerequisites

- Node.js 20+ (for `esbuild`, the dev server, and the vendor script)
- Python 3.11+ with the `build` package (for the wheel build step):
  `pip install build`
- Network access **once**, to vendor Pyodide (`npm run vendor:pyodide`)

## One-time setup

```bash
cd browser
npm install                 # installs esbuild
npm run vendor:pyodide      # downloads Pyodide 0.26.4 into vendor/pyodide/
```

`vendor/pyodide/` is not committed; the `.gitignore` keeps everything except
the `.gitkeep` placeholder out of source control. The pinned Pyodide version
lives in `scripts/vendor-pyodide.mjs` — bump it deliberately.

## Build

```bash
npm run build               # bundle JS + copy HTML/CSS + vendored Pyodide → dist/
npm run build:wheel         # build archithreat-*.whl into dist/wheels/
printf '{"wheel": "%s"}\n' "$(ls dist/wheels/*.whl | head -1 | xargs -n1 basename)" \
  > dist/wheels/index.json
```

Order matters: `npm run build` wipes `dist/` before recreating it, so run
`build:wheel` **after** `build`. Then write `wheels/index.json` so the worker
can find the version-suffixed wheel filename without guessing.

The two scripts are separate because `build:wheel` shells out to Python and
is unnecessary if you're iterating on JS only. Re-run `build:wheel` whenever
the core package version changes.

After both have run, `dist/` contains:

```
dist/
├── index.html
├── style.css
├── main.js                 (bundled, minified)
├── main.js.map
├── worker.js               (bundled separately for worker context)
├── worker.js.map
├── pyodide/                (vendored Pyodide runtime)
│   ├── pyodide.js
│   ├── pyodide.asm.wasm
│   └── …
└── wheels/
    └── archithreat-2.0.0-py3-none-any.whl
```

All paths are relative, so the same `dist/` works under any URL prefix
(e.g., `https://username.github.io/archithreat/`).

## Serve locally

```bash
npm run dev                 # build + serve on http://127.0.0.1:8080
# or, if dist/ already built:
npm run serve
```

The dev server is ~70 lines of Node `http`; no extra dependencies.

## Verify

Open the page, watch the status panel switch from "Loading runtime…" to
"Pyodide ready", then exercise:

1. **Convert** — pick `examples/airport_demo.xml`, click **Convert**, check
   that a `.drawio` file downloads.
2. **Inventory** — pick the same file, click **Run inventory**, check that a
   formatted report appears.
3. **Validate mapping** — click **Load default**, then **Validate** — should
   report a valid mapping.

Open DevTools → Network. After the initial assets load, no further requests
should fire when you run a conversion. That's the whole privacy claim.

## Smoke test

A Playwright smoke test lives at `tests/browser/test_smoke.py`. It is marked
`browser` and `slow`, and skips gracefully if Playwright browsers are not
installed or `dist/` does not exist.

```bash
cd ..
.venv/bin/python -m playwright install chromium       # one-time
cd browser && npm run build && npm run build:wheel    # produce dist/ (order matters)
cd .. && .venv/bin/pytest -m browser tests/browser/   # run the smoke test
```

## Publishing (deferred)

`pages.yaml` in `.github/workflows/` will publish `dist/` to GitHub Pages on
tagged releases. Until then, the workflow is intentionally not wired up:
running the static site is a single `npm run dev` away, and Ron's first
deploy target may be elsewhere.

## Layout

```
browser/
├── package.json            # esbuild + scripts; no framework deps
├── index.html              # single page; three tabs + mapping editor
├── style.css               # minimal, color-blind-safe (Okabe–Ito), no fonts
├── main.js                 # main thread: UI, file plumbing, worker bridge
├── ui.js                   # tab/status/file helpers
├── worker.js               # Pyodide host; calls into the Python core
├── scripts/
│   ├── build.mjs           # bundle + copy → dist/
│   ├── serve.mjs           # tiny static dev server
│   └── vendor-pyodide.mjs  # one-time Pyodide download
├── vendor/pyodide/         # ignored except for .gitkeep; populated by vendor:pyodide
└── dist/                   # build output; ignored
```

## Notes

- The worker uses classic-script `importScripts('./pyodide/pyodide.js')` —
  Pyodide 0.26.x ships a script that registers `loadPyodide` on the global
  scope, which is what we want from a worker bundled by esbuild.
- The wheel is installed via `micropip.install(localUrl, deps=False)` —
  `lxml`, `pydantic`, and `pyyaml` are already provided by Pyodide's package
  set, so we don't need PyPI access for the deps either.
- The build script writes `wheels/index.json` only if you choose to add a
  manifest step yourself. For the default single-wheel layout, the worker
  guesses the filename based on `pyproject.toml`'s pinned version.
