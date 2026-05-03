"""archithreat: ArchiMate to threat-model converter."""

from __future__ import annotations

__version__ = "3.2.0"

from .core.emitters import EMITTERS, available_targets, get_emitter
from .core.inventory import InventoryReport, inventory_bytes, inventory_path
from .core.mapper import apply_mapping
from .core.mappings import (
    DEFAULT_TARGET,
    MappingValidationError,
    load_default_mapping,
    load_mapping,
    validate_mapping,
)
from .core.parser import ParserError, parse_bytes, parse_path
from .core.resolver import resolve_with_synthetic

__all__ = [
    "DEFAULT_TARGET",
    "EMITTERS",
    "InventoryReport",
    "MappingValidationError",
    "ParserError",
    "__version__",
    "apply_mapping",
    "available_targets",
    "convert_bytes",
    "get_emitter",
    "inventory_bytes",
    "inventory_path",
    "load_default_mapping",
    "load_mapping",
    "parse_bytes",
    "parse_path",
    "resolve_with_synthetic",
    "validate_mapping",
]


def convert_bytes(
    data: bytes,
    mapping_source: str | bytes | None = None,
    target: str = DEFAULT_TARGET,
    source_name: str = "",
) -> bytes:
    """End-to-end conversion: bytes in, bytes out. Used by all three shells."""
    mapping = (
        load_mapping(mapping_source, target=target)
        if mapping_source is not None
        else load_default_mapping(target)
    )
    model = parse_bytes(data)
    resolved = resolve_with_synthetic(model, mapping)
    mapped = apply_mapping(resolved, mapping, source_name=source_name or model.name)
    emitter = get_emitter(target)
    return emitter.emit(mapped)
