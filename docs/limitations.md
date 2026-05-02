# Limitations

Purpose: an honest list of what [archithreat](../src/archithreat/__init__.py) (currently 3.0.1) does not do, why it does not do it, and when it might.

## Contents

- [Currently out of scope](#currently-out-of-scope)
- [Future work](#future-work)

## Currently out of scope

**ArchiMate Physical layer (Equipment, Facility, Distribution Network).** Doubles mapping complexity and forces nested-vs-composite zone decisions that benefit from real downstream feedback. The parser preserves physical-layer information; the resolver and mapper skip it with a warning. Trust zones are logical only.

**Realizations crossing into Physical.** Skipped with a warning. Application-on-equipment realization is deferred until physical-layer support lands.

**Motivation, Strategy, Implementation & Migration layers.** Silently ignored. They describe organizational rationale and project tracking, not attack surface.

**Junction elements.** Warned and skipped. Flattening at the source model is the documented workaround; see [patterns.md anti-patterns](patterns.md#junctions-used-as-logic).

**Derived relationships.** Out of scope by definition: derived relationships exist in views but not as model elements, so the parser cannot see them. Materialize them as explicit relationships in the source model if you need them.

**Re-import / sync / merge into existing threat models.** archithreat is one-shot conversion today. Idempotent re-import (matching components in the target by ArchiMate ID) is roadmap work, see below.

**Direct REST API integration with any threat-modeling vendor.** archithreat produces files; the user imports them on the receiving side. REST API push is roadmap work.

**Layout fidelity to the source view geometry.** Deterministic auto-layout. View geometry was laid out for ArchiMate notation, not the target's containment model, and frequently produces broken visuals when components nest into hosts. Modelers will hand-adjust in the receiving tool. A `--preserve-layout` opt-in is on the roadmap.

**A public hosted service.** Architecture models for critical infrastructure describe attack surfaces and frequently cannot leave their owning organization by policy or contract. The browser app and self-hosted container cover the web-UX audience without violating the constraint by construction. See [privacy.md](privacy.md).

**User accounts, sessions, persistence, multi-tenancy, RBAC, audit trails.** The self-hosted container is a stateless converter, not an application platform. Operators front it with their own auth proxy if they want any of these.

**Helm charts, Kubernetes manifests, docker-compose.** The container ships; orchestration is the operator's responsibility. Operators who can run a container orchestrator can write 30 lines of manifest; operators who cannot are better served by the browser app.

## Future work

The roadmap is the spec's roadmap, not a marketing roadmap. Dates are not commitments.

### Already shipped (this is the current state)

- **Two emitters**: `iriusrisk` (draw.io / mxGraph for IriusRisk) and `threatdragon` (OWASP Threat Dragon v2 JSON). See [targets.md](targets.md).
- **User-facing target selection** across all surfaces: `--target` CLI flag (plus `archithreat targets`), `target` field on JSON API, target dropdown in browser shell + HTMX UI.
- **Full IriusRisk library coverage**: 118 component rules in the bundled `iriusrisk.yaml` resolve to refs that exist in current Community / Enterprise installations (CD-V2-* namespace). Regen pipeline at [`scripts/regen_iriusrisk_defaults.py`](../scripts/regen_iriusrisk_defaults.py) keeps the mapping fresh against any installation.
- **Trust-zone dedupe**: synthetic external zone folds into a real Grouping with the same target identity (e.g. matching `ir.ref` UUID), so actors without explicit zone composition land in the right zone instead of creating a duplicate Internet boundary.
- **Browser-side preview** of `iriusrisk` output via vendored drawio viewer — no upload, no third-party iframe.

### Roadmap — quality of life

- Source view geometry as optional layout source (`--preserve-layout`).
- Improved auto-layout (graphviz `dot` via `pydot` in CLI/server; pure-Python fallback in browser).
- Per-view conversion (one diagram per ArchiMate view rather than one merged).
- Service worker for full offline use of the browser app.

### Roadmap — physical layer

- Physical layer parsing (Equipment, Facility, Distribution Network).
- 2D zoning: composite zone names (`partner-network @ public-edge`) first; nested zones once IriusRisk threat-library behavior with nested zones is confirmed.
- Property passthrough for physical-zone-derived attributes.
- Additional emitters as demand surfaces: Microsoft Threat Modeling Tool `.tm7`, OTM (Open Threat Model).

### Roadmap — REST API targets

- Direct REST API push as an alternative to file output, for targets that support it (IriusRisk first).
- Idempotent re-import: detect existing components by ArchiMate ID stored in target metadata; update rather than recreate.
- Sync mode: diff source model against existing threat model; apply changes only.

### Speculative

- Other source formats: Archi `.archimate`, Sparx EA via Open Exchange, plain ArchiMate XML.
- Plugin architecture so target mappings live as separately installable packages, versioned per shape library.
