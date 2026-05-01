"""Shared pytest fixtures and CLI options."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURES / "expected" / "drawio_iriusrisk"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Regenerate golden output files from fixtures.",
    )


@pytest.fixture
def update_goldens(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-goldens"))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def golden_dir() -> Path:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    return GOLDEN_DIR


@pytest.fixture
def minimal_xml(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "minimal.xml").read_bytes()


@pytest.fixture
def cohosted_xml(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "co_hosted.xml").read_bytes()


@pytest.fixture
def external_actor_xml(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "external_actor.xml").read_bytes()


@pytest.fixture
def orphans_xml(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "orphans.xml").read_bytes()


@pytest.fixture
def lemonade_xml(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "lemonade_shop.xml").read_bytes()
