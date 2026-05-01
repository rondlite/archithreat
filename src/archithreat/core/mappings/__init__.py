"""Mapping table loading and validation.

The ``target`` argument exists from v1 even though only ``drawio-iriusrisk`` is
valid; v2 hooks additional targets in here without changing call sites.
"""

from __future__ import annotations

import os
from importlib import resources
from typing import Any, cast

import yaml
from pydantic import ValidationError as PydanticValidationError

from .base import BaseMapping
from .drawio_iriusrisk import TARGET_ID as DRAWIO_IRIUSRISK_TARGET
from .drawio_iriusrisk import DrawioMapping

DEFAULT_TARGET = DRAWIO_IRIUSRISK_TARGET

# Registry of target_id -> mapping schema class.
MAPPING_SCHEMAS: dict[str, type[BaseMapping]] = {
    DRAWIO_IRIUSRISK_TARGET: DrawioMapping,
}


class UnknownTargetError(ValueError):
    """Raised when a target_id has no registered mapping schema."""


class MappingValidationError(Exception):
    """Raised when a mapping document fails schema validation."""

    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        super().__init__(f"Mapping validation failed: {len(errors)} error(s)")


def _read(source: str | bytes | os.PathLike[str]) -> str:
    if isinstance(source, bytes):
        return source.decode("utf-8")
    if isinstance(source, str) and (
        "\n" in source or source.lstrip().startswith(("version", "target"))
    ):
        # treat as raw YAML body (heuristic)
        if not os.path.exists(source):
            return source
    if isinstance(source, str | os.PathLike):
        with open(source, encoding="utf-8") as f:
            return f.read()
    raise TypeError(f"Unsupported mapping source type: {type(source)!r}")


def _load_yaml(source: str | bytes | os.PathLike[str]) -> dict[str, Any]:
    text = _read(source)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MappingValidationError(
            [{"loc": (), "msg": f"YAML parse error: {exc}", "type": "yaml_error"}]
        ) from exc
    if not isinstance(data, dict):
        raise MappingValidationError(
            [
                {
                    "loc": (),
                    "msg": "Mapping document must be a YAML mapping (dict)",
                    "type": "type_error",
                }
            ]
        )
    return data


def _schema_for(target: str) -> type[BaseMapping]:
    if target not in MAPPING_SCHEMAS:
        raise UnknownTargetError(f"Unknown target {target!r}; known: {sorted(MAPPING_SCHEMAS)}")
    return MAPPING_SCHEMAS[target]


def load_mapping(
    source: str | bytes | os.PathLike[str], target: str = DEFAULT_TARGET
) -> BaseMapping:
    """Load and validate a mapping from YAML source.

    ``source`` may be a path, raw YAML text, or YAML bytes.
    """
    data = _load_yaml(source)
    declared_target = data.get("target")
    if declared_target and declared_target != target:
        raise MappingValidationError(
            [
                {
                    "loc": ("target",),
                    "msg": f"YAML declares target {declared_target!r}; expected {target!r}",
                    "type": "value_error",
                }
            ]
        )
    schema = _schema_for(target)
    try:
        return schema.model_validate(data)
    except PydanticValidationError as exc:
        raise MappingValidationError(cast(list[dict[str, Any]], exc.errors())) from exc


def load_default_mapping(target: str = DEFAULT_TARGET) -> BaseMapping:
    """Load the bundled default mapping for the given target."""
    schema = _schema_for(target)
    filename = f"{target.replace('-', '_')}.yaml"
    pkg = resources.files("archithreat.core.defaults")
    text = (pkg / filename).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return schema.model_validate(data)


def default_mapping_text(target: str = DEFAULT_TARGET) -> str:
    """Return the raw bundled default mapping YAML as text."""
    _schema_for(target)  # validates target exists
    filename = f"{target.replace('-', '_')}.yaml"
    pkg = resources.files("archithreat.core.defaults")
    return (pkg / filename).read_text(encoding="utf-8")


def validate_mapping(
    source: str | bytes | os.PathLike[str], target: str = DEFAULT_TARGET
) -> list[dict[str, Any]]:
    """Validate a mapping. Returns a (possibly empty) list of error dicts."""
    try:
        load_mapping(source, target=target)
    except MappingValidationError as exc:
        return exc.errors
    return []


__all__ = [
    "DEFAULT_TARGET",
    "MAPPING_SCHEMAS",
    "MappingValidationError",
    "UnknownTargetError",
    "default_mapping_text",
    "load_default_mapping",
    "load_mapping",
    "validate_mapping",
]
