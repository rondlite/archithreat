"""HTMX UI tests: page renders and partial swap shape."""

from __future__ import annotations

from .conftest import async_run


def _get(client, url, **kw):
    return async_run(client.get(url, **kw))


def _post(client, url, **kw):
    return async_run(client.post(url, **kw))


def test_index_renders(client) -> None:
    r = _get(client, "/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "archithreat" in r.text
    # Privacy panel is on every page.
    assert "What this does to your data" in r.text
    assert "github.com/rondlite/archithreat/blob/main/docs/privacy.md" in r.text


def test_convert_page_renders(client) -> None:
    r = _get(client, "/convert")
    assert r.status_code == 200
    assert "<form" in r.text
    assert 'name="model"' in r.text
    assert 'id="result-panel"' in r.text


def test_inventory_page_renders(client) -> None:
    r = _get(client, "/inventory")
    assert r.status_code == 200
    assert 'name="model"' in r.text


def test_validate_mapping_page_renders(client) -> None:
    r = _get(client, "/validate-mapping")
    assert r.status_code == 200
    assert 'name="mapping"' in r.text or 'name="mapping_text"' in r.text


def test_ui_convert_returns_result_partial(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r = _post(client, "/ui/convert", files=files)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    # hx-target swap shape: returned partial replaces the #result-panel section.
    assert 'id="result-panel"' in r.text
    assert "Conversion complete" in r.text
    assert 'download="lemonade_shop.drawio"' in r.text


def test_ui_convert_error_partial(client) -> None:
    files = {"model": ("bad.xml", b"<nope/>", "application/xml")}
    r = _post(client, "/ui/convert", files=files)
    assert r.status_code == 400
    assert 'id="result-panel"' in r.text
    assert "Error" in r.text


def test_ui_inventory_returns_result_partial(client, lemonade_xml_bytes: bytes) -> None:
    files = {"model": ("lemonade_shop.xml", lemonade_xml_bytes, "application/xml")}
    r = _post(client, "/ui/inventory", files=files)
    assert r.status_code == 200
    assert 'id="result-panel"' in r.text
    assert "Inventory report" in r.text


def test_ui_validate_mapping_partial_text_input(client) -> None:
    # Default mapping, posted as text -> valid.
    default_yaml = _get(client, "/api/v1/mapping/default").text
    r = _post(client, "/ui/validate-mapping", data={"mapping_text": default_yaml})
    assert r.status_code == 200
    assert 'id="result-panel"' in r.text
    assert "Mapping is valid" in r.text
