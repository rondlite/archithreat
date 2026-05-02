# Patterns

Purpose: catalogue the ArchiMate modeling shapes that [archithreat](../src/archithreat/__init__.py) understands and the ones it warns about, with concrete fixtures pointing at the resulting draw.io structure.

## Contents

- [Single app on single host](#single-app-on-single-host)
- [Co-hosted apps](#co-hosted-apps)
- [External actor](#external-actor)
- [Multi-zone with cross-zone flow](#multi-zone-with-cross-zone-flow)
- [Realization via TechnologyService](#realization-via-technologyservice)
- [Anti-patterns](#anti-patterns)

---

## Single app on single host

**Elements:** one `Grouping` (zone), one `Node` (host), one `ApplicationComponent`. **Relationships:** `Composition` (zone contains host), `Realization` (app realized by host).

The minimal viable model. Fixture: [tests/fixtures/minimal.xml](../tests/fixtures/minimal.xml).

```xml
<element identifier="g_dmz" xsi:type="Grouping"><name>DMZ</name></element>
<element identifier="n_web" xsi:type="Node"><name>web-host</name></element>
<element identifier="a_app" xsi:type="ApplicationComponent"><name>App</name></element>
<relationship xsi:type="Composition" source="g_dmz" target="n_web"/>
<relationship xsi:type="Realization" source="a_app" target="n_web"/>
```

**Resulting draw.io:** one zone cell `DMZ` (parent `1`); one host container `web-host` parented to the zone; one component cell `App` parented to the host. No edges.

## Co-hosted apps

**Elements:** one zone, one Node, multiple ApplicationComponents. **Relationships:** one Composition (zone-host), one Realization per app, optional Flows between apps.

Fixture: [tests/fixtures/co_hosted.xml](../tests/fixtures/co_hosted.xml). Three apps share one host:

```xml
<element identifier="n_box" xsi:type="Node"><name>app-box</name></element>
<element identifier="a_one" xsi:type="ApplicationComponent"><name>AppOne</name></element>
<element identifier="a_two" xsi:type="ApplicationComponent"><name>AppTwo</name></element>
<element identifier="a_three" xsi:type="ApplicationComponent"><name>AppThree</name></element>
<relationship xsi:type="Realization" source="a_one" target="n_box"/>
<relationship xsi:type="Realization" source="a_two" target="n_box"/>
<relationship xsi:type="Realization" source="a_three" target="n_box"/>
<relationship xsi:type="Flow" source="a_one" target="a_two"/>
<relationship xsi:type="Flow" source="a_two" target="a_three"/>
```

**Resulting draw.io:** one host container `app-box` with three component cells inside it (`AppOne`, `AppTwo`, `AppThree`). Two edges between sibling components inside the same host. Co-location is visible structurally; the host's attack surface is shared between the apps.

## External actor

**Elements:** one zone, one host, one ApplicationComponent, one `BusinessActor`. **Relationships:** Composition (zone-host), Realization (app-host), `Serving` (app serves actor).

Fixture: [tests/fixtures/external_actor.xml](../tests/fixtures/external_actor.xml).

```xml
<element identifier="g_internal" xsi:type="Grouping"><name>Internal</name></element>
<element identifier="n_host" xsi:type="Node"><name>backend-host</name></element>
<element identifier="a_api" xsi:type="ApplicationComponent"><name>API</name></element>
<element identifier="ba_customer" xsi:type="BusinessActor"><name>Customer</name></element>
<relationship xsi:type="Composition" source="g_internal" target="n_host"/>
<relationship xsi:type="Realization" source="a_api" target="n_host"/>
<relationship xsi:type="Serving" source="a_api" target="ba_customer"/>
```

The `Customer` actor is not placed in any Grouping. The resolver puts it in the synthetic `external` zone. **Resulting draw.io:** two zone cells (`Internal` and `External`); the `Internal` zone contains the `backend-host` container with `API` inside; the `External` zone contains the `Customer` actor cell. One edge connects `API` to `Customer` (Serving inverts direction, so the data flow points from `Customer` to `API`).

## Multi-zone with cross-zone flow

**Elements:** multiple Groupings, hosts in each, ApplicationComponents in each, Flows that cross zone boundaries. **Relationships:** Composition (zone-host), Realization (app-host), Flow with `crosses_zone=true`.

Anchor: [tests/fixtures/lemonade_shop.xml](../tests/fixtures/lemonade_shop.xml). Five zones (`Internet`, `DMZ`, `Internal Network`, `Payment Provider`, `Shop Floor`); apps reach across zones via Flow:

```xml
<relationship xsi:type="Flow" source="a_storefront" target="a_orderapi">
  <properties>
    <property propertyDefinitionRef="propdef_protocol">
      <value>HTTPS</value>
    </property>
  </properties>
</relationship>
```

**Resulting draw.io:** five zone cells. Hosts are containment-parented to their zones; apps to their hosts. The Flow `Storefront → Order API` is an edge whose endpoints sit in different zones (`DMZ` vs. `Internal Network`); the edge's `crosses_zone` flag is true and its `protocol=HTTPS` property is carried through via property passthrough. IriusRisk treats cross-zone edges as candidates for transport-level threats; this is why preserving the zone information matters.

## Realization via TechnologyService

ArchiMate models often interpose a `TechnologyService` between an `ApplicationComponent` and the `Node` that ultimately provides it. The resolver walks through. From SPEC §5.1.3 step 3:

```xml
<element identifier="a_orderapi" xsi:type="ApplicationComponent"><name>Order API</name></element>
<element identifier="ts_runtime" xsi:type="TechnologyService"><name>k8s pod</name></element>
<element identifier="n_node" xsi:type="Node"><name>node-1</name></element>
<relationship xsi:type="Realization" source="a_orderapi" target="ts_runtime"/>
<relationship xsi:type="Realization" source="ts_runtime" target="n_node"/>
```

**Resulting draw.io:** one host container `node-1` with `Order API` inside it. The intermediate `k8s pod` `TechnologyService` does not emit as its own component; it is a routing waypoint for realization. If you want it visible in the threat model, model it as a separate Application Component or extend the mapping.

---

## Anti-patterns

### Orphans (no realization)

**Symptom:** an `ApplicationComponent` has no `Realization` to any `Node` or `TechnologyService`. **Warning code:** `unrealized_application_component`. Fixture: [tests/fixtures/orphans.xml](../tests/fixtures/orphans.xml).

```xml
<element identifier="a_orphan" xsi:type="ApplicationComponent"><name>OrphanApp</name></element>
<element identifier="n_lonely" xsi:type="Node"><name>lonely-host</name></element>
<!-- no Realization between them -->
```

The component still emits, but with `host_node_id=None`. It will sit at the zone level rather than inside a host. **Fix:** add a `Realization` from the Application Component to the Node it actually runs on. If you genuinely have an unhosted abstraction (a SaaS service you consume), model it as a Business Actor or extend the mapping for `ApplicationService`.

### Unzoned elements

**Symptom:** an element is reachable by no Composition or Aggregation chain that terminates at a `Grouping` or `Location`. **Warning code:** `unzoned_element`. The resolver places the element in the synthetic `unzoned` zone (rendered with a dashed border per the default mapping).

**Fix:** place the element under a `Grouping` via `Composition`. Or, if the element legitimately has no zone (a free-standing Business Actor representing the outside world), promote it to an external actor by giving it a Flow/Serving relationship to an Application/Technology element — the resolver will then route it into the synthetic `external` zone instead.

You can also change behavior with `--unzoned-policy fail` if you want CI to refuse models that contain unzoned elements.

### Junctions used as logic

**Symptom:** the model uses ArchiMate `Junction` elements (or-junction, and-junction) to express conditional relationship semantics. **Warning code:** `junction_skipped`. archithreat does not currently interpret junctions; the parser sees them, the resolver logs and excludes them, and any relationships that route through them are dropped along the way.

**Fix:** flatten the junction. If A → junction → B, C, D was meant to express "A flows to B and C and D," replace it with three direct relationships `A → B`, `A → C`, `A → D`. The expressivity loss matters at the EA layer, but threat models analyse direct edges and would lose the junction semantics on import anyway.
