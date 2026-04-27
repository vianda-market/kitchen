"""
Unit tests for activation_service.compute_restaurant_missing — pure logic only.

DB-touching functions (maybe_activate_restaurant, get_restaurant_readiness,
_check_restaurant_prereqs) are covered by Postman collections per kitchen testing
convention: services/ → Postman.

Pure function under test:
    compute_restaurant_missing(*, status, is_archived, has_plate_kitchen_days, has_qr)
    → list[str]  (subset of the four known keys)
"""

from app.services.activation_service import compute_restaurant_missing


class TestComputeRestaurantMissingAllMet:
    """All prereqs satisfied → empty missing list → is_ready_for_signup."""

    def test_all_met_returns_empty_list(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert result == []

    def test_empty_list_implies_ready(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert len(result) == 0


class TestComputeRestaurantMissingStatusNotActive:
    """status != 'active' → 'status_active' in missing."""

    def test_pending_status(self):
        result = compute_restaurant_missing(
            status="pending",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "status_active" in result

    def test_inactive_status(self):
        result = compute_restaurant_missing(
            status="inactive",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "status_active" in result

    def test_none_status(self):
        result = compute_restaurant_missing(
            status=None,
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "status_active" in result


class TestComputeRestaurantMissingArchived:
    """is_archived=True → 'not_archived' in missing."""

    def test_archived_restaurant(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=True,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "not_archived" in result

    def test_archived_does_not_add_status_active_when_active(self):
        """Archived + active status: only not_archived is in missing."""
        result = compute_restaurant_missing(
            status="active",
            is_archived=True,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "status_active" not in result
        assert "not_archived" in result


class TestComputeRestaurantMissingPlateKitchenDays:
    """No plate_kitchen_days → 'plate_kitchen_days' in missing."""

    def test_no_plate_kitchen_days(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=False,
            has_qr=True,
        )
        assert "plate_kitchen_days" in result

    def test_has_plate_kitchen_days_not_in_missing(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "plate_kitchen_days" not in result


class TestComputeRestaurantMissingQR:
    """No QR → 'qr' in missing."""

    def test_no_qr(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=False,
        )
        assert "qr" in result

    def test_has_qr_not_in_missing(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert "qr" not in result


class TestComputeRestaurantMissingMultiple:
    """Multiple missing prereqs accumulate correctly."""

    def test_all_missing(self):
        result = compute_restaurant_missing(
            status="pending",
            is_archived=True,
            has_plate_kitchen_days=False,
            has_qr=False,
        )
        assert set(result) == {"status_active", "not_archived", "plate_kitchen_days", "qr"}

    def test_only_pkd_and_qr_missing(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=False,
            has_qr=False,
        )
        assert set(result) == {"plate_kitchen_days", "qr"}

    def test_only_status_missing(self):
        result = compute_restaurant_missing(
            status="pending",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert result == ["status_active"]

    def test_pending_no_qr(self):
        result = compute_restaurant_missing(
            status="pending",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=False,
        )
        assert set(result) == {"status_active", "qr"}


class TestComputeRestaurantMissingReturnType:
    """Return type is always list[str]."""

    def test_returns_list(self):
        result = compute_restaurant_missing(
            status="active",
            is_archived=False,
            has_plate_kitchen_days=True,
            has_qr=True,
        )
        assert isinstance(result, list)

    def test_returns_list_when_all_missing(self):
        result = compute_restaurant_missing(
            status="pending",
            is_archived=True,
            has_plate_kitchen_days=False,
            has_qr=False,
        )
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)

    def test_known_keys_only(self):
        """Only keys from the defined set appear in missing."""
        known = {"status_active", "not_archived", "plate_kitchen_days", "qr"}
        for status in ("active", "pending", None):
            for archived in (True, False):
                for pkd in (True, False):
                    for qr in (True, False):
                        result = compute_restaurant_missing(
                            status=status,
                            is_archived=archived,
                            has_plate_kitchen_days=pkd,
                            has_qr=qr,
                        )
                        assert set(result).issubset(known), (
                            f"Unexpected keys for status={status}, archived={archived}, pkd={pkd}, qr={qr}: {result}"
                        )
