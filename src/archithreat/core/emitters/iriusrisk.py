"""draw.io / mxGraph emitter for IriusRisk.

Produces a single-page mxGraph XML document compatible with draw.io desktop,
draw.io web, and IriusRisk's embedded editor. Layout is deterministic auto-
layout; modelers will hand-adjust in IriusRisk. Internal validation: parse the
output back and assert structural invariants.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from lxml import etree

from ..model import MappedComponent, MappedConnection, MappedModel, MappedZone

TARGET_ID = "iriusrisk"

ID_OK = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

# Layout constants (px)
ZONE_PADDING = 40
ZONE_HEADER = 30
COMPONENT_W = 160
COMPONENT_H = 60
COMPONENT_PAD = 20
HOST_HEADER = 30
HOST_W_MIN = 200
HOST_H_MIN = 120
ZONE_GAP = 60
ZONE_TOP = 40
ZONE_LEFT = 40


@dataclass
class _Cell:
    """Internal accumulator before serializing to XML."""

    cid: str
    parent: str
    style: str
    label: str
    x: int = 0
    y: int = 0
    w: int = COMPONENT_W
    h: int = COMPONENT_H
    is_edge: bool = False
    source: str | None = None
    target: str | None = None
    user_attrs: dict[str, str] | None = None


class DrawioIriusriskEmitter:
    target_id: str = TARGET_ID
    output_extension: str = "drawio"
    output_media_type: str = "application/xml"

    def emit(self, model: MappedModel) -> bytes:
        from . import EmitterError

        cells: list[_Cell] = []
        id_map: dict[str, str] = {}  # original_id -> drawio_cell_id

        def cid_for(original: str) -> str:
            if original in id_map:
                return id_map[original]
            cid = original if ID_OK.match(original) else _stable_hash(original)
            # ensure no collision
            base = cid
            n = 0
            while cid in id_map.values():
                n += 1
                cid = f"{base}_{n}"
            id_map[original] = cid
            return cid

        # Layout: place zones left to right.
        zones = sorted(model.zones.values(), key=lambda z: z.zone.name.lower())
        zone_layouts = _layout_zones(zones, model)

        # Emit cells in dependency order: zones, then hosts inside zones, then
        # non-host components, then edges.

        for zlayout in zone_layouts:
            mz = zlayout.mapped_zone
            zid = cid_for(mz.zone.id)
            cells.append(
                _Cell(
                    cid=zid,
                    parent="1",
                    style=_style_from(mz.target_data),
                    label=mz.zone.name,
                    x=zlayout.x,
                    y=zlayout.y,
                    w=zlayout.w,
                    h=zlayout.h,
                )
            )
            for host_layout in zlayout.hosts:
                mc = host_layout.mapped_component
                hid = cid_for(mc.component.id)
                cells.append(
                    _Cell(
                        cid=hid,
                        parent=zid,
                        style=_style_from(mc.target_data),
                        label=_label_for(mc),
                        x=host_layout.x,
                        y=host_layout.y,
                        w=host_layout.w,
                        h=host_layout.h,
                        user_attrs=_user_attrs_for(mc),
                    )
                )
                for child_layout in host_layout.children:
                    mcc = child_layout.mapped_component
                    ccid = cid_for(mcc.component.id)
                    cells.append(
                        _Cell(
                            cid=ccid,
                            parent=hid,
                            style=_style_from(mcc.target_data),
                            label=_label_for(mcc),
                            x=child_layout.x,
                            y=child_layout.y,
                            w=child_layout.w,
                            h=child_layout.h,
                            user_attrs=_user_attrs_for(mcc),
                        )
                    )
            for free_layout in zlayout.free_components:
                mcc = free_layout.mapped_component
                ccid = cid_for(mcc.component.id)
                cells.append(
                    _Cell(
                        cid=ccid,
                        parent=zid,
                        style=_style_from(mcc.target_data),
                        label=_label_for(mcc),
                        x=free_layout.x,
                        y=free_layout.y,
                        w=free_layout.w,
                        h=free_layout.h,
                        user_attrs=_user_attrs_for(mcc),
                    )
                )

        # Edges. Parent="1" so edges live at the top level.
        for mconn in model.connections:
            conn = mconn.connection
            src_cid = id_map.get(conn.source_component_id)
            tgt_cid = id_map.get(conn.target_component_id)
            if src_cid is None or tgt_cid is None:
                # endpoint dropped earlier — skip
                continue
            eid = cid_for(conn.id)
            cells.append(
                _Cell(
                    cid=eid,
                    parent="1",
                    style=_style_from(mconn.target_data),
                    label=_edge_label(mconn),
                    is_edge=True,
                    source=src_cid,
                    target=tgt_cid,
                    user_attrs=_user_attrs_for_conn(mconn),
                )
            )

        xml_bytes = _serialize(cells, model.source_name or "archithreat")

        # Internal validation
        _validate_output(xml_bytes, raise_cls=EmitterError)
        return xml_bytes


# ---------- Layout ----------


@dataclass
class _ChildLayout:
    mapped_component: MappedComponent
    x: int
    y: int
    w: int
    h: int


@dataclass
class _HostLayout:
    mapped_component: MappedComponent
    x: int
    y: int
    w: int
    h: int
    children: list[_ChildLayout]


@dataclass
class _ZoneLayout:
    mapped_zone: MappedZone
    x: int
    y: int
    w: int
    h: int
    hosts: list[_HostLayout]
    free_components: list[_ChildLayout]


def _layout_zones(zones: list[MappedZone], model: MappedModel) -> list[_ZoneLayout]:
    """Deterministic auto-layout per SPEC §5.1.6."""
    by_zone_hosts: dict[str, list[MappedComponent]] = {}
    by_zone_app_in_host: dict[tuple[str, str], list[MappedComponent]] = {}
    by_zone_free: dict[str, list[MappedComponent]] = {}

    for mc in model.components.values():
        comp = mc.component
        z = comp.zone_id
        if comp.is_host:
            by_zone_hosts.setdefault(z, []).append(mc)
        elif comp.host_node_id is not None and comp.host_node_id in model.components:
            host_zone = model.components[comp.host_node_id].component.zone_id
            by_zone_app_in_host.setdefault((host_zone, comp.host_node_id), []).append(mc)
        else:
            by_zone_free.setdefault(z, []).append(mc)

    # Sort everything deterministically.
    for k_str in by_zone_hosts:
        by_zone_hosts[k_str].sort(key=lambda m: (m.component.name.lower(), m.component.id))
    for k_str in by_zone_free:
        by_zone_free[k_str].sort(key=lambda m: (m.component.name.lower(), m.component.id))
    for k_tuple in by_zone_app_in_host:
        by_zone_app_in_host[k_tuple].sort(key=lambda m: (m.component.name.lower(), m.component.id))

    layouts: list[_ZoneLayout] = []
    cursor_x = ZONE_LEFT
    for mz in zones:
        zone_id = mz.zone.id
        host_layouts: list[_HostLayout] = []
        host_y = ZONE_HEADER + ZONE_PADDING
        max_inner_w = HOST_W_MIN
        for host_mc in by_zone_hosts.get(zone_id, []):
            kids = by_zone_app_in_host.get((zone_id, host_mc.component.id), [])
            kids_per_row = max(1, min(3, len(kids)))
            rows = (len(kids) + kids_per_row - 1) // kids_per_row
            host_inner_w = max(
                HOST_W_MIN,
                kids_per_row * COMPONENT_W + (kids_per_row + 1) * COMPONENT_PAD,
            )
            host_inner_h = max(
                HOST_H_MIN,
                HOST_HEADER + rows * COMPONENT_H + (rows + 1) * COMPONENT_PAD,
            )
            child_layouts: list[_ChildLayout] = []
            for i, kid in enumerate(kids):
                row = i // kids_per_row
                col = i % kids_per_row
                child_x = COMPONENT_PAD + col * (COMPONENT_W + COMPONENT_PAD)
                child_y = HOST_HEADER + COMPONENT_PAD + row * (COMPONENT_H + COMPONENT_PAD)
                child_layouts.append(
                    _ChildLayout(
                        mapped_component=kid,
                        x=child_x,
                        y=child_y,
                        w=COMPONENT_W,
                        h=COMPONENT_H,
                    )
                )
            host_layouts.append(
                _HostLayout(
                    mapped_component=host_mc,
                    x=ZONE_PADDING,
                    y=host_y,
                    w=host_inner_w,
                    h=host_inner_h,
                    children=child_layouts,
                )
            )
            host_y += host_inner_h + COMPONENT_PAD
            max_inner_w = max(max_inner_w, host_inner_w)

        free = by_zone_free.get(zone_id, [])
        free_layouts: list[_ChildLayout] = []
        free_per_row = max(1, min(3, len(free))) if free else 1
        for i, fc in enumerate(free):
            row = i // free_per_row
            col = i % free_per_row
            fx = ZONE_PADDING + col * (COMPONENT_W + COMPONENT_PAD)
            fy = host_y + row * (COMPONENT_H + COMPONENT_PAD)
            free_layouts.append(
                _ChildLayout(
                    mapped_component=fc,
                    x=fx,
                    y=fy,
                    w=COMPONENT_W,
                    h=COMPONENT_H,
                )
            )
            max_inner_w = max(
                max_inner_w,
                free_per_row * COMPONENT_W + (free_per_row + 1) * COMPONENT_PAD,
            )

        free_rows = (len(free) + free_per_row - 1) // free_per_row if free else 0
        free_h = free_rows * (COMPONENT_H + COMPONENT_PAD)
        zone_w = max_inner_w + 2 * ZONE_PADDING
        zone_h = max(host_y + free_h + ZONE_PADDING, HOST_H_MIN + 2 * ZONE_PADDING)

        layouts.append(
            _ZoneLayout(
                mapped_zone=mz,
                x=cursor_x,
                y=ZONE_TOP,
                w=zone_w,
                h=zone_h,
                hosts=host_layouts,
                free_components=free_layouts,
            )
        )
        cursor_x += zone_w + ZONE_GAP
    return layouts


# ---------- Serialization ----------


def _serialize(cells: list[_Cell], diagram_name: str) -> bytes:
    mxfile = etree.Element("mxfile", host="archithreat", version="1.0")
    diagram = etree.SubElement(mxfile, "diagram", id=_stable_hash(diagram_name), name=diagram_name)
    graph = etree.SubElement(
        diagram,
        "mxGraphModel",
        dx="1422",
        dy="757",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth="850",
        pageHeight="1100",
        math="0",
        shadow="0",
    )
    root = etree.SubElement(graph, "root")
    etree.SubElement(root, "mxCell", id="0")
    etree.SubElement(root, "mxCell", id="1", parent="0")

    for c in cells:
        if c.user_attrs:
            user = etree.SubElement(root, "UserObject", id=c.cid, label=c.label)
            for k, v in c.user_attrs.items():
                user.set(k, v)
            mx = etree.SubElement(
                user,
                "mxCell",
                style=c.style,
                parent=c.parent,
            )
        else:
            mx = etree.SubElement(
                root,
                "mxCell",
                id=c.cid,
                value=c.label,
                style=c.style,
                parent=c.parent,
            )
        if c.is_edge:
            mx.set("edge", "1")
            if c.source is not None:
                mx.set("source", c.source)
            if c.target is not None:
                mx.set("target", c.target)
            etree.SubElement(mx, "mxGeometry", relative="1").set("as", "geometry")
        else:
            mx.set("vertex", "1")
            geom = etree.SubElement(
                mx,
                "mxGeometry",
                x=str(c.x),
                y=str(c.y),
                width=str(c.w),
                height=str(c.h),
            )
            geom.set("as", "geometry")

    return etree.tostring(mxfile, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ---------- Helpers ----------


def _style_from(target_data: dict[str, object]) -> str:
    spec = target_data.get("iriusrisk")
    if isinstance(spec, dict):
        style = spec.get("style", "")
        if isinstance(style, str):
            return style
    return ""


def _label_for(mc: MappedComponent) -> str:
    return mc.component.name


def _edge_label(mconn: MappedConnection) -> str:
    pt = mconn.target_data.get("passthrough_properties")
    if isinstance(pt, dict):
        protocol = pt.get("protocol")
        if isinstance(protocol, str):
            return protocol
    return ""


def _user_attrs_for(mc: MappedComponent) -> dict[str, str] | None:
    pt = mc.target_data.get("passthrough_properties")
    if not isinstance(pt, dict) or not pt:
        return None
    return {k: str(v) for k, v in pt.items()}


def _user_attrs_for_conn(mconn: MappedConnection) -> dict[str, str] | None:
    pt = mconn.target_data.get("passthrough_properties")
    if not isinstance(pt, dict) or not pt:
        return None
    return {k: str(v) for k, v in pt.items()}


def _stable_hash(value: str) -> str:
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"id_{h}"


def _validate_output(xml_bytes: bytes, raise_cls: type[Exception]) -> None:
    """Re-parse output and assert structural invariants."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise raise_cls(f"Emitter produced malformed XML: {exc}") from exc

    # Collect all cell ids (mxCell/@id and UserObject/@id).
    cell_ids: set[str] = set()
    for el in root.iter("mxCell"):
        cid = el.get("id")
        if cid:
            cell_ids.add(cid)
    for el in root.iter("UserObject"):
        cid = el.get("id")
        if cid:
            cell_ids.add(cid)

    # Validate parent/source/target references.
    parents: dict[str, str] = {}
    for el in root.iter("mxCell"):
        cid = el.get("id")
        parent = el.get("parent")
        source = el.get("source")
        target = el.get("target")
        if cid:
            if parent and parent not in cell_ids:
                raise raise_cls(f"mxCell {cid!r} has unknown parent {parent!r}")
            if parent:
                parents[cid] = parent
        if source and source not in cell_ids:
            raise raise_cls(f"Edge {cid!r} has unknown source {source!r}")
        if target and target not in cell_ids:
            raise raise_cls(f"Edge {cid!r} has unknown target {target!r}")

    # No cell is its own ancestor.
    for cid in parents:
        seen: set[str] = set()
        cur: str | None = cid
        while cur is not None:
            if cur in seen:
                raise raise_cls(f"Cycle detected in parent chain at {cid!r}")
            seen.add(cur)
            cur = parents.get(cur)
            if cur == cid:
                raise raise_cls(f"Cell {cid!r} is its own ancestor")


__all__ = ["TARGET_ID", "DrawioIriusriskEmitter"]
