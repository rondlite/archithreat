"""Limits: upload size guard, rate limiter, request timeout watchdog.

All three are configured from :mod:`archithreat.web.settings` and are wired into
the FastAPI app in :mod:`archithreat.web.app`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, TypeVar

from fastapi import HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from .settings import Settings, get_settings

T = TypeVar("T")

# Shared executor for synchronous CPU-bound conversion calls. A modest pool is
# fine: each request occupies one worker for the duration of its conversion.
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="archithreat-convert")


def _rate_limit_key(request: Request) -> str:
    """Per-IP key. Honors X-Forwarded-For if a trusted-proxy list is set."""
    settings = get_settings()
    if settings.forwarded_allow_ips:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return get_remote_address(request)


def _rate_limit_string() -> str:
    rpm = get_settings().rate_limit_per_minute
    # Effectively unlimited when rpm <= 0; slowapi has no explicit "off" so we
    # set a very large bound and the no-op decorator below short-circuits it.
    if rpm <= 0:
        return "1000000/minute"
    return f"{rpm}/minute"


def build_limiter() -> Limiter:
    """Build the slowapi Limiter. Memory backend; per-IP."""
    return Limiter(
        key_func=_rate_limit_key,
        default_limits=[],
        storage_uri="memory://",
        headers_enabled=True,
    )


def rate_limit_enabled() -> bool:
    return get_settings().rate_limit_per_minute > 0


def apply_rate_limit(limiter: Limiter, route: Callable[..., Any]) -> Callable[..., Any]:
    """Apply slowapi limit to a route, no-op when rate limiting is disabled."""
    if not rate_limit_enabled():
        return route
    decorated: Callable[..., Any] = limiter.limit(_rate_limit_string())(route)
    return decorated


async def enforce_upload_size(upload: UploadFile, settings: Settings | None = None) -> bytes:
    """Read an UploadFile fully into memory, enforcing the size cap.

    Raises 413 if the payload exceeds the configured maximum. Returns the bytes
    so the caller can pass them straight into the conversion core via BytesIO.
    """
    settings = settings or get_settings()
    cap = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "upload_too_large",
                    "message": (f"Upload exceeds {settings.max_upload_mb} MB limit"),
                    "details": {"limit_bytes": cap},
                },
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def run_with_timeout(
    func: Callable[..., T],
    *args: Any,
    timeout: int | None = None,
    **kwargs: Any,
) -> T:
    """Run a synchronous function in a thread with a wall-clock timeout.

    Raises ``HTTPException(504)`` if the call exceeds the configured request
    timeout. The thread itself is not killable in Python; the watchdog returns a
    504 to the client and the worker continues until the call returns.
    """
    settings = get_settings()
    deadline = timeout if timeout is not None else settings.request_timeout_seconds
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(_EXECUTOR, lambda: func(*args, **kwargs))
    try:
        return await asyncio.wait_for(fut, timeout=deadline)
    except (TimeoutError, FuturesTimeoutError) as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "code": "request_timeout",
                "message": f"Conversion exceeded {deadline}s timeout",
                "details": None,
            },
        ) from exc


CoroFn = Callable[..., Awaitable[Any]]


__all__ = [
    "apply_rate_limit",
    "build_limiter",
    "enforce_upload_size",
    "rate_limit_enabled",
    "run_with_timeout",
]
