"""Tests for GET /api/v1/qr-codes/.../print HTML endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.schemas.consolidated_schemas import QRCodePrintContextSchema


@pytest.fixture
def mock_current_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "Internal",
        "role_name": "Admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_auth(mock_current_user):
    def _override_get_current_user():
        return mock_current_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_current_user, None)


def _sample_print_ctx() -> QRCodePrintContextSchema:
    return QRCodePrintContextSchema(
        qr_code_id=uuid4(),
        restaurant_id=uuid4(),
        restaurant_name="Test Bistro",
        country_code="US",
        street_type="St",
        street_name="Main",
        building_number="10",
        city="New York",
        province="NY",
        postal_code="10001",
        country_name="United States",
        image_storage_path="qrcodes/x/y.png",
    )


@patch("app.services.qr_code_print_service.load_qr_png_base64", return_value="Zm9v")
@patch("app.routes.qr_code.get_qr_code_print_context_by_id")
def test_print_by_qr_code_id_returns_html(
    mock_get_ctx, _mock_load, client_with_auth
):
    ctx = _sample_print_ctx()
    mock_get_ctx.return_value = ctx
    r = client_with_auth.get(f"/api/v1/qr-codes/{ctx.qr_code_id}/print")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Test Bistro" in r.text
    assert "data:image/png;base64,Zm9v" in r.text


@patch("app.services.qr_code_print_service.load_qr_png_base64", return_value="Zm9v")
@patch("app.routes.qr_code.get_qr_code_print_context_by_id")
def test_print_autoprint_true_includes_onload_print(
    mock_get_ctx, _mock_load, client_with_auth
):
    ctx = _sample_print_ctx()
    mock_get_ctx.return_value = ctx
    r = client_with_auth.get(
        f"/api/v1/qr-codes/{ctx.qr_code_id}/print",
        params={"autoprint": "true"},
    )
    assert r.status_code == 200
    assert "window.onload" in r.text
    assert "window.print()" in r.text


@patch("app.services.qr_code_print_service.load_qr_png_base64", return_value="Zm9v")
@patch("app.routes.qr_code.get_qr_code_print_context_by_id")
def test_print_autoprint_one_does_not_autoprint(
    mock_get_ctx, _mock_load, client_with_auth
):
    ctx = _sample_print_ctx()
    mock_get_ctx.return_value = ctx
    r = client_with_auth.get(
        f"/api/v1/qr-codes/{ctx.qr_code_id}/print",
        params={"autoprint": "1"},
    )
    assert r.status_code == 200
    assert "window.onload" not in r.text


@patch("app.services.qr_code_print_service.load_qr_png_base64", return_value="Zm9v")
@patch("app.routes.qr_code.get_qr_code_print_context_by_id")
def test_print_autoprint_yes_does_not_autoprint(
    mock_get_ctx, _mock_load, client_with_auth
):
    ctx = _sample_print_ctx()
    mock_get_ctx.return_value = ctx
    r = client_with_auth.get(
        f"/api/v1/qr-codes/{ctx.qr_code_id}/print",
        params={"autoprint": "yes"},
    )
    assert r.status_code == 200
    assert "window.onload" not in r.text


@patch("app.routes.qr_code.get_qr_code_print_context_by_id", return_value=None)
def test_print_not_found_returns_404(_mock_get_ctx, client_with_auth):
    qid = uuid4()
    r = client_with_auth.get(f"/api/v1/qr-codes/{qid}/print")
    assert r.status_code == 404


@patch("app.services.qr_code_print_service.load_qr_png_base64", return_value="Zm9v")
@patch("app.routes.qr_code.get_qr_code_print_context_by_id")
@patch("app.routes.qr_code.qr_code_service")
@patch("app.routes.qr_code.restaurant_service")
def test_print_by_restaurant_id_returns_html(
    mock_restaurant_svc, mock_qr_svc, mock_get_ctx, _mock_load, client_with_auth
):
    ctx = _sample_print_ctx()
    rid = ctx.restaurant_id
    mock_restaurant_svc.get_by_id.return_value = MagicMock(restaurant_id=rid)
    mock_qr_svc.get_by_field.return_value = MagicMock(
        qr_code_id=ctx.qr_code_id, is_archived=False
    )
    mock_get_ctx.return_value = ctx
    r = client_with_auth.get(f"/api/v1/qr-codes/restaurant/{rid}/print")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Test Bistro" in r.text


@patch("app.routes.qr_code.restaurant_service")
def test_print_by_restaurant_no_restaurant_404(mock_rs, client_with_auth):
    mock_rs.get_by_id.return_value = None
    r = client_with_auth.get(f"/api/v1/qr-codes/restaurant/{uuid4()}/print")
    assert r.status_code == 404


@patch("app.routes.qr_code.qr_code_service")
@patch("app.routes.qr_code.restaurant_service")
def test_print_by_restaurant_no_qr_404(mock_rs, mock_qr, client_with_auth):
    mock_rs.get_by_id.return_value = MagicMock()
    mock_qr.get_by_field.return_value = None
    r = client_with_auth.get(f"/api/v1/qr-codes/restaurant/{uuid4()}/print")
    assert r.status_code == 404


def test_autoprint_enabled_helper():
    from app.services.qr_code_print_service import autoprint_enabled

    assert autoprint_enabled(None) is False
    assert autoprint_enabled("true") is True
    assert autoprint_enabled("TRUE") is True
    assert autoprint_enabled("1") is False
    assert autoprint_enabled("yes") is False
