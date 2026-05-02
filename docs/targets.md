# Targets

Purpose: per-target documentation for the emitters [archithreat](../src/archithreat/__init__.py) ships.

## Contents

- [iriusrisk](#iriusrisk)
- [threatdragon](#threatdragon)
- [Future targets](#future-targets)

## Selecting a target

CLI: `archithreat convert input.xml output.ext --target <id>`
JSON API: `POST /api/v1/convert` with `target=<id>` form field
HTMX UI: dropdown on the Convert / Inventory / Validate-Mapping pages
Browser shell: dropdown on the Convert tab and inside the Mapping editor

`archithreat targets` lists every registered target with its file extension and media type.

## iriusrisk

**Audience:** architects and security analysts who run their EA in ArchiMate (BiZZdesign, Sparx EA, Archi) and their threat modeling in IriusRisk.

**Threat-modeling tool fed:** [IriusRisk](https://www.iriusrisk.com/), which uses draw.io as its embedded diagram editor and recognizes components via mxCell `style` strings carrying `ir.componentDefinition.ref=<id>` (and trust zones via `ir.ref=<library-zone-uuid>`).

**File format produced:** mxGraph XML (`.drawio`), single-page document, compatible with draw.io desktop, draw.io web, and IriusRisk's embedded editor. Reference: <https://www.drawio.com/doc/faq/save-file-format>.

**Implementation:** [`src/archithreat/core/emitters/iriusrisk.py`](../src/archithreat/core/emitters/iriusrisk.py). Default mapping at [`src/archithreat/core/defaults/iriusrisk.yaml`](../src/archithreat/core/defaults/iriusrisk.yaml). Component refs and zone UUIDs are extracted from IriusRisk's public Community shape libraries (<https://github.com/iriusrisk/Community/tree/master/ShapeLibraries>).

### Import procedure

In IriusRisk:

1. Open or create a project.
2. Open the project's diagram view.
3. Use the **Diagram → Import draw.io** menu (the exact label varies by IriusRisk version; the function lives under the diagram-actions menu in every recent release).
4. Select the `.drawio` file produced by archithreat.
5. IriusRisk reads the mxGraph XML, places shapes by their `style` strings, and reconstructs containment from `parent` references. Trust zones become IriusRisk trust zones; components inside zones become IriusRisk components; flows become data-flow lines.

After import, IriusRisk's threat library attaches threats automatically to recognized components. Components whose `ir.componentDefinition.ref` is not in your installation's library appear as generic shapes; either convert them inside IriusRisk or override the ref in your mapping YAML.

### Known caveats

If your installation uses a customised library (e.g. `CD-V2-*` prefixes), copy the bundled default mapping YAML and replace the refs. Validate with `archithreat validate-mapping path/to/your.yaml --target iriusrisk`.

Edge `ir.assets` and `ir.tags` (linked DataObject and protocol) live inside the mxCell `style` string. The current emitter does not template those from per-relationship properties; modellers add them in IriusRisk's editor after import. v2.1+ will template them.

## threatdragon

**Audience:** teams running [OWASP Threat Dragon](https://owasp.org/www-project-threat-dragon/) for STRIDE threat modeling and wanting to seed diagrams from authoritative ArchiMate models instead of drawing by hand.

**Threat-modeling tool fed:** Threat Dragon (desktop and web). Threat Dragon uses [JointJS / X6](https://x6.antv.antgroup.com/) for diagramming and stores models as a single JSON document.

**File format produced:** OWASP Threat Dragon v2 model JSON (`.json`). Schema reference and sample models: <https://github.com/OWASP/threat-dragon/tree/main/ThreatDragonModels>.

**Implementation:** [`src/archithreat/core/emitters/threatdragon.py`](../src/archithreat/core/emitters/threatdragon.py). Default mapping at [`src/archithreat/core/defaults/threatdragon.yaml`](../src/archithreat/core/defaults/threatdragon.yaml).

### Import procedure

In Threat Dragon:

1. Open Threat Dragon (desktop or hosted).
2. Choose **Open Existing Threat Model** (or **Import**, depending on version).
3. Select the `.json` file produced by archithreat.
4. Threat Dragon loads the diagram. The diagram type is set to **STRIDE**; cells appear as processes, stores, actors, flows, and trust-boundary rectangles.

### Stencil mapping

| ArchiMate | Threat Dragon |
|---|---|
| `ApplicationComponent` (default) | `process` (`tm.Process`) |
| `ApplicationComponent` with `tech_stack=web` property | `process` with `isWebApplication: true` |
| `ApplicationComponent` named `*auth*` | `process` with `providesAuthentication: true` |
| `ApplicationService`, `Node`, `Device`, `SystemSoftware`, `Artifact` | `process` (TD has no host stencil) |
| `BusinessActor`, `BusinessRole` | `actor` (`tm.Actor`) |
| `DataObject` | `store` (`tm.Store`) |
| `DataObject` named `*credentials*`, `*secrets*`, `*tokens*` | `store` with `storesCredentials: true`, `isEncrypted: true` |
| `DataObject` named `*audit*`, `*log*` | `store` with `isALog: true` |
| `Grouping`, `Location` | `trust-boundary-box` (rectangle, dashed) |
| `Flow`, `Triggering` | `flow` (source → target) |
| `Serving`, `UsedBy` | `flow` (target → source) |
| `Access` (write) | `flow` (source → target) |
| `Access` (read) | `flow` (target → source) |

Flows with a `protocol` property matching `https`, `tls`, `mtls`, `wss`, `sftp`, `ftps`, or `ssh` are emitted with `isEncrypted: true`. Other protocols pass through verbatim into the flow's `data.protocol` field.

### Known caveats

- TD has no first-class host stencil. ArchiMate Nodes and Devices collapse to `process` in TD output. Containment is *visual* (components positioned inside trust-boundary rectangles); TD's JSON model has no parent-child relationship between cells.
- Trust boundaries use `trust-boundary-box` (deterministic rectangle) rather than `trust-boundary-curve` (free-form curves through user-supplied points). Boxes auto-layout cleanly; curves cannot.
- The `threats` array on each cell is emitted empty. Threats are populated inside Threat Dragon by the user (or by TD's threat-generation engine).
- Diagram type is hardcoded to STRIDE. LINDDUN / CIA / DIE diagram types are not yet selectable; future work.

## Future targets

The following targets are on the roadmap (see [limitations.md](limitations.md#future-work)). None ship today.

- **Microsoft Threat Modeling Tool** (`.tm7`). Broader enterprise install base.
- **IriusRisk REST API**. Direct push as an alternative to file output, supporting idempotent re-import.
- **OTM (Open Threat Model)**. Vendor-neutral interchange for threat models.
