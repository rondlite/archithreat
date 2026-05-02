# Software Bill of Materials

archithreat 3.1.0 — third-party components, versions, sources, and licenses.

This SBOM covers what archithreat **ships and vendors**. Runtime Python and
Node dependencies pulled by `pip install` / `npm install` are not vendored;
their licenses are governed by their own packages and reported by `pip
licenses` / `npm ls --license`.

## archithreat itself

| Field | Value |
|---|---|
| Name | archithreat |
| Version | 3.1.0 |
| License | Apache-2.0 — see [LICENSE](LICENSE) |
| Source | <https://github.com/rondlite/archithreat> |

## Vendored runtime components

These are downloaded by one-time vendor scripts (`browser/scripts/vendor-*.mjs`)
and copied into the published browser bundle (`browser/dist/`).

### Pyodide

| Field | Value |
|---|---|
| Name | Pyodide |
| Version | 0.26.4 |
| License | **MPL-2.0** (Mozilla Public License 2.0) |
| Source | <https://github.com/pyodide/pyodide> |
| Release | <https://github.com/pyodide/pyodide/releases/tag/0.26.4> |
| Vendor script | [browser/scripts/vendor-pyodide.mjs](browser/scripts/vendor-pyodide.mjs) |
| Vendored at | `browser/vendor/pyodide/` (gitignored) → `browser/dist/pyodide/` at build time |
| Notes | Pyodide bundles CPython, lxml, pydantic, pyyaml, and other scientific Python libraries. Each carries its own upstream license; see Pyodide's own packages manifest. MPL-2.0 applies to Pyodide's runtime code. |

### drawio viewer (jgraph/drawio)

| Field | Value |
|---|---|
| Name | drawio viewer (`viewer-static.min.js`) |
| Version | 24.7.17 |
| License | **Apache-2.0** |
| Source | <https://github.com/jgraph/drawio> |
| Release | <https://github.com/jgraph/drawio/releases/tag/v24.7.17> |
| Direct file | <https://raw.githubusercontent.com/jgraph/drawio/v24.7.17/src/main/webapp/js/viewer-static.min.js> |
| Vendor script | [browser/scripts/vendor-drawio.mjs](browser/scripts/vendor-drawio.mjs) |
| Vendored at | `browser/vendor/drawio/` (gitignored) → `browser/dist/drawio/` at build time |
| Use | In-browser preview of `iriusrisk` `.drawio` output (Convert tab → Preview button). No conversion logic depends on it; archithreat works fully without the viewer being present. |
| Notes | The viewer bundles DOMPurify (also Apache-2.0 / MPL-2.0 dual-licensed) and other small upstream JS utilities, all credited inside the minified bundle. |

### HTMX (web shell)

| Field | Value |
|---|---|
| Name | HTMX |
| Version | 1.9.x (vendor target — see notes) |
| License | **0BSD** (zero-clause BSD; effectively public-domain-equivalent) |
| Source | <https://github.com/bigskysoftware/htmx> |
| Bundled at | `src/archithreat/web/static/htmx.min.js` |
| Notes | The current file in-tree is a placeholder; before relying on the HTMX UI in production, vendor a real htmx 1.9.x release into that path. The JSON API at `/api/v1/*` does not depend on htmx. See [docs/self-hosting.md](docs/self-hosting.md). |

## Runtime Python dependencies (declared, not vendored)

Resolved by `pip install archithreat` from PyPI. Versions are minimums; the
solver picks the latest compatible release at install time.

| Package | Min version | License (typical) |
|---|---|---|
| lxml | 5.0 | BSD-3-Clause |
| pydantic | 2.5 | MIT |
| pyyaml | 6.0 | MIT |
| click (CLI extra) | 8.1 | BSD-3-Clause |
| fastapi (web extra) | 0.110 | MIT |
| uvicorn (web extra) | 0.27 | BSD-3-Clause |
| jinja2 (web extra) | 3.1 | BSD-3-Clause |
| python-multipart (web extra) | 0.0.9 | Apache-2.0 |
| slowapi (web extra) | 0.1.9 | MIT |

Run `pip licenses --packages archithreat` (or `pip-licenses`) on a real
install to capture the exact resolved set with full license text.

## Build-time-only dependencies (not shipped)

These do not appear in the published wheel or browser bundle.

| Package | Use | License |
|---|---|---|
| esbuild | JS bundling for browser shell | MIT |
| build (PyPA) | wheel build for browser shell | MIT |
| pytest, pytest-cov, hypothesis, ruff, mypy, httpx, playwright, pre-commit | development & testing | various MIT/BSD/Apache-2.0 |

## IriusRisk component library (data, not code)

The `iriusrisk` default mapping ([src/archithreat/core/defaults/iriusrisk.yaml](src/archithreat/core/defaults/iriusrisk.yaml))
contains component-definition reference IDs and trust-zone UUIDs that
target the **IriusRisk CD-V2-* shape library**. Those IDs are data
generated against a live IriusRisk REST API by
[scripts/regen_iriusrisk_defaults.py](scripts/regen_iriusrisk_defaults.py)
and are not third-party code. archithreat does not redistribute the
IriusRisk shape definitions, icons, or threat catalogues.

## License compatibility summary

| Component | License | Compatible with Apache-2.0 distribution? |
|---|---|---|
| archithreat | Apache-2.0 | — |
| Pyodide | MPL-2.0 | Yes (file-level copyleft; archithreat does not modify Pyodide files). |
| drawio viewer | Apache-2.0 | Yes. |
| HTMX | 0BSD | Yes. |

The published browser bundle (`browser/dist/`) is therefore distributable
under Apache-2.0 with attribution preserved for the vendored components.
Each vendored payload carries its own upstream license header inside the
file (visible if you open the minified script in an editor).
