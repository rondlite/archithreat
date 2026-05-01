"""Apply a BaseMapping (or subclass) to a ResolvedModel.

Output: MappedModel with target_data dicts attached to each zone, component, and
connection. Pure function. The mapper is target-independent — it walks rules and
copies fields. Per-target schemas are validated by Pydantic at load time.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from .mappings.base import (
    BaseMapping,
    ComponentRule,
    ConnectionRule,
    ZoneRule,
    match_element,
    match_relationship,
)
from .model import (
    Element,
    MappedComponent,
    MappedConnection,
    MappedModel,
    MappedZone,
    Relationship,
    ResolvedConnection,
    ResolvedModel,
    Zone,
)
from .resolver import EXTERNAL_ID

logger = logging.getLogger(__name__)


def apply_mapping(
    resolved: ResolvedModel,
    mapping: BaseMapping,
    source_name: str = "",
) -> MappedModel:
    """Combine resolver output with mapping rules into a MappedModel."""
    mapped_zones = _map_zones(resolved.zones, mapping)
    mapped_components = _map_components(resolved, mapping)
    mapped_connections = _map_connections(resolved, mapping)
    return MappedModel(
        zones=mapped_zones,
        components=mapped_components,
        connections=mapped_connections,
        source_name=source_name,
    )


def _map_zones(zones: dict[str, Zone], mapping: BaseMapping) -> dict[str, MappedZone]:
    out: dict[str, MappedZone] = {}
    for zone in zones.values():
        target_data: dict[str, Any] = {}
        if zone.is_synthetic:
            kind: Literal["unzoned", "external"] = (
                "external" if zone.id == EXTERNAL_ID else "unzoned"
            )
            spec = mapping.synthetic_zones.get(kind)
            if spec is not None:
                # SyntheticZone may carry extra fields per target (e.g. style)
                target_data = spec.model_dump(exclude={"name"})
        else:
            # Match the zone element against zone_rules to pick a style.
            # We don't have the original Element here, so we fake one from Zone fields.
            faux = Element(
                id=zone.id,
                name=zone.name,
                archimate_type="Grouping",  # zone rules normally match Grouping/Location
                layer="Composite",
                properties=dict(zone.properties),
            )
            idx = match_element(_as_zone_rules(mapping), faux)
            if idx is None:
                # Try Location explicitly.
                faux_loc = Element(
                    id=zone.id,
                    name=zone.name,
                    archimate_type="Location",
                    layer="Composite",
                    properties=dict(zone.properties),
                )
                idx = match_element(_as_zone_rules(mapping), faux_loc)
            if idx is not None:
                rule = mapping.zone_rules[idx]
                target_data = _rule_target_data(rule)
        out[zone.id] = MappedZone(zone=zone, target_data=target_data)
    return out


def _map_components(resolved: ResolvedModel, mapping: BaseMapping) -> dict[str, MappedComponent]:
    out: dict[str, MappedComponent] = {}
    passthrough = mapping.property_passthrough.components
    for comp in resolved.components.values():
        faux = Element(
            id=comp.id,
            name=comp.name,
            archimate_type=comp.archimate_type,
            layer="Other",  # layer not used by component_rules
            properties=dict(comp.properties),
        )
        idx = match_element(_as_component_rules(mapping), faux)
        if idx is None:
            policy = mapping.defaults.unmatched_element
            if policy == "fail":
                raise ValueError(
                    f"No component_rule matched element {comp.id!r} ({comp.archimate_type})"
                )
            if policy == "skip_with_warning":
                logger.warning(
                    "No component_rule matched element %s (%s); skipping",
                    comp.id,
                    comp.archimate_type,
                )
            continue
        rule = mapping.component_rules[idx]
        target_data = _rule_target_data(rule)
        target_data["passthrough_properties"] = {
            k: v for k, v in comp.properties.items() if k in passthrough
        }
        out[comp.id] = MappedComponent(component=comp, target_data=target_data)
    return out


def _map_connections(resolved: ResolvedModel, mapping: BaseMapping) -> list[MappedConnection]:
    out: list[MappedConnection] = []
    passthrough = mapping.property_passthrough.connections
    for conn in resolved.connections:
        faux = Relationship(
            id=conn.id,
            archimate_type=conn.archimate_type,
            source_id=conn.source_component_id,
            target_id=conn.target_component_id,
            properties=dict(conn.properties),
        )
        idx = match_relationship(_as_connection_rules(mapping), faux)
        if idx is None:
            policy = mapping.defaults.unmatched_relationship
            if policy == "fail":
                raise ValueError(
                    f"No connection_rule matched relationship {conn.id!r} ({conn.archimate_type})"
                )
            if policy == "skip_with_warning":
                logger.warning(
                    "No connection_rule matched relationship %s (%s); skipping",
                    conn.id,
                    conn.archimate_type,
                )
            continue
        rule = mapping.connection_rules[idx]
        target_data = _rule_target_data(rule)
        target_data["passthrough_properties"] = {
            k: v for k, v in conn.properties.items() if k in passthrough
        }
        # Apply direction
        directed_conn = _apply_direction(conn, target_data)
        out.append(MappedConnection(connection=directed_conn, target_data=target_data))
    return out


def _apply_direction(conn: ResolvedConnection, target_data: dict[str, Any]) -> ResolvedConnection:
    """Possibly swap source/target depending on the rule's declared direction."""
    direction: str | None = None
    # Find the per-target spec dict (e.g., {"iriusrisk": {...}}) — flatten to find direction.
    for value in target_data.values():
        if isinstance(value, dict) and "direction" in value:
            direction = value["direction"]
            break
    if direction is None or direction == "source_to_target":
        return conn
    if direction == "target_to_source":
        return ResolvedConnection(
            id=conn.id,
            source_component_id=conn.target_component_id,
            target_component_id=conn.source_component_id,
            archimate_type=conn.archimate_type,
            crosses_zone=conn.crosses_zone,
            properties=conn.properties,
        )
    if direction == "by_access_type":
        access = conn.properties.get("access_type", "").lower()
        if access in {"write", "update"}:
            return conn  # source -> target (caller writes to target)
        # default (read): target -> source semantically
        return ResolvedConnection(
            id=conn.id,
            source_component_id=conn.target_component_id,
            target_component_id=conn.source_component_id,
            archimate_type=conn.archimate_type,
            crosses_zone=conn.crosses_zone,
            properties=conn.properties,
        )
    return conn


def _rule_target_data(rule: ZoneRule | ComponentRule | ConnectionRule) -> dict[str, Any]:
    """Extract per-target fields from a rule, excluding the shared ``match`` block."""
    dump = rule.model_dump()
    dump.pop("match", None)
    return dump


def _as_zone_rules(mapping: BaseMapping) -> list[ZoneRule]:
    return list(mapping.zone_rules)


def _as_component_rules(mapping: BaseMapping) -> list[ComponentRule]:
    return list(mapping.component_rules)


def _as_connection_rules(mapping: BaseMapping) -> list[ConnectionRule]:
    return list(mapping.connection_rules)


__all__ = ["apply_mapping"]
