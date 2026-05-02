# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.0.1] - 2026-05-02

### Fixed
- Full `iriusrisk.yaml` component-ref regeneration. The bundled mapping
  carried refs scraped from the outdated public IriusRisk Community
  GitHub repo; current Community and Enterprise installations both ship
  the **CD-V2-*** namespace, so on import IriusRisk treated every cell
  as a stub component (shape recognized, no library binding, no threats
  attached). All 118 distinct refs in the YAML — across AWS, Azure, GCP,
  OCI, Kubernetes, databases, identity, web servers, network, messaging,
  SaaS, and generic shapes — now resolve to refs that exist in the live
  installed library. Verified against a live IriusRisk REST API
  (`/api/v2/components`, 1408 active component definitions catalogued).

### Added
- `scripts/regen_iriusrisk_defaults.py` — pages the IriusRisk REST API,
  caches the component catalog locally (gitignored, installation-private),
  rewrites every `ir.componentDefinition.ref=<x>` and `component_type:`
  field in `iriusrisk.yaml` to its CD-V2 equivalent, and reports any
  unmapped refs. Run on library version bumps via
  `IRIUSRISK_BASE_URL=<url> IRIUSRISK_TOKEN=<token> python
  scripts/regen_iriusrisk_defaults.py`.

### Changed
- `iriusrisk` default mapping `zone_rules` extended with name-pattern
  matches for the most common deployment-typical Grouping names so they
  bind to the right standard IriusRisk trust zone instead of falling to
  the catch-all: `dmz|perimeter|edge` → Public; `private[- ]?secured|
  internal|intranet|backend|backoffice|production|prod|corporate|
  on[- ]?prem|workplace|office|warehouse|shop[- ]?floor|factory|plant`
  → Private Secured; `payment|billing|finance|vendor|gateway|provider`
  → Trusted Partner. Existing canonical patterns (`internet`,
  `public cloud`, `public`, `third-party|saas|vendor`, `trusted partner`)
  unchanged. Modelers using these names get correct, distinct trust
  zones in IriusRisk on import.
- Lemonade demo Groupings renamed to canonical IriusRisk zone names
  (`Internet`, `Public`, `Private Secured`, `Trusted Partner`,
  `Third Party / SaaS`) so the example fixture imports as 5 distinct
  standard zones with no `zone_name_unrecognized` warnings. Component
  IDs (`z_dmz`, `z_internal`, `z_payments`, `z_shop`) unchanged for
  diff stability; only the visible zone labels changed.
- Default `iriusrisk` mapping fallback for unrecognized `Grouping`/`Location`
  zones changed from **Private Secured** (`ir.ref=2ab4effa-…`) to **Internet**
  (`ir.ref=f0ba7722-…`) per threat-modeling convention: an unidentified zone
  is, by default, untrusted. The resolver now emits a `zone_name_unrecognized`
  warning whenever the catch-all fires so the fallback is never silent.
  Existing CLI `--strict` flag fails on the warning. Override by adding a
  name-patterned rule above the catch-all for your installation's zones.

### Fixed
- Mapper folds the synthetic `external` zone into a real zone whose name or
  target-identity key matches (for `iriusrisk`, the `ir.ref` UUID parsed
  from the zone's mxCell style). Previously, a model containing a real
  Internet `Grouping` plus any actor without explicit zone composition
  would emit two trust zones with the same `ir.ref`, which IriusRisk
  imports as a collision and silently drops one — leaving the actor
  unzoned. Components routed through the synthetic now land in the real
  zone instead. Selection prefers a real zone whose **name** matches the
  synthetic's, then falls back to identity-key matching, so multiple real
  zones sharing a fallback key don't misroute the synthetic.
  Generalized via `BaseMapping.zone_identity_key()`; subclasses override
  (only `iriusrisk` does today).
- `examples/lemonade_shop.xml` and `tests/fixtures/lemonade_shop.xml`:
  added explicit `Composition z_internet → ba_kitchen` so Kitchen Staff
  is in the Internet zone by model intent rather than falling through
  the synthetic-external dedupe path. Added `data_classification: internal`
  to Inventory DB so it tints identically to Orders DB on IriusRisk
  import.

## [3.0.0] - 2026-05-02

### Changed (BREAKING — target id rename)
- Target id `drawio-iriusrisk` renamed to `iriusrisk` for consistency with
  `threatdragon` (single-tool name) and the existing `iriusrisk:` per-target
  blocks already used in mapping YAML. The CLI `--target iriusrisk` flag,
  `archithreat targets` output, JSON API `target` field, browser shell
  dropdown values, and the `target:` field in mapping YAML all use the new
  id. CLI `--help` now states explicitly that `iriusrisk` emits draw.io /
  mxGraph XML for IriusRisk.
- Existing mapping YAML files declaring `target: drawio-iriusrisk` must be
  updated to `target: iriusrisk`. No automatic backward-compat alias.
- Internal renames: `src/archithreat/core/emitters/drawio_iriusrisk.py` →
  `iriusrisk.py`, `core/mappings/drawio_iriusrisk.py` → `iriusrisk.py`,
  `core/defaults/drawio_iriusrisk.yaml` → `iriusrisk.yaml`,
  `tests/fixtures/expected/drawio_iriusrisk/` → `expected/iriusrisk/`.
  Class names (`DrawioIriusriskEmitter`, `DrawioMapping`, `DrawioStyleSpec`,
  …) keep the `Drawio` prefix — they describe draw.io implementation
  detail, not the user-facing target id.

## [2.0.1] - 2026-05-02

### Changed
- Threat Dragon default mapping no longer maps `Node`, `Device`,
  `SystemSoftware`, or `Artifact` to TD's `process` stencil. TD has no host
  concept, so emitting hosts as duplicate processes was noise in TD's STRIDE
  view. The mapper's `unmatched_element: skip_with_warning` policy drops
  them silently from TD output. IriusRisk output is unaffected — hosts still
  render as container shapes per spec §6.3.
- `examples/pet_shop.xml` and `tests/fixtures/pet_shop.xml` rebuilt as a
  cross-target fixture: apps realize onto hosts (IriusRisk gets nested
  containment), Postgres serves both data stores, two trust zones. Same
  fixture produces idiomatic output for both targets — IriusRisk shows
  three-tier nesting; TD shows flat STRIDE with hosts skipped.

## [2.0.0] - 2026-05-02

### Added (BREAKING — new emitter target + user-facing target selection)
- **Second emitter target: `threatdragon`** (OWASP Threat Dragon v2 JSON).
  Maps ArchiMate elements to TD STRIDE stencils:
  ApplicationComponent → process (with `isWebApplication: true` for
  `tech_stack=web`); DataObject → store (auto-detects credentials, audit
  logs, encrypted classifications); BusinessActor / BusinessRole → actor;
  Grouping / Location → trust-boundary-box. Flows carry `protocol`,
  `isEncrypted`, `isPublicNetwork` data.
- **User-facing target selection** (per spec §6.11) ships across all surfaces:
  - CLI: `archithreat convert ... --target {drawio-iriusrisk|threatdragon}`,
    same flag on `inventory`, `validate-mapping`, `show-defaults`.
  - CLI: new `archithreat targets` lists registered targets with extension
    and media type.
  - JSON API: `target` form field on `POST /api/v1/convert`,
    `POST /api/v1/inventory`, `POST /api/v1/mapping/validate`;
    `?target=<id>` query string on `GET /api/v1/mapping/default`.
    Unknown target returns `{"error": {"code": "unknown_target"}}` 400.
  - HTMX UI: target dropdown on convert / inventory / validate-mapping pages.
  - Browser shell: target dropdown on the Convert tab and inside the
    Mapping editor.
- New TD-flavoured demo fixture `examples/pet_shop.xml` exercising
  TD-idiomatic patterns (credential store, audit log, HTTPS flows,
  external actor).
- `tests/fixtures/expected/threatdragon/` golden outputs for all 6
  fixtures (minimal, co_hosted, external_actor, orphans, lemonade_shop,
  pet_shop).

### Changed
- `archithreat.core.emitters.EMITTERS` registry now has 2 entries.
  Code that depended on the registry having exactly one entry has been
  updated; if you scripted around `available_targets()` returning a
  single-element list, that assumption no longer holds.

### Documentation
- `docs/targets.md` documents both targets with import procedures and
  per-target stencil mappings.
- `docs/adding-a-target.md` retroactively validated by this exercise.

## [1.1.0] - 2026-05-01

### Changed (BREAKING — review imports into IriusRisk)
- Default mapping rebuilt from IriusRisk's public Community shape libraries
  (https://github.com/iriusrisk/Community/tree/master/ShapeLibraries):
  - Trust zones grew from 4 to 6 (added Public, Public Cloud, Third Party / SaaS
    UUIDs from `Trust_zone_IriusRisk.xml`).
  - Component rules grew from 18 to 140, with name-pattern dispatch covering
    AWS (S3, EC2, Lambda, RDS, DynamoDB, CloudFront, API Gateway, Cognito,
    SQS/SNS, IAM, Kinesis, ECS/EKS/Fargate, ElastiCache, MSK), Azure (Blob,
    Cosmos, Functions, Key Vault, SQL, AD, AKS, Redis, VM), GCP (Compute
    Engine, Storage, BigQuery, GKE, Functions, Pub/Sub, IAM), databases
    (Postgres, MySQL, MariaDB, MS SQL, Mongo, SQLite, Redis, Oracle,
    Cassandra, CouchDB, IBM Db2, Neo4j, Hazelcast, Informix, Riak),
    identity (OAuth2 AS/RS/client, OIDC IdP/RP, SAML IdP/SP, Kerberos, LDAP,
    Active Directory), web servers (NGINX, Apache HTTP, Tomcat, IIS, FTP,
    SSH, IBM WebSphere), network (LB, Firewall, Proxy, Router, DNS, VPN,
    CDN, ISP), containers (Docker + Kubernetes), messaging (Kafka, MQTT),
    SaaS (WordPress, Drupal, Joomla, CMS, CRM, ERP, SIEM, IDS, IPS, EDR,
    XDR, DLP, Antivirus), payment, browser / mobile / Android / iOS, IoT.
- Component refs switched from `CD-V2-*` (custom IriusRisk variant prefix)
  to canonical Community library refs (e.g. `web-ui`, `postgresql`,
  `CD-NGINX`). The `CD-V2-*` prefix is not present in IriusRisk's public
  shape libraries; if your installation requires it, copy the bundled
  default and override the refs.
- DataObject default is now `other-database` (verified canonical fallback)
  instead of `CD-V2-POSTGRESQL`. DataObjects with name patterns matching
  postgres/mysql/mongo/etc. resolve to specific database refs.
- BusinessActor / BusinessRole default is now `CD-BROWSER` (closest stock
  Community shape; no first-class human-actor shape exists in the public
  library).

### Fixed
- YAML double-quoted strings interpret `\b` as backspace, silently breaking
  every regex word-boundary in `name_pattern` values. All patterns now use
  YAML single quotes so regex metacharacters pass through verbatim.

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
