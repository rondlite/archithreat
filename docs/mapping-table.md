# Mapping table

Purpose: schema reference and customization guide for the YAML mapping table that drives [archithreat](../src/archithreat/__init__.py)'s ArchiMate-to-target translation.

## Contents

- [Schema](#schema)
- [How matching works](#how-matching-works)
- [Harvesting IriusRisk style strings](#harvesting-iriusrisk-style-strings)
- [Validating a custom mapping](#validating-a-custom-mapping)
- [Worked example: overriding a single rule](#worked-example-overriding-a-single-rule)

## Schema

The shared schema lives in [`mappings/base.py`](../src/archithreat/core/mappings/base.py). Per-target extensions live in sibling files (today, [`mappings/iriusrisk.py`](../src/archithreat/core/mappings/iriusrisk.py)). The default mapping for the v1 target is [`defaults/iriusrisk.yaml`](../src/archithreat/core/defaults/iriusrisk.yaml). The structure is:

```yaml
version: 1
target: iriusrisk

zone_rules:
  - match:
      archimate_type: Grouping            # optional
      property:                           # optional
        name: zone_type                   #   property name on the element
        equals: logical                   #   one of equals | regex | exists
      name_pattern: "^DMZ"                # optional, regex against element.name
    iriusrisk:
      zone_name_property: name
      style: "shape=mxgraph.iriusrisk.trust_zone;..."

synthetic_zones:                          # both keys required
  unzoned:
    name: "Unzoned"
    style: "shape=...;dashed=1;..."
  external:
    name: "External"
    style: "shape=...;fillColor=#fff2cc;..."

component_rules:
  - match:
      archimate_type: ApplicationComponent
      property: { name: tech_stack, equals: web }
    iriusrisk:
      component_type: web_application
      style: "shape=mxgraph.iriusrisk.web_application;..."
      is_container: false                 # optional; true makes the shape host children

connection_rules:
  - match:
      archimate_type: Flow
    iriusrisk:
      style: "edgeStyle=orthogonalEdgeStyle;..."
      direction: source_to_target         # source_to_target | target_to_source | by_access_type

property_passthrough:
  components: [protocol, data_classification, patch_authority, tech_stack]
  connections: [protocol, port, authentication, encryption]

defaults:
  unmatched_element: skip_with_warning    # skip_with_warning | skip_silent | fail
  unmatched_relationship: skip_with_warning
```

Pydantic enforces extra-key rejection on most blocks and requires both `synthetic_zones.unzoned` and `synthetic_zones.external`. A `MatchCondition` requires at least one of `archimate_type`, `property`, or `name_pattern`. A `PropertyMatcher` requires at least one of `equals`, `regex`, or `exists`.

## How matching works

Rules are evaluated in declaration order. **First match wins.** Put your most specific rules first and your fallback rule last. The matching helpers are `match_element` and `match_relationship` in [`base.py`](../src/archithreat/core/mappings/base.py).

A rule's `match` block is conjunctive: every condition listed must hold for the rule to fire.

- `archimate_type` is exact-match against the element's `xsi:type` (namespace-stripped).
- `name_pattern` is `re.search` against `element.name` (or `relationship.name`).
- `property` looks up `element.properties[name]` and applies one or more of `equals` (exact), `regex` (`re.search`), `exists` (true means the key is present, false means absent).

If no rule matches, the `defaults` policy applies:

- `skip_with_warning` (the default) emits a warning record and drops the element/relationship.
- `skip_silent` drops it without a warning.
- `fail` raises and aborts the conversion.

Connection rules also pick a `direction`. `source_to_target` and `target_to_source` are literal. `by_access_type` reads the relationship's `access_type` (read/write/update) and reverses or preserves accordingly.

## Harvesting IriusRisk style strings

The default mapping ships with `style=` strings that follow the mxCell grammar but use `shape=mxgraph.iriusrisk.*` identifiers that should be confirmed against your IriusRisk installation before relying on round-trip into IriusRisk's editor. The output is structurally valid draw.io regardless; the question is only whether IriusRisk's library recognizes the shape on import.

The reliable way to harvest the canonical strings is the **reference-diagram method**:

1. In IriusRisk, open the embedded draw.io editor and create a small diagram containing one of every shape you care about (web application, host, data store, trust zone, generic application, actor, etc.).
2. Save the diagram. IriusRisk persists it as draw.io XML.
3. Export or fetch the saved file (the IriusRisk admin UI exposes raw diagram XML; a project export will also include it).
4. Open the file in a text editor. Each shape is an `mxCell` with a `style="..."` attribute. Copy the `style` value verbatim into the matching rule in your mapping YAML.
5. Repeat for edges if you want IriusRisk-specific edge styles.

Style strings are version-coupled to the IriusRisk shape library. If your installation upgrades the library, re-harvest. Customizing the mapping is exactly the seam designed for this.

## Validating a custom mapping

```bash
archithreat validate-mapping path/to/my_mapping.yaml
```

Exit code 0 means the YAML parses and satisfies the Pydantic schema. Non-zero prints the structured validation errors. The same call is reachable from the web shell at `POST /api/v1/mapping/validate` and from the browser app's "Validate" button — all three call the same `validate_mapping` function in [`mappings/__init__.py`](../src/archithreat/core/mappings/__init__.py).

Validation does not test that your style strings render correctly in IriusRisk; that requires a round-trip in the receiving tool.

## Worked example: overriding a single rule

You want all `ApplicationComponent` elements with `tech_stack=mobile` to render as a custom shape `shape=mxgraph.mycorp.mobile_app` instead of the default. Start by copying the default:

```bash
archithreat show-defaults > mycorp_mapping.yaml
```

Edit the `mobile` rule:

```yaml
component_rules:
  - match:
      archimate_type: ApplicationComponent
      property: { name: tech_stack, equals: mobile }
    iriusrisk:
      component_type: mobile_application
      style: "shape=mxgraph.mycorp.mobile_app;html=1;whiteSpace=wrap;fillColor=#cfe2f3;strokeColor=#3d85c6;"
  # ...rest unchanged
```

Validate, then run:

```bash
archithreat validate-mapping mycorp_mapping.yaml
archithreat convert model.xml model.drawio --mapping mycorp_mapping.yaml
```

Because rules are first-match-wins, the more-specific `tech_stack=mobile` rule must appear above the catch-all `archimate_type: ApplicationComponent` rule. If you flip the order, the catch-all wins and the override never fires.
