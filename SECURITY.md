# Security

Purpose: how to report vulnerabilities in [archithreat](src/archithreat/__init__.py), and the threat model of the tool itself.

## Reporting a vulnerability

If you have found a security issue:

- **Preferred:** open a GitHub issue on this repository with the `security` label.
- **Email:** rondlite@gmail.com (Ron, project owner).

Please include enough detail for the issue to be reproduced — a fixture, a request, or a stack trace if you have one. If the issue exposes user content or model data, redact before sending.

There is no PGP key requirement and no formal SLA. The project is maintained by individuals; expect a response in days, not hours. Critical issues affecting the published Docker image or browser bundle will receive priority over feature work.

## Threat model of the tool itself

archithreat ingests untrusted XML and untrusted YAML and emits XML or JSON. The threats below are the ones the design takes seriously.

### XXE (XML External Entity)

The web shell receives untrusted XML uploads. XXE attacks can otherwise read local files, contact internal network endpoints, or expand into denial-of-service via entity expansion ("billion laughs").

**Mitigation:** the parser ([`core/parser.py`](src/archithreat/core/parser.py)) constructs `lxml.etree.XMLParser` with:

- `resolve_entities=False` — external entities are not resolved.
- `no_network=True` — the parser will not contact external URIs.
- `huge_tree=False` — entity expansion is bounded; pathological documents are rejected.

The CLI and browser shells use the same hardened parser settings, for consistency rather than necessity.

### Denial of service via large or pathological inputs

The parser, resolver, mapper, and emitter are O(n) in element/relationship counts but do allocate. A huge upload can exhaust memory; a pathological structure (deeply nested compositions, dense relationship graphs) can chew CPU.

**Mitigation in the web shell:**

- Upload size is bounded by `ARCHITHREAT_MAX_UPLOAD_MB` (default 50). Enforced at the streaming layer in [`web/limits.py`](src/archithreat/web/limits.py); requests exceeding the limit are rejected before the parser sees them.
- Per-request wall-clock timeout via `ARCHITHREAT_REQUEST_TIMEOUT_SECONDS` (default 120). On timeout the response is 504.
- Per-IP rate limiting via `ARCHITHREAT_RATE_LIMIT_PER_MINUTE` (default 30). Setting this to 0 disables it; do not disable on internet-exposed deployments.
- XXE hardening (above) bounds entity expansion.

The CLI has no upload limit by design — it is the user's own machine and the user is the operator. Apply OS-level limits (`ulimit`, cgroups) if you run the CLI in a constrained environment.

### Authentication and authorization (deliberately out of scope)

The self-hosted container ships **no authentication and no authorization**. Anyone who can reach its bind port can convert files. This is a deliberate scope decision: the container is a stateless converter, not an application platform; building auth into it would force it to also build session handling, password storage, MFA flows, and audit logging — all of which exist as solved problems in operator-controlled infrastructure.

**Operators are expected to front the container with their own auth proxy** if they expose it beyond a trusted internal network. nginx with basic auth, oauth2-proxy, an Identity-Aware Proxy, an internal LB with mTLS — any of these are appropriate.

The container does not log user content or output, but request metadata (method, path, status, duration, client IP, request ID) is logged. If client IP is sensitive in your environment, suppress it at your reverse proxy or set `ARCHITHREAT_LOG_LEVEL=warning` to reduce log volume.

### Browser shell

The browser app runs Pyodide and the core wheel from same-origin paths in the user's own browser. There is no third-party script load, no CDN dependency, no analytics. Code executes in the user's own origin; the trust boundary is the browser's same-origin policy.

If you serve the bundle from infrastructure that injects scripts (analytics tags, performance monitoring), those scripts run in the same origin as archithreat and can read any data the page handles. The privacy guarantee in [docs/privacy.md](docs/privacy.md) applies to the bundle as shipped, not to a bundle a third party has modified.

### What this threat model does not cover

- The security of the receiving threat-modeling tool (IriusRisk, Threat Dragon, MS TMT). archithreat produces files; the receiving tool's import path is its own threat surface.
- The security of the user's source ArchiMate model. If the model itself contains secrets (credentials in element documentation, API keys in property values), those will be carried through to the output.
- Supply-chain compromise of upstream dependencies (`lxml`, `pydantic`, `pyyaml`, `fastapi`). Standard practice applies: pin versions, scan for advisories, rebuild on disclosure.
