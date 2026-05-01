"""archithreat conversion core: pure-Python, Pyodide-compatible, target-independent.

Pipeline: parse -> resolve -> map -> emit. Each stage is independently testable.
"""

from __future__ import annotations

from .model import (
    Element,
    MappedComponent,
    MappedConnection,
    MappedModel,
    MappedZone,
    OpenExchangeModel,
    RealizationLink,
    Relationship,
    ResolvedComponent,
    ResolvedConnection,
    ResolvedModel,
    ResolverWarning,
    View,
    ViewConnection,
    ViewNode,
    Zone,
)

__all__ = [
    "Element",
    "MappedComponent",
    "MappedConnection",
    "MappedModel",
    "MappedZone",
    "OpenExchangeModel",
    "RealizationLink",
    "Relationship",
    "ResolvedComponent",
    "ResolvedConnection",
    "ResolvedModel",
    "ResolverWarning",
    "View",
    "ViewConnection",
    "ViewNode",
    "Zone",
]
