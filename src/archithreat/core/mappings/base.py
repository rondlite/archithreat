"""Shared mapping schema (target-independent).

Each target subclasses ``ZoneRule``, ``ComponentRule``, ``ConnectionRule`` to add
its own emit-time fields, and subclasses ``BaseMapping`` to bind those subclasses.
The matching machinery (first-match-wins, conditions, passthrough) lives here.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..model import Element, Relationship


class PropertyMatcher(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    equals: str | None = None
    regex: str | None = None
    exists: bool | None = None

    @model_validator(mode="after")
    def _at_least_one_op(self) -> PropertyMatcher:
        if self.equals is None and self.regex is None and self.exists is None:
            raise ValueError("PropertyMatcher requires equals, regex, or exists")
        return self


class MatchCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archimate_type: str | None = None
    property: PropertyMatcher | None = None
    name_pattern: str | None = None

    @model_validator(mode="after")
    def _at_least_one_condition(self) -> MatchCondition:
        if self.archimate_type is None and self.property is None and self.name_pattern is None:
            raise ValueError(
                "MatchCondition needs at least one of: archimate_type, property, name_pattern"
            )
        return self


class BaseRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match: MatchCondition


class ZoneRule(BaseRule):
    """Match Composite-layer elements (Grouping/Location) and label them as zones."""


class ComponentRule(BaseRule):
    """Match elements that should become threat-model components."""


class ConnectionRule(BaseRule):
    """Match relationships that should become threat-model connections."""


class SyntheticZone(BaseModel):
    model_config = ConfigDict(extra="allow")  # target-specific style fields

    name: str


class PropertyPassthrough(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unmatched_element: Literal["skip_with_warning", "skip_silent", "fail"] = "skip_with_warning"
    unmatched_relationship: Literal["skip_with_warning", "skip_silent", "fail"] = (
        "skip_with_warning"
    )


class BaseMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    target: str
    zone_rules: list[ZoneRule] = Field(default_factory=list)
    synthetic_zones: dict[Literal["unzoned", "external"], SyntheticZone]
    component_rules: list[ComponentRule] = Field(default_factory=list)
    connection_rules: list[ConnectionRule] = Field(default_factory=list)
    property_passthrough: PropertyPassthrough = Field(default_factory=PropertyPassthrough)
    defaults: Defaults = Field(default_factory=Defaults)

    @model_validator(mode="after")
    def _both_synthetic_zones_required(self) -> BaseMapping:
        missing = {"unzoned", "external"} - set(self.synthetic_zones)
        if missing:
            raise ValueError(
                f"synthetic_zones must define both 'unzoned' and 'external'; missing: {sorted(missing)}"
            )
        return self

    def zone_identity_key(self, target_data: dict[str, object]) -> str | None:
        """Return a target-specific identifier for a zone's emit-time identity.

        When two zones (e.g. a real Grouping and the synthetic external) would
        emit with the same identity in the receiving tool, the mapper folds
        the synthetic into the real one to avoid duplicate trust zones.

        Default: no dedupe. Subclasses override to extract the relevant ref
        (for IriusRisk, ``ir.ref=<uuid>`` from the mxCell style string).
        """
        return None


# ---------- Matching helpers ----------


def _match_property(prop: PropertyMatcher, props: dict[str, str]) -> bool:
    value = props.get(prop.name)
    if prop.exists is not None:
        present = value is not None
        if present != prop.exists:
            return False
    if prop.equals is not None:
        if value != prop.equals:
            return False
    if prop.regex is not None:
        if value is None or not re.search(prop.regex, value):
            return False
    return True


def _condition_matches(
    cond: MatchCondition, archimate_type: str, name: str, properties: dict[str, str]
) -> bool:
    if cond.archimate_type is not None and cond.archimate_type != archimate_type:
        return False
    if cond.name_pattern is not None and not re.search(cond.name_pattern, name):
        return False
    if cond.property is not None and not _match_property(cond.property, properties):
        return False
    return True


def match_element(rules: list[ZoneRule] | list[ComponentRule], element: Element) -> int | None:
    """Return index of first matching rule, or None."""
    for i, r in enumerate(rules):
        if _condition_matches(r.match, element.archimate_type, element.name, element.properties):
            return i
    return None


def match_relationship(rules: list[ConnectionRule], relationship: Relationship) -> int | None:
    for i, r in enumerate(rules):
        if _condition_matches(
            r.match,
            relationship.archimate_type,
            relationship.name or "",
            relationship.properties,
        ):
            return i
    return None
