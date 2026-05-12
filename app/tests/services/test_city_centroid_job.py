"""
Tests for app.services.cron.city_centroid_job.weekly_entry().

All test cases use mocks — repo convention for services/ is to patch db
calls rather than exercise a real DB (see test_city_map_service.py for
the established pattern in this directory).

Logical cases covered:
1. Happy path: 2 cities, 3 restaurants each, correct AVG centroid stored.
2. Empty city: city with no active geocoded restaurants is absent from the
   SELECT result and its centroid columns are left untouched.
3. Inactive/archived restaurants excluded: filtering happens in SQL (the
   SELECT only returns active rows); test verifies restaurants absent from
   centroid rows do not affect the result.
4. No geocoded address excluded: same as above — SQL WHERE filters them.
5. Idempotency: two successive calls with the same data produce the same
   centroid values; centroid_computed_at would advance (handled by DB now()).
6. NUMERIC(9,6) precision: coords with >6 decimal places are rounded before
   the UPDATE call.
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

CITY_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CITY_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CITY_C = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")  # empty city (no restaurants)


def _make_centroid_row(city_id: UUID, lat: float, lng: float, count: int = 3) -> dict[str, Any]:
    return {
        "city_metadata_id": city_id,
        "centroid_lat": Decimal(str(lat)),
        "centroid_lng": Decimal(str(lng)),
        "restaurant_count": count,
    }


def _make_city_id_row(city_id: UUID) -> dict[str, Any]:
    return {"city_metadata_id": city_id}


def _run_with_mocks(centroid_rows: list, all_city_rows: list):
    """
    Helper: patch db_read to return centroid_rows for the AVG query and
    all_city_rows for the count query; patch get_db_connection_context with
    a mock connection whose cursor supports execute().
    Returns (result, mock_cursor).
    """
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    # db_read is called twice: first for centroid SELECT, then for all-cities count
    db_read_side_effects = [centroid_rows, all_city_rows]

    with (
        patch("app.services.cron.city_centroid_job.get_db_connection_context", return_value=mock_db),
        patch("app.services.cron.city_centroid_job.db_read", side_effect=db_read_side_effects) as mock_read,
    ):
        from app.services.cron.city_centroid_job import weekly_entry

        result = weekly_entry()

    return result, mock_cursor, mock_read


class TestWeeklyEntryHappyPath:
    """Two cities with known coordinates — centroid should be exact AVG."""

    def test_cities_updated_count(self):
        centroid_rows = [
            _make_centroid_row(CITY_A, lat=-34.0, lng=-58.0, count=3),
            _make_centroid_row(CITY_B, lat=40.0, lng=-73.0, count=3),
        ]
        all_cities = [_make_city_id_row(CITY_A), _make_city_id_row(CITY_B)]

        result, _, _ = _run_with_mocks(centroid_rows, all_cities)

        assert result["success"] is True
        assert result["cities_updated"] == 2

    def test_cities_skipped_zero_when_all_have_restaurants(self):
        centroid_rows = [
            _make_centroid_row(CITY_A, lat=-34.0, lng=-58.0),
            _make_centroid_row(CITY_B, lat=40.0, lng=-73.0),
        ]
        all_cities = [_make_city_id_row(CITY_A), _make_city_id_row(CITY_B)]

        result, _, _ = _run_with_mocks(centroid_rows, all_cities)

        assert result["cities_skipped_no_restaurants"] == 0

    def test_update_called_once_per_city(self):
        centroid_rows = [
            _make_centroid_row(CITY_A, lat=-34.0, lng=-58.0),
            _make_centroid_row(CITY_B, lat=40.0, lng=-73.0),
        ]
        all_cities = [_make_city_id_row(CITY_A), _make_city_id_row(CITY_B)]

        _, mock_cursor, _ = _run_with_mocks(centroid_rows, all_cities)

        # cursor.execute called once per city
        assert mock_cursor.execute.call_count == 2

    def test_update_args_contain_correct_rounded_coords(self):
        centroid_rows = [
            _make_centroid_row(CITY_A, lat=-34.123456, lng=-58.654321),
        ]
        all_cities = [_make_city_id_row(CITY_A)]

        _, mock_cursor, _ = _run_with_mocks(centroid_rows, all_cities)

        executed_args = mock_cursor.execute.call_args[0][1]  # (sql, params) tuple
        lat_arg, lng_arg, city_arg = executed_args
        assert lat_arg == round(-34.123456, 6)
        assert lng_arg == round(-58.654321, 6)
        assert city_arg == str(CITY_A)

    def test_result_has_required_keys(self):
        centroid_rows = [_make_centroid_row(CITY_A, -34.0, -58.0)]
        all_cities = [_make_city_id_row(CITY_A)]

        result, _, _ = _run_with_mocks(centroid_rows, all_cities)

        assert "cities_updated" in result
        assert "cities_skipped_no_restaurants" in result
        assert "timestamp" in result
        assert "success" in result


class TestEmptyCity:
    """City C has no active geocoded restaurants — it is absent from centroid_rows."""

    def test_skipped_count_reflects_cities_without_restaurants(self):
        # Only CITY_A and CITY_B return from the AVG query; CITY_C has nothing
        centroid_rows = [
            _make_centroid_row(CITY_A, -34.0, -58.0),
            _make_centroid_row(CITY_B, 40.0, -73.0),
        ]
        all_cities = [_make_city_id_row(CITY_A), _make_city_id_row(CITY_B), _make_city_id_row(CITY_C)]

        result, _, _ = _run_with_mocks(centroid_rows, all_cities)

        assert result["cities_updated"] == 2
        assert result["cities_skipped_no_restaurants"] == 1

    def test_no_update_issued_for_city_with_no_restaurants(self):
        # CITY_C absent from centroid rows → no execute() call for it
        centroid_rows = [_make_centroid_row(CITY_A, -34.0, -58.0)]
        all_cities = [_make_city_id_row(CITY_A), _make_city_id_row(CITY_C)]

        _, mock_cursor, _ = _run_with_mocks(centroid_rows, all_cities)

        # Only one execute() — for CITY_A; CITY_C should not appear
        assert mock_cursor.execute.call_count == 1
        executed_city_ids = [c[0][1][2] for c in mock_cursor.execute.call_args_list]
        assert str(CITY_C) not in executed_city_ids


class TestExclusionFiltering:
    """
    Archived restaurants and un-geocoded addresses are excluded at the SQL
    level (WHERE clause in _QUERY_CITY_CENTROIDS). These tests verify that
    the rows returned by db_read (after SQL filtering) are the only ones
    included in the centroid computation — the job does not re-filter in Python.
    """

    def test_only_active_rows_contribute_to_centroid(self):
        """Centroid row already reflects only active/geocoded restaurants (SQL-filtered)."""
        # SQL would average 2 active restaurants at (-34.0, -58.0) and (-34.2, -58.2);
        # the archived one at (-35.0, -59.0) is excluded by the WHERE clause.
        avg_lat = (-34.0 + -34.2) / 2  # = -34.1
        avg_lng = (-58.0 + -58.2) / 2  # = -58.1
        centroid_rows = [_make_centroid_row(CITY_A, avg_lat, avg_lng, count=2)]
        all_cities = [_make_city_id_row(CITY_A)]

        _, mock_cursor, _ = _run_with_mocks(centroid_rows, all_cities)

        executed_args = mock_cursor.execute.call_args[0][1]
        lat_arg, lng_arg, _ = executed_args
        assert lat_arg == round(avg_lat, 6)
        assert lng_arg == round(avg_lng, 6)

    def test_city_absent_when_all_restaurants_archived(self):
        """If all restaurants for a city are archived, city absent from centroid_rows → skipped."""
        # CITY_B has no active restaurants → SQL returns nothing for it
        centroid_rows = [_make_centroid_row(CITY_A, -34.0, -58.0)]
        all_cities = [_make_city_id_row(CITY_A), _make_city_id_row(CITY_B)]

        result, _, _ = _run_with_mocks(centroid_rows, all_cities)

        assert result["cities_updated"] == 1
        assert result["cities_skipped_no_restaurants"] == 1


class TestIdempotency:
    """Two successive calls with the same centroid data produce the same UPDATE args."""

    def test_second_call_produces_same_centroid_values(self):
        centroid_rows = [_make_centroid_row(CITY_A, -34.123456, -58.654321)]
        all_cities = [_make_city_id_row(CITY_A)]

        result1, cursor1, _ = _run_with_mocks(centroid_rows, all_cities)

        centroid_rows2 = [_make_centroid_row(CITY_A, -34.123456, -58.654321)]
        all_cities2 = [_make_city_id_row(CITY_A)]
        result2, cursor2, _ = _run_with_mocks(centroid_rows2, all_cities2)

        args1 = cursor1.execute.call_args[0][1]
        args2 = cursor2.execute.call_args[0][1]

        assert args1[0] == args2[0]  # lat identical
        assert args1[1] == args2[1]  # lng identical
        assert args1[2] == args2[2]  # city_id identical
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["cities_updated"] == result2["cities_updated"]


class TestNumericPrecision:
    """Coordinates with >6 decimal places are rounded to 6 before the UPDATE."""

    def test_more_than_6_decimal_places_rounded(self):
        # AVG may yield many decimal places
        centroid_rows = [_make_centroid_row(CITY_A, lat=-34.1234567890, lng=-58.9876543210)]
        all_cities = [_make_city_id_row(CITY_A)]

        _, mock_cursor, _ = _run_with_mocks(centroid_rows, all_cities)

        lat_arg, lng_arg, _ = mock_cursor.execute.call_args[0][1]
        # Must round to exactly 6 places
        assert lat_arg == round(-34.1234567890, 6)
        assert lng_arg == round(-58.9876543210, 6)
        # Should have at most 6 decimal places
        assert len(str(abs(lat_arg)).split(".")[-1]) <= 6
        assert len(str(abs(lng_arg)).split(".")[-1]) <= 6


class TestErrorHandling:
    """On exception the job returns success=False without re-raising."""

    def test_db_error_returns_failure_dict(self):
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)

        with (
            patch("app.services.cron.city_centroid_job.get_db_connection_context", return_value=mock_db),
            patch("app.services.cron.city_centroid_job.db_read", side_effect=RuntimeError("boom")),
        ):
            from app.services.cron import city_centroid_job

            result = city_centroid_job.weekly_entry()

        assert result["success"] is False
        assert "error" in result
        assert "boom" in result["error"]
        assert "timestamp" in result

    def test_no_cities_returns_success_with_zero_updated(self):
        """Empty DB (no cities, no restaurants) is a valid no-op run."""
        centroid_rows: list = []
        all_cities: list = []

        result, _, _ = _run_with_mocks(centroid_rows, all_cities)

        assert result["success"] is True
        assert result["cities_updated"] == 0
        assert result["cities_skipped_no_restaurants"] == 0
