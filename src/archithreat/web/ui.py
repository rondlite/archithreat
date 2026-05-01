"""HTMX UI router (SPEC §5.4).

The UI is intentionally thin: each form posts to an ``/ui/...`` endpoint that
returns an HTML partial replacing a result panel via ``hx-target``.
"""

from __future__ import annotations

import base64
from importlib import resources

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import __version__, convert_bytes
from ..core.emitters import get_emitter
from ..core.inventory import inventory_bytes
from ..core.mappings import (
    DEFAULT_TARGET,
    MAPPING_SCHEMAS,
    MappingValidationError,
    load_default_mapping,
    validate_mapping,
)
from ..core.parser import ParserError
from .api import _safe_stem
from .limits import enforce_upload_size, run_with_timeout

router = APIRouter()

_TEMPLATE_DIR = resources.files("archithreat.web") / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def _ctx(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": __version__,
        "privacy_url": ("https://github.com/rondlite/archithreat/blob/main/docs/privacy.md"),
        "targets": sorted(MAPPING_SCHEMAS.keys()),
        "default_target": DEFAULT_TARGET,
    }
    base.update(extra)
    return base


def _resolve_target(value: str | None) -> str:
    target = value or DEFAULT_TARGET
    if target not in MAPPING_SCHEMAS:
        target = DEFAULT_TARGET
    return target


def _render(request: Request, name: str, **extra: object) -> HTMLResponse:
    return templates.TemplateResponse(request, name, _ctx(**extra))


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _render(request, "index.html")


@router.get("/convert", response_class=HTMLResponse)
def convert_page(request: Request) -> HTMLResponse:
    return _render(request, "convert.html")


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request) -> HTMLResponse:
    return _render(request, "inventory.html")


@router.get("/validate-mapping", response_class=HTMLResponse)
def validate_page(request: Request) -> HTMLResponse:
    return _render(request, "validate.html")


@router.post("/ui/convert", response_class=HTMLResponse)
async def ui_convert(
    request: Request,
    model: UploadFile = File(...),
    mapping_text: str | None = Form(default=None),
    target: str | None = Form(default=None),
) -> HTMLResponse:
    try:
        target_id = _resolve_target(target)
        model_bytes = await enforce_upload_size(model)
        stem = _safe_stem(model.filename)
        output = await run_with_timeout(
            convert_bytes,
            model_bytes,
            mapping_source=mapping_text or None,
            target=target_id,
            source_name=stem,
        )
        emitter = get_emitter(target_id)
        # Inline the bytes as a data URL so the user can download without any
        # server-side persistence. SPEC §5.4: nothing user-supplied hits disk.
        data_url = (
            f"data:{emitter.output_media_type};base64,{base64.b64encode(output).decode('ascii')}"
        )
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            _ctx(
                kind="convert",
                ok=True,
                size=len(output),
                filename=f"{stem}.{emitter.output_extension}",
                download_url=data_url,
            ),
        )
    except ParserError as exc:
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            _ctx(kind="convert", ok=False, error_message=str(exc)),
            status_code=400,
        )
    except MappingValidationError as exc:
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            _ctx(kind="convert", ok=False, error_message=str(exc)),
            status_code=400,
        )


@router.post("/ui/inventory", response_class=HTMLResponse)
async def ui_inventory(
    request: Request,
    model: UploadFile = File(...),
    target: str | None = Form(default=None),
) -> HTMLResponse:
    try:
        target_id = _resolve_target(target)
        model_bytes = await enforce_upload_size(model)
        mapping = load_default_mapping(target=target_id)
        report = await run_with_timeout(inventory_bytes, model_bytes, mapping)
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            _ctx(
                kind="inventory",
                ok=True,
                report_text=report.to_text(),
            ),
        )
    except ParserError as exc:
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            _ctx(kind="inventory", ok=False, error_message=str(exc)),
            status_code=400,
        )


@router.post("/ui/validate-mapping", response_class=HTMLResponse)
async def ui_validate_mapping(
    request: Request,
    mapping_text: str | None = Form(default=None),
    mapping: UploadFile | None = File(default=None),
    target: str | None = Form(default=None),
) -> HTMLResponse:
    target_id = _resolve_target(target)
    payload: bytes | str | None = None
    if mapping is not None and mapping.filename:
        payload = await enforce_upload_size(mapping)
    elif mapping_text:
        payload = mapping_text

    if payload is None:
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            _ctx(
                kind="validate",
                ok=False,
                error_message="Provide a mapping file or paste mapping text.",
            ),
            status_code=400,
        )

    errors = validate_mapping(payload, target=target_id)
    return templates.TemplateResponse(
        request,
        "partials/result.html",
        _ctx(
            kind="validate",
            ok=not errors,
            errors=errors,
        ),
    )


__all__ = ["router"]
