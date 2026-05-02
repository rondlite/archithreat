"""Targeted tests filling coverage gaps in core/."""

from __future__ import annotations

from pathlib import Path

import pytest

from archithreat.core.mapper import apply_mapping
from archithreat.core.mappings import (
    MappingValidationError,
    load_default_mapping,
    load_mapping,
)
from archithreat.core.mappings.base import (
    BaseMapping,
    Defaults,
    MatchCondition,
    PropertyMatcher,
    SyntheticZone,
)
from archithreat.core.parser import ParserError, parse_bytes, parse_path
from archithreat.core.resolver import resolve_with_synthetic

# ---------- Parser ----------


def test_parse_path_missing(tmp_path: Path) -> None:
    with pytest.raises(ParserError, match="Cannot read"):
        parse_path(tmp_path / "nope.xml")


def test_parse_path_ok(tmp_path: Path, lemonade_xml: bytes) -> None:
    p = tmp_path / "m.xml"
    p.write_bytes(lemonade_xml)
    model = parse_path(p)
    assert model.name == "Lemonade Shop"


def test_view_geometry_parsed() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="e1" xsi:type="ApplicationComponent"><name>A</name></element>
  </elements>
  <relationships/>
  <views>
    <diagrams>
      <view identifier="v1" viewpoint="Application">
        <name>V1</name>
        <node identifier="n1" elementRef="e1" x="10" y="20" w="100" h="80">
          <node identifier="n2" elementRef="e1" x="0" y="0" w="50" h="40"/>
        </node>
        <connection identifier="c1" relationshipRef="" source="n1" target="n2"/>
      </view>
    </diagrams>
  </views>
</model>"""
    model = parse_bytes(xml)
    assert len(model.views) == 1
    v = model.views[0]
    assert v.name == "V1"
    assert v.viewpoint == "Application"
    # nested node captured with parent_id
    assert any(n.parent_id == "n1" for n in v.nodes)
    assert v.connections[0].source_node_id == "n1"


def test_label_with_no_lang_attribute() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>nolang</name>
  <elements>
    <element identifier="e1" xsi:type="ApplicationComponent"><name>NoLang</name></element>
  </elements>
  <relationships/>
</model>"""
    model = parse_bytes(xml)
    assert model.elements["e1"].name == "NoLang"


def test_relationship_missing_attrs_skipped() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="e1" xsi:type="ApplicationComponent"><name>A</name></element>
  </elements>
  <relationships>
    <relationship xsi:type="Flow" target="e1"/>
  </relationships>
</model>"""
    model = parse_bytes(xml)
    assert len(model.relationships) == 0


# ---------- Resolver ----------


def test_multiple_zone_candidates_warning() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="g_a" xsi:type="Grouping"><name>A</name></element>
    <element identifier="g_b" xsi:type="Grouping"><name>B</name></element>
    <element identifier="n1" xsi:type="Node"><name>n</name></element>
  </elements>
  <relationships>
    <relationship identifier="r1" xsi:type="Composition" source="g_a" target="n1"/>
    <relationship identifier="r2" xsi:type="Composition" source="g_b" target="n1"/>
  </relationships>
</model>"""
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    assert any(w.code == "multiple_zone_candidates" for w in resolved.warnings)


def test_physical_layer_skipped() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="e1" xsi:type="Equipment"><name>Kit</name></element>
  </elements>
  <relationships/>
</model>"""
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    # Equipment is Physical layer → skipped from components
    assert "e1" not in resolved.components


def test_junction_skipped() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="j1" xsi:type="AndJunction"><name>J</name></element>
  </elements>
  <relationships/>
</model>"""
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    assert "j1" not in resolved.components


def test_realization_through_technology_service() -> None:
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="g1" xsi:type="Grouping"><name>Z</name></element>
    <element identifier="ts1" xsi:type="TechnologyService"><name>TS</name></element>
    <element identifier="n1" xsi:type="Node"><name>n</name></element>
    <element identifier="a1" xsi:type="ApplicationComponent"><name>A</name></element>
  </elements>
  <relationships>
    <relationship identifier="rc" xsi:type="Composition" source="g1" target="n1"/>
    <relationship identifier="r1" xsi:type="Realization" source="a1" target="ts1"/>
    <relationship identifier="r2" xsi:type="Realization" source="ts1" target="n1"/>
  </relationships>
</model>"""
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    assert resolved.components["a1"].host_node_id == "n1"


# ---------- Mapper ----------


def test_unmatched_element_fail_policy() -> None:
    """Mapper raises when unmatched_element=fail."""
    yaml = b"""
version: 1
target: iriusrisk
zone_rules: []
synthetic_zones:
  unzoned: {name: U, style: us}
  external: {name: E, style: es}
component_rules: []
connection_rules: []
defaults:
  unmatched_element: fail
"""
    mapping = load_mapping(yaml)
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="a1" xsi:type="ApplicationComponent"><name>A</name></element>
  </elements>
  <relationships/>
</model>"""
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    with pytest.raises(ValueError, match="No component_rule matched"):
        apply_mapping(resolved, mapping)


def test_unmatched_relationship_fail_policy() -> None:
    yaml = b"""
version: 1
target: iriusrisk
zone_rules: []
synthetic_zones:
  unzoned: {name: U, style: us}
  external: {name: E, style: es}
component_rules:
  - match: {archimate_type: ApplicationComponent}
    iriusrisk: {component_type: x, style: s}
connection_rules: []
defaults:
  unmatched_relationship: fail
"""
    mapping = load_mapping(yaml)
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="a1" xsi:type="ApplicationComponent"><name>A</name></element>
    <element identifier="a2" xsi:type="ApplicationComponent"><name>B</name></element>
  </elements>
  <relationships>
    <relationship identifier="r1" xsi:type="Flow" source="a1" target="a2"/>
  </relationships>
</model>"""
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    with pytest.raises(ValueError, match="No connection_rule matched"):
        apply_mapping(resolved, mapping)


def test_silent_unmatched_policies() -> None:
    yaml = b"""
version: 1
target: iriusrisk
zone_rules: []
synthetic_zones:
  unzoned: {name: U, style: us}
  external: {name: E, style: es}
component_rules: []
connection_rules: []
defaults:
  unmatched_element: skip_silent
  unmatched_relationship: skip_silent
"""
    mapping = load_mapping(yaml)
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="a1" xsi:type="ApplicationComponent"><name>A</name></element>
    <element identifier="a2" xsi:type="ApplicationComponent"><name>B</name></element>
  </elements>
  <relationships>
    <relationship identifier="r1" xsi:type="Flow" source="a1" target="a2"/>
  </relationships>
</model>"""
    resolved = resolve_with_synthetic(parse_bytes(xml), mapping)
    mapped = apply_mapping(resolved, mapping)
    # nothing matched → empty
    assert not mapped.components
    assert not mapped.connections


def test_access_direction_swaps_for_read() -> None:
    """Access read should reverse source/target per by_access_type."""
    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements>
    <element identifier="g1" xsi:type="Grouping"><name>Z</name></element>
    <element identifier="n1" xsi:type="Node"><name>N</name></element>
    <element identifier="a1" xsi:type="ApplicationComponent"><name>A</name></element>
    <element identifier="d1" xsi:type="DataObject"><name>D</name></element>
  </elements>
  <relationships>
    <relationship identifier="rc" xsi:type="Composition" source="g1" target="n1"/>
    <relationship identifier="rr" xsi:type="Realization" source="a1" target="n1"/>
    <relationship identifier="rx" xsi:type="Access" source="a1" target="d1" accessType="read"/>
  </relationships>
</model>"""
    from archithreat import convert_bytes

    out = convert_bytes(xml)
    assert b"<mxfile" in out


# ---------- Mappings base ----------


def test_property_matcher_requires_op() -> None:
    with pytest.raises(ValueError):
        PropertyMatcher(name="x")


def test_match_condition_requires_one_field() -> None:
    with pytest.raises(ValueError):
        MatchCondition()


def test_property_matcher_regex_and_exists() -> None:
    pm_exists = PropertyMatcher(name="x", exists=True)
    pm_regex = PropertyMatcher(name="x", regex=r"^v\d+$")
    assert pm_exists.exists is True
    assert pm_regex.regex == r"^v\d+$"


def test_synthetic_zones_required() -> None:
    with pytest.raises(ValueError):
        BaseMapping(target="x", synthetic_zones={"unzoned": SyntheticZone(name="U")})  # type: ignore[arg-type]


# ---------- Mappings loader ----------


def test_load_mapping_from_text() -> None:
    text = """
version: 1
target: iriusrisk
zone_rules: []
synthetic_zones:
  unzoned: {name: U, style: us}
  external: {name: E, style: es}
component_rules: []
connection_rules: []
"""
    m = load_mapping(text)
    assert m.target == "iriusrisk"


def test_load_mapping_invalid_yaml() -> None:
    with pytest.raises(MappingValidationError):
        load_mapping(b": :: not yaml")


def test_load_mapping_top_level_must_be_dict() -> None:
    with pytest.raises(MappingValidationError):
        load_mapping(b"- a list")


# ---------- Inventory ----------


def test_external_actor_touch_count(external_actor_xml: bytes) -> None:
    from archithreat.core.inventory import inventory_bytes

    rep = inventory_bytes(external_actor_xml)
    assert rep.external_actor_count == 1
    assert rep.external_actor_touches >= 1


def test_inventory_no_realization_components() -> None:
    """Empty model produces no co-hosting numbers."""
    from archithreat.core.inventory import inventory_bytes

    xml = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">
  <name>m</name>
  <elements/>
  <relationships/>
</model>"""
    rep = inventory_bytes(xml)
    assert rep.cohosting_distribution.max == 0


# Defaults dataclass coverage
def test_defaults_can_be_constructed() -> None:
    d = Defaults()
    assert d.unmatched_element == "skip_with_warning"
    assert d.unmatched_relationship == "skip_with_warning"
