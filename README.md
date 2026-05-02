# archithreat

[![CI](https://github.com/rondlite/archithreat/actions/workflows/ci.yaml/badge.svg)](https://github.com/rondlite/archithreat/actions/workflows/ci.yaml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Convert **ArchiMate 3.x** architecture models into **threat-modeling artifacts**, preserving logical trust zones, host containment, and connection semantics. Two output targets ship: **IriusRisk-compatible draw.io** and **OWASP Threat Dragon v2 JSON**. The codebase is structured so further targets slot in without rework.

## Why

Threat-modeling tools that consume diagrams expect specific input formats (draw.io for IriusRisk, `.tm7` for Microsoft TMT, JSON for OWASP Threat Dragon). None ingest ArchiMate directly. Organizations doing serious EA in ArchiMate (TOGAF, BiZZdesign, Sparx EA) have no path from authoritative architecture into their threat model except manual reconstruction. archithreat closes that gap.

## Privacy by design

Architecture models for critical infrastructure describe attack surfaces and frequently cannot leave their owning organization. archithreat ships **three surfaces, no hosted service**:

- **CLI** — local conversion for engineers and CI pipelines.
- **Browser app** — static site (Pyodide); runs entirely in your browser, no upload.
- **Self-hosted container** — FastAPI image you run inside your trust zone.

## Install (CLI)

```bash
pip install archithreat[cli]
archithreat convert input.xml output.drawio --target iriusrisk
archithreat convert input.xml output.json    --target threatdragon
archithreat targets
```

## Browser app

Open the published GitHub Pages site, drop your `.xml` in, pick a target from the dropdown, download the `.drawio` or `.json`. Nothing leaves your browser.

## Self-hosted container

```bash
docker run --rm -p 8000:8000 ghcr.io/rondlite/archithreat:latest
# open http://localhost:8000
```

## Documentation

- [docs/concepts.md](docs/concepts.md) — modeling discipline behind the conversion
- [docs/mapping-table.md](docs/mapping-table.md) — YAML schema + customization
- [docs/patterns.md](docs/patterns.md) — supported patterns
- [docs/limitations.md](docs/limitations.md) — known gaps and future work
- [docs/self-hosting.md](docs/self-hosting.md) — Docker deployment
- [docs/browser.md](docs/browser.md) — browser app capabilities
- [docs/privacy.md](docs/privacy.md) — what each surface does and does not see
- [docs/targets.md](docs/targets.md) — supported output targets
- [docs/adding-a-target.md](docs/adding-a-target.md) — contributor guide for new emitters

## Status

v3.1.0. See [CHANGELOG.md](CHANGELOG.md) and [ROADMAP](docs/limitations.md#future-work).

## License

Apache 2.0 — see [LICENSE](LICENSE). For third-party / vendored components and their licenses (Pyodide, drawio viewer, HTMX, declared Python deps), see [SBOM.md](SBOM.md).
