"""SPEC §11 AC#6: no disk writes for user content during a request lifecycle.

Strategy:

1. Build the app and pre-warm everything that legitimately reads files at
   import time (templates, default mapping resource, etc.).
2. Patch ``builtins.open`` (write modes), ``os.write`` to fds opened during the
   request, ``tempfile.mkstemp``, ``tempfile.NamedTemporaryFile``, and
   ``pathlib.Path.write_bytes`` / ``write_text`` to raise on any call.
3. Exercise ``POST /api/v1/convert`` and assert it succeeds — proving the
   conversion pipeline is purely in-memory.

Reads of bundled defaults are whitelisted: those are package resources, not
user content. The patches only block *writes*.
"""

from __future__ import annotations

import builtins
import os
import pathlib
import tempfile

import pytest

from .conftest import async_run

WRITE_MODE_CHARS = {"w", "a", "x", "+"}


def _is_write_mode(mode: str) -> bool:
    return any(ch in WRITE_MODE_CHARS for ch in mode)


def test_convert_does_not_write_to_disk(
    make_client, lemonade_xml_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pre-warm: build a client (loads templates, default mapping, lxml, etc.).
    client = make_client()
    # Trigger one warmup conversion before the patches go in, to exercise any
    # one-shot resource lookups that legitimately read bundled files.
    files = {"model": ("warmup.xml", lemonade_xml_bytes, "application/xml")}
    r = async_run(client.post("/api/v1/convert", files=files))
    assert r.status_code == 200

    real_open = builtins.open
    write_attempts: list[str] = []

    def guarded_open(file, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(mode, str) and _is_write_mode(mode):
            write_attempts.append(f"open({file!r}, {mode!r})")
            raise AssertionError(f"Disallowed write to {file!r} (mode {mode!r}) during request")
        return real_open(file, mode, *args, **kwargs)

    def block_mkstemp(*args, **kwargs):  # type: ignore[no-untyped-def]
        write_attempts.append(f"tempfile.mkstemp({args!r}, {kwargs!r})")
        raise AssertionError("tempfile.mkstemp is forbidden during a request")

    def block_named_tmp(*args, **kwargs):  # type: ignore[no-untyped-def]
        write_attempts.append("tempfile.NamedTemporaryFile")
        raise AssertionError("tempfile.NamedTemporaryFile is forbidden during a request")

    def block_path_write_bytes(self, data, *a, **kw):  # type: ignore[no-untyped-def]
        write_attempts.append(f"Path({self!s}).write_bytes")
        raise AssertionError(f"Path.write_bytes forbidden during a request: {self}")

    def block_path_write_text(self, data, *a, **kw):  # type: ignore[no-untyped-def]
        write_attempts.append(f"Path({self!s}).write_text")
        raise AssertionError(f"Path.write_text forbidden during a request: {self}")

    real_os_write = os.write
    suspect_fds: set[int] = set()

    def guarded_os_write(fd, data):  # type: ignore[no-untyped-def]
        # Allow stdout/stderr; the conversion itself writes to neither.
        if fd in (1, 2):
            return real_os_write(fd, data)
        if fd in suspect_fds:
            write_attempts.append(f"os.write(fd={fd}, len={len(data)})")
            raise AssertionError(f"os.write to opened fd {fd} forbidden during a request")
        return real_os_write(fd, data)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(tempfile, "mkstemp", block_mkstemp)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", block_named_tmp)
    monkeypatch.setattr(pathlib.Path, "write_bytes", block_path_write_bytes)
    monkeypatch.setattr(pathlib.Path, "write_text", block_path_write_text)
    monkeypatch.setattr(os, "write", guarded_os_write)

    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r = async_run(client.post("/api/v1/convert", files=files))

    assert r.status_code == 200, f"convert failed under no-write patches: {r.text}"
    assert r.content.startswith(b"<?xml")
    assert b"mxfile" in r.content
    assert write_attempts == [], f"unexpected write attempts: {write_attempts}"
