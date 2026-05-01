"""Property-based tests with hypothesis."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from archithreat import convert_bytes
from archithreat.core.mappings import load_default_mapping
from archithreat.core.parser import parse_bytes
from archithreat.core.resolver import resolve_with_synthetic

# Small grammar that generates schema-valid Open Exchange documents.

ID_ALPHABET = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=8,
)


def _ids(prefix: str, n: int) -> list[str]:
    return [f"{prefix}_{i}" for i in range(n)]


@given(
    n_groups=st.integers(min_value=1, max_value=3),
    n_nodes=st.integers(min_value=1, max_value=5),
    n_apps=st.integers(min_value=0, max_value=8),
)
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_generated_models_round_trip(n_groups: int, n_nodes: int, n_apps: int) -> None:
    groups = _ids("g", n_groups)
    nodes = _ids("n", n_nodes)
    apps = _ids("a", n_apps)

    elements = []
    for gid in groups:
        elements.append(
            f'<element identifier="{gid}" xsi:type="Grouping"><name>{gid}</name></element>'
        )
    for nid in nodes:
        elements.append(f'<element identifier="{nid}" xsi:type="Node"><name>{nid}</name></element>')
    for aid in apps:
        elements.append(
            f'<element identifier="{aid}" xsi:type="ApplicationComponent"><name>{aid}</name></element>'
        )

    relationships = []
    rid = 0
    # Each node lives in first group
    for nid in nodes:
        rid += 1
        relationships.append(
            f'<relationship identifier="r{rid}" xsi:type="Composition" source="{groups[0]}" target="{nid}"/>'
        )
    # Each app realized to first node
    for aid in apps:
        rid += 1
        relationships.append(
            f'<relationship identifier="r{rid}" xsi:type="Realization" source="{aid}" target="{nodes[0]}"/>'
        )
    # First two apps connected
    if len(apps) >= 2:
        rid += 1
        relationships.append(
            f'<relationship identifier="r{rid}" xsi:type="Flow" source="{apps[0]}" target="{apps[1]}"/>'
        )

    xml = (
        '<?xml version="1.0"?><model '
        'xmlns="http://www.opengroup.org/xsd/archimate/3.0/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" identifier="m">'
        "<name>m</name>"
        "<elements>" + "".join(elements) + "</elements>"
        "<relationships>" + "".join(relationships) + "</relationships>"
        "</model>"
    ).encode()

    model = parse_bytes(xml)
    mapping = load_default_mapping()
    resolved = resolve_with_synthetic(model, mapping)

    # Invariant: every resolved component traces back to a source element.
    for c in resolved.components.values():
        assert c.id in model.elements

    # Invariant: every connection endpoint exists as a component.
    for conn in resolved.connections:
        assert conn.source_component_id in resolved.components
        assert conn.target_component_id in resolved.components

    # Conversion succeeds and produces non-empty output.
    out = convert_bytes(xml)
    assert out.startswith(b"<?xml")
