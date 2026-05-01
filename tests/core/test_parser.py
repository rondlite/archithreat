"""Parser unit tests."""

from __future__ import annotations

import pytest

from archithreat.core.parser import ParserError, parse_bytes


def test_parses_minimal(minimal_xml: bytes) -> None:
    model = parse_bytes(minimal_xml)
    assert model.name == "minimal"
    assert "g_dmz" in model.elements
    assert "n_web" in model.elements
    assert "a_app" in model.elements
    assert model.elements["g_dmz"].layer == "Composite"
    assert model.elements["n_web"].layer == "Technology"
    assert model.elements["a_app"].layer == "Application"
    assert "r_compose" in model.relationships
    assert "r_realize" in model.relationships
    assert model.relationships["r_compose"].archimate_type == "Composition"


def test_rejects_empty_input() -> None:
    with pytest.raises(ParserError, match="Empty"):
        parse_bytes(b"")


def test_rejects_malformed_xml() -> None:
    with pytest.raises(ParserError, match="Malformed"):
        parse_bytes(b"<not-xml")


def test_rejects_wrong_namespace() -> None:
    bad = b'<?xml version="1.0"?><model xmlns="http://example.com/other"/>'
    with pytest.raises(ParserError, match="namespace"):
        parse_bytes(bad)


def test_xxe_disabled() -> None:
    """External entity references must not be resolved."""
    xxe = b"""<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/" identifier="x">
  <name>&xxe;</name>
</model>"""
    # Either entity is rejected (XMLSyntaxError -> ParserError) or model parses
    # with the entity stripped. Either way, /etc/passwd contents must not appear.
    try:
        model = parse_bytes(xxe)
        assert "root:" not in (model.name or "")
    except ParserError:
        pass


def test_property_definitions_resolve(lemonade_xml: bytes) -> None:
    model = parse_bytes(lemonade_xml)
    storefront = model.elements["a_storefront"]
    assert storefront.properties.get("tech_stack") == "web"
    dmz = model.elements["z_dmz"]
    assert dmz.properties.get("zone_type") == "logical"


def test_access_type_captured(lemonade_xml: bytes) -> None:
    model = parse_bytes(lemonade_xml)
    rel = model.relationships["ra_orders_db"]
    assert rel.archimate_type == "Access"
    assert rel.access_type == "write"


def test_relationship_properties_captured(lemonade_xml: bytes) -> None:
    model = parse_bytes(lemonade_xml)
    rel = model.relationships["rf_storefront_order"]
    assert rel.properties.get("protocol") == "HTTPS"


def test_accepts_bytearray(minimal_xml: bytes) -> None:
    """Pyodide passes Uint8Array which Python sees as a buffer-protocol object."""
    model = parse_bytes(bytearray(minimal_xml))
    assert "g_dmz" in model.elements


def test_accepts_memoryview(minimal_xml: bytes) -> None:
    model = parse_bytes(memoryview(minimal_xml))
    assert "g_dmz" in model.elements


def test_rejects_non_buffer_input() -> None:
    with pytest.raises(ParserError, match="bytes-like"):
        parse_bytes(["not", "bytes"])  # type: ignore[arg-type]


def test_unknown_xsi_type_recorded() -> None:
    weird = b"""<?xml version="1.0"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       identifier="m">
  <name>m</name>
  <elements>
    <element identifier="e1" xsi:type="UnobtainiumElement">
      <name>weird</name>
    </element>
  </elements>
</model>"""
    model = parse_bytes(weird)
    assert model.elements["e1"].archimate_type == "UnobtainiumElement"
    assert model.elements["e1"].layer == "Other"
