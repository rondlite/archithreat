# Adding a target

Purpose: contributor guide for adding a new emitter to [archithreat](../src/archithreat/__init__.py). Two emitters ship today (`iriusrisk`, `threatdragon`); the architecture is designed so further targets land as additive files without touching parsing, resolving, or shell code.

## Contents

- [The four files you write](#the-four-files-you-write)
- [Step 1: Subclass the mapping schema](#step-1-subclass-the-mapping-schema)
- [Step 2: Write the default YAML](#step-2-write-the-default-yaml)
- [Step 3: Implement the Emitter protocol](#step-3-implement-the-emitter-protocol)
- [Step 4: Register at import time](#step-4-register-at-import-time)
- [Step 5: Fixtures and goldens](#step-5-fixtures-and-goldens)
- [Step 6: Document](#step-6-document)

## The four files you write

For a hypothetical target `threatdragon`:

- `src/archithreat/core/mappings/threatdragon.py` — schema extensions
- `src/archithreat/core/defaults/threatdragon.yaml` — default mapping
- `src/archithreat/core/emitters/threatdragon.py` — the emitter
- `tests/fixtures/expected/threatdragon/*.json` — golden outputs

Plus a one-line edit to [`core/emitters/__init__.py`](../src/archithreat/core/emitters/__init__.py) to register the new emitter at module import.

## Step 1: Subclass the mapping schema

The shared schema lives in [`mappings/base.py`](../src/archithreat/core/mappings/base.py): `BaseMapping`, `ZoneRule`, `ComponentRule`, `ConnectionRule`, plus the matching helpers (`match_element`, `match_relationship`, `_condition_matches`). You inherit the matching machinery for free.

Create `src/archithreat/core/mappings/threatdragon.py` and subclass:

```python
from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from .base import BaseMapping, ComponentRule, ConnectionRule, ZoneRule

class ThreatDragonStyleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_type: str           # e.g., "tm.Process", "tm.Store", "tm.Actor"
    shape: str                    # Threat Dragon's shape identifier
    is_container: bool = False

class ThreatDragonComponentRule(ComponentRule):
    threatdragon: ThreatDragonStyleSpec

class ThreatDragonZoneRule(ZoneRule):
    threatdragon: dict[str, str]  # whatever zone metadata you need

class ThreatDragonConnectionRule(ConnectionRule):
    threatdragon: dict[str, str]

class ThreatDragonMapping(BaseMapping):
    component_rules: list[ThreatDragonComponentRule]
    zone_rules: list[ThreatDragonZoneRule]
    connection_rules: list[ThreatDragonConnectionRule]
```

The structure mirrors [`iriusrisk.py`](../src/archithreat/core/mappings/iriusrisk.py); copy that file as your starting point.

## Step 2: Write the default YAML

Create `src/archithreat/core/defaults/threatdragon.yaml`. The structure is the same as the [iriusrisk default](../src/archithreat/core/defaults/iriusrisk.yaml) but the per-target sections (`threatdragon:` blocks here, `iriusrisk:` blocks there) use your subclass's fields.

Cover at minimum: `ApplicationComponent`, `Node`, `BusinessActor`, `DataObject`, `Grouping`, plus `Flow`, `Serving`, `Access` connection rules. Put the most-specific rules first (first-match-wins).

## Step 3: Implement the Emitter protocol

The protocol lives in [`core/emitters/__init__.py`](../src/archithreat/core/emitters/__init__.py):

```python
@runtime_checkable
class Emitter(Protocol):
    target_id: str
    output_extension: str
    output_media_type: str
    def emit(self, model: MappedModel) -> bytes: ...
```

Create `src/archithreat/core/emitters/threatdragon.py`:

```python
from __future__ import annotations
import json
from ..model import MappedModel
from . import EmitterError

class ThreatDragonEmitter:
    target_id = "threatdragon"
    output_extension = "json"
    output_media_type = "application/json"

    def emit(self, model: MappedModel) -> bytes:
        # walk model.zones, model.components, model.connections.
        # build the Threat Dragon JSON shape.
        # use component.target_data["threatdragon"] for per-target style/type.
        out = {...}
        data = json.dumps(out, indent=2).encode("utf-8")
        # internal validation: re-parse, sanity-check structure.
        try:
            json.loads(data)
        except Exception as exc:
            raise EmitterError(f"emitted output failed re-parse: {exc}") from exc
        return data
```

Internal validation after emission catches emitter bugs early — broken edges, dangling parents, malformed JSON. Treat any failure here as a bug, not a user error.

## Step 4: Register at import time

Edit `core/emitters/__init__.py` to add a side-effect import next to the existing one:

```python
# Side-effect imports: register all v-N+ emitters at package import time.
from . import iriusrisk as _iriusrisk  # noqa: E402, F401
from . import threatdragon as _threatdragon          # noqa: E402, F401

register(_iriusrisk.DrawioIriusriskEmitter())
register(_threatdragon.ThreatDragonEmitter())
```

`available_targets()` will now return `["iriusrisk", "threatdragon"]`. The `target` parameter in `mappings.load_default_mapping(target=...)` and `get_emitter(target_id=...)` accepts the new value.

## Step 5: Fixtures and goldens

Reuse the existing fixtures in [`tests/fixtures/`](../tests/fixtures/) — `minimal.xml`, `co_hosted.xml`, `external_actor.xml`, `lemonade_shop.xml`, `orphans.xml` — and add target-scoped goldens under `tests/fixtures/expected/threatdragon/`. Compare structurally (parse both as JSON, normalize, compare trees) rather than byte-for-byte.

Add unit tests under `tests/core/emitters/test_threatdragon.py`: structural properties (parent-child correctness, edge endpoint validity, ID uniqueness), per-target schema validation in `tests/core/mappings/test_threatdragon.py`.

Goldens regenerate via `pytest --update-goldens` and are reviewed by hand before commit.

## Step 6: Document

Add a subsection to [`docs/targets.md`](targets.md) covering: audience, threat-modeling tool fed, file format produced, import procedure on the receiving side, and known caveats. Update the "Future targets" list in the same file.

If your target needs operator-facing nuance (network access, auth, etc.), update [`docs/self-hosting.md`](self-hosting.md) accordingly.

The user-facing `--target` flag (CLI), `target` field (JSON API), and target dropdown (UIs) read directly from the registry, so your emitter becomes selectable everywhere as soon as it registers — the registry is the single source of truth.
