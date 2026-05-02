"""Per-target mapping schema tests."""

from __future__ import annotations

import pytest

from archithreat.core.mappings import (
    MAPPING_SCHEMAS,
    UnknownTargetError,
    load_default_mapping,
    load_mapping,
)
from archithreat.core.mappings.iriusrisk import DrawioMapping


def test_target_registered() -> None:
    assert "iriusrisk" in MAPPING_SCHEMAS
    assert MAPPING_SCHEMAS["iriusrisk"] is DrawioMapping


def test_default_mapping_is_drawio_subclass() -> None:
    m = load_default_mapping()
    assert isinstance(m, DrawioMapping)


def test_unknown_target_raises() -> None:
    with pytest.raises(UnknownTargetError):
        load_default_mapping(target="not-a-real-target")


def test_drawio_component_rule_requires_iriusrisk_field() -> None:
    bad = b"""
version: 1
target: iriusrisk
zone_rules: []
synthetic_zones:
  unzoned: {name: U, style: us}
  external: {name: E, style: es}
component_rules:
  - match: {archimate_type: ApplicationComponent}
    # missing iriusrisk: block
connection_rules: []
"""
    from archithreat.core.mappings import MappingValidationError

    with pytest.raises(MappingValidationError):
        load_mapping(bad)
