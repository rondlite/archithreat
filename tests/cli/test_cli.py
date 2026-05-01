"""CLI tests using click.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from archithreat.cli.main import cli


def test_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.output


def test_show_defaults() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["show-defaults"])
    assert result.exit_code == 0
    assert "drawio-iriusrisk" in result.output


def test_convert_minimal(tmp_path: Path, fixtures_dir: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "out.drawio"
    result = runner.invoke(
        cli,
        ["convert", str(fixtures_dir / "minimal.xml"), str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.stat().st_size > 100


def test_convert_input_missing(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["convert", str(tmp_path / "nope.xml"), str(tmp_path / "o.drawio")])
    assert result.exit_code == 2


def test_convert_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_bytes(b"<not-xml")
    runner = CliRunner()
    result = runner.invoke(cli, ["convert", str(bad), str(tmp_path / "o.drawio")])
    assert result.exit_code == 3


def test_validate_default_mapping(tmp_path: Path) -> None:
    # Round-trip: write defaults, validate them
    runner = CliRunner()
    show = runner.invoke(cli, ["show-defaults"])
    p = tmp_path / "m.yaml"
    p.write_text(show.output)
    result = runner.invoke(cli, ["validate-mapping", str(p)])
    assert result.exit_code == 0


def test_validate_invalid_mapping(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("just a string\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["validate-mapping", str(p)])
    assert result.exit_code == 5


def test_inventory_text(fixtures_dir: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["inventory", str(fixtures_dir / "lemonade_shop.xml"), "--format", "text"]
    )
    assert result.exit_code == 0
    assert "ApplicationComponent" in result.output


def test_inventory_json(fixtures_dir: Path) -> None:
    import json

    runner = CliRunner()
    result = runner.invoke(
        cli, ["inventory", str(fixtures_dir / "lemonade_shop.xml"), "--format", "json"]
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["model_name"] == "Lemonade Shop"


def test_strict_exits_nonzero_on_warnings(tmp_path: Path, fixtures_dir: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "o.drawio"
    result = runner.invoke(
        cli,
        [
            "convert",
            str(fixtures_dir / "orphans.xml"),
            str(out),
            "--strict",
        ],
    )
    assert result.exit_code == 1


def test_report_alongside_convert(tmp_path: Path, fixtures_dir: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "o.drawio"
    rep = tmp_path / "r.json"
    result = runner.invoke(
        cli,
        [
            "convert",
            str(fixtures_dir / "lemonade_shop.xml"),
            str(out),
            "--report",
            str(rep),
        ],
    )
    assert result.exit_code == 0
    assert rep.exists()
    import json

    parsed = json.loads(rep.read_text())
    assert parsed["model_name"] == "Lemonade Shop"
