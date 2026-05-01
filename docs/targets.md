# Targets

Purpose: per-target documentation for the emitters [archithreat](../src/archithreat/__init__.py) ships. v1 has exactly one entry. Future targets get their own subsections here.

## Contents

- [drawio-iriusrisk](#drawio-iriusrisk)
- [Future targets](#future-targets)

## drawio-iriusrisk

**Audience:** architects and security analysts who run their EA in ArchiMate (BiZZdesign, Sparx EA, Archi) and their threat modeling in IriusRisk.

**Threat-modeling tool fed:** [IriusRisk](https://www.iriusrisk.com/), which uses draw.io as its embedded diagram editor and recognizes components by matching mxCell `style=` strings against its shape library.

**File format produced:** mxGraph XML (`.drawio`), single-page document, compatible with draw.io desktop, draw.io web, and IriusRisk's embedded editor. Reference: <https://www.drawio.com/doc/faq/save-file-format>.

**Implementation:** [`src/archithreat/core/emitters/drawio_iriusrisk.py`](../src/archithreat/core/emitters/drawio_iriusrisk.py). Default mapping at [`src/archithreat/core/defaults/drawio_iriusrisk.yaml`](../src/archithreat/core/defaults/drawio_iriusrisk.yaml).

### Import procedure

In IriusRisk:

1. Open or create a project.
2. Open the project's diagram view.
3. Use the **Diagram → Import draw.io** menu (the exact label varies by IriusRisk version; the function lives under the diagram-actions menu in every recent release).
4. Select the `.drawio` file produced by archithreat.
5. IriusRisk reads the mxGraph XML, places shapes by their `style=` strings, and reconstructs containment from `parent` references. Trust zones become IriusRisk trust zones; hosts become container shapes; components become components inside their hosts.

After import, IriusRisk's threat library will attach threats automatically to the components it recognizes. Components whose styles do not match the IriusRisk shape library will appear as generic shapes; you can convert them to recognized components inside IriusRisk, or fix the mapping and re-export.

### Known caveats

The `style=` strings in the default mapping are placeholders. They follow the mxCell style grammar correctly and the structural output (parents, children, edges, IDs) is valid draw.io that IriusRisk's editor can open, but the `shape=mxgraph.iriusrisk.*` shape identifiers used in the defaults need to be confirmed against your IriusRisk installation's shape library before you rely on round-trip recognition.

The fix is documented in [mapping-table.md](mapping-table.md#harvesting-iriusrisk-style-strings): build a reference diagram in IriusRisk's editor, save it, copy the real `style=` values out of the saved XML, and paste them into your mapping YAML. This is a one-time exercise per IriusRisk shape library version.

If IriusRisk's import surfaces UserObject attributes as component properties, the property passthrough in the default mapping (`protocol`, `data_classification`, `patch_authority`, `tech_stack` for components; `protocol`, `port`, `authentication`, `encryption` for connections) will land as IriusRisk component metadata. If it does not, the data is still in the file for tooling that does read it.

## Future targets

The following targets are on the roadmap (see [limitations.md](limitations.md#future-work)). None ship in v1. **Do not** assume they work today.

- **OWASP Threat Dragon** (JSON schema). Open-source, easy to test, attractive as a v2 second target.
- **Microsoft Threat Modeling Tool** (`.tm7`). Broader enterprise install base.
- **IriusRisk REST API**. Direct push as an alternative to file output, supporting idempotent re-import. v3 work.

When a second target ships, the `--target` CLI flag, the `target` field in `POST /api/v1/convert`, and the target dropdown in both UIs land at the same time.
