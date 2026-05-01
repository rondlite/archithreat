# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.4] - 2026-05-01

### Fixed
- Wheel build no longer produces duplicate ZIP entries. The `force-include`
  block overlapped with the `packages` discovery, causing PyPI to reject
  the upload (PEP 625 archive validation). Default mapping YAML is now
  bundled via standard package data discovery.

## [1.0.3] - 2026-05-01

### Changed
- Version bump to keep PyPI in sync with the GitHub tag (1.0.1 and 1.0.2
  were used during initial trusted-publisher setup; no PyPI release exists
  for those tags). 1.0.3 is the first PyPI release.

## [1.0.1] - 2026-05-01

### Changed
- Default mapping (`drawio-iriusrisk.yaml`) audited against real IriusRisk
  template exports. Replaced placeholder shape IDs with verified `CD-V2-*`
  component-library refs (Web UI, Web Service, Mobile UI, Browser, Web Client,
  PostgreSQL, MySQL, Microsoft SQL Server, MongoDB NoSQL, SQLite, Redis,
  NGINX server/ingress, OpenShift cluster/control-plane/gateway/pod).
- Trust zones now use canonical IriusRisk UUIDs: Internet, Private Secured,
  Trusted Partner, Untrusted Third-Party SaaS — dispatched by name pattern.
- Edge style updated to IriusRisk's curved gray data-flow visual; stripped
  invented `ir.type=DATAFLOW` attribute that does not appear in real exports.

### Fixed
- Parser accepts any bytes-like input (bytes, bytearray, memoryview, Pyodide
  `Uint8Array` proxy). Previously rejected non-`bytes` inputs with lxml's
  "can only parse strings" error in the browser shell.
- Resolver: `Device` and `SystemSoftware` are now treated as `Node` subtypes
  for realization-walking, matching ArchiMate 3 semantics.
- Resolver: `ApplicationComponent` zone is inherited from its host's zone
  when no direct containment edge exists — fixes apps falling to `__unzoned__`
  in models that use realization-only host placement.
- Lemonade demo fixture tightened: Postgres app on db-server, DataObjects
  composed into Internal Network zone — no more dangling host or unzoned
  data.
- Pages workflow: build the browser bundle BEFORE the wheel; emit
  `dist/wheels/index.json` so the worker resolves version-suffixed wheels.

## [1.0.0] - 2026-05-01

### Added
- Initial v1 implementation: ArchiMate 3.x Open Exchange XML to IriusRisk-compatible draw.io conversion.
- CLI shell (`archithreat convert | inventory | validate-mapping | show-defaults | serve`).
- Browser shell (Pyodide-based static site, no upload required).
- Self-hosted FastAPI container with HTMX UI and JSON API.
- Pluggable emitter architecture; v1 ships one emitter (`drawio-iriusrisk`).
- YAML-based mapping table with Pydantic-validated schema.
- Inventory mode for target-independent model surveys.
