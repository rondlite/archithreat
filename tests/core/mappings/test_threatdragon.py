"""Threat Dragon mapping schema tests."""

from __future__ import annotations

import pytest

from archithreat.core.mappings import (
    MAPPING_SCHEMAS,
    MappingValidationError,
    UnknownTargetError,
    load_default_mapping,
    load_mapping,
)
from archithreat.core.mappings.threatdragon import ThreatDragonMapping


def test_target_registered() -> None:
    assert "threatdragon" in MAPPING_SCHEMAS
    assert MAPPING_SCHEMAS["threatdragon"] is ThreatDragonMapping


def test_default_mapping_is_td_subclass() -> None:
    m = load_default_mapping(target="threatdragon")
    assert isinstance(m, ThreatDragonMapping)
    assert m.target == "threatdragon"
    assert m.zone_rules
    assert m.component_rules
    assert m.connection_rules


def test_unknown_target_raises() -> None:
    with pytest.raises(UnknownTargetError):
        load_default_mapping(target="not-a-real-target")


def test_td_component_rule_requires_threatdragon_field() -> None:
    bad = b"""
version: 1
target: threatdragon
zone_rules: []
synthetic_zones:
  unzoned: {name: U}
  external: {name: E}
component_rules:
  - match: {archimate_type: ApplicationComponent}
connection_rules: []
"""
    with pytest.raises(MappingValidationError):
        load_mapping(bad, target="threatdragon")


def test_td_target_mismatch() -> None:
    yaml_text = b"""
version: 1
target: iriusrisk
zone_rules: []
synthetic_zones:
  unzoned: {name: U}
  external: {name: E}
component_rules: []
connection_rules: []
"""
    with pytest.raises(MappingValidationError):
        load_mapping(yaml_text, target="threatdragon")
