"""Click-based CLI for archithreat.

Imports only from ``archithreat.core`` and stdlib. The ``serve`` subcommand
imports ``archithreat.web`` lazily so installs without the ``[web]`` extra still
work for everything else.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import click

from .. import __version__
from ..core.emitters import available_targets, get_emitter
from ..core.inventory import inventory_path
from ..core.mappings import (
    DEFAULT_TARGET,
    MAPPING_SCHEMAS,
    MappingValidationError,
    default_mapping_text,
    load_default_mapping,
    load_mapping,
)
from ..core.parser import ParserError, parse_path

_TARGET_CHOICES = sorted(MAPPING_SCHEMAS.keys())

# Exit codes (per SPEC §5.2)
EXIT_OK = 0
EXIT_WARNINGS_STRICT = 1
EXIT_INPUT_NOT_FOUND = 2
EXIT_PARSE_ERROR = 3
EXIT_NAMESPACE_ERROR = 4
EXIT_MAPPING_INVALID = 5
EXIT_EMITTER_BUG = 6


@click.group()
@click.version_option(__version__, prog_name="archithreat")
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    default="warning",
    help="Application log level.",
)
def cli(log_level: str) -> None:
    """Convert ArchiMate models into threat-modeling artifacts."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(levelname)s %(name)s: %(message)s",
    )


@cli.command()
@click.argument("input_path", type=click.Path(exists=False, dir_okay=False, path_type=Path))
@click.argument("output_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--target",
    type=click.Choice(_TARGET_CHOICES),
    default=DEFAULT_TARGET,
    show_default=True,
    help="Output target. Determines emitter + bundled default mapping.",
)
@click.option(
    "--mapping",
    "mapping_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to mapping YAML; falls back to bundled default for the chosen target.",
)
@click.option(
    "--view",
    "view_name",
    type=str,
    default=None,
    help="Restrict conversion to a single named view (default: whole model).",
)
@click.option("--unzoned-policy", type=click.Choice(["warn", "fail", "silent"]), default="warn")
@click.option("--unrealized-policy", type=click.Choice(["warn", "fail", "silent"]), default="warn")
@click.option(
    "--report",
    "report_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write inventory report alongside conversion (text or json by extension).",
)
@click.option(
    "--strict", is_flag=True, default=False, help="Exit non-zero if any warning is emitted."
)
def convert(
    input_path: Path,
    output_path: Path,
    target: str,
    mapping_path: Path | None,
    view_name: str | None,
    unzoned_policy: str,
    unrealized_policy: str,
    report_path: Path | None,
    strict: bool,
) -> None:
    """Convert INPUT_PATH (ArchiMate XML) into OUTPUT_PATH (target output)."""
    if not input_path.exists():
        click.echo(f"Input not found: {input_path}", err=True)
        sys.exit(EXIT_INPUT_NOT_FOUND)

    try:
        mapping = (
            load_mapping(mapping_path, target=target)
            if mapping_path
            else load_default_mapping(target=target)
        )
    except MappingValidationError as exc:
        click.echo(f"Mapping invalid: {len(exc.errors)} error(s)", err=True)
        for e in exc.errors:
            click.echo(f"  - {_fmt_err(e)}", err=True)
        sys.exit(EXIT_MAPPING_INVALID)

    try:
        model = parse_path(input_path)
    except ParserError as exc:
        msg = str(exc)
        click.echo(f"Parser error: {msg}", err=True)
        if "namespace" in msg.lower():
            sys.exit(EXIT_NAMESPACE_ERROR)
        sys.exit(EXIT_PARSE_ERROR)

    if view_name is not None:
        names = {v.name: v for v in model.views}
        if view_name not in names:
            click.echo(
                f"View {view_name!r} not found. Available: {sorted(names)}",
                err=True,
            )
            sys.exit(EXIT_INPUT_NOT_FOUND)
        # v1: view filtering not yet implemented; warn and continue with full model.
        click.echo(
            "warning: --view filtering not implemented in v1; converting full model",
            err=True,
        )

    from ..core.mapper import apply_mapping
    from ..core.resolver import resolve_with_synthetic

    resolved = resolve_with_synthetic(model, mapping)

    warnings_count = len(resolved.warnings)
    if warnings_count:
        if unzoned_policy == "fail" or unrealized_policy == "fail":
            for w in resolved.warnings:
                if unzoned_policy == "fail" and w.code == "multiple_zone_candidates":
                    click.echo(f"FAIL [{w.code}] {w.message}", err=True)
                    sys.exit(EXIT_WARNINGS_STRICT)
                if unrealized_policy == "fail" and w.code == "application_component_unrealized":
                    click.echo(f"FAIL [{w.code}] {w.message}", err=True)
                    sys.exit(EXIT_WARNINGS_STRICT)
        if unzoned_policy != "silent" or unrealized_policy != "silent":
            for w in resolved.warnings:
                click.echo(f"warning [{w.code}] {w.message}", err=True)

    try:
        mapped = apply_mapping(resolved, mapping, source_name=model.name)
        emitter = get_emitter(mapping.target)
        out = emitter.emit(mapped)
    except Exception as exc:
        click.echo(f"Internal emitter error: {exc}", err=True)
        sys.exit(EXIT_EMITTER_BUG)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(out)
    click.echo(f"wrote {output_path} ({len(out)} bytes)")

    if report_path is not None:
        report = inventory_path(input_path, mapping=mapping)
        if report_path.suffix.lower() == ".json":
            report_path.write_text(report.to_json(), encoding="utf-8")
        elif report_path.suffix.lower() in {".md", ".markdown"}:
            report_path.write_text(report.to_markdown(), encoding="utf-8")
        else:
            report_path.write_text(report.to_text(), encoding="utf-8")
        click.echo(f"wrote {report_path}")

    if strict and warnings_count:
        sys.exit(EXIT_WARNINGS_STRICT)


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json", "markdown"]), default="text")
@click.option(
    "--target",
    type=click.Choice(_TARGET_CHOICES),
    default=DEFAULT_TARGET,
    show_default=True,
    help="Target whose default mapping should be used (inventory is target-independent; this only picks the mapping for zone-rule warnings).",
)
@click.option(
    "--mapping",
    "mapping_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
def inventory(
    input_path: Path, fmt: str, target: str, mapping_path: Path | None
) -> None:
    """Survey the model without producing output."""
    try:
        mapping = (
            load_mapping(mapping_path, target=target)
            if mapping_path
            else load_default_mapping(target=target)
        )
    except MappingValidationError as exc:
        click.echo(f"Mapping invalid: {len(exc.errors)} error(s)", err=True)
        sys.exit(EXIT_MAPPING_INVALID)
    try:
        report = inventory_path(input_path, mapping=mapping)
    except ParserError as exc:
        click.echo(f"Parser error: {exc}", err=True)
        sys.exit(EXIT_PARSE_ERROR)
    if fmt == "json":
        click.echo(report.to_json())
    elif fmt == "markdown":
        click.echo(report.to_markdown())
    else:
        click.echo(report.to_text())


@cli.command("validate-mapping")
@click.argument("mapping_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--target",
    type=click.Choice(_TARGET_CHOICES),
    default=DEFAULT_TARGET,
    show_default=True,
    help="Schema target to validate against.",
)
def validate_mapping_cmd(mapping_path: Path, target: str) -> None:
    """Validate a mapping YAML against the schema."""
    try:
        load_mapping(mapping_path, target=target)
    except MappingValidationError as exc:
        click.echo(f"Invalid: {len(exc.errors)} error(s)", err=True)
        for e in exc.errors:
            click.echo(f"  - {_fmt_err(e)}", err=True)
        sys.exit(EXIT_MAPPING_INVALID)
    click.echo("OK")


@cli.command("show-defaults")
@click.option(
    "--target",
    type=click.Choice(_TARGET_CHOICES),
    default=DEFAULT_TARGET,
    show_default=True,
    help="Which target's default mapping to print.",
)
def show_defaults(target: str) -> None:
    """Print the bundled default mapping YAML for the given target."""
    click.echo(default_mapping_text(target), nl=False)


@cli.command("targets")
def targets_cmd() -> None:
    """List the registered output targets."""
    for t in available_targets():
        e = get_emitter(t)
        click.echo(f"{t}\t.{e.output_extension}\t{e.output_media_type}")


@cli.command()
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8000, type=int, show_default=True)
def serve(host: str, port: int) -> None:
    """Start the local web shell (FastAPI). Requires the [web] extra."""
    try:
        import uvicorn

        from ..web.app import create_app
    except ImportError as exc:
        click.echo(
            "The web shell is not installed. Reinstall with: pip install 'archithreat[web]'",
            err=True,
        )
        click.echo(f"  ({exc})", err=True)
        sys.exit(2)
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


def _fmt_err(e: dict[str, Any]) -> str:
    loc = e.get("loc") or ()
    msg = e.get("msg", "")
    loc_str = ".".join(str(p) for p in loc) if loc else "<root>"
    return f"{loc_str}: {msg}"


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
