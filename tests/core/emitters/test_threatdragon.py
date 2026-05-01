"""Threat Dragon emitter tests: structural invariants + golden integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archithreat import convert_bytes
from archithreat.core.emitters import EmitterError, available_targets, get_emitter
from archithreat.core.emitters.threatdragon import (
    TARGET_ID,
    ThreatDragonEmitter,
    _validate,
)


def _emit(data: bytes) -> bytes:
    return convert_bytes(data, target=TARGET_ID)


def test_target_in_registry() -> None:
    assert TARGET_ID in available_targets()
    assert isinstance(get_emitter(TARGET_ID), ThreatDragonEmitter)


def test_emitter_metadata() -> None:
    e = ThreatDragonEmitter()
    assert e.target_id == "threatdragon"
    assert e.output_extension == "json"
    assert e.output_media_type == "application/json"


def test_minimal_output_well_formed(minimal_xml: bytes) -> None:
    out = _emit(minimal_xml)
    doc = json.loads(out)
    assert doc["version"] == "2.0.0"
    assert "summary" in doc
    assert "detail" in doc
    assert isinstance(doc["detail"]["diagrams"], list)
    assert len(doc["detail"]["diagrams"]) == 1
    diagram = doc["detail"]["diagrams"][0]
    assert diagram["diagramType"] == "STRIDE"
    assert isinstance(diagram["cells"], list)


def test_pet_shop_shapes(pet_shop_xml: bytes) -> None:
    out = _emit(pet_shop_xml)
    doc = json.loads(out)
    cells = doc["detail"]["diagrams"][0]["cells"]
    by_shape: dict[str, list[dict]] = {}
    for c in cells:
        by_shape.setdefault(c["shape"], []).append(c)
    # 2 trust boundary boxes, 3 processes, 2 stores, 1 actor + flows
    assert len(by_shape["trust-boundary-box"]) == 2
    assert len(by_shape["process"]) == 3
    assert len(by_shape["store"]) == 2
    assert len(by_shape["actor"]) == 1
    assert len(by_shape["flow"]) >= 5


def test_storefront_marked_web_application(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    storefront = next(
        c for c in cells if c["shape"] == "process" and c["data"]["name"] == "Storefront"
    )
    assert storefront["data"]["isWebApplication"] is True


def test_credentials_marked_credentials_store(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    creds = next(
        c for c in cells if c["shape"] == "store" and c["data"]["name"] == "User Credentials"
    )
    assert creds["data"]["storesCredentials"] is True
    assert creds["data"]["isEncrypted"] is True


def test_audit_log_marked_log(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    audit = next(
        c for c in cells if c["shape"] == "store" and c["data"]["name"] == "Audit Log"
    )
    assert audit["data"]["isALog"] is True


def test_https_flow_marked_encrypted(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    flows = [c for c in cells if c["shape"] == "flow"]
    https_flows = [f for f in flows if f["data"]["protocol"] == "HTTPS"]
    assert https_flows
    assert all(f["data"]["isEncrypted"] for f in https_flows)


def test_actor_default(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    actor = next(
        c for c in cells if c["shape"] == "actor" and c["data"]["name"] == "Customer"
    )
    assert actor["data"]["type"] == "tm.Actor"
    assert actor["data"]["providesAuthentication"] is False


def test_flows_resolve_endpoints(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    cell_ids = {c["id"] for c in cells}
    for f in (c for c in cells if c["shape"] == "flow"):
        assert f["source"]["cell"] in cell_ids
        assert f["target"]["cell"] in cell_ids


def test_trust_boundary_has_correct_type(pet_shop_xml: bytes) -> None:
    doc = json.loads(_emit(pet_shop_xml))
    cells = doc["detail"]["diagrams"][0]["cells"]
    boundaries = [c for c in cells if c["shape"] == "trust-boundary-box"]
    for b in boundaries:
        assert b["data"]["type"] == "tm.BoundaryBox"
        assert b["data"]["isTrustBoundary"] is True
        assert b["zIndex"] == -50


def test_emitter_internal_validation_catches_orphan_flow() -> None:
    bad = json.dumps(
        {
            "version": "2.0.0",
            "summary": {"title": "x", "owner": "", "description": "", "id": 0},
            "detail": {
                "contributors": [],
                "diagramTop": 0,
                "reviewer": "",
                "threatTop": 0,
                "diagrams": [
                    {
                        "id": "d",
                        "title": "x",
                        "diagramType": "STRIDE",
                        "version": "2.0.0",
                        "thumbnail": "",
                        "cells": [
                            {
                                "id": "f1",
                                "shape": "flow",
                                "source": {"cell": "ghost"},
                                "target": {"cell": "ghost2"},
                            }
                        ],
                    }
                ],
            },
        }
    ).encode()
    with pytest.raises(EmitterError):
        _validate(bad, raise_cls=EmitterError)


def test_pet_shop_golden(
    pet_shop_xml: bytes, golden_dir_td: Path, update_goldens: bool
) -> None:
    out = _emit(pet_shop_xml)
    golden = golden_dir_td / "pet_shop.json"
    if update_goldens or not golden.exists():
        golden.write_bytes(out)
    assert _normalize(out) == _normalize(golden.read_bytes())


@pytest.mark.parametrize("name", ["minimal", "co_hosted", "external_actor", "orphans", "lemonade_shop"])
def test_fixture_goldens(
    name: str, fixtures_dir: Path, golden_dir_td: Path, update_goldens: bool
) -> None:
    src = (fixtures_dir / f"{name}.xml").read_bytes()
    out = _emit(src)
    golden = golden_dir_td / f"{name}.json"
    if update_goldens or not golden.exists():
        golden.write_bytes(out)
    assert _normalize(out) == _normalize(golden.read_bytes())


def _normalize(data: bytes) -> str:
    """Canonical JSON for stable comparison (sorted keys, no extra whitespace)."""
    return json.dumps(json.loads(data), sort_keys=True, separators=(",", ":"))


def test_default_target_still_drawio() -> None:
    """End-to-end without target= argument keeps drawio-iriusrisk as default."""
    from archithreat.core.mappings import DEFAULT_TARGET

    assert DEFAULT_TARGET == "drawio-iriusrisk"
