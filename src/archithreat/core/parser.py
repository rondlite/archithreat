"""Parse ArchiMate 3.x Open Exchange XML into an OpenExchangeModel.

XXE-hardened: no entity resolution, no network, capped tree depth.
Reference: https://www.opengroup.org/xsd/archimate/3.0/archimate3_Diagram.xsd
"""

from __future__ import annotations

import logging
import os
from typing import Final

from lxml import etree

from .model import (
    ArchiMateLayer,
    Element,
    OpenExchangeModel,
    Relationship,
    View,
    ViewConnection,
    ViewNode,
)

logger = logging.getLogger(__name__)

ARCHIMATE_NS: Final = "http://www.opengroup.org/xsd/archimate/3.0/"
XSI_NS: Final = "http://www.w3.org/2001/XMLSchema-instance"
XML_NS: Final = "http://www.w3.org/XML/1998/namespace"

NS: Final = {"a": ARCHIMATE_NS, "xsi": XSI_NS}

# Map of ArchiMate concrete types to layer.
LAYER_BY_TYPE: Final[dict[str, ArchiMateLayer]] = {
    # Strategy
    "Resource": "Strategy",
    "Capability": "Strategy",
    "ValueStream": "Strategy",
    "CourseOfAction": "Strategy",
    # Business
    "BusinessActor": "Business",
    "BusinessRole": "Business",
    "BusinessCollaboration": "Business",
    "BusinessInterface": "Business",
    "BusinessProcess": "Business",
    "BusinessFunction": "Business",
    "BusinessInteraction": "Business",
    "BusinessEvent": "Business",
    "BusinessService": "Business",
    "BusinessObject": "Business",
    "Contract": "Business",
    "Representation": "Business",
    "Product": "Business",
    # Application
    "ApplicationComponent": "Application",
    "ApplicationCollaboration": "Application",
    "ApplicationInterface": "Application",
    "ApplicationFunction": "Application",
    "ApplicationProcess": "Application",
    "ApplicationInteraction": "Application",
    "ApplicationEvent": "Application",
    "ApplicationService": "Application",
    "DataObject": "Application",
    # Technology
    "Node": "Technology",
    "Device": "Technology",
    "SystemSoftware": "Technology",
    "TechnologyCollaboration": "Technology",
    "TechnologyInterface": "Technology",
    "Path": "Technology",
    "CommunicationNetwork": "Technology",
    "TechnologyFunction": "Technology",
    "TechnologyProcess": "Technology",
    "TechnologyInteraction": "Technology",
    "TechnologyEvent": "Technology",
    "TechnologyService": "Technology",
    "Artifact": "Technology",
    # Physical
    "Equipment": "Physical",
    "Facility": "Physical",
    "DistributionNetwork": "Physical",
    "Material": "Physical",
    # Motivation
    "Stakeholder": "Motivation",
    "Driver": "Motivation",
    "Assessment": "Motivation",
    "Goal": "Motivation",
    "Outcome": "Motivation",
    "Principle": "Motivation",
    "Requirement": "Motivation",
    "Constraint": "Motivation",
    "Meaning": "Motivation",
    "Value": "Motivation",
    # Implementation & migration
    "WorkPackage": "Implementation",
    "Deliverable": "Implementation",
    "ImplementationEvent": "Implementation",
    "Plateau": "Implementation",
    "Gap": "Implementation",
    # Composite
    "Grouping": "Composite",
    "Location": "Composite",
    # Junction (treated specially by resolver)
    "Junction": "Other",
    "AndJunction": "Other",
    "OrJunction": "Other",
}


class ParserError(Exception):
    """Raised when input cannot be parsed into an OpenExchangeModel."""


def _q(local: str) -> str:
    return f"{{{ARCHIMATE_NS}}}{local}"


def _xsi_type(elem: etree._Element) -> str:
    raw = elem.get(f"{{{XSI_NS}}}type", "")
    if not raw:
        return "Unknown"
    # may be prefixed: e.g., "archimate:ApplicationComponent"
    if ":" in raw:
        return raw.split(":", 1)[1]
    return raw


def _text_of(elem: etree._Element | None) -> str | None:
    if elem is None:
        return None
    text = "".join(str(t) for t in elem.itertext()).strip()
    return text or None


def _label_text(elem: etree._Element, tag_local: str) -> str | None:
    # ArchiMate uses <name> and <documentation> child elements that may carry xml:lang.
    # First xml:lang="en" then any.
    candidates = elem.findall(_q(tag_local))
    if not candidates:
        return None
    for c in candidates:
        if c.get(f"{{{XML_NS}}}lang") == "en":
            t = _text_of(c)
            if t:
                return t
    return _text_of(candidates[0])


def _properties_of(elem: etree._Element, prop_def_index: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    properties_block = elem.find(_q("properties"))
    if properties_block is None:
        return out
    for p in properties_block.findall(_q("property")):
        ref = p.get("propertyDefinitionRef")
        key = prop_def_index.get(ref, ref) if ref else None
        if not key:
            continue
        value = _label_text(p, "value")
        if value is not None:
            out[key] = value
    return out


def _build_property_definition_index(root: etree._Element) -> dict[str, str]:
    index: dict[str, str] = {}
    block = root.find(_q("propertyDefinitions"))
    if block is None:
        return index
    for pd in block.findall(_q("propertyDefinition")):
        pd_id = pd.get("identifier")
        name = _label_text(pd, "name")
        if pd_id and name:
            index[pd_id] = name
    return index


def _parse_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_bytes(data: bytes) -> OpenExchangeModel:
    """Parse Open Exchange XML bytes into an OpenExchangeModel.

    Hardened against XXE: external entities disabled, no network, tree size capped.
    """
    if not data:
        raise ParserError("Empty input")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        huge_tree=False,
        remove_comments=True,
        remove_pis=True,
    )
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise ParserError(f"Malformed XML: {exc}") from exc

    if not root.tag.startswith(f"{{{ARCHIMATE_NS}}}"):
        raise ParserError(
            f"Root element not in ArchiMate 3.x namespace ({ARCHIMATE_NS}); "
            f"got {root.tag!r}. This tool requires Open Exchange 3.x."
        )

    prop_def_index = _build_property_definition_index(root)

    name = _label_text(root, "name") or "model"
    documentation = _label_text(root, "documentation")

    elements = _parse_elements(root, prop_def_index)
    relationships = _parse_relationships(root, prop_def_index)
    views = _parse_views(root)

    return OpenExchangeModel(
        name=name,
        documentation=documentation,
        elements=elements,
        relationships=relationships,
        views=views,
    )


def parse_path(path: str | os.PathLike[str]) -> OpenExchangeModel:
    """Convenience wrapper for parse_bytes that reads from disk (CLI use)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise ParserError(f"Cannot read {path!r}: {exc}") from exc
    return parse_bytes(data)


def _parse_elements(root: etree._Element, prop_def_index: dict[str, str]) -> dict[str, Element]:
    out: dict[str, Element] = {}
    block = root.find(_q("elements"))
    if block is None:
        return out
    for e in block.findall(_q("element")):
        eid = e.get("identifier")
        if not eid:
            logger.warning("Element missing identifier; skipping")
            continue
        atype = _xsi_type(e)
        if atype == "Unknown":
            logger.warning("Element %s missing xsi:type; recording as Unknown", eid)
        layer = LAYER_BY_TYPE.get(atype, "Other")
        out[eid] = Element(
            id=eid,
            name=_label_text(e, "name") or eid,
            archimate_type=atype,
            layer=layer,
            documentation=_label_text(e, "documentation"),
            properties=_properties_of(e, prop_def_index),
        )
    return out


def _parse_relationships(
    root: etree._Element, prop_def_index: dict[str, str]
) -> dict[str, Relationship]:
    out: dict[str, Relationship] = {}
    block = root.find(_q("relationships"))
    if block is None:
        return out
    for r in block.findall(_q("relationship")):
        rid = r.get("identifier")
        src = r.get("source")
        tgt = r.get("target")
        if not (rid and src and tgt):
            logger.warning("Relationship missing required attribute(s); skipping")
            continue
        atype = _xsi_type(r)
        access_type = r.get("accessType") if atype == "Access" else None
        out[rid] = Relationship(
            id=rid,
            archimate_type=atype,
            source_id=src,
            target_id=tgt,
            name=_label_text(r, "name"),
            documentation=_label_text(r, "documentation"),
            properties=_properties_of(r, prop_def_index),
            access_type=access_type,
        )
    return out


def _parse_views(root: etree._Element) -> list[View]:
    views: list[View] = []
    views_block = root.find(_q("views"))
    if views_block is None:
        return views
    diagrams = views_block.find(_q("diagrams"))
    if diagrams is None:
        return views
    for v in diagrams.findall(_q("view")):
        vid = v.get("identifier") or f"view_{len(views)}"
        nodes = _parse_view_nodes(v)
        connections = _parse_view_connections(v)
        views.append(
            View(
                id=vid,
                name=_label_text(v, "name") or vid,
                viewpoint=v.get("viewpoint"),
                nodes=nodes,
                connections=connections,
            )
        )
    return views


def _parse_view_nodes(parent: etree._Element, parent_node_id: str | None = None) -> list[ViewNode]:
    out: list[ViewNode] = []
    for n in parent.findall(_q("node")):
        nid = n.get("identifier") or ""
        out.append(
            ViewNode(
                id=nid,
                element_ref=n.get("elementRef"),
                x=_parse_int(n.get("x")),
                y=_parse_int(n.get("y")),
                width=_parse_int(n.get("w")),
                height=_parse_int(n.get("h")),
                parent_id=parent_node_id,
            )
        )
        # nested nodes
        out.extend(_parse_view_nodes(n, nid))
    return out


def _parse_view_connections(view: etree._Element) -> list[ViewConnection]:
    out: list[ViewConnection] = []
    for c in view.findall(_q("connection")):
        cid = c.get("identifier") or ""
        src = c.get("source") or ""
        tgt = c.get("target") or ""
        if not (src and tgt):
            continue
        out.append(
            ViewConnection(
                id=cid,
                relationship_ref=c.get("relationshipRef"),
                source_node_id=src,
                target_node_id=tgt,
            )
        )
    return out
