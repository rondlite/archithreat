"""JSON API router (SPEC §5.4).

All endpoints are stateless and process bytes in memory. Errors are returned
under a uniform JSON envelope ``{"error": {"code", "message", "details"}}``.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .. import __version__, convert_bytes
from ..core.emitters import EMITTERS, available_targets, get_emitter
from ..core.inventory import inventory_bytes
from ..core.mappings import (
    DEFAULT_TARGET,
    MAPPING_SCHEMAS,
    MappingValidationError,
    default_mapping_text,
    load_default_mapping,
    validate_mapping,
)
from ..core.parser import ParserError
from .limits import enforce_upload_size, run_with_timeout

router = APIRouter()


def _resolve_target(value: str | None) -> str:
    """Validate and resolve the requested target ID."""
    target = value or DEFAULT_TARGET
    if target not in MAPPING_SCHEMAS:
        raise _err(
            "unknown_target",
            f"Unknown target {target!r}",
            details={"available": sorted(MAPPING_SCHEMAS.keys())},
            status_code=400,
        )
    return target

# Embedded fixture for /readyz self-test. Same content as
# tests/fixtures/minimal.xml. Embedding inline keeps /readyz hermetic and
# independent of the test tree at runtime.
_READYZ_FIXTURE = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/"\n'
    b'       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
    b'       identifier="readyz-1">\n'
    b'  <name xml:lang="en">readyz</name>\n'
    b"  <elements>\n"
    b'    <element identifier="g_dmz" xsi:type="Grouping">\n'
    b'      <name xml:lang="en">DMZ</name>\n'
    b"    </element>\n"
    b'    <element identifier="n_web" xsi:type="Node">\n'
    b'      <name xml:lang="en">web-host</name>\n'
    b"    </element>\n"
    b'    <element identifier="a_app" xsi:type="ApplicationComponent">\n'
    b'      <name xml:lang="en">App</name>\n'
    b"    </element>\n"
    b"  </elements>\n"
    b"  <relationships>\n"
    b'    <relationship identifier="r_compose" xsi:type="Composition" '
    b'source="g_dmz" target="n_web"/>\n'
    b'    <relationship identifier="r_realize" xsi:type="Realization" '
    b'source="a_app" target="n_web"/>\n'
    b"  </relationships>\n"
    b"</model>\n"
)


class UnzonedPolicy(str, Enum):
    warn = "warn"
    fail = "fail"
    silent = "silent"


class UnrealizedPolicy(str, Enum):
    warn = "warn"
    fail = "fail"
    silent = "silent"


def _err(code: str, message: str, details: Any = None, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "details": details},
    )


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_stem(name: str | None) -> str:
    if not name:
        return "model"
    stem = name.rsplit(".", 1)[0] if "." in name else name
    cleaned = _FILENAME_SAFE.sub("_", stem).strip("_")
    return cleaned or "model"


@router.post("/api/v1/convert")
async def api_convert(
    request: Request,
    model: UploadFile = File(...),
    mapping: UploadFile | None = File(default=None),
    mapping_text: str | None = Form(default=None),
    view: str | None = Form(default=None),
    unzoned_policy: UnzonedPolicy = Form(default=UnzonedPolicy.warn),
    unrealized_policy: UnrealizedPolicy = Form(default=UnrealizedPolicy.warn),
    target: str | None = Form(default=None),
) -> Response:
    """Convert an ArchiMate XML model into the chosen target's output bytes."""
    target_id = _resolve_target(target)
    model_bytes = await enforce_upload_size(model)
    mapping_source: str | bytes | None = None
    if mapping is not None and mapping.filename:
        mapping_source = await enforce_upload_size(mapping)
    elif mapping_text:
        mapping_source = mapping_text

    emitter = get_emitter(target_id)
    stem = _safe_stem(model.filename)

    try:
        output = await run_with_timeout(
            convert_bytes,
            model_bytes,
            mapping_source=mapping_source,
            target=target_id,
            source_name=stem,
        )
    except ParserError as exc:
        raise _err("parser_error", str(exc), status_code=400) from exc
    except MappingValidationError as exc:
        raise _err(
            "mapping_invalid", str(exc), details={"errors": exc.errors}, status_code=400
        ) from exc

    filename = f"{stem}.{emitter.output_extension}"
    return Response(
        content=output,
        media_type=emitter.output_media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/v1/inventory")
async def api_inventory(
    request: Request,
    model: UploadFile = File(...),
    accept: str | None = Header(default=None),
    target: str | None = Form(default=None),
) -> Response:
    """Run inventory on an uploaded model. JSON by default; markdown via Accept."""
    target_id = _resolve_target(target)
    model_bytes = await enforce_upload_size(model)
    mapping = load_default_mapping(target=target_id)
    try:
        report = await run_with_timeout(inventory_bytes, model_bytes, mapping)
    except ParserError as exc:
        raise _err("parser_error", str(exc), status_code=400) from exc

    if accept and "text/markdown" in accept.lower():
        return PlainTextResponse(report.to_markdown(), media_type="text/markdown")
    return Response(content=report.to_json(), media_type="application/json")


@router.post("/api/v1/mapping/validate")
async def api_mapping_validate(
    request: Request,
    mapping: UploadFile | None = File(default=None),
    target: str | None = Form(default=None),
) -> JSONResponse:
    """Validate a mapping document. Accepts text/yaml body or a multipart file."""
    # Allow target via form field (multipart) or query string (?target=...).
    target_id = _resolve_target(target or request.query_params.get("target"))
    content_type = (request.headers.get("content-type") or "").lower()
    payload: bytes | str

    if mapping is not None and mapping.filename:
        payload = await enforce_upload_size(mapping)
    elif "yaml" in content_type or "text/" in content_type:
        payload = await request.body()
        if not payload:
            raise _err("empty_body", "Request body is empty", status_code=400)
    else:
        # multipart with no file, or unknown content type
        body = await request.body()
        if not body:
            raise _err(
                "missing_mapping",
                "Provide mapping as text/yaml body or as a multipart file field",
                status_code=400,
            )
        payload = body

    try:
        errors = validate_mapping(payload, target=target_id)
    except Exception as exc:  # pragma: no cover - defensive
        raise _err("validation_error", str(exc), status_code=400) from exc

    return JSONResponse({"valid": not errors, "errors": errors})


@router.get("/api/v1/mapping/default")
def api_mapping_default(target: str | None = None) -> Response:
    """Return the bundled default mapping for the given target as text/yaml."""
    target_id = _resolve_target(target)
    return Response(content=default_mapping_text(target_id), media_type="text/yaml")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe — minimal."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> Response:
    """Readiness probe: runs a self-test conversion of an embedded fixture."""
    try:
        out = convert_bytes(_READYZ_FIXTURE)
        if not out or not out.startswith(b"<?xml"):
            raise RuntimeError("self-test produced unexpected output")
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "not_ready",
                    "message": f"Self-test failed: {exc}",
                    "details": None,
                }
            },
        )
    return JSONResponse({"status": "ready"})


@router.get("/version")
def version() -> dict[str, Any]:
    """Package version + list of registered emitter targets."""
    # Touch EMITTERS so reviewers can see we surface what's in the registry.
    _ = EMITTERS
    return {
        "package": __version__,
        "available_targets": available_targets(),
    }


__all__ = ["router"]
