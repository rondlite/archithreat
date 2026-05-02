"""draw.io emitter tests: structural invariants + golden integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from archithreat import convert_bytes
from archithreat.core.emitters import (
    EMITTERS,
    EmitterError,
    available_targets,
    get_emitter,
    register,
    unregister,
)
from archithreat.core.emitters.iriusrisk import (
    TARGET_ID,
    DrawioIriusriskEmitter,
)
from archithreat.core.model import MappedModel


def _convert(data: bytes) -> bytes:
    return convert_bytes(data)


def test_drawio_in_registry() -> None:
    assert TARGET_ID in available_targets()


def test_emitter_register_unregister_roundtrip() -> None:
    """SPEC §11 AC#7: stub emitter registers, runs, and is removable."""

    class StubEmitter:
        target_id = "stub-test-only"
        output_extension = "stub"
        output_media_type = "application/octet-stream"

        def emit(self, model: MappedModel) -> bytes:
            return b"STUB"

    stub = StubEmitter()
    try:
        register(stub)
        assert "stub-test-only" in EMITTERS
        assert get_emitter("stub-test-only") is stub
        assert get_emitter("stub-test-only").emit(MappedModel({}, {}, [])) == b"STUB"
    finally:
        unregister("stub-test-only")
    assert "stub-test-only" not in EMITTERS


def test_minimal_output_is_well_formed(minimal_xml: bytes) -> None:
    out = _convert(minimal_xml)
    root = etree.fromstring(out)
    assert root.tag == "mxfile"


def test_required_root_cells_present(minimal_xml: bytes) -> None:
    out = _convert(minimal_xml)
    root = etree.fromstring(out)
    cells = root.iter("mxCell")
    ids = {c.get("id") for c in cells}
    assert "0" in ids
    assert "1" in ids


def test_host_contains_app_components(cohosted_xml: bytes) -> None:
    out = _convert(cohosted_xml)
    root = etree.fromstring(out)
    parents: dict[str, str] = {}
    for c in root.iter("mxCell"):
        cid = c.get("id")
        parent = c.get("parent")
        if cid and parent:
            parents[cid] = parent
    # Each app should have n_box as parent
    for app_id in ("a_one", "a_two", "a_three"):
        assert parents[app_id] == "n_box", f"{app_id} parent={parents[app_id]}"


def test_zones_contain_hosts(cohosted_xml: bytes) -> None:
    out = _convert(cohosted_xml)
    root = etree.fromstring(out)
    parents = {c.get("id"): c.get("parent") for c in root.iter("mxCell")}
    assert parents["n_box"] == "g_internal"


def test_edges_endpoints_resolve(cohosted_xml: bytes) -> None:
    out = _convert(cohosted_xml)
    root = etree.fromstring(out)
    cell_ids = {c.get("id") for c in root.iter("mxCell") if c.get("id")}
    cell_ids |= {c.get("id") for c in root.iter("UserObject") if c.get("id")}
    for c in root.iter("mxCell"):
        if c.get("edge") == "1":
            assert c.get("source") in cell_ids
            assert c.get("target") in cell_ids


def test_emitter_internal_validation_catches_bad_parent() -> None:
    """Force a malformed cell list and verify validator raises EmitterError."""
    from archithreat.core.emitters.iriusrisk import _Cell, _serialize, _validate_output

    bad = [
        _Cell(cid="x", parent="nonexistent_parent", style="", label="x"),
    ]
    xml = _serialize(bad, "diag")
    with pytest.raises(EmitterError):
        _validate_output(xml, raise_cls=EmitterError)


def test_lemonade_golden(lemonade_xml: bytes, golden_dir: Path, update_goldens: bool) -> None:
    out = _convert(lemonade_xml)
    golden = golden_dir / "lemonade_shop.drawio"
    if update_goldens or not golden.exists():
        golden.write_bytes(out)
    expected = golden.read_bytes()
    # Compare structural tree, not bytes (spacing, attribute order may differ)
    assert _normalize(out) == _normalize(expected)


@pytest.mark.parametrize("name", ["minimal", "co_hosted", "external_actor", "orphans"])
def test_fixture_goldens(
    name: str, fixtures_dir: Path, golden_dir: Path, update_goldens: bool
) -> None:
    src = (fixtures_dir / f"{name}.xml").read_bytes()
    out = _convert(src)
    golden = golden_dir / f"{name}.drawio"
    if update_goldens or not golden.exists():
        golden.write_bytes(out)
    assert _normalize(out) == _normalize(golden.read_bytes())


def _normalize(xml_bytes: bytes) -> str:
    """Canonicalize XML for stable comparison."""
    root = etree.fromstring(xml_bytes)
    return etree.tostring(root, method="c14n").decode()


def test_passthrough_properties_emitted_as_userobject(lemonade_xml: bytes) -> None:
    out = _convert(lemonade_xml)
    root = etree.fromstring(out)
    user_objects = root.iter("UserObject")
    found_tech_stack = False
    for uo in user_objects:
        if uo.get("tech_stack") == "web":
            found_tech_stack = True
            break
    assert found_tech_stack, "Expected at least one UserObject with tech_stack=web"


def test_isinstance_emitter_protocol() -> None:
    from archithreat.core.emitters import Emitter

    assert isinstance(DrawioIriusriskEmitter(), Emitter)
