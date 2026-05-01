"""Resolver unit tests."""

from __future__ import annotations

from archithreat.core.mappings import load_default_mapping
from archithreat.core.parser import parse_bytes
from archithreat.core.resolver import (
    EXTERNAL_ID,
    UNZONED_ID,
    resolve,
    resolve_with_synthetic,
)


def test_minimal_resolves(minimal_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(minimal_xml), mapping)
    assert "g_dmz" in resolved.zones
    assert "n_web" in resolved.components
    assert "a_app" in resolved.components
    assert resolved.components["n_web"].is_host is True
    assert resolved.components["a_app"].host_node_id == "n_web"


def test_co_hosted(cohosted_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve(parse_bytes(cohosted_xml), mapping)
    apps = [c for c in resolved.components.values() if c.archimate_type == "ApplicationComponent"]
    assert {a.id for a in apps} == {"a_one", "a_two", "a_three"}
    assert all(a.host_node_id == "n_box" for a in apps)


def test_external_actor(external_actor_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(external_actor_xml), mapping)
    actor = resolved.components["ba_customer"]
    assert actor.is_external_actor is True
    assert actor.zone_id == EXTERNAL_ID
    assert EXTERNAL_ID in resolved.zones


def test_orphans(orphans_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(orphans_xml), mapping)
    assert UNZONED_ID in resolved.zones
    assert resolved.components["a_orphan"].zone_id == UNZONED_ID
    assert resolved.components["n_lonely"].zone_id == UNZONED_ID
    # Orphan app has no node realization → warning
    assert any(w.code == "application_component_unrealized" for w in resolved.warnings)


def test_lemonade_zone_assignment(lemonade_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(lemonade_xml), mapping)
    # storefront on web-server-1 in DMZ
    assert resolved.components["a_storefront"].host_node_id == "n_webserver"
    assert resolved.components["n_webserver"].zone_id == "z_dmz"
    # order api in internal
    assert resolved.components["a_orderapi"].host_node_id == "n_appserver"
    assert resolved.components["n_appserver"].zone_id == "z_internal"


def test_connection_crosses_zone_flag(lemonade_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(lemonade_xml), mapping)
    # storefront -> orderapi crosses DMZ to Internal
    cross = next(c for c in resolved.connections if c.id == "rf_storefront_order")
    assert cross.crosses_zone is True
    # orderapi -> inventory both in internal
    same = next(c for c in resolved.connections if c.id == "rf_order_inv")
    assert same.crosses_zone is False


def test_access_type_propagated(lemonade_xml: bytes) -> None:
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(parse_bytes(lemonade_xml), mapping)
    conn = next(c for c in resolved.connections if c.id == "ra_orders_db")
    assert conn.properties.get("access_type") == "write"
