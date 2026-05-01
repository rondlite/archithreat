"""Inventory mode tests."""

from __future__ import annotations

import json

from archithreat.core.inventory import inventory_bytes


def test_lemonade_inventory(lemonade_xml: bytes) -> None:
    report = inventory_bytes(lemonade_xml)
    assert report.model_name == "Lemonade Shop"
    assert report.counts_by_type["ApplicationComponent"] == 5
    assert report.counts_by_type["Node"] == 4
    # Realization coverage
    assert report.realization_coverage["application_components_total"] == 5
    assert report.realization_coverage["with_node_realization"] == 5
    assert report.realization_coverage["orphans"] == 0
    # External actors
    assert report.external_actor_count >= 1
    # Co-hosting: app-server-1 has Order API + Inventory
    assert report.cohosting_distribution.max >= 2


def test_orphans_inventory(orphans_xml: bytes) -> None:
    report = inventory_bytes(orphans_xml)
    assert report.realization_coverage["orphans"] == 1
    assert any(w.code == "application_component_unrealized" for w in report.warnings)


def test_text_format(lemonade_xml: bytes) -> None:
    report = inventory_bytes(lemonade_xml)
    text = report.to_text()
    assert "archithreat inventory" in text
    assert "ApplicationComponent" in text


def test_json_format(lemonade_xml: bytes) -> None:
    report = inventory_bytes(lemonade_xml)
    parsed = json.loads(report.to_json())
    assert parsed["model_name"] == "Lemonade Shop"


def test_markdown_format(lemonade_xml: bytes) -> None:
    md = inventory_bytes(lemonade_xml).to_markdown()
    assert md.startswith("# Inventory")
