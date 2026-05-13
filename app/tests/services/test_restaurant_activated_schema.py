"""
Unit tests for RestaurantActivatedSchema and the response schemas that embed it.

Validates:
  - RestaurantActivatedSchema shape (id: UUID, name: str)
  - ViandaKitchenDayCreateResponseSchema wraps items + optional restaurant_activated
  - QRCodeResponseSchema has optional restaurant_activated field
  - restaurant_activated=None is serialized as explicit null (not omitted)
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.schemas.consolidated_schemas import (
    QRCodeResponseSchema,
    RestaurantActivatedSchema,
    ViandaKitchenDayCreateResponseSchema,
    ViandaKitchenDayResponseSchema,
)

# ---------------------------------------------------------------------------
# RestaurantActivatedSchema
# ---------------------------------------------------------------------------


class TestRestaurantActivatedSchema:
    def test_valid_construction(self):
        rid = uuid4()
        schema = RestaurantActivatedSchema(restaurant_id=rid, name="Cocina del Sol")
        assert schema.restaurant_id == rid
        assert schema.name == "Cocina del Sol"

    def test_requires_restaurant_id(self):
        with pytest.raises(ValidationError):
            RestaurantActivatedSchema(name="Only Name")  # type: ignore[call-arg]

    def test_requires_name(self):
        with pytest.raises(ValidationError):
            RestaurantActivatedSchema(restaurant_id=uuid4())  # type: ignore[call-arg]

    def test_serializes_uuid_as_string(self):
        rid = uuid4()
        schema = RestaurantActivatedSchema(restaurant_id=rid, name="Test")
        dumped = schema.model_dump(mode="json")
        assert isinstance(dumped["restaurant_id"], str)
        assert UUID(dumped["restaurant_id"]) == rid

    def test_name_is_str(self):
        schema = RestaurantActivatedSchema(restaurant_id=uuid4(), name="Nombre")
        assert isinstance(schema.name, str)


# ---------------------------------------------------------------------------
# ViandaKitchenDayCreateResponseSchema
# ---------------------------------------------------------------------------


def _make_vkd_response(**overrides) -> ViandaKitchenDayResponseSchema:
    defaults = {
        "vianda_kitchen_day_id": uuid4(),
        "vianda_id": uuid4(),
        "kitchen_day": "monday",
        "status": "active",
        "is_archived": False,
        "created_date": datetime.utcnow(),
        "modified_by": uuid4(),
        "modified_date": datetime.utcnow(),
    }
    defaults.update(overrides)
    return ViandaKitchenDayResponseSchema(**defaults)  # type: ignore[arg-type]


class TestViandaKitchenDayCreateResponseSchema:
    def test_valid_with_no_activation(self):
        item = _make_vkd_response()
        schema = ViandaKitchenDayCreateResponseSchema(items=[item], restaurant_activated=None)
        assert schema.restaurant_activated is None
        assert len(schema.items) == 1

    def test_valid_with_activation(self):
        item = _make_vkd_response()
        activated = RestaurantActivatedSchema(restaurant_id=uuid4(), name="My Restaurant")
        schema = ViandaKitchenDayCreateResponseSchema(items=[item], restaurant_activated=activated)
        assert schema.restaurant_activated is not None
        assert schema.restaurant_activated.name == "My Restaurant"

    def test_restaurant_activated_defaults_to_none(self):
        item = _make_vkd_response()
        schema = ViandaKitchenDayCreateResponseSchema(items=[item])
        assert schema.restaurant_activated is None

    def test_restaurant_activated_present_in_serialization_when_none(self):
        """restaurant_activated must appear as null in JSON, not be omitted."""
        item = _make_vkd_response()
        schema = ViandaKitchenDayCreateResponseSchema(items=[item])
        dumped = schema.model_dump(mode="json")
        assert "restaurant_activated" in dumped
        assert dumped["restaurant_activated"] is None

    def test_restaurant_activated_present_in_serialization_when_set(self):
        item = _make_vkd_response()
        rid = uuid4()
        activated = RestaurantActivatedSchema(restaurant_id=rid, name="Activated")
        schema = ViandaKitchenDayCreateResponseSchema(items=[item], restaurant_activated=activated)
        dumped = schema.model_dump(mode="json")
        assert dumped["restaurant_activated"] is not None
        assert UUID(dumped["restaurant_activated"]["restaurant_id"]) == rid

    def test_items_can_be_multiple(self):
        items = [_make_vkd_response() for _ in range(3)]
        schema = ViandaKitchenDayCreateResponseSchema(items=items)
        assert len(schema.items) == 3

    def test_items_empty_list_is_valid(self):
        schema = ViandaKitchenDayCreateResponseSchema(items=[])
        assert schema.items == []


# ---------------------------------------------------------------------------
# QRCodeResponseSchema — restaurant_activated field
# ---------------------------------------------------------------------------


def _make_qr_response(**overrides) -> QRCodeResponseSchema:
    defaults = {
        "qr_code_id": uuid4(),
        "restaurant_id": uuid4(),
        "qr_code_payload": "https://vianda.app/qr?id=abc&sig=deadbeef",
        "qr_code_image_url": "https://storage.googleapis.com/test/qr.png",
        "image_storage_path": "qr-codes/test/abc.png",
        "qr_code_checksum": None,
        "is_archived": False,
        "status": "active",
        "created_date": datetime.utcnow(),
        "modified_date": datetime.utcnow(),
    }
    defaults.update(overrides)
    return QRCodeResponseSchema(**defaults)  # type: ignore[arg-type]


class TestQRCodeResponseSchemaActivatedField:
    def test_restaurant_activated_defaults_to_none(self):
        schema = _make_qr_response()
        assert schema.restaurant_activated is None

    def test_restaurant_activated_present_in_json_as_null(self):
        """restaurant_activated must appear as null in JSON when not set."""
        schema = _make_qr_response()
        dumped = schema.model_dump(mode="json")
        assert "restaurant_activated" in dumped
        assert dumped["restaurant_activated"] is None

    def test_restaurant_activated_set_correctly(self):
        rid = uuid4()
        activated = RestaurantActivatedSchema(restaurant_id=rid, name="QR Restaurant")
        schema = _make_qr_response(restaurant_activated=activated)
        assert schema.restaurant_activated is not None
        assert schema.restaurant_activated.restaurant_id == rid
        assert schema.restaurant_activated.name == "QR Restaurant"

    def test_restaurant_activated_in_json_when_set(self):
        rid = uuid4()
        activated = RestaurantActivatedSchema(restaurant_id=rid, name="QR Restaurant")
        schema = _make_qr_response(restaurant_activated=activated)
        dumped = schema.model_dump(mode="json")
        assert dumped["restaurant_activated"] is not None
        assert UUID(dumped["restaurant_activated"]["restaurant_id"]) == rid

    def test_existing_qr_fields_unchanged(self):
        """Existing GET / list responses: restaurant_activated=null does not break anything."""
        qr_id = uuid4()
        restaurant_id = uuid4()
        schema = _make_qr_response(qr_code_id=qr_id, restaurant_id=restaurant_id)
        dumped = schema.model_dump(mode="json")
        assert UUID(dumped["qr_code_id"]) == qr_id
        assert UUID(dumped["restaurant_id"]) == restaurant_id
        assert dumped["restaurant_activated"] is None
