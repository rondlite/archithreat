# Concepts

Purpose: explain the modeling discipline that makes ArchiMate-to-threat-model conversion meaningful, so the output of [archithreat](../src/archithreat/__init__.py) reflects intentional architectural decisions rather than accidents of notation.

## Contents

- [Application-Component-centric threat modeling](#application-component-centric-threat-modeling)
- [Trust zones via Grouping and Location](#trust-zones-via-grouping-and-location)
- [Realization as containment](#realization-as-containment)
- [Multiplicity](#multiplicity)
- [External actors](#external-actors)

## Application-Component-centric threat modeling

The unit of analysis in a threat model is "a thing with its own attack surface." In ArchiMate, that thing maps cleanly to an `ApplicationComponent`. archithreat emits one threat-model component per ArchiMate Application Component. Nodes that host one or more Application Components emit as **container shapes** with the Application Components as children.

This matches two realities at once. First, threat-modeling tools (IriusRisk, Threat Dragon, MS TMT) reason about software components and the hosts they run on; they do not reason about EA constructs like ApplicationCollaboration. Second, this is how modelers structure their BiZZdesign / Sparx EA models in practice: an Application Component is the thing the security review is about; the Node is where it lives.

Other ArchiMate Application-layer elements (`ApplicationService`, `ApplicationFunction`, `ApplicationInterface`) are recognized but emit only when explicitly mapped. v1 keeps the surface narrow on purpose: each additional element type that becomes a component is a new threat-modeling abstraction that needs its own catalogue entry.

## Trust zones via Grouping and Location

Trust zones in v1 are **logical only**. archithreat treats `Grouping` and `Location` elements as zones. Composition or Aggregation from a zone to an element places that element in that zone. The matching is done in the [resolver](../src/archithreat/core/resolver.py), driven by the [zone rules](../src/archithreat/core/defaults/drawio_iriusrisk.yaml) in the active mapping.

Two synthetic zones exist for elements that escape classification: `unzoned` (an element is in no zone) and `external` (a Business Actor or Role talking to an Application/Technology element from outside). Both surface as warnings; both are configurable via `--unzoned-policy` and via the mapping's `synthetic_zones` block.

Physical zoning (the ArchiMate Physical layer plus 2D physical/logical composites) is deferred to v2. The parser does not discard physical-layer information; the resolver simply skips it in v1.

## Realization as containment

`Realization` from an `ApplicationComponent` to a `Node` becomes parent-child containment in the output. It is not an edge. This is structurally closer to "this software runs on this host," it lines up with how IriusRisk's threat library expects host-contains-application, and it removes visual clutter that edges would create.

Anchor example, [tests/fixtures/lemonade_shop.xml](../tests/fixtures/lemonade_shop.xml):

```xml
<element identifier="z_dmz" xsi:type="Grouping"><name>DMZ</name></element>
<element identifier="n_webserver" xsi:type="Node"><name>web-server-1</name></element>
<element identifier="a_storefront" xsi:type="ApplicationComponent"><name>Storefront</name></element>

<relationship xsi:type="Composition" source="z_dmz" target="n_webserver"/>
<relationship xsi:type="Realization" source="a_storefront" target="n_webserver"/>
```

Resulting draw.io structure (one zone cell containing one host cell containing one component cell):

```
mxCell id="z_dmz"          parent="1"          (zone "DMZ")
  mxCell id="n_webserver"  parent="z_dmz"      (host "web-server-1", is_container=true)
    mxCell id="a_storefront" parent="n_webserver" (component "Storefront")
```

If a Realization passes through a `TechnologyService` on its way to a Node, the resolver walks through it. The resulting containment is still ApplicationComponent inside the terminal Node.

## Multiplicity

archithreat does not synthesize multiplicity. The modeler controls it.

- One Application Component realized by twelve Nodes: twelve components emitted, one per Node.
- One Application Component realized by one Node with an `instances: 12` property: one component emitted, with `instances` carried through as metadata via property passthrough.

If you want twelve instances visible in the threat model, model twelve Nodes. If you want one component annotated with a count, use a property. Either is valid; the converter does not have an opinion.

## External actors

Business Actors and Business Roles connected (via Flow, Serving, Triggering, etc.) to Application or Technology elements become **external** entities. They are placed in the synthetic `external` zone unless explicitly placed inside a zone-mapped Grouping (as the `Customer` actor is in the lemonade fixture, where they sit in the `Internet` zone).

External actors are entry points. They are the surface of the threat model that users, partner systems, and untrusted networks touch. Modeling them as zone-placed Business Actors gives the downstream tool the signal it needs to attach untrusted-input threats automatically.

The other Business-layer elements (`BusinessProcess`, `BusinessFunction`, `BusinessInteraction`) are silently ignored by v1; they are organizational abstractions, not attack surfaces.
