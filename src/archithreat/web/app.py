"""FastAPI application factory for the archithreat web shell.

``create_app()`` is intentionally side-effect-free: it builds a fresh app and
attaches all routers, middleware, the rate limiter, and the static mount.
``archithreat serve`` and the Docker entrypoint both call it.
"""

from __future__ import annotations

from importlib import resources
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

from .. import __version__
from .api import router as api_router
from .limits import build_limiter, rate_limit_enabled
from .settings import Settings, reset_settings_cache
from .ui import router as ui_router


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a FastAPI application; tests call this with a fresh Settings."""
    # Tests mutate env then call create_app; make sure cached settings reload.
    reset_settings_cache()
    if settings is None:
        from .settings import get_settings

        settings = get_settings()

    app = FastAPI(
        title="archithreat",
        version=__version__,
        description=(
            "ArchiMate to threat-model converter. Stateless, in-memory, "
            "no persistence of user content."
        ),
    )

    # CORS only when the operator has configured origins.
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    # Rate limiter: register on app.state and as exception handler. slowapi
    # decorators on routes (or via apply_rate_limit) consult app.state.limiter.
    limiter = build_limiter()
    app.state.limiter = limiter
    app.state.rate_limit_enabled = rate_limit_enabled()
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # If rate limiting is enabled, wrap incoming requests for / and /api with
    # the default limit. We attach via middleware so we don't have to decorate
    # each route individually and so disabling at runtime is a config flip.
    if rate_limit_enabled():
        rpm = settings.rate_limit_per_minute
        import limits as _limits

        rate_item = _limits.parse(f"{rpm}/minute")

        @app.middleware("http")
        async def _rate_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
            # slowapi's pure-middleware path is not stable across versions; we
            # implement the per-IP counter here using the same Limiter storage.
            from .limits import _rate_limit_key

            key = _rate_limit_key(request)
            allowed = limiter.limiter.hit(rate_item, key)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content=_envelope(
                        "rate_limited",
                        f"Rate limit of {rpm}/minute exceeded",
                    ),
                )
            return await call_next(request)

    # Routers
    app.include_router(api_router)
    app.include_router(ui_router)

    # Static files (CSS + placeholder htmx).
    static_dir = resources.files("archithreat.web") / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Uniform JSON error envelope for HTTPException raised by our routes.
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(  # type: ignore[no-untyped-def]
        request: Request, exc: StarletteHTTPException
    ):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=_envelope(
                    str(detail.get("code")),
                    str(detail.get("message", "")),
                    detail.get("details"),
                ),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc_handler(  # type: ignore[no-untyped-def]
        request: Request, exc: RequestValidationError
    ):
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "validation_error",
                "Request validation failed",
                details={"errors": exc.errors()},
            ),
        )

    return app


__all__ = ["create_app"]
