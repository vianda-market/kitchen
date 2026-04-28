"""
Unit tests for activation_service.maybe_activate_restaurant return contract.

maybe_activate_restaurant was changed (kitchen #172 follow-up) to return
dict | None instead of bool, so callers can surface the activated restaurant
info in API responses.

  - Returns None   when restaurant is not pending, archived, or prereqs unmet.
  - Returns {"id": UUID, "name": str}  when activation fires.

DB is mocked via unittest.mock.patch on `_check_restaurant_prereqs` and
`db.cursor()` so no live DB is needed.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.activation_service import maybe_activate_restaurant


def _make_prereqs(
    *,
    status: str = "pending",
    name: str = "Test Restaurant",
    is_archived: bool = False,
    has_plate_kitchen_days: bool = True,
    has_qr: bool = True,
) -> dict:
    return {
        "status": status,
        "name": name,
        "is_archived": is_archived,
        "has_plate_kitchen_days": has_plate_kitchen_days,
        "has_qr": has_qr,
    }


class TestMaybeActivateRestaurantReturnsNone:
    """Scenarios where activation does NOT fire → None returned."""

    def test_returns_none_when_already_active(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(status="active"),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert result is None

    def test_returns_none_when_archived(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(is_archived=True),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert result is None

    def test_returns_none_when_no_plate_kitchen_days(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(has_plate_kitchen_days=False),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert result is None

    def test_returns_none_when_no_qr(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(has_qr=False),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert result is None

    def test_returns_none_when_update_affects_zero_rows(self):
        """UPDATE matches 0 rows (race condition: already activated between check and UPDATE)."""
        restaurant_id = uuid4()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 0  # no row updated
        mock_db.cursor.return_value = mock_cursor

        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert result is None


class TestMaybeActivateRestaurantReturnsDict:
    """Activation fires → dict with id and name."""

    def test_returns_dict_when_activation_fires(self):
        restaurant_id = uuid4()
        restaurant_name = "La Cocina"
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 1  # activation row updated
        mock_db.cursor.return_value = mock_cursor

        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(name=restaurant_name),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)

        assert result is not None
        assert isinstance(result, dict)
        assert result["id"] == restaurant_id
        assert result["name"] == restaurant_name

    def test_returned_id_matches_input_restaurant_id(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 1
        mock_db.cursor.return_value = mock_cursor

        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(name="Some Name"),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)

        assert result is not None
        assert result["id"] is restaurant_id

    def test_returned_dict_has_id_and_name_keys(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 1
        mock_db.cursor.return_value = mock_cursor

        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(name="Mi Restaurante"),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)

        assert result is not None
        assert set(result.keys()) == {"id", "name"}


class TestMaybeActivateRestaurantReturnType:
    """Return type is always dict | None — never bool."""

    def test_not_bool_on_no_activation(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(status="active"),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert not isinstance(result, bool), "Return value must not be bool when activation does not fire"

    def test_not_bool_on_activation(self):
        restaurant_id = uuid4()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.rowcount = 1
        mock_db.cursor.return_value = mock_cursor

        with patch(
            "app.services.activation_service._check_restaurant_prereqs",
            return_value=_make_prereqs(),
        ):
            result = maybe_activate_restaurant(restaurant_id, mock_db)
        assert not isinstance(result, bool), "Return value must not be bool when activation fires"
