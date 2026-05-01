"""Emitter protocol and registry.

v1 ships exactly one emitter (``drawio-iriusrisk``); the registry exists from
day one to make additional targets a one-file addition in v2+.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..model import MappedModel


class EmitterError(Exception):
    """Raised by an emitter when its internal validation fails (a bug)."""


class UnknownTargetError(KeyError):
    """Raised when ``get_emitter`` is called with an unknown target_id."""


@runtime_checkable
class Emitter(Protocol):
    target_id: str
    output_extension: str
    output_media_type: str

    def emit(self, model: MappedModel) -> bytes: ...


EMITTERS: dict[str, Emitter] = {}


def register(emitter: Emitter) -> None:
    EMITTERS[emitter.target_id] = emitter


def unregister(target_id: str) -> None:
    EMITTERS.pop(target_id, None)


def get_emitter(target_id: str) -> Emitter:
    try:
        return EMITTERS[target_id]
    except KeyError as exc:
        raise UnknownTargetError(target_id) from exc


def available_targets() -> list[str]:
    return sorted(EMITTERS.keys())


# Side-effect import: register the bundled emitters at package import time.
from . import drawio_iriusrisk as _drawio_iriusrisk  # noqa: E402
from . import threatdragon as _threatdragon  # noqa: E402

register(_drawio_iriusrisk.DrawioIriusriskEmitter())
register(_threatdragon.ThreatDragonEmitter())


__all__ = [
    "EMITTERS",
    "Emitter",
    "EmitterError",
    "UnknownTargetError",
    "available_targets",
    "get_emitter",
    "register",
    "unregister",
]
