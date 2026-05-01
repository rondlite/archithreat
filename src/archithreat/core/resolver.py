"""Resolve a parsed OpenExchangeModel into a target-independent ResolvedModel.

Algorithm (per SPEC §5.1.3):
1. Identify zone elements via mapping zone_rules.
2. Walk Composition/Aggregation upward to assign each element to a zone.
3. Resolve realization chains (ApplicationComponent -> ... -> Node).
4. Identify hosts (Nodes targeted by realization).
5. Identify external actors (Business Actors connected to App/Tech elements).
6. Classify connections (Flow/Serving/Access/Used-By/Triggering).
7. Detect skip cases (Junctions, Physical layer, unknown types).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable

from .mappings.base import BaseMapping, match_element
from .model import (
    Element,
    OpenExchangeModel,
    RealizationLink,
    Relationship,
    ResolvedComponent,
    ResolvedConnection,
    ResolvedModel,
    ResolverWarning,
    Zone,
)

logger = logging.getLogger(__name__)

UNZONED_ID = "__unzoned__"
EXTERNAL_ID = "__external__"

CONTAINMENT_TYPES = {"Composition", "Aggregation"}
CONNECTION_TYPES = {"Flow", "Serving", "Access", "UsedBy", "Used-By", "Triggering"}
SKIP_LAYERS = {"Physical", "Motivation", "Strategy", "Implementation"}
JUNCTION_TYPES = {"Junction", "AndJunction", "OrJunction"}

EXTERNAL_ACTOR_TYPES = {"BusinessActor", "BusinessRole"}


def resolve(model: OpenExchangeModel, mapping: BaseMapping) -> ResolvedModel:
    """Run the full resolver pipeline."""
    warnings: list[ResolverWarning] = []
    skipped: list[ResolverWarning] = []

    zones = _build_zones(model, mapping, warnings)
    zone_assignment = _assign_zones(model, zones, warnings)
    realization_links = _resolve_realizations(model, warnings, skipped)
    realization_index = _build_realization_index(realization_links)
    host_ids = {link.node_id for link in realization_links if link.node_id}

    components = _build_components(
        model, zones, zone_assignment, realization_index, host_ids, warnings
    )

    connections = _build_connections(model, components, zones, realization_index, warnings, skipped)

    return ResolvedModel(
        zones=zones,
        components=components,
        connections=connections,
        warnings=warnings,
        skipped=skipped,
        realization_links=realization_links,
    )


# ---------- Stages ----------


def _build_zones(
    model: OpenExchangeModel, mapping: BaseMapping, warnings: list[ResolverWarning]
) -> dict[str, Zone]:
    zones: dict[str, Zone] = {}
    for element in model.elements.values():
        if element.layer != "Composite":
            continue
        rule_idx = match_element(mapping.zone_rules, element)
        if rule_idx is None:
            warnings.append(
                ResolverWarning(
                    code="zone_rule_no_match",
                    message=f"Composite element {element.name!r} did not match any zone rule",
                    element_id=element.id,
                )
            )
            continue
        zones[element.id] = Zone(
            id=element.id,
            name=element.name,
            is_synthetic=False,
            properties=dict(element.properties),
        )
    # synthetic zones added on-demand by callers below
    return zones


def _ensure_synthetic_zone(zones: dict[str, Zone], mapping: BaseMapping, kind: str) -> str:
    zone_id = UNZONED_ID if kind == "unzoned" else EXTERNAL_ID
    if zone_id not in zones:
        spec = mapping.synthetic_zones[kind]  # type: ignore[index]
        zones[zone_id] = Zone(id=zone_id, name=spec.name, is_synthetic=True)
    return zone_id


def _assign_zones(
    model: OpenExchangeModel,
    zones: dict[str, Zone],
    warnings: list[ResolverWarning],
) -> dict[str, str | None]:
    """Walk Composition/Aggregation upward; first zone reached wins (deterministic)."""
    parents: dict[str, list[str]] = defaultdict(list)
    for rel in model.relationships.values():
        if rel.archimate_type in CONTAINMENT_TYPES:
            # source contains target
            parents[rel.target_id].append(rel.source_id)

    # sort for determinism
    for k in parents:
        parents[k] = sorted(parents[k])

    assignment: dict[str, str | None] = {}
    for element_id in model.elements:
        if element_id in zones:
            assignment[element_id] = element_id
            continue
        zone = _walk_to_zone(element_id, parents, zones, warnings)
        assignment[element_id] = zone
    return assignment


def _walk_to_zone(
    start: str,
    parents: dict[str, list[str]],
    zones: dict[str, Zone],
    warnings: list[ResolverWarning],
) -> str | None:
    seen: set[str] = set()
    queue: list[str] = list(parents.get(start, []))
    multiple = False
    found: str | None = None
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if current in zones:
            if found is None:
                found = current
            elif found != current:
                multiple = True
            continue
        queue.extend(parents.get(current, []))
    if multiple:
        warnings.append(
            ResolverWarning(
                code="multiple_zone_candidates",
                message=f"Element {start!r} has multiple zone ancestors; using {found!r}",
                element_id=start,
            )
        )
    return found


def _resolve_realizations(
    model: OpenExchangeModel,
    warnings: list[ResolverWarning],
    skipped: list[ResolverWarning],
) -> list[RealizationLink]:
    """Walk Realization edges from ApplicationComponents to Nodes (possibly via TechnologyService)."""
    # source_id -> [target_id] for Realization
    realization_edges: dict[str, list[str]] = defaultdict(list)
    for rel in model.relationships.values():
        if rel.archimate_type == "Realization":
            realization_edges[rel.source_id].append(rel.target_id)
    for k in realization_edges:
        realization_edges[k].sort()

    links: list[RealizationLink] = []
    seen_components: set[str] = set()
    for element in model.elements.values():
        if element.archimate_type != "ApplicationComponent":
            continue
        if element.id in seen_components:
            continue
        seen_components.add(element.id)
        node_ids = _walk_realization(element.id, realization_edges, model.elements, skipped)
        if not node_ids:
            warnings.append(
                ResolverWarning(
                    code="application_component_unrealized",
                    message=f"ApplicationComponent {element.name!r} has no realization to a Node",
                    element_id=element.id,
                )
            )
            links.append(RealizationLink(application_component_id=element.id, node_id=None))
        else:
            for nid in sorted(node_ids):
                links.append(RealizationLink(application_component_id=element.id, node_id=nid))
    return links


def _walk_realization(
    start: str,
    realization_edges: dict[str, list[str]],
    elements: dict[str, Element],
    skipped: list[ResolverWarning],
) -> set[str]:
    """Walk realization chain. Stop at a Node; pass through TechnologyService."""
    found_nodes: set[str] = set()
    seen: set[str] = set()
    queue: list[str] = list(realization_edges.get(start, []))
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        target = elements.get(current)
        if target is None:
            continue
        if target.layer == "Physical":
            skipped.append(
                ResolverWarning(
                    code="realization_to_physical_skipped",
                    message=f"Realization to Physical-layer element {target.name!r} skipped (out of v1 scope)",
                    element_id=current,
                )
            )
            continue
        # ArchiMate 3: Device and SystemSoftware are Node subtypes — terminators.
        if target.archimate_type in {"Node", "Device", "SystemSoftware"}:
            found_nodes.add(current)
            continue
        if target.archimate_type in {"TechnologyService", "Artifact"}:
            queue.extend(realization_edges.get(current, []))
            continue
        # unknown intermediate; record and keep walking
        queue.extend(realization_edges.get(current, []))
    return found_nodes


def _build_realization_index(
    realization_links: list[RealizationLink],
) -> dict[str, str | None]:
    """ApplicationComponent ID -> first host Node ID (deterministic by sorted node_ids)."""
    index: dict[str, str | None] = {}
    for link in realization_links:
        existing = index.get(link.application_component_id, "_unset_")
        if existing == "_unset_":
            index[link.application_component_id] = link.node_id
    return index


def _build_components(
    model: OpenExchangeModel,
    zones: dict[str, Zone],
    zone_assignment: dict[str, str | None],
    realization_index: dict[str, str | None],
    host_ids: set[str],
    warnings: list[ResolverWarning],
) -> dict[str, ResolvedComponent]:
    components: dict[str, ResolvedComponent] = {}

    # First pass: determine host zone assignments (so apps can inherit).
    host_zones: dict[str, str | None] = {}
    for host_id in host_ids:
        host_zones[host_id] = zone_assignment.get(host_id)

    for element in model.elements.values():
        # Composite elements become zones, not components.
        if element.id in zones:
            continue
        if element.layer == "Composite":
            continue
        # Skip wholly-skipped layers.
        if element.layer in SKIP_LAYERS:
            continue
        # Skip junctions.
        if element.archimate_type in JUNCTION_TYPES:
            continue

        zone_id = zone_assignment.get(element.id)
        is_external = element.archimate_type in EXTERNAL_ACTOR_TYPES

        host_node_id: str | None = None
        is_host = False
        if element.archimate_type == "ApplicationComponent":
            host_node_id = realization_index.get(element.id)
            if host_node_id and host_node_id in zones:
                # host is a zone, not a Node — should not happen
                host_node_id = None
            # Inherit zone from host when the component itself is not directly contained.
            if zone_id is None and host_node_id is not None:
                zone_id = host_zones.get(host_node_id)
        elif element.id in host_ids:
            is_host = True

        if zone_id is None:
            zone_id = EXTERNAL_ID if is_external else UNZONED_ID

        components[element.id] = ResolvedComponent(
            id=element.id,
            name=element.name,
            archimate_type=element.archimate_type,
            zone_id=zone_id,
            host_node_id=host_node_id,
            is_host=is_host,
            is_external_actor=is_external,
            properties=dict(element.properties),
        )

    return components


def _build_connections(
    model: OpenExchangeModel,
    components: dict[str, ResolvedComponent],
    zones: dict[str, Zone],
    realization_index: dict[str, str | None],
    warnings: list[ResolverWarning],
    skipped: list[ResolverWarning],
) -> list[ResolvedConnection]:
    connections: list[ResolvedConnection] = []
    for rel in model.relationships.values():
        if rel.archimate_type not in CONNECTION_TYPES:
            continue
        src_id = _component_for(rel.source_id, components, realization_index)
        tgt_id = _component_for(rel.target_id, components, realization_index)
        if src_id is None or tgt_id is None:
            skipped.append(
                ResolverWarning(
                    code="connection_endpoint_unmapped",
                    message=f"Relationship {rel.id!r} ({rel.archimate_type}) has unmapped endpoint(s)",
                    element_id=rel.id,
                )
            )
            continue
        if src_id == tgt_id:
            skipped.append(
                ResolverWarning(
                    code="connection_self_loop",
                    message=f"Relationship {rel.id!r} resolves to a self-loop after realization",
                    element_id=rel.id,
                )
            )
            continue
        src_zone = components[src_id].zone_id
        tgt_zone = components[tgt_id].zone_id
        crosses = src_zone != tgt_zone
        props = dict(rel.properties)
        if rel.access_type:
            props["access_type"] = rel.access_type
        connections.append(
            ResolvedConnection(
                id=rel.id,
                source_component_id=src_id,
                target_component_id=tgt_id,
                archimate_type=rel.archimate_type,
                crosses_zone=crosses,
                properties=props,
            )
        )
    return connections


def _component_for(
    element_id: str,
    components: dict[str, ResolvedComponent],
    realization_index: dict[str, str | None],
) -> str | None:
    if element_id in components:
        return element_id
    return None


def finalize_synthetic_zones(model: ResolvedModel, mapping: BaseMapping) -> None:
    """Add synthetic zones to ``model.zones`` if any component references them."""
    referenced = {c.zone_id for c in model.components.values()}
    if UNZONED_ID in referenced and UNZONED_ID not in model.zones:
        spec = mapping.synthetic_zones["unzoned"]
        model.zones[UNZONED_ID] = Zone(id=UNZONED_ID, name=spec.name, is_synthetic=True)
    if EXTERNAL_ID in referenced and EXTERNAL_ID not in model.zones:
        spec = mapping.synthetic_zones["external"]
        model.zones[EXTERNAL_ID] = Zone(id=EXTERNAL_ID, name=spec.name, is_synthetic=True)


def resolve_with_synthetic(model: OpenExchangeModel, mapping: BaseMapping) -> ResolvedModel:
    """Convenience: resolve + materialize synthetic zones."""
    resolved = resolve(model, mapping)
    finalize_synthetic_zones(resolved, mapping)
    return resolved


__all__ = [
    "EXTERNAL_ID",
    "UNZONED_ID",
    "finalize_synthetic_zones",
    "resolve",
    "resolve_with_synthetic",
]


# Silence unused-import lint for typing references kept for clarity.
_ = (Iterable, Relationship)
