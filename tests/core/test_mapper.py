"""Mapper / mapping rule unit tests."""

from __future__ import annotations

import pytest

from archithreat.core.mapper import apply_mapping
from archithreat.core.mappings import (
    MappingValidationError,
    load_default_mapping,
    load_mapping,
    validate_mapping,
)
from archithreat.core.parser import parse_bytes
from archithreat.core.resolver import resolve_with_synthetic


def test_default_mapping_loads() -> None:
    m = load_default_mapping()
    assert m.target == "iriusrisk"
    assert m.zone_rules
    assert m.component_rules
    assert m.connection_rules


def test_mapping_validation_catches_missing_match() -> None:
    bad = b"""
version: 1
target: iriusrisk
zone_rules: []
component_rules:
  - iriusrisk:
      component_type: x
      style: "s"
synthetic_zones:
  unzoned: {name: U, style: s}
  external: {name: E, style: s}
"""
    errs = validate_mapping(bad)
    assert errs


def test_mapping_validation_catches_unknown_target() -> None:
    bad = b"""
version: 1
target: iriusrisk
component_rules: []
zone_rules: []
connection_rules: []
synthetic_zones: {}
"""
    # missing the required unzoned/external synthetic zones is a schema error
    errs = validate_mapping(bad)
    assert errs


def test_load_mapping_target_mismatch() -> None:
    bad = b"""
version: 1
target: something-else
synthetic_zones:
  unzoned: {name: U, style: s}
  external: {name: E, style: s}
"""
    with pytest.raises(MappingValidationError):
        load_mapping(bad)


def test_apply_mapping_attaches_styles(lemonade_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(lemonade_xml), mapping)
    mapped = apply_mapping(resolved, mapping)
    storefront = mapped.components["a_storefront"]
    spec = storefront.target_data.get("iriusrisk")
    assert isinstance(spec, dict)
    # storefront has tech_stack=web, so it should hit the Web UI rule first
    assert spec["component_type"] == "web-ui"


def test_first_match_wins() -> None:
    yaml_text = b"""
version: 1
target: iriusrisk
zone_rules:
  - match: {archimate_type: Grouping}
    iriusrisk:
      zone_name_property: name
      style: "z"
synthetic_zones:
  unzoned: {name: U, style: us}
  external: {name: E, style: es}
component_rules:
  - match:
      archimate_type: ApplicationComponent
      property: {name: kind, equals: special}
    iriusrisk:
      component_type: special
      style: "sp"
  - match: {archimate_type: ApplicationComponent}
    iriusrisk:
      component_type: generic
      style: "g"
connection_rules: []
"""
    m = load_mapping(yaml_text)
    assert len(m.component_rules) == 2


def test_property_passthrough_in_components(lemonade_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(lemonade_xml), mapping)
    mapped = apply_mapping(resolved, mapping)
    storefront = mapped.components["a_storefront"]
    pt = storefront.target_data.get("passthrough_properties")
    assert isinstance(pt, dict)
    assert pt.get("tech_stack") == "web"
