"""JSON API happy-path + error-envelope tests for every documented endpoint."""

from __future__ import annotations

import json

from archithreat import __version__

from .conftest import async_run


def _post(client, url, **kwargs):
    return async_run(client.post(url, **kwargs))


def _get(client, url, **kwargs):
    return async_run(client.get(url, **kwargs))


# ---------- /healthz ----------


def test_healthz(client) -> None:
    r = _get(client, "/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------- /readyz ----------


def test_readyz_ready(client) -> None:
    r = _get(client, "/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


# ---------- /version ----------


def test_version(client) -> None:
    r = _get(client, "/version")
    assert r.status_code == 200
    body = r.json()
    assert body["package"] == __version__
    assert "iriusrisk" in body["available_targets"]
    assert "threatdragon" in body["available_targets"]


# ---------- /api/v1/mapping/default ----------


def test_mapping_default_returns_yaml(client) -> None:
    r = _get(client, "/api/v1/mapping/default")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/yaml")
    assert "version:" in r.text
    assert "iriusrisk" in r.text


# ---------- /api/v1/mapping/validate ----------


def test_mapping_validate_default_is_valid(client) -> None:
    default_yaml = _get(client, "/api/v1/mapping/default").text
    r = _post(
        client,
        "/api/v1/mapping/validate",
        content=default_yaml.encode("utf-8"),
        headers={"content-type": "text/yaml"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["errors"] == []


def test_mapping_validate_invalid(client) -> None:
    r = _post(
        client,
        "/api/v1/mapping/validate",
        content=b"this: : not: yaml: [",
        headers={"content-type": "text/yaml"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["errors"]


def test_mapping_validate_missing_payload_envelope(client) -> None:
    r = _post(client, "/api/v1/mapping/validate")
    assert r.status_code == 400
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] in {"empty_body", "missing_mapping"}


# ---------- /api/v1/convert ----------


def test_convert_happy_path(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r = _post(client, "/api/v1/convert", files=files)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    cd = r.headers["content-disposition"]
    assert "attachment" in cd
    assert "lemonade_shop.drawio" in cd
    assert r.content.startswith(b"<?xml")
    assert b"mxfile" in r.content


def test_convert_threatdragon_target(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    data = {"target": "threatdragon"}
    r = _post(client, "/api/v1/convert", files=files, data=data)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    cd = r.headers["content-disposition"]
    assert "lemonade_shop.json" in cd
    assert b'"version": "2.0.0"' in r.content
    assert b"trust-boundary-box" in r.content


def test_convert_unknown_target(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("m.xml", lemonade_xml_bytes, "application/xml")}
    r = _post(client, "/api/v1/convert", files=files, data={"target": "no-such"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "unknown_target"


def test_mapping_default_threatdragon(client) -> None:
    r = _get(client, "/api/v1/mapping/default", params={"target": "threatdragon"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/yaml")
    assert b"target: threatdragon" in r.content


def test_convert_rejects_invalid_xml(client) -> None:
    files = {"model": ("bad.xml", b"<not-archimate/>", "application/xml")}
    r = _post(client, "/api/v1/convert", files=files)
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "parser_error"
    assert isinstance(body["error"]["message"], str)


def test_convert_with_invalid_mapping_envelope(client, lemonade_xml_bytes: bytes) -> None:
    files = {
        "model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml"),
        "mapping": ("m.yaml", b"target: iriusrisk\nversion: 1\n", "text/yaml"),
    }
    r = _post(client, "/api/v1/convert", files=files)
    # Missing required schema fields => mapping_invalid envelope.
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "mapping_invalid"


def test_convert_missing_model_returns_validation_envelope(client) -> None:
    r = _post(client, "/api/v1/convert", data={})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"


# ---------- /api/v1/inventory ----------


def test_inventory_json(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r = _post(client, "/api/v1/inventory", files=files)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = json.loads(r.text)
    assert "counts_by_type" in body
    assert "counts_by_layer" in body


def test_inventory_markdown_via_accept(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r = _post(
        client,
        "/api/v1/inventory",
        files=files,
        headers={"accept": "text/markdown"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# Inventory:")


def test_inventory_rejects_invalid_xml(client) -> None:
    files = {"model": ("bad.xml", b"<nope/>", "application/xml")}
    r = _post(client, "/api/v1/inventory", files=files)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "parser_error"
