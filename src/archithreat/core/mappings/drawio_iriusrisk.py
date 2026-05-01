"""Target-specific mapping schema for the v1 emitter (draw.io for IriusRisk).

Extends the shared base schema with mxCell-style fields. Style values shipped in
the bundled default YAML are placeholders pending final IriusRisk shape catalog
verification (see SPEC §10.1).
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

TARGET_ID = "drawio-iriusrisk"


class DrawioStyleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_type: str  # IriusRisk component category, used as label/metadata
    style: str  # mxCell style string (TODO: replace placeholders with real IriusRisk styles)
    is_container: bool = False


class DrawioZoneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_name_property: str = "name"
    style: str  # mxCell style string for the swimlane


class DrawioConnectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str
    direction: Literal["source_to_target", "target_to_source", "by_access_type"] = (
        "source_to_target"
    )


class DrawioSyntheticZone(SyntheticZone):
    model_config = ConfigDict(extra="forbid")

    style: str


class DrawioZoneRule(ZoneRule):
    iriusrisk: DrawioZoneSpec


class DrawioComponentRule(ComponentRule):
    iriusrisk: DrawioStyleSpec


class DrawioConnectionRule(ConnectionRule):
    iriusrisk: DrawioConnectionSpec


class DrawioMapping(BaseMapping):
    target: Literal["drawio-iriusrisk"] = "drawio-iriusrisk"
    zone_rules: list[DrawioZoneRule] = Field(default_factory=list)  # type: ignore[assignment]
    synthetic_zones: dict[Literal["unzoned", "external"], DrawioSyntheticZone]  # type: ignore[assignment]
    component_rules: list[DrawioComponentRule] = Field(default_factory=list)  # type: ignore[assignment]
    connection_rules: list[DrawioConnectionRule] = Field(default_factory=list)  # type: ignore[assignment]
