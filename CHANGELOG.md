# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
