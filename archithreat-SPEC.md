# archithreat — ArchiMate to threat-model converter

**Status:** v1 specification
**Owner:** Ron (BISO)
**Purpose:** Convert ArchiMate 3.x architecture models into threat-modeling artifacts, preserving logical trust zones, host containment, and connection semantics. v1 ships a single output target — IriusRisk-compatible draw.io — with the codebase structured so future targets (Microsoft Threat Modeling Tool, OWASP Threat Dragon, IriusRisk REST API, etc.) slot in without rework.

## Distribution surfaces

The same conversion core ships in three shells, all of which keep model data inside the user's own trust boundary:

1. **Python CLI** for power users, CI pipelines, and headless conversion.
2. **Browser app** running entirely client-side via Pyodide. Served as a static site (any static host, including GitHub Pages) but executes the conversion in the user's browser; no model data leaves the user's machine.
3. **Self-hosted FastAPI container** for organizations that want a web UI on internal infrastructure, deployed inside their own trust zone. The container is a distribution mechanism, not a service offered by the project.

**There is no public hosted service.** This is deliberate and structural: architecture models for critical infrastructure describe attack surfaces and frequently cannot legally or contractually leave their owning organization's trust zones. The browser version requires no upload; the container version runs on the user's own infrastructure. Both satisfy the constraint by construction rather than by promise.

---

## 1. Background and motivation

Threat-modeling tools that consume architecture diagrams expect specific input formats. IriusRisk uses draw.io (mxGraph) as its embedded diagram engine, recognizing components only when their mxCell `style` strings match its shape library. Microsoft Threat Modeling Tool uses `.tm7`. OWASP Threat Dragon uses a JSON schema. None of them ingest ArchiMate directly. The result is that organizations doing serious enterprise architecture in ArchiMate (TOGAF shops, BiZZdesign customers, Sparx EA users) have no path from their authoritative architecture model into their threat model except manual reconstruction.

`archithreat` produces threat-model artifacts directly from a standard ArchiMate Open Exchange XML export, so that:

- Architecture-as-source-of-truth pipelines (BiZZdesign → threat-modeling tool) become possible without manual reconstruction.
- Modeling discipline established at the EA layer (trust zones, realization, co-hosting) is preserved through to the threat model.
- Customers of threat-modeling vendors can pressure-test integrations before vendors ship native importers, and provide concrete feedback on edge cases.

**v1 produces one target: IriusRisk-compatible draw.io.** This is the most immediate need for the project's owner and the broadest available threat-modeling tool that uses draw.io as an editor. The codebase is organized so additional targets ship as additional emitters without changes to parsing, resolving, or shell code.

**Why three distribution surfaces?** A CLI fits the engineering audience naturally but presumes a Python toolchain. The broader audience this tool needs to reach — architects, security analysts, threat modelers — is better served by a web UI. A browser-only static site reaches anyone with a browser without requiring infrastructure or trust in a hosted service; a self-hosted container suits organizations that want a stable internal endpoint for repeat use.

**Why privacy-first by design?** Architecture models for critical infrastructure (utilities, finance, health) describe operational attack surfaces. Policies and contracts frequently forbid uploading them to third-party services. By processing entirely in the user's own trust zone — in their browser, on their CLI, or in their self-hosted container — `archithreat` meets that constraint structurally.

**Non-goals for v1:** Physical-layer support, idempotent re-import / sync, support for ArchiMate Junction / derived relationships, Motivation/Strategy/Implementation layers, server-side persistence, user accounts, authentication, multi-tenancy, audit logging, billing, any public hosted service, multiple output targets in the CLI surface (the second emitter slot exists in the code, not in the user-facing options). These are documented as future work or explicit non-goals.

---

## 2. Scope

### 2.1 In scope

**Conversion core (shared across all three shells):**

- Parsing ArchiMate 3.x Open Exchange XML (`http://www.opengroup.org/xsd/archimate/3.0/`).
- Resolving realization chains across Application and Technology layers.
- Mapping ArchiMate Grouping / Location elements to trust zones (logical only in v1).
- Mapping ArchiMate Application Components, Nodes, Business Actors, and Data Objects to threat-model components.
- Emitting parent-child containment for co-hosted Application Components inside Nodes.
- Emitting Flow / Serving / Access / Used-By relationships as connections with direction preserved.
- A YAML-based mapping table that externalizes the ArchiMate-to-target mapping.
- Pluggable emitter architecture: v1 ships exactly one emitter (`iriusrisk`); the architecture supports additional emitters in v2+.
- An inventory / lint mode that surveys the model without producing output (target-independent).
- Pure-Python implementation, Pyodide-compatible dependency footprint.

**CLI:**

- Sensible defaults and verbose diagnostics.
- Subcommands: `convert`, `inventory`, `validate-mapping`, `show-defaults`, `serve`.
- v1 CLI does not expose a `--target` flag; the single available target is implicit. v2 adds `--target` when a second emitter ships.
- Open-source-ready packaging: license, readme, contribution guide, tests, CI config, full type hints.

**Browser app:**

- Pure static site: HTML, CSS, JavaScript, vendored Pyodide and the core wheel. No backend.
- Three core flows: convert, inventory, validate mapping.
- File upload via File API, result download via Blob URL — both stay in the browser.
- Built-in mapping table editor (textarea with YAML syntax cues; load default, paste custom, validate).
- Hosting-agnostic: drop the build output behind any static host. A GitHub Pages publish workflow is included as a reference deployment.

**Self-hosted FastAPI container:**

- Single FastAPI application serving JSON API + HTMX-rendered HTML UI.
- Stateless: no database, no on-disk file writes for user content, no logs containing model contents.
- Configurable upload size and request timeouts; sensible defaults.
- Health and readiness endpoints for container orchestration.
- Single Docker image, single port, no external runtime dependencies.
- The same FastAPI app is also reachable via `archithreat serve` from the CLI for local use without Docker.

### 2.2 Explicitly out of scope (v1)

- ArchiMate Physical layer (Equipment, Facility, Distribution Network) — warn and skip.
- Realizations crossing into Physical — warn and skip.
- Motivation, Strategy, Implementation & Migration layers — silently ignore.
- Junction elements — warn and skip; document workaround.
- Derived relationships (relationships shown in views but not present as model elements) — out of scope by definition; the parser only sees explicit relationships.
- Re-import / sync / merge into existing threat models — one-shot conversion only.
- Direct REST API integration with any threat-modeling vendor — produce files, leave import to the user.
- Layout fidelity to the source view geometry — automatic layout in v1 (see §6.5).
- A public hosted service. The project ships software, not a service.
- User accounts, sessions, persistence, multi-tenancy, RBAC, audit trails.
- Helm charts, Kubernetes manifests, docker-compose. The container ships; orchestration is the operator's responsibility.
- A user-facing `--target` flag. v1 has one target; v2 introduces the flag.

---

## 3. Architecture overview

```
                              ┌──────────────────────────────┐
                              │    archithreat.core          │
                              │  parser → resolver →         │
                              │   mapper → emitter           │
                              │  (pure Python, Pyodide-safe) │
                              └──────────────────────────────┘
                                       ▲      ▲      ▲
                                       │      │      │
                ┌──────────────────────┘      │      └────────────────────┐
                │                             │                           │
        ┌───────────────┐           ┌───────────────────┐         ┌────────────────┐
        │   CLI shell   │           │  Browser shell    │         │  Web shell     │
        │   (click)     │           │  (Pyodide + JS)   │         │  (FastAPI)     │
        └───────────────┘           └───────────────────┘         └────────────────┘
                │                            │                            │
                ▼                            ▼                    ┌───────┴────────┐
        files in/out                   File API ↔ Blob            │                │
                                                          ┌───────────┐   ┌────────────┐
                                                          │ JSON API  │   │  HTMX UI   │
                                                          └───────────┘   └────────────┘
                                                                       │
                                                                       ▼
                                                            self-hosted Docker
                                                            (inside user's trust zone)
```

The conversion core is a pure Python library with no I/O coupling: it accepts bytes/strings and returns bytes/strings, never touching the filesystem itself. Each shell is a thin wrapper that supplies the I/O layer appropriate to its environment. The shells do not depend on each other.

The conversion pipeline has four pure stages plus one configuration input:

1. **Parse** — Open Exchange XML → typed in-memory model.
2. **Resolve** — walk realization chains, attach Groupings, identify external actors, classify components. Target-independent.
3. **Map** — apply the YAML mapping table to assign target-specific types and styles.
4. **Emit** — produce the target's output format. v1 ships one emitter (draw.io for IriusRisk); the architecture supports more.

Each stage is independently testable. Inventory mode terminates after stage 2 and is therefore target-independent.

---

## 4. Project structure

```
archithreat/
├── pyproject.toml                # PEP 621; dependency groups: core, cli, web, dev
├── README.md                     # Intro and quickstart for all three surfaces
├── LICENSE                       # Apache 2.0 (default; see §10 question 6)
├── CONTRIBUTING.md
├── CHANGELOG.md                  # Keep-a-changelog
├── SECURITY.md                   # Disclosure policy + threat model of the tool itself
├── Dockerfile                    # Multi-stage, slim final image
├── .dockerignore
├── .github/workflows/
│   ├── ci.yaml
│   ├── release.yaml              # PyPI wheel, Docker image, browser bundle
│   └── pages.yaml                # Publish browser app to GitHub Pages
├── docs/
│   ├── concepts.md               # ArchiMate-to-threat-model modeling discipline
│   ├── mapping-table.md          # YAML schema + customization
│   ├── patterns.md               # Supported patterns with examples
│   ├── limitations.md            # Known gaps, future work
│   ├── self-hosting.md           # Docker run, env vars, sizing notes (no manifests)
│   ├── browser.md                # Browser app: capabilities, limits, offline use
│   ├── privacy.md                # Trust-zone reasoning, what each surface does and doesn't see
│   ├── targets.md                # Per-target documentation; v1 has one entry (iriusrisk)
│   └── adding-a-target.md        # Contributor guide for new emitters (forward-looking)
├── src/
│   └── archithreat/
│       ├── __init__.py           # Re-exports core public API
│       ├── __main__.py           # python -m archithreat
│       ├── core/
│       │   ├── __init__.py
│       │   ├── parser.py
│       │   ├── model.py
│       │   ├── resolver.py
│       │   ├── mapper.py
│       │   ├── inventory.py
│       │   ├── mappings/
│       │   │   ├── __init__.py
│       │   │   ├── base.py                        # shared schema (zones, components, connections, passthrough)
│       │   │   └── iriusrisk.py            # target-specific extensions to base schema
│       │   ├── emitters/
│       │   │   ├── __init__.py                    # Emitter protocol; registry
│       │   │   └── iriusrisk.py            # the only v1 emitter
│       │   └── defaults/
│       │       └── iriusrisk.yaml          # default mapping for the v1 target
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       └── web/
│           ├── __init__.py
│           ├── app.py            # FastAPI factory
│           ├── api.py            # JSON endpoints
│           ├── ui.py             # HTMX endpoints rendering Jinja2
│           ├── settings.py       # Pydantic Settings (env-driven)
│           ├── limits.py         # Upload size, timeout, rate limit
│           ├── templates/
│           │   ├── base.html
│           │   ├── index.html
│           │   ├── result.html
│           │   └── partials/
│           │       └── *.html
│           └── static/
│               ├── style.css
│               └── htmx.min.js   # vendored, no CDN dependency
├── browser/
│   ├── package.json              # esbuild + dev server only; no framework
│   ├── index.html
│   ├── main.js                   # Pyodide bootstrap, file/blob plumbing, UI wiring
│   ├── ui.js                     # Small UI controller (vanilla)
│   ├── style.css
│   └── README.md                 # How to build and serve locally
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── minimal.xml
│   │   ├── kiosk_dmz.xml
│   │   ├── co_hosted.xml
│   │   ├── orphans.xml
│   │   └── expected/
│   │       └── iriusrisk/
│   │           └── *.drawio                       # golden outputs scoped per target
│   ├── core/
│   │   ├── test_parser.py
│   │   ├── test_resolver.py
│   │   ├── test_mapper.py
│   │   ├── test_inventory.py
│   │   ├── mappings/
│   │   │   └── test_iriusrisk.py
│   │   └── emitters/
│   │       └── test_iriusrisk.py
│   ├── cli/
│   │   └── test_cli.py
│   ├── web/
│   │   ├── test_api.py
│   │   ├── test_ui.py
│   │   ├── test_limits.py
│   │   └── test_no_persistence.py                 # asserts no disk writes during requests
│   └── browser/
│       └── test_smoke.py                          # Playwright: load page, run conversion in-browser
└── examples/
    ├── lemonade_shop.xml
    └── pet_shop.xml
```

The `core/` layout is the structural commitment to multi-target. `mappings/`, `emitters/`, and `defaults/` are all directories from day one even though each contains exactly one target-specific file. v2 adds `mappings/threatdragon.py`, `emitters/threatdragon.py`, `defaults/threatdragon.yaml` without touching the shells.

---

## 5. Component specifications

### 5.1 Conversion core

#### 5.1.1 Parser (`core/parser.py`)

**Responsibilities:** Read Open Exchange XML and produce a flat, typed in-memory representation. Target-independent.

**Library:** `lxml` (faster than stdlib `xml.etree`, better namespace handling, good error messages, ships as a precompiled Pyodide wheel). Streaming is unnecessary; tens of thousands of elements fit in memory comfortably.

**Public API:**

```python
def parse_bytes(data: bytes) -> OpenExchangeModel: ...
def parse_path(path: str | os.PathLike) -> OpenExchangeModel: ...
```

`parse_path` wraps `parse_bytes` for CLI convenience. The browser and web shells call `parse_bytes` directly; they never write input to disk.

**Output:** an `OpenExchangeModel` dataclass. Schema reference: <https://www.opengroup.org/xsd/archimate/3.0/archimate3_Diagram.xsd>.

**Key parsing rules:**

- Reject XML missing the ArchiMate 3.x namespace; emit a clear error.
- Treat unknown element types as `Element` with `archimate_type="Unknown"` and a logged warning. Do not fail.
- `xsi:type` determines concrete element/relationship types; namespace-strip before storing.
- Property definitions live in a separate `<propertyDefinitions>` block; the parser resolves them into per-element dicts.
- View nodes carry geometry (`x`, `y`, `w`, `h`) and an `elementRef`. Store both for v2; v1 ignores geometry but does not discard it.
- **XXE hardening:** construct `lxml.etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)`. The web shell receives untrusted input; XXE is a real risk. CLI and browser shells use the same settings for consistency.

**Failure modes:**

- File / payload not readable → `ParserError` with cause.
- Malformed XML → `ParserError` with line/column from `lxml`.
- Missing required namespace → `ParserError` with explanation.
- Schema-invalid but parseable → warning, continue. Production exports often skip optional declarations.

**Open Exchange element types the parser must recognize:**

Application: `ApplicationComponent`, `ApplicationCollaboration`, `ApplicationInterface`, `ApplicationFunction`, `ApplicationProcess`, `ApplicationInteraction`, `ApplicationEvent`, `ApplicationService`, `DataObject`.

Technology: `Node`, `Device`, `SystemSoftware`, `TechnologyCollaboration`, `TechnologyInterface`, `Path`, `CommunicationNetwork`, `TechnologyFunction`, `TechnologyProcess`, `TechnologyInteraction`, `TechnologyEvent`, `TechnologyService`, `Artifact`.

Business (limited use in v1): `BusinessActor`, `BusinessRole`, `BusinessCollaboration`.

Composite: `Grouping`, `Location`.

Relationships: `Composition`, `Aggregation`, `Assignment`, `Realization`, `Used-By` (`Serving`), `Access`, `Influence`, `Triggering`, `Flow`, `Specialization`, `Association`.

(Junction, Motivation, Strategy, Physical, and Implementation types are parsed into generic records but flagged for resolver skip.)

#### 5.1.2 In-memory model (`core/model.py`)

Pure dataclasses, frozen where practical, no behavior. Fully typed. Target-independent.

```python
from dataclasses import dataclass, field
from typing import Literal

ArchiMateLayer = Literal[
    "Strategy", "Business", "Application", "Technology",
    "Physical", "Motivation", "Implementation", "Composite", "Other"
]

@dataclass(frozen=True)
class Element:
    id: str
    name: str
    archimate_type: str
    layer: ArchiMateLayer
    documentation: str | None = None
    properties: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class Relationship:
    id: str
    archimate_type: str
    source_id: str
    target_id: str
    name: str | None = None
    documentation: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    access_type: str | None = None   # Access: read/write/update; None otherwise

@dataclass(frozen=True)
class ViewNode:
    id: str
    element_ref: str | None
    x: int
    y: int
    width: int
    height: int
    parent_id: str | None

@dataclass(frozen=True)
class ViewConnection:
    id: str
    relationship_ref: str | None
    source_node_id: str
    target_node_id: str

@dataclass(frozen=True)
class View:
    id: str
    name: str
    viewpoint: str | None
    nodes: list[ViewNode]
    connections: list[ViewConnection]

@dataclass
class OpenExchangeModel:
    name: str
    documentation: str | None
    elements: dict[str, Element]
    relationships: dict[str, Relationship]
    views: list[View]
```

#### 5.1.3 Resolver (`core/resolver.py`)

**Responsibilities:** Walk the parsed model and produce a `ResolvedModel`. Target-independent — the resolver knows about ArchiMate semantics but nothing about IriusRisk, draw.io, or any other downstream system.

**Algorithm:**

1. **Identify trust zone elements.** Find all `Grouping` and `Location` elements. Apply mapping-table rules (the shared `base.py` schema includes zone rules) to determine which qualify. Build `zones: dict[str, Zone]` keyed by element ID.

2. **Assign elements to zones.** For each non-zone element, walk Composition and Aggregation upward until a zone is reached, or none is. Elements not in any zone go to a synthetic `unzoned` zone with a warning. An element belongs to one zone in v1; multiple compositions resolve to the first deterministically (sorted by zone ID) with a warning.

3. **Resolve realization chains.** For each Application Component, follow `Realization` source-to-target. Targets are typically Nodes, sometimes a TechnologyService that itself realizes a Node — walk through. Record `(application_component_id, node_id)` as `RealizationLink`. Application Components without realization get `node_id=None` and a warning.

4. **Identify hosts.** Any Node that is the target of one or more realizations is a host. Hosts become container shapes in target outputs that support containment.

5. **Identify external actors.** Business Actors and Roles connected to Application/Technology elements become "external" entities, placed in a synthetic `external` zone unless explicitly placed in a zone-mapped Grouping.

6. **Classify connections.** Flow, Serving, Access, Used-By, Triggering between Application/Technology elements (or from Business Actor into them) produce `ResolvedConnection` records with:
   - source and target IDs (mapped through realization where needed)
   - direction (data flow direction; Serving inverts source/target relative to ArchiMate)
   - protocol/auth properties carried over if present
   - flag: crosses a trust zone boundary

7. **Detect skip cases.** Junction elements, Physical-layer elements, non-adjacent-layer realizations, and unknown types are logged with IDs and reasons, and excluded.

**Output dataclasses** are target-independent; per-target styles attach later in the mapper stage.

```python
@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    is_synthetic: bool = False
    properties: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class RealizationLink:
    application_component_id: str
    node_id: str | None

@dataclass(frozen=True)
class ResolvedComponent:
    id: str
    name: str
    archimate_type: str
    zone_id: str
    host_node_id: str | None
    is_host: bool = False
    is_external_actor: bool = False
    properties: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class ResolvedConnection:
    id: str
    source_component_id: str
    target_component_id: str
    archimate_type: str
    crosses_zone: bool
    properties: dict[str, str] = field(default_factory=dict)

@dataclass
class ResolvedModel:
    zones: dict[str, Zone]
    components: dict[str, ResolvedComponent]
    connections: list[ResolvedConnection]
    warnings: list[ResolverWarning]
```

#### 5.1.4 Mappings (`core/mappings/`)

The mapping system is split into shared and target-specific parts so a v2 target inherits the matching machinery without rewriting it.

**`mappings/base.py`** defines the shared schema: rule structure, match conditions (archimate_type, property equals/regex/exists, name regex), property passthrough, and defaults policy. It does not know about styles, shapes, or target-specific fields.

```python
class MatchCondition(BaseModel):
    archimate_type: str | None = None
    property: PropertyMatcher | None = None
    name_pattern: str | None = None

class BaseRule(BaseModel):
    match: MatchCondition

class BaseMapping(BaseModel):
    version: int = 1
    zone_rules: list["ZoneRule"]
    synthetic_zones: dict[Literal["unzoned", "external"], "SyntheticZone"]
    component_rules: list["ComponentRule"]
    connection_rules: list["ConnectionRule"]
    property_passthrough: PropertyPassthrough
    defaults: Defaults
```

The base schema uses generic types (`ZoneRule`, `ComponentRule`, `ConnectionRule`) that target-specific modules subclass with their own emit-time fields.

**`mappings/iriusrisk.py`** extends the base schema with draw.io-specific fields:

```python
class DrawioStyleSpec(BaseModel):
    component_type: str            # IriusRisk component category
    style: str                     # mxCell style string
    is_container: bool = False     # render as container shape

class DrawioComponentRule(ComponentRule):
    iriusrisk: DrawioStyleSpec

class DrawioMapping(BaseMapping):
    component_rules: list[DrawioComponentRule]
    # ...similar overrides for zones and connections
```

A v2 target ships its own subclass — e.g., `mappings/threatdragon.py` — with its own emit-time fields, reusing the base matching rules.

**Public API (in `mappings/__init__.py`):**

```python
def load_mapping(source: str | bytes | os.PathLike, target: str = "iriusrisk") -> BaseMapping: ...
def load_default_mapping(target: str = "iriusrisk") -> BaseMapping: ...
def validate_mapping(source: str | bytes | os.PathLike, target: str = "iriusrisk") -> list[ValidationError]: ...
```

The `target` argument exists in the API now even though only one value is valid in v1 — it's the seam where v2 hooks in.

**Default mapping YAML (`core/defaults/iriusrisk.yaml`):**

```yaml
version: 1
target: iriusrisk

zone_rules:
  - match:
      archimate_type: Grouping
      property:
        name: zone_type
        equals: logical
    iriusrisk:
      zone_name_property: name
      style: "shape=mxgraph.iriusrisk.trust_zone;..."   # placeholder
  - match:
      archimate_type: Grouping
    iriusrisk:
      zone_name_property: name
      style: "shape=mxgraph.iriusrisk.trust_zone;..."

synthetic_zones:
  unzoned:
    name: "Unzoned"
    style: "shape=mxgraph.iriusrisk.trust_zone;dashed=1;..."
  external:
    name: "External"
    style: "shape=mxgraph.iriusrisk.trust_zone;fillColor=#fff2cc;..."

component_rules:
  - match:
      archimate_type: ApplicationComponent
      property:
        name: tech_stack
        equals: web
    iriusrisk:
      component_type: web_application
      style: "shape=mxgraph.iriusrisk.web_application;..."
  - match:
      archimate_type: ApplicationComponent
    iriusrisk:
      component_type: generic_application
      style: "shape=mxgraph.iriusrisk.generic_application;..."
  - match:
      archimate_type: Node
    iriusrisk:
      component_type: host
      style: "shape=mxgraph.iriusrisk.host;..."
      is_container: true
  - match:
      archimate_type: BusinessActor
    iriusrisk:
      component_type: actor
      style: "shape=mxgraph.iriusrisk.actor;..."
  - match:
      archimate_type: DataObject
    iriusrisk:
      component_type: data_store
      style: "shape=mxgraph.iriusrisk.data_store;..."

connection_rules:
  - match:
      archimate_type: Flow
    iriusrisk:
      style: "edgeStyle=orthogonalEdgeStyle;rounded=0;..."
      direction: source_to_target
  - match:
      archimate_type: Serving
    iriusrisk:
      style: "edgeStyle=orthogonalEdgeStyle;rounded=0;..."
      direction: target_to_source
  - match:
      archimate_type: Access
    iriusrisk:
      style: "edgeStyle=orthogonalEdgeStyle;rounded=0;..."
      direction: by_access_type

property_passthrough:
  components: [protocol, data_classification, patch_authority]
  connections: [protocol, port, authentication, encryption]

defaults:
  unmatched_element: skip_with_warning
  unmatched_relationship: skip_with_warning
```

**Matching rules (target-independent):**

- Rules evaluated in declaration order; first match wins.
- A `match` block can combine `archimate_type`, `property`, and `name_pattern`. All listed conditions must hold.
- Pydantic enforces: each rule has at least one condition; per-target fields are non-empty as their schema requires.

#### 5.1.5 Mapper (`core/mapper.py`)

**Responsibilities:** Apply a validated `BaseMapping` (or subclass) to a `ResolvedModel`. Output: `MappedModel`, structurally identical to `ResolvedModel` plus a `target_data: dict[str, Any]` per component and per connection holding the target-specific style/type info attached by the mapping. The mapper itself is target-independent; it walks rules and copies fields. Pure function; no I/O.

#### 5.1.6 Emitters (`core/emitters/`)

The emitter is the only stage that knows about a specific output format.

**Emitter protocol (`core/emitters/__init__.py`):**

```python
from typing import Protocol

class Emitter(Protocol):
    target_id: str          # e.g., "iriusrisk"
    output_extension: str   # e.g., "drawio"
    output_media_type: str  # e.g., "application/xml"

    def emit(self, model: MappedModel) -> bytes: ...

EMITTERS: dict[str, Emitter] = {}

def register(emitter: Emitter) -> None:
    EMITTERS[emitter.target_id] = emitter

def get_emitter(target_id: str) -> Emitter:
    if target_id not in EMITTERS:
        raise UnknownTargetError(target_id)
    return EMITTERS[target_id]
```

The registry is populated at import time. v1 has one entry; v2 adds more without changing this file.

**v1 emitter (`core/emitters/iriusrisk.py`):**

Produces a draw.io XML byte string from a `MappedModel`.

**Output format:** mxGraph XML, single-page document compatible with draw.io desktop, draw.io web, and IriusRisk's embedded editor. Reference: <https://www.drawio.com/doc/faq/save-file-format>.

**Structure:**

```xml
<mxfile host="archithreat" version="1.0">
  <diagram id="..." name="...">
    <mxGraphModel dx="..." dy="..." grid="1" ...>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <!-- Trust zones as swimlanes, parent="1" -->
        <!-- Hosts as containers, parent=zone_id -->
        <!-- Components as shapes, parent=host_id or zone_id -->
        <!-- Edges, source/target referring to component IDs -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Emission order:**

1. Header and graph model wrapper.
2. Mandatory `mxCell id="0"` and `id="1"` (draw.io structural roots).
3. One `mxCell` per zone, `vertex="1"`, parent=`"1"`.
4. One `mxCell` per host, `vertex="1"`, parent=zone_id.
5. One `mxCell` per non-host component, `vertex="1"`, parent=`host_id` or `zone_id`.
6. One `mxCell` per connection, `edge="1"`, parent=`"1"`, with `source` and `target` attributes pointing to component cells.

**Layout strategy (v1):** Auto-layout, deterministic. Zones laid out left-to-right by name. Hosts within a zone laid out top-to-bottom in declaration order, sized to fit children. Non-host components in a zone laid out in a grid. Components inside a host laid out in a grid. Edges use orthogonal routing. Auto-layout is usable but not pretty; modelers will hand-adjust in IriusRisk. v2 may use source view geometry.

**ID handling:** Use ArchiMate element IDs as draw.io cell IDs where they match `[a-zA-Z_][a-zA-Z0-9_-]*`; otherwise hash to a stable replacement and record the mapping in a `<UserObject>` attribute for traceability.

**Property passthrough:** Component properties from the passthrough list are emitted as `<UserObject>` attributes wrapping the `mxCell`. Best-effort, documented.

**Internal validation:** After emission, parse the output back with `lxml` and assert all edge `source`/`target` IDs reference existing vertex cells, all `parent` IDs reference existing cells, no cell is its own ancestor, document is well-formed. Validation failures are an internal bug; raise `EmitterError`.

#### 5.1.7 Inventory mode (`core/inventory.py`)

Diagnostic mode that runs parser + resolver and produces a structured report without emitting. Target-independent. Useful for pre-flight checks, ongoing model-hygiene tooling (run weekly in CI against the EA repo), and producing a "real numbers" conversation-opener with vendors.

**Public API:**

```python
def inventory_bytes(data: bytes) -> InventoryReport: ...
def inventory_path(path: str | os.PathLike) -> InventoryReport: ...
```

**Report contents:**

- Counts by ArchiMate type (e.g., 1,234 ApplicationComponents, 340 Nodes, 28 Groupings).
- Counts by layer.
- Realization coverage: ApplicationComponents with realization to a Node, directly vs. via TechnologyService, vs. orphaned.
- Zone coverage: elements inside vs. outside a zone, broken down by layer.
- Co-hosting analysis: components-per-host distribution (median, max, p95).
- External-actor count and the Application/Technology elements they touch.
- Warning summary: counts by code with sample element IDs (first 5).
- Skipped-element summary: counts by skip reason.

**Output formats:** `text` (default), `json`, `markdown`.

### 5.2 CLI shell (`cli/main.py`)

`click`-based CLI. Imports only from `core` and stdlib.

**Commands (v1):**

```
archithreat convert <input.xml> <output.drawio> [options]
archithreat inventory <input.xml> [options]
archithreat validate-mapping <mapping.yaml>
archithreat show-defaults                    # prints the default mapping
archithreat serve [--host 0.0.0.0] [--port 8000]
```

The `convert` command implicitly produces the v1 target's output. There is no `--target` flag in v1; v2 introduces it. `show-defaults` prints the v1 target's default mapping (no `--target` argument needed).

The `serve` subcommand starts the web shell locally without Docker. It imports `archithreat.web` lazily so the CLI install can omit web dependencies via the `[cli]` extra.

**Common options:**

- `--mapping FILE` — path to mapping YAML; falls back to bundled default.
- `--view NAME` — restrict conversion to a single named view (default: whole model into one diagram).
- `--unzoned-policy {warn,fail,silent}` — what to do when elements lack a zone.
- `--unrealized-policy {warn,fail,silent}` — what to do when ApplicationComponents lack realization.
- `--log-level {debug,info,warning,error}`.
- `--report FILE` — write inventory report alongside conversion (text or json by extension).
- `--strict` — exit non-zero if any warning is emitted.

**Exit codes:**

- 0 — success.
- 1 — completed with warnings under `--strict`.
- 2 — input not found / unreadable.
- 3 — XML parse error.
- 4 — schema / namespace error.
- 5 — mapping invalid.
- 6 — internal emitter error (bug).

### 5.3 Browser shell

Static site that loads Pyodide, installs the `archithreat` core wheel, and runs conversions entirely in-browser.

**Build pipeline:** Source in `browser/`. `npm run build` produces `dist/` of static assets — HTML, JS, CSS, vendored Pyodide runtime, and the core wheel built from the same `pyproject.toml`. `esbuild` for JS minification. No frameworks. CI `pages.yaml` publishes `dist/` to GitHub Pages on tagged releases.

**Runtime flow:**

1. Page loads. Pyodide bootstraps in a Web Worker.
2. Worker `pip install`s the core wheel from a same-origin path (the wheel ships in `dist/`; no PyPI fetch at runtime).
3. UI shows three actions: **Convert**, **Inventory**, **Validate mapping**. Plus a collapsible mapping editor with the default prefilled.
4. User picks a `.xml` via `<input type="file">`. File API reads to `ArrayBuffer`; main thread posts bytes to the worker.
5. Worker calls `core.parser.parse_bytes`, runs the pipeline, returns:
   - Convert: the target's output bytes. Main thread wraps in `Blob`, creates an object URL, triggers download with the target's file extension.
   - Inventory: structured report rendered as HTML.
   - Validate: validation result rendered as HTML.
6. No network I/O after page load. No `fetch` of user content.

**Capabilities and limits:** Pyodide cold start ~3–5s. File size practical ceiling ~100 MB; warn at 50 MB. Inventory cheaper than convert. Page works fully offline once loaded.

**Mapping editing:** Textarea with "Load default" and "Validate" buttons. On validate, the worker calls `core.mappings.validate_mapping(text)` and renders structured errors. On convert, textarea content is the mapping; if empty, falls back to default.

**Why a Web Worker:** Pyodide on the main thread blocks the UI during conversion. A worker keeps the page interactive and lets the UI cancel a stuck conversion by terminating the worker.

### 5.4 Web shell (`web/app.py`)

A FastAPI application serving JSON API + HTMX-rendered HTML UI. Same app whether started by `archithreat serve` or by the Docker entrypoint.

**Stateless guarantees:**

- No database. No file writes for user content. No `tempfile` use; processing happens entirely in memory via `BytesIO`.
- Application logs record request metadata (method, path, status, duration, client IP, request ID) but never include uploaded content, mapping content, or output content.
- `tests/web/test_no_persistence.py` patches `open`, `os.write`, `tempfile.*`, and the cwd's filesystem to assert no path under the application's process writes during a request lifecycle.

**JSON API (v1):**

```
POST /api/v1/convert
  Content-Type: multipart/form-data
  Fields:
    model:   file (.xml)
    mapping: file or text (optional; default applied if absent)
    view:    string (optional; restricts to one view)
    unzoned_policy:    enum (default "warn")
    unrealized_policy: enum (default "warn")
  Response 200: target's media type; download as <model_name>.<target_extension>
  Response 4xx: application/json error envelope

POST /api/v1/inventory
  Same multipart input minus mapping/view/policies.
  Response 200: application/json (or text/markdown via Accept header)

POST /api/v1/mapping/validate
  Content-Type: text/yaml or multipart with one file field
  Response 200: application/json with validation results

GET  /api/v1/mapping/default
  Response 200: text/yaml — bundled default mapping

GET  /healthz
  Liveness; minimal, always succeeds while the process is up.

GET  /readyz
  200 if core imports succeed and a self-test conversion of an embedded fixture passes; 503 otherwise.

GET  /version
  JSON with package version, core version, build commit, available targets list (v1: ["iriusrisk"]).
```

The `/api/v1/convert` endpoint does not take a `target` parameter in v1. The default is implicit. v2 adds `target` as an optional field, defaulting to `iriusrisk` for backward compatibility. OpenAPI / Swagger UI at `/docs`, ReDoc at `/redoc`.

**HTML UI:** HTMX over Jinja2. Three pages: convert, inventory, validate-mapping. Form submissions are HTMX-driven (`hx-post` + `hx-target`) and replace a result panel inline. A "What this does to your data" panel on every page links to `docs/privacy.md`. Semantic HTML, proper labels, keyboard-navigable, color-blind-safe palette.

**Configuration (Pydantic Settings, env-driven):**

| Variable | Default | Meaning |
|---|---|---|
| `ARCHITHREAT_HOST` | `0.0.0.0` | Bind address |
| `ARCHITHREAT_PORT` | `8000` | Bind port |
| `ARCHITHREAT_MAX_UPLOAD_MB` | `50` | Hard limit on `model` and `mapping` size |
| `ARCHITHREAT_REQUEST_TIMEOUT_SECONDS` | `120` | Conversion timeout |
| `ARCHITHREAT_RATE_LIMIT_PER_MINUTE` | `30` | Per-IP rate limit; set 0 to disable |
| `ARCHITHREAT_CORS_ORIGINS` | `""` (none) | Comma-separated allowed origins |
| `ARCHITHREAT_LOG_LEVEL` | `info` | Application log level |
| `ARCHITHREAT_FORWARDED_ALLOW_IPS` | `""` | Trusted proxies for `X-Forwarded-For` |

**Concurrency:** uvicorn with `--workers N`. Conversion is CPU-bound and synchronous within a request; FastAPI runs sync handlers in a thread pool. Per-request timeout enforced with a watchdog cancelling the thread.

**Limits and rate limiting (`web/limits.py`):** Upload size enforced at the streaming layer. Per-IP rate limit via `slowapi`, memory-only. Request timeout: wall-clock guard around the conversion call; on timeout, return 504.

### 5.5 Docker container

Multi-stage build. Builder: `python:3.12-slim`, builds wheel. Runtime: `python:3.12-slim`, copies wheel, installs into `--user` directory under non-root account, runs uvicorn. Final image ~100 MB; published to GHCR (`ghcr.io/<org>/archithreat:<tag>`). Runs as UID 1000, healthcheck pointed at `/healthz`. Single port (8000 default).

**Run example (in `docs/self-hosting.md`):**

```bash
docker run --rm -p 8000:8000 \
  -e ARCHITHREAT_MAX_UPLOAD_MB=100 \
  -e ARCHITHREAT_RATE_LIMIT_PER_MINUTE=60 \
  ghcr.io/<org>/archithreat:latest
```

Operators handle their own orchestration. Docs note that a typical Rancher / Kubernetes deployment maps cleanly: one Deployment, one Service, optional Ingress with TLS. No manifests shipped — operators either know how, or they aren't the audience for the container option (the browser app is).

OCI standard labels (`org.opencontainers.image.source`, `version`, `revision`, `licenses`, `description`) populated from CI.

### 5.6 Dependencies

#### Runtime, core (must be Pyodide-compatible)

- `lxml >= 5.0` — XML parsing/emission. Pyodide-compatible.
- `pydantic >= 2.5` — model validation. Pyodide-compatible.
- `pyyaml >= 6.0` — YAML loading. Pyodide-compatible.

#### Runtime, CLI (extra: `archithreat[cli]`)

- `click >= 8.1`.

#### Runtime, web (extra: `archithreat[web]`)

- `fastapi >= 0.110`.
- `uvicorn[standard] >= 0.27`.
- `jinja2 >= 3.1`.
- `python-multipart` for form uploads.
- `slowapi` for rate limiting.

#### Browser (built into `dist/`)

- Pyodide (vendored).
- esbuild (build-time only).
- htmx is for the web shell only; the browser shell uses vanilla JS.

#### Development

- `pytest`, `pytest-cov`, `hypothesis`.
- `ruff`, `mypy`.
- `playwright` for browser smoke tests.
- `httpx` for FastAPI tests.
- `pre-commit`.

#### Build / packaging

- `pyproject.toml` with `hatchling` backend.
- Source layout `src/archithreat/`.
- Console script `archithreat = archithreat.cli.main:main`.
- Extras: `[cli]`, `[web]`, `[dev]`. Default (`pip install archithreat`) installs only the core; `pip install archithreat[web]` is what the Dockerfile uses.

### 5.7 Repository hosting

GitHub. CI on GitHub Actions. Releases publish to PyPI (trusted publishing). Container image to GHCR. Browser bundle to GitHub Pages on tagged releases.

---

## 6. Design decisions and rationale

### 6.1 Application-Component-centric, but Node-aware

One threat-model component per ArchiMate Application Component. Nodes that host one or more Application Components emit as **container shapes** with the Application Components as children. Matches the threat-modeling principle that the unit of analysis is "a thing with its own attack surface," matches how modelers structure their BiZZdesign models, and uses native parent-child containment in any target that supports it.

### 6.2 Multiplicity through the model, not synthesized

If a model says "one ApplicationComponent realized by twelve Nodes," the converter emits twelve components. If a model says "one ApplicationComponent realized by one Node with `instances: 12` property," the converter emits one component (the property passes through as metadata). Multiplicity decisions stay in the modeler's hands.

### 6.3 Realization expressed as containment, not as edges

Realization from ApplicationComponent to Node becomes parent-child containment in the output, not an edge. Containment is structurally closer to "this software runs on this host," IriusRisk's threat library expects host-contains-application, and it removes visual clutter.

### 6.4 Logical zones only in v1

Physical zoning deferred to v2: it doubles mapping complexity, forces nested-vs-composite zone decisions that benefit from real downstream feedback, and is unnecessary for demonstrating the concept. Parser does not discard physical-layer information; resolver and mapper skip it. v2 is additive.

### 6.5 Auto-layout, not source geometry preservation

v1 uses deterministic auto-layout. Source geometry was laid out for ArchiMate notation, not the target's containment model, and often produces broken visuals when components nest into hosts. Modelers will hand-adjust regardless. v2 may add `--preserve-layout`.

### 6.6 Mapping table externalized as YAML

Hard-coding the mapping would couple the tool to a specific shape library version. Externalizing lets vendors ship updated style strings without a code release, lets organizations customize for their library extensions, and turns the mapping into documentation of the modeling discipline. YAML chosen over JSON for human readability (comments, multi-line strings). Pydantic enforces schema correctness.

### 6.7 Why three surfaces, not one

The CLI alone underserves non-engineering users (architects, security analysts). A single hosted web service violates the trust-zone constraint that motivates the project — architecture models often cannot leave their owning organization. The browser app delivers a web UX with no infrastructure and no upload; the self-hosted container delivers a web UX with a stable internal endpoint for organizations that want one. Together they cover the audience without compromising data handling.

### 6.8 Why HTMX over a SPA framework for the web UI

The web UI has three forms and a result panel. A SPA framework brings a build step, a JS dependency tree, hydration, state management, and a larger attack surface, all for surface area that fits in a few HTML templates. HTMX renders server-side, keeps the dependency tree small, avoids client-side state entirely, and is faster to audit. The browser app uses vanilla JS for the same reason.

### 6.9 Why a Web Worker in the browser app

Pyodide on the main thread blocks the page during conversion. A Web Worker keeps the UI interactive, makes cancellation possible, and isolates the runtime. The cost is a postMessage boundary, which is small for the bytes-in / bytes-out shape of this tool.

### 6.10 Why no public hosted service

Architecture models for critical infrastructure describe attack surfaces and frequently cannot leave the owning organization, by policy, contract, or law. A public hosted service would either be unusable for the audience that most needs the tool, or be a target for the most sensitive data the tool processes. Both are bad outcomes. Shipping software (CLI, container, browser bundle) avoids both: every deployment runs inside the user's chosen trust zone.

### 6.11 Halfway multi-target structure

The codebase commits to multi-target structurally — `mappings/`, `emitters/`, and `defaults/` are directories from day one with target-tagged files inside, the emitter registry exists, the `target_id` parameter exists in core APIs. The user-facing surface, however, stays single-target: no `--target` CLI flag, no `target` field in the JSON API, no target dropdown in either UI. v1 has one target; introducing user-facing target selection now would design an interaction model against a sample size of one. v2 ships the second target *and* the user-facing flag together, when there's enough signal to know what the interaction should look like.

### 6.12 Project naming

`archithreat` is descriptive (ArchiMate + threat) without binding to a specific output format or downstream tool. The earlier working name `archi2irius` baked one destination into the project's identity and would have aged badly as v2+ targets arrived. `archithreat` survives the lifetime of the project regardless of which threat-modeling tools rise or fall in popularity.

---

## 7. Test strategy

### 7.1 Unit tests (core)

One test per parser-recognized element type, one per failure mode. Resolver tests for each algorithmic step with focused fixtures. Mapper tests for rule matching (first-match-wins, property conditions, regex, fallthrough). Per-emitter tests for structural output properties (parent-child correctness, edge endpoint validity, ID uniqueness) rather than byte-for-byte output. Per-mapping tests for target-specific schema validation.

Coverage target: 90% line coverage on core; the gap is unreachable error paths.

### 7.2 CLI tests

`click.testing.CliRunner` for argument parsing, exit codes, error messages.

### 7.3 Web tests

`httpx.AsyncClient` against the FastAPI app in-process. Each endpoint's happy path and error envelopes. `test_no_persistence.py` patches the filesystem and asserts no writes during a request lifecycle. `test_limits.py` covers upload size, rate limiting, timeout enforcement.

### 7.4 Browser smoke tests

Playwright headed-mode tests: launch a local static server against `dist/`, load the page, wait for Pyodide ready, upload a fixture, click convert, assert the download. One smoke test per primary flow. Slow; runs in a separate CI job.

### 7.5 Integration / golden tests

Fixture models with corresponding expected outputs under `tests/fixtures/expected/<target_id>/`. Compare structurally (parse both as XML or appropriate format, normalize, compare trees). Goldens regenerate via `pytest --update-goldens`, are reviewed by hand, are committed.

Fixtures included in v1:

- `minimal.xml` — one Application Component, one Node, one realization, one Grouping.
- `co_hosted.xml` — three Application Components on one Node.
- `external_actor.xml` — Business Actor connected across a zone boundary.
- `orphans.xml` — components without realization, elements outside any zone.

### 7.6 Round-trip validation

Manual / semi-automated: open the v1 target's output in IriusRisk, confirm shapes and zones are recognized correctly. Procedure documented in `docs/testing.md`. Gated on access to an IriusRisk instance; runs at release time.

### 7.7 Property-based tests

`hypothesis` generates randomized but schema-valid Open Exchange documents and asserts: all elements in the resolved model trace back to elements in the source; no connection references a non-existent component; `warnings + skipped + emitted == source count`.

### 7.8 CI configuration

GitHub Actions:

- `ci.yaml`: matrix Python 3.11/3.12/3.13 on ubuntu-latest. Steps: ruff check, ruff format check, mypy strict, pytest with coverage. Lint mapping YAML in `examples/` against the schema.
- `release.yaml`: on tagged releases, build wheel + sdist (publish to PyPI via trusted publishing), build Docker image (publish to GHCR), build browser bundle.
- `pages.yaml`: on tagged releases, publish browser bundle to GitHub Pages.

---

## 8. Documentation deliverables

### 8.1 README.md

One-paragraph description, the EA-to-threat-modeling gap explained briefly, three-way install/use sections (CLI, browser, Docker), link to `docs/`, license, status / Python version / license badges.

### 8.2 docs/concepts.md

The modeling discipline that makes the conversion meaningful: Application-Component-centric threat modeling, trust zones via Grouping/Location, realization as containment, multiplicity rules, external actors. Doubles as training material referenced from the BISO program.

### 8.3 docs/mapping-table.md

Schema reference (base + per-target extensions), how to harvest target-specific style strings (the reference-diagram method for IriusRisk), common patterns, how to validate a custom mapping.

### 8.4 docs/patterns.md

Patterns and anti-patterns reference. One section per pattern with a small ArchiMate fixture and resulting target output. Anti-patterns include the warning code emitted and how to fix the model.

### 8.5 docs/limitations.md

Honest list of what v1 cannot do, with rationale and pointer to roadmap.

### 8.6 docs/self-hosting.md

How to run the Docker container: env vars, `docker run` example, sizing notes, suggested resource limits, TLS termination guidance (operator's responsibility), no shipped manifests.

### 8.7 docs/browser.md

Browser app capabilities and limits, how to host the static bundle on your own infrastructure, offline use, cold-start expectations, file size limits.

### 8.8 docs/privacy.md

What each surface does and does not see. The trust-zone reasoning behind the design. Demonstrable claims (e.g., "the browser app makes no network requests after page load — verifiable in devtools"; "the web container makes no disk writes for user content — covered by `test_no_persistence.py`"). Engineering claims that can be inspected and tested, not legal language.

### 8.9 docs/targets.md

One subsection per supported target. v1 has exactly one entry: `iriusrisk`. Documents the target's audience, the threat-modeling tool it feeds, the file format produced, the import procedure on the receiving side, and known caveats. Future targets get their own subsections.

### 8.10 docs/adding-a-target.md

Forward-looking contributor guide for adding a new emitter. Covers: subclass the base mapping schema, implement the `Emitter` protocol, register in the emitter `__init__`, add a default mapping YAML, add fixtures and goldens, document in `targets.md`. Included in v1 even though no second target exists yet — partly to validate the architecture by writing the docs as if onboarding a contributor, partly to lower the activation energy for the eventual v2 work.

### 8.11 SECURITY.md

Disclosure policy, threat model of the tool itself (XXE hardening, denial-of-service via large/pathological inputs, unbounded recursion in malformed models), known limitations (no AuthN/Z because it's out of scope for v1).

### 8.12 CHANGELOG.md, CONTRIBUTING.md

Keep-a-changelog from day one. CONTRIBUTING covers dev environment setup, running tests across the three shells, mapping table contributions for new shape library versions, and the link to `adding-a-target.md` for new emitter contributions.

---

## 9. Roadmap (post-v1)

**v1.1 — quality of life:**

- Source view geometry as optional layout source (`--preserve-layout`).
- Improved auto-layout (graphviz `dot` via `pydot` in CLI/server; pure-Python fallback in browser).
- Per-view conversion (one diagram per ArchiMate view rather than one merged).
- Service worker for full offline use of the browser app.

**v2 — physical zones + second target + user-facing target selection:**

- Physical layer parsing (Equipment, Facility, Distribution Network).
- 2D zoning: composite zone names (`partner-network @ public-edge`) at v2.0; nested zones at v2.1 once IriusRisk threat-library behavior is confirmed.
- Property passthrough for physical-zone-derived attributes.
- Second emitter ships (likely OWASP Threat Dragon JSON or Microsoft Threat Modeling Tool `.tm7`, depending on demand).
- User-facing target selection: `--target` CLI flag, `target` field in JSON API, target dropdown in both UIs.

**v3 — REST API targets:**

- Direct REST API push as alternative to file output for targets that support it (IriusRisk first).
- Idempotent re-import: detect existing components by ArchiMate ID stored in target metadata; update rather than recreate.
- Sync mode: diff source model against existing threat model; apply changes only.

**Speculative:**

- Other source formats: Archi `.archimate`, Sparx EA via Open Exchange, plain ArchiMate XML.
- Plugin architecture so target mappings live as separate installable packages per shape library version.

---

## 10. Open questions

1. **IriusRisk style strings.** Canonical `style=` values for IriusRisk's draw.io shapes. Resolution: ask IriusRisk directly (Ron's access), or harvest from a reference diagram. Default mapping ships placeholders.

2. **IriusRisk import behavior for nested zones.** v2 question; for now, document v1's flat zoning.

3. **UserObject property passthrough.** Does IriusRisk surface mxCell `UserObject` attributes as component properties on import? Resolution: test.

4. **Edge protocol metadata format.** Edge labels? UserObject attributes on edges? Style flags? Resolution: ask.

5. **Zone synthesis policy.** Synthetic `unzoned` zone acceptable, or refuse? Configurable via `--unzoned-policy`; default `warn`.

6. **License choice.** Apache 2.0 (default; patent grant, enterprise-friendly) vs. MIT (broader adoption). Default to Apache 2.0 unless reasons emerge.

7. **Pyodide wheel hosting.** Embed in `dist/` (current plan, simplest, offline-friendly) vs. fetch from PyPI at runtime (smaller bundle, requires network at first load). Embedded is consistent with the offline-by-default browser story.

8. **Second target priority.** Threat Dragon (open-source, easy to test) vs. Microsoft Threat Modeling Tool (broader enterprise install base) vs. IriusRisk REST API (deeper integration with v1's primary downstream). Decide before v2 design starts.

---

## 11. Acceptance criteria for v1

The v1 is "done" when:

1. `archithreat convert` produces a valid output file from each fixture in `tests/fixtures/`.
2. Each fixture's output, opened in draw.io and IriusRisk, renders shapes recognized as IriusRisk components and trust zones (manual round-trip check, documented).
3. `archithreat inventory` produces clean text and JSON reports on a real-world Open Exchange export from BiZZdesign.
4. Browser app loads, runs each of the three flows, and produces results identical to the CLI for the bundled fixtures (Playwright smoke test passes).
5. Docker container starts, passes `/healthz` and `/readyz`, and serves the same conversions over HTTP API and HTML UI for the bundled fixtures.
6. `test_no_persistence.py` passes: no disk writes for user content during web requests.
7. The emitter registry has exactly one entry (`iriusrisk`); the architecture for adding a second is exercised in unit tests with a stub emitter that registers, runs through the pipeline, and is unregistered between tests.
8. Test coverage ≥ 90% on core; lower on shells but CI-enforced minimums set in `pyproject.toml`.
9. `mypy --strict` passes with zero errors.
10. `ruff check` and `ruff format --check` pass.
11. Documentation in `docs/` is complete (concepts, mapping, patterns, limitations, self-hosting, browser, privacy, targets, adding-a-target).
12. CI passes on Python 3.11, 3.12, 3.13.
13. A non-author can install the CLI, follow the README quickstart, and produce a working conversion of `examples/pet_shop.xml` without help.
14. A non-author can open the published browser app, upload `examples/pet_shop.xml`, and download a working output without help.
15. A non-author can `docker run` the published image, open the UI, and produce a working conversion without help.

The last three are the real ones. Everything else is in service of them.
