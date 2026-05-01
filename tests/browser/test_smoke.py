"""Playwright smoke test for the browser shell.

Marked ``browser`` and ``slow``. Skips with a clear message when the prereqs
are not in place so the default ``pytest`` invocation stays green.

Prereqs (all must hold):
    1. ``playwright`` Python package importable — already in ``[dev]``.
    2. Playwright browsers installed: ``python -m playwright install chromium``.
    3. ``browser/dist/`` exists — i.e., ``cd browser && npm run build`` has run
       and ``vendor/pyodide/`` plus ``wheels/archithreat-*.whl`` are populated.

The test:
    * Spawns a tiny static HTTP server on ``127.0.0.1`` against ``dist/``.
    * Loads the page, waits for the "Pyodide ready" indicator
      (``document.body.dataset.pyodide === 'ready'``).
    * Uploads ``tests/fixtures/lemonade_shop.xml`` to the Convert form's file
      input.
    * Clicks Convert and asserts that a download is triggered.
    * Tears down the server and the browser.
"""

from __future__ import annotations

import contextlib
import http.server
import socket
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

import pytest

pytestmark = [pytest.mark.browser, pytest.mark.slow]

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "browser" / "dist"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "lemonade_shop.xml"


def _playwright_browsers_installed() -> bool:
    """Return True iff a Playwright Chromium binary is installed.

    ``playwright install --dry-run chromium`` exits 0 with "is already
    installed" output when the browser is present.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    output = (result.stdout or "") + (result.stderr or "")
    # Heuristic: the dry-run output mentions either "already installed" or
    # nothing-to-install when present, and "downloading" / "install location"
    # when missing.
    return "already installed" in output.lower() or (
        result.returncode == 0 and "download" not in output.lower()
    )


def _require_prereqs() -> None:
    if not DIST_DIR.exists():
        pytest.skip("browser/dist/ not found. Run `cd browser && npm run build` first.")
    if not (DIST_DIR / "index.html").exists():
        pytest.skip("browser/dist/index.html missing — incomplete build.")
    wheels = (
        list((DIST_DIR / "wheels").glob("archithreat-*.whl"))
        if (DIST_DIR / "wheels").exists()
        else []
    )
    if not wheels:
        pytest.skip("No archithreat wheel in dist/wheels/. Run `npm run build:wheel`.")
    pyodide_js = DIST_DIR / "pyodide" / "pyodide.js"
    if not pyodide_js.exists():
        pytest.skip("Vendored Pyodide missing in dist/. Run `npm run vendor:pyodide` then rebuild.")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright Python package not installed.")
    if not _playwright_browsers_installed():
        pytest.skip(
            "Playwright Chromium browser not installed. "
            "Run `python -m playwright install chromium`."
        )
    if not FIXTURE.exists():
        pytest.skip(f"Fixture not found: {FIXTURE}")


class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    """Static handler that doesn't pollute stdout with request logs."""

    def log_message(self, format: str, *args: object) -> None:
        return

    def end_headers(self) -> None:
        # Pyodide is happier when these are present.
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


@contextlib.contextmanager
def _serve(directory: Path):
    handler = type(
        "Handler",
        (_SilentHandler,),
        {"directory": str(directory)},
    )

    # Bind to an ephemeral port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_browser_shell_convert_smoke() -> None:
    """End-to-end: load page, wait for Pyodide, upload XML, click Convert
    once per output target, and assert the suggested filename's extension
    matches the picked target."""
    _require_prereqs()

    from playwright.sync_api import sync_playwright

    # (target dropdown value, expected download extension)
    cases = [
        ("drawio-iriusrisk", ".drawio"),
        ("threatdragon", ".json"),
    ]

    with _serve(DIST_DIR) as url, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")

            # Pyodide bootstrap is slow (~10s cold). Allow up to 90s.
            page.wait_for_function(
                "document.body.dataset.pyodide === 'ready'",
                timeout=90_000,
            )

            page.set_input_files("#file-convert", str(FIXTURE))

            for target_value, expected_ext in cases:
                page.select_option("#target", target_value)
                with page.expect_download(timeout=60_000) as download_info:
                    page.click("#btn-convert")
                download = download_info.value
                assert download.suggested_filename.endswith(expected_ext), (
                    f"target {target_value!r}: expected suffix {expected_ext}, "
                    f"got {download.suggested_filename!r}"
                )
        finally:
            browser.close()
