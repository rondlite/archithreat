# Contributing to archithreat

Thanks for taking interest. archithreat is open-source under Apache 2.0.

## Dev environment

```bash
git clone https://github.com/rondlite/archithreat
cd archithreat
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[cli,web,dev]"
pre-commit install
```

## Running tests

```bash
pytest                              # core + cli + web
pytest -m "not browser and not slow"
pytest tests/browser                # requires playwright install
ruff check .
ruff format --check .
mypy
```

## Structure

The conversion core (`src/archithreat/core/`) is target-independent. Per-target
code lives in `core/mappings/`, `core/emitters/`, and `core/defaults/`. The
three shells (`cli/`, `web/`, `browser/`) wrap the core and depend on no
each other.

## Mapping table contributions

Updates to the bundled IriusRisk mapping (e.g., new shape library version) are
welcome. Edit `src/archithreat/core/defaults/iriusrisk.yaml`, regenerate
goldens with `pytest --update-goldens`, and submit a PR with the rationale.

## Adding a new emitter target

See [docs/adding-a-target.md](docs/adding-a-target.md).

## Code style

- `ruff` for lint + format.
- `mypy --strict` for typing.
- Tests required for any logic change.
- 90% line coverage on `core/`.
