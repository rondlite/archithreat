"""In-memory representation of a parsed ArchiMate Open Exchange document.

Pure dataclasses, no behavior, no I/O. Target-independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ArchiMateLayer = Literal[
    "Strategy",
    "Business",
    "Application",
    "Technology",
    "Physical",
    "Motivation",
    "Implementation",
    "Composite",
    "Other",
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
    access_type: str | None = None  # Access: read/write/update; None otherwise


@dataclass(frozen=True)
class ViewNode:
    id: str
    element_ref: str | None
    x: int
    y: int
    width: int
    height: int
    parent_id: str | None = None


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


# ---------- Resolver output (target-independent) ----------


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
    host_node_id: str | None = None
    is_host: bool = False
    is_external_actor: bool = False
    properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedConnection:
    id: str
    source_component_id: str
    target_component_id: str
    archimate_type: str
    crosses_zone: bool = False
    properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolverWarning:
    code: str
    message: str
    element_id: str | None = None


@dataclass
class ResolvedModel:
    zones: dict[str, Zone]
    components: dict[str, ResolvedComponent]
    connections: list[ResolvedConnection]
    warnings: list[ResolverWarning] = field(default_factory=list)
    skipped: list[ResolverWarning] = field(default_factory=list)
    realization_links: list[RealizationLink] = field(default_factory=list)


# ---------- Mapper output ----------


@dataclass(frozen=True)
class MappedComponent:
    component: ResolvedComponent
    target_data: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MappedConnection:
    connection: ResolvedConnection
    target_data: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MappedZone:
    zone: Zone
    target_data: dict[str, object] = field(default_factory=dict)


@dataclass
class MappedModel:
    zones: dict[str, MappedZone]
    components: dict[str, MappedComponent]
    connections: list[MappedConnection]
    source_name: str = ""
