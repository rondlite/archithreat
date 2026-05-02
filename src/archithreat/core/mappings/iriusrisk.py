"""Target-specific mapping schema for the v1 emitter (draw.io for IriusRisk).

Extends the shared base schema with mxCell-style fields. Style values shipped in
the bundled default YAML are placeholders pending final IriusRisk shape catalog
verification (see SPEC §10.1).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import (
    BaseMapping,
    ComponentRule,
    ConnectionRule,
    SyntheticZone,
    ZoneRule,
)

_IR_REF_RE = re.compile(r"(?:^|;)ir\.ref=([^;]+)")

TARGET_ID = "iriusrisk"


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
    target: Literal["iriusrisk"] = "iriusrisk"
    zone_rules: list[DrawioZoneRule] = Field(default_factory=list)  # type: ignore[assignment]
    synthetic_zones: dict[Literal["unzoned", "external"], DrawioSyntheticZone]  # type: ignore[assignment]
    component_rules: list[DrawioComponentRule] = Field(default_factory=list)  # type: ignore[assignment]
    connection_rules: list[DrawioConnectionRule] = Field(default_factory=list)  # type: ignore[assignment]

    def zone_identity_key(self, target_data: dict[str, object]) -> str | None:
        """IriusRisk identifies trust zones by their ``ir.ref`` UUID embedded in
        the mxCell style. Two zones with the same ref collide on import."""
        spec = target_data.get("iriusrisk")
        style: str | None = None
        if isinstance(spec, dict):
            v = spec.get("style")
            if isinstance(v, str):
                style = v
        if style is None:
            top = target_data.get("style")
            if isinstance(top, str):
                style = top  # synthetic zones store style at top level
        if style is None:
            return None
        m = _IR_REF_RE.search(style)
        return m.group(1) if m else None
