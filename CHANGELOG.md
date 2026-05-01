# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial v1 implementation: ArchiMate 3.x Open Exchange XML to IriusRisk-compatible draw.io conversion.
- CLI shell (`archithreat convert | inventory | validate-mapping | show-defaults | serve`).
- Browser shell (Pyodide-based static site, no upload required).
- Self-hosted FastAPI container with HTMX UI and JSON API.
- Pluggable emitter architecture; v1 ships one emitter (`drawio-iriusrisk`).
- YAML-based mapping table with Pydantic-validated schema.
- Inventory mode for target-independent model surveys.
