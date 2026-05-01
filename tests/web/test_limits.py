"""Upload size + rate limit enforcement."""

from __future__ import annotations

from .conftest import async_run


def _post(client, url, **kw):
    return async_run(client.post(url, **kw))


def test_upload_too_large_returns_413(make_client) -> None:
    # 1 MB cap, 2 MB payload.
    client = make_client(ARCHITHREAT_MAX_UPLOAD_MB="1")
    big = b"x" * (2 * 1024 * 1024)
    files = {"model": ("big.xml", big, "application/xml")}
    r = _post(client, "/api/v1/convert", files=files)
    assert r.status_code == 413
    body = r.json()
    assert body["error"]["code"] == "upload_too_large"
    assert "1 MB" in body["error"]["message"]


def test_rate_limit_blocks_second_request(make_client, lemonade_xml_bytes: bytes) -> None:
    client = make_client(ARCHITHREAT_RATE_LIMIT_PER_MINUTE="1")
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r1 = async_run(client.get("/healthz"))
    assert r1.status_code == 200
    r2 = _post(client, "/api/v1/convert", files=files)
    assert r2.status_code == 429
    body = r2.json()
    assert body["error"]["code"] == "rate_limited"


def test_rate_limit_disabled_when_zero(make_client) -> None:
    client = make_client(ARCHITHREAT_RATE_LIMIT_PER_MINUTE="0")
    for _ in range(5):
        r = async_run(client.get("/healthz"))
        assert r.status_code == 200
