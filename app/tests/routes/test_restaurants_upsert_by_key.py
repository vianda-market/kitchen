"""
Tests for restaurant upsert:
- PUT /restaurants/by-key: insert, update, idempotency.
- PUT /restaurants/by-key: auth guard (non-employee returns 403).
- PUT /restaurants/by-key: immutable institution_id on update.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.services.crud_service import restaurant_service

# Needs live Postgres (TestClient triggers DB pool init via unmocked code paths).
# Excluded from unit test job by -m "not database"; runs in acceptance (Newman).
pytestmark = pytest.mark.database


@pytest.fixture
def mock_employee_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "internal",
        "role_name": "admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_employee(mock_employee_user):
    def _override_get_employee_user():
        return mock_employee_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)


def _make_restaurant_dto(*, canonical_key=None):
    """Build a minimal mock restaurant DTO."""
    rid = uuid4()
    iid = uuid4()
    eid = uuid4()
    aid = uuid4()
    mbid = uuid4()
    currency_id = uuid4()

    m = MagicMock()
    m.restaurant_id = rid
    m.institution_id = iid
    m.institution_entity_id = eid
    m.address_id = aid
    m.name = "Cambalache"
    m.cuisine_id = None
    m.pickup_instructions = None
    m.tagline = None
    m.tagline_i18n = None
    m.is_featured = False
    m.cover_image_url = None
    m.average_rating = None
    m.review_count = 0
    m.verified_badge = False
    m.spotlight_label = None
    m.spotlight_label_i18n = None
    m.member_perks = None
    m.member_perks_i18n = None
    m.require_kiosk_code_verification = False
    m.is_archived = False
    m.status = "pending"
    m.canonical_key = canonical_key
    m.created_date = "2026-01-01T00:00:00Z"
    m.modified_date = "2026-01-01T00:00:00Z"
    m.created_by = None
    m.modified_by = mbid

    # _restaurant_to_response calls model_dump() to build the response dict.
    # Return a proper dict so RestaurantResponseSchema can be constructed.
    m.model_dump.return_value = {
        "restaurant_id": rid,
        "institution_id": iid,
        "institution_entity_id": eid,
        "address_id": aid,
        "currency_metadata_id": currency_id,
        "name": "Cambalache",
        "cuisine_id": None,
        "cuisine_name": None,
        "pickup_instructions": None,
        "tagline": None,
        "tagline_i18n": None,
        "is_featured": False,
        "cover_image_url": None,
        "average_rating": None,
        "review_count": 0,
        "verified_badge": False,
        "spotlight_label": None,
        "spotlight_label_i18n": None,
        "member_perks": None,
        "member_perks_i18n": None,
        "require_kiosk_code_verification": False,
        "is_archived": False,
        "status": "pending",
        "canonical_key": canonical_key,
        "created_date": "2026-01-01T00:00:00Z",
        "modified_date": "2026-01-01T00:00:00Z",
        "is_ready_for_signup": None,
        "missing": None,
    }
    return m


def _make_entity_mock(currency_metadata_id=None):
    m = MagicMock()
    m.currency_metadata_id = currency_metadata_id or uuid4()
    return m


def _make_credit_currency_mock():
    m = MagicMock()
    m.currency_code = "ARS"
    return m


def _valid_upsert_payload(*, canonical_key="E2E_RESTAURANT_CAMBALACHE"):
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "institution_id": str(uuid4()),
        "institution_entity_id": str(uuid4()),
        "address_id": str(uuid4()),
        "name": "Cambalache",
    }


class TestRestaurantUpsertByKey:
    """PUT /api/v1/restaurants/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.routes.restaurant.find_restaurant_by_canonical_key")
    @patch("app.routes.restaurant.institution_entity_service")
    @patch("app.routes.restaurant.credit_currency_service")
    @patch.object(restaurant_service, "create")
    @patch("app.routes.restaurant.restaurant_balance_service")
    def test_upsert_inserts_when_key_not_found(
        self,
        mock_balance_service,
        mock_create,
        mock_credit_currency_service,
        mock_entity_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /restaurants/by-key with a new canonical_key inserts a new restaurant and returns 200."""
        mock_find.return_value = None  # key does not exist yet

        entity_mock = _make_entity_mock()
        mock_entity_service.get_by_id.return_value = entity_mock

        currency_mock = _make_credit_currency_mock()
        mock_credit_currency_service.get_by_id.return_value = currency_mock

        created = _make_restaurant_dto(canonical_key="E2E_RESTAURANT_CAMBALACHE")
        mock_create.return_value = created

        mock_balance_service.create_balance_record.return_value = True

        payload = _valid_upsert_payload(canonical_key="E2E_RESTAURANT_CAMBALACHE")

        with (
            patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant", return_value=uuid4()),
            patch("app.services.address_service.update_address_type_from_linkages"),
        ):
            resp = client_with_employee.put("/api/v1/restaurants/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "restaurant_id" in data
        mock_create.assert_called_once()

    @patch("app.routes.restaurant.find_restaurant_by_canonical_key")
    @patch.object(restaurant_service, "update")
    def test_upsert_updates_when_key_exists(self, mock_update, mock_find, client_with_employee):
        """PUT /restaurants/by-key with an existing canonical_key updates the restaurant and returns 200."""
        existing = _make_restaurant_dto(canonical_key="E2E_RESTAURANT_CAMBALACHE")
        mock_find.return_value = existing

        updated = _make_restaurant_dto(canonical_key="E2E_RESTAURANT_CAMBALACHE")
        updated.name = "Cambalache Renovado"
        mock_update.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_RESTAURANT_CAMBALACHE")
        payload["name"] = "Cambalache Renovado"

        with patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant", return_value=uuid4()):
            resp = client_with_employee.put("/api/v1/restaurants/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        # canonical_key, institution_id, institution_entity_id must not be passed to update
        update_payload = mock_update.call_args[0][1]
        assert "canonical_key" not in update_payload
        assert "institution_id" not in update_payload
        assert "institution_entity_id" not in update_payload

    @patch("app.routes.restaurant.find_restaurant_by_canonical_key")
    @patch("app.routes.restaurant.institution_entity_service")
    @patch("app.routes.restaurant.credit_currency_service")
    @patch.object(restaurant_service, "create")
    @patch("app.routes.restaurant.restaurant_balance_service")
    def test_upsert_idempotent_same_payload_twice(
        self,
        mock_balance_service,
        mock_create,
        mock_credit_currency_service,
        mock_entity_service,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload should behave consistently."""
        mock_find.return_value = None  # First call: insert
        entity_mock = _make_entity_mock()
        mock_entity_service.get_by_id.return_value = entity_mock
        currency_mock = _make_credit_currency_mock()
        mock_credit_currency_service.get_by_id.return_value = currency_mock
        created = _make_restaurant_dto(canonical_key="E2E_RESTAURANT_IDEMPOTENT")
        mock_create.return_value = created
        mock_balance_service.create_balance_record.return_value = True

        payload = _valid_upsert_payload(canonical_key="E2E_RESTAURANT_IDEMPOTENT")

        with (
            patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant", return_value=uuid4()),
            patch("app.services.address_service.update_address_type_from_linkages"),
        ):
            resp1 = client_with_employee.put("/api/v1/restaurants/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created
        with (
            patch.object(restaurant_service, "update") as mock_update,
            patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant", return_value=uuid4()),
        ):
            mock_update.return_value = created
            resp2 = client_with_employee.put("/api/v1/restaurants/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    def test_upsert_requires_employee_auth(self):
        """PUT /restaurants/by-key without employee auth returns 403."""

        def _override_get_employee_user():
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Forbidden")

        def _override_oauth2_scheme():
            return "test-token"

        app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
        app.dependency_overrides[get_employee_user] = _override_get_employee_user
        try:
            with TestClient(app) as c:
                payload = _valid_upsert_payload()
                resp = c.put("/api/v1/restaurants/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)

    def test_upsert_rejects_supplier_role(self):
        """PUT /restaurants/by-key with a supplier (non-internal) token returns 403."""
        supplier_user = {
            "user_id": str(uuid4()),
            "role_type": "supplier",
            "role_name": "admin",
            "institution_id": str(uuid4()),
        }

        def _override_get_current_user():
            return supplier_user

        def _override_oauth2_scheme():
            return "supplier-test-token"

        app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
        app.dependency_overrides[get_current_user] = _override_get_current_user
        try:
            with TestClient(app) as c:
                payload = _valid_upsert_payload()
                resp = c.put("/api/v1/restaurants/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.routes.restaurant.find_restaurant_by_canonical_key")
    @patch.object(restaurant_service, "update")
    def test_upsert_institution_id_immutable_on_update(self, mock_update, mock_find, client_with_employee):
        """PUT /restaurants/by-key update path must not pass institution_id to restaurant_service.update.

        institution_id is immutable after creation.  Even if the caller sends a
        different institution_id in the payload, it must be silently stripped and
        the existing institution association preserved.
        """
        original_institution_id = uuid4()
        existing = _make_restaurant_dto(canonical_key="E2E_RESTAURANT_IMMUTABLE_TEST")
        existing.institution_id = original_institution_id
        mock_find.return_value = existing

        updated = _make_restaurant_dto(canonical_key="E2E_RESTAURANT_IMMUTABLE_TEST")
        mock_update.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_RESTAURANT_IMMUTABLE_TEST")
        # Caller sends a different institution_id — must be ignored
        payload["institution_id"] = str(uuid4())

        with patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant", return_value=uuid4()):
            resp = client_with_employee.put("/api/v1/restaurants/by-key", json=payload)

        assert resp.status_code == 200
        update_payload = mock_update.call_args[0][1]
        assert "institution_id" not in update_payload, (
            "institution_id must be stripped from the update payload — it is immutable after creation"
        )
