# Limitations

Purpose: an honest list of what [archithreat](../src/archithreat/__init__.py) v1 does not do, why it does not do it, and when it might.

## Contents

- [Out of scope for v1](#out-of-scope-for-v1)
- [Future work](#future-work)

## Out of scope for v1

**ArchiMate Physical layer (Equipment, Facility, Distribution Network).** Doubles mapping complexity and forces nested-vs-composite zone decisions that benefit from real downstream feedback. The parser preserves physical-layer information; the resolver and mapper skip it with a warning. v1 zones are logical only.

**Realizations crossing into Physical.** Skipped with a warning. Application-on-equipment realization is a v2 question.

**Motivation, Strategy, Implementation & Migration layers.** Silently ignored. They describe organizational rationale and project tracking, not attack surface.

**Junction elements.** Warned and skipped. Flattening at the source model is the documented workaround; see [patterns.md anti-patterns](patterns.md#junctions-used-as-logic).

**Derived relationships.** Out of scope by definition: derived relationships exist in views but not as model elements, so the parser cannot see them. Materialize them as explicit relationships in the source model if you need them.

**Re-import / sync / merge into existing threat models.** v1 is one-shot conversion. Idempotent re-import (matching components in the target by ArchiMate ID) is v3 work.

**Direct REST API integration with any threat-modeling vendor.** v1 produces files; the user imports them on the receiving side. REST API integration is v3.

**Layout fidelity to the source view geometry.** v1 uses deterministic auto-layout. View geometry was laid out for ArchiMate notation, not the target's containment model, and frequently produces broken visuals when components nest into hosts. Modelers will hand-adjust in the receiving tool. v1.1 may add `--preserve-layout` as an opt-in.

**A public hosted service.** Architecture models for critical infrastructure describe attack surfaces and frequently cannot leave their owning organization by policy or contract. The browser app and self-hosted container cover the web-UX audience without violating the constraint by construction. See [privacy.md](privacy.md).

**User accounts, sessions, persistence, multi-tenancy, RBAC, audit trails.** The self-hosted container is a stateless converter, not an application platform. Operators front it with their own auth proxy if they want any of these.

**Helm charts, Kubernetes manifests, docker-compose.** The container ships; orchestration is the operator's responsibility. Operators who can run a container orchestrator can write 30 lines of manifest; operators who cannot are better served by the browser app.

**A user-facing `--target` flag.** v1 has exactly one target (`drawio-iriusrisk`); the codebase commits to multi-target structurally (registry, per-target directories, `target_id` parameters in core APIs) but the user-facing surfaces stay single-target until v2 ships a second target. Designing the interaction model against a sample size of one would be premature.

## Future work

The roadmap is the spec's roadmap, not a marketing roadmap. Dates are not commitments.

### v1.1 — quality of life

- Source view geometry as optional layout source (`--preserve-layout`).
- Improved auto-layout (graphviz `dot` via `pydot` in CLI/server; pure-Python fallback in browser).
- Per-view conversion (one diagram per ArchiMate view rather than one merged).
- Service worker for full offline use of the browser app.

### v2 — physical zones, second target, user-facing target selection

- Physical layer parsing (Equipment, Facility, Distribution Network).
- 2D zoning: composite zone names (`partner-network @ public-landside`) at v2.0; nested zones at v2.1 once IriusRisk threat-library behavior with nested zones is confirmed.
- Property passthrough for physical-zone-derived attributes.
- Second emitter ships. Likely OWASP Threat Dragon JSON or Microsoft Threat Modeling Tool `.tm7`, depending on demand.
- User-facing target selection lands at the same time as the second target: `--target` CLI flag, `target` field in JSON API, target dropdown in the browser app and the web UI.

### v3 — REST API targets

- Direct REST API push as an alternative to file output, for targets that support it (IriusRisk first).
- Idempotent re-import: detect existing components by ArchiMate ID stored in target metadata; update rather than recreate.
- Sync mode: diff source model against existing threat model; apply changes only.

### Speculative

- Other source formats: Archi `.archimate`, Sparx EA via Open Exchange, plain ArchiMate XML.
- Plugin architecture so target mappings live as separately installable packages, versioned per shape library.
