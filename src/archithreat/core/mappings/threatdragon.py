"""OWASP Threat Dragon v2 target mapping schema.

Threat Dragon's diagram format is a single JSON document keyed by ``summary`` /
``detail.diagrams[].cells``. Each cell is a JointJS / X6 shape: ``process``,
``store``, ``actor``, ``trust-boundary-box``, or ``flow``. See
https://github.com/OWASP/threat-dragon/tree/main/ThreatDragonModels for
reference samples.

Notes:
- TD has no first-class host concept. ArchiMate Nodes/Devices map to
  ``process`` (there is no ``host`` stencil); apps and hosts both render as
  process bubbles. Containment is *visual* — components positioned inside a
  trust-boundary-box. The box is not a parent of cells in the JSON model.
- Trust boundaries here use ``trust-boundary-box`` (rectangle) rather than
  ``trust-boundary-curve`` (free-form curve through points). Boxes are deterministic
  and easy to auto-layout; curves require user gestures we cannot synthesize.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import (
    BaseMapping,
    ComponentRule,
    ConnectionRule,
    SyntheticZone,
    ZoneRule,
)

TARGET_ID = "threatdragon"

ShapeKind = Literal["process", "store", "actor"]
DirectionKind = Literal["source_to_target", "target_to_source", "by_access_type"]


class ThreatDragonStencilSpec(BaseModel):
    """Per-component stencil + data attributes."""

    model_config = ConfigDict(extra="forbid")

    shape: ShapeKind
    # tm.<Type> string matching the shape.
    # - process → tm.Process
    # - store   → tm.Store
    # - actor   → tm.Actor
    type_name: str  # filled in mapper; explicit here for clarity
    # Optional per-shape booleans; only those relevant to the shape are used.
    is_web_application: bool = False
    privilege_level: str = ""
    is_encrypted: bool = False
    is_signed: bool = False
    is_a_log: bool = False
    stores_credentials: bool = False
    stores_inventory: bool = False
    handles_card_payment: bool = False
    handles_goods_or_services: bool = False
    provides_authentication: bool = False
    out_of_scope: bool = False


class ThreatDragonZoneSpec(BaseModel):
    """Trust boundary box specification."""

    model_config = ConfigDict(extra="forbid")

    zone_name_property: str = "name"
    # Always a trust-boundary-box (we don't emit curves).
    # Visual style overrides — sensible defaults per TD's stock styling.
    stroke_color: str = "#333333"
    stroke_dasharray: str = "10 5"
    stroke_width: int = 3
    rx: int = 10
    ry: int = 10


class ThreatDragonFlowSpec(BaseModel):
    """Data-flow line specification."""

    model_config = ConfigDict(extra="forbid")

    direction: DirectionKind = "source_to_target"
    is_encrypted: bool = False
    is_public_network: bool = False
    protocol: str = ""
    stroke_color: str = "#333333"
    stroke_width: int = 1


class ThreatDragonSyntheticZone(SyntheticZone):
    model_config = ConfigDict(extra="forbid")

    stroke_color: str = "#999999"
    stroke_dasharray: str = "10 5"


class ThreatDragonZoneRule(ZoneRule):
    threatdragon: ThreatDragonZoneSpec


class ThreatDragonComponentRule(ComponentRule):
    threatdragon: ThreatDragonStencilSpec


class ThreatDragonConnectionRule(ConnectionRule):
    threatdragon: ThreatDragonFlowSpec


class ThreatDragonMapping(BaseMapping):
    target: Literal["threatdragon"] = "threatdragon"
    zone_rules: list[ThreatDragonZoneRule] = Field(default_factory=list)  # type: ignore[assignment]
    synthetic_zones: dict[Literal["unzoned", "external"], ThreatDragonSyntheticZone]  # type: ignore[assignment]
    component_rules: list[ThreatDragonComponentRule] = Field(default_factory=list)  # type: ignore[assignment]
    connection_rules: list[ThreatDragonConnectionRule] = Field(default_factory=list)  # type: ignore[assignment]
