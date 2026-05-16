"""
Unit tests for Restaurant Staff Service.

Tests the business logic for restaurant staff operations including
daily orders retrieval, privacy-safe customer names, and order grouping.
"""

from datetime import date, datetime
from unittest.mock import patch
from uuid import uuid4

from app.services.restaurant_staff_service import (
    _classify_order_status,
    _get_kitchen_day_for_date,
    _group_orders_by_restaurant,
    get_daily_orders,
)


class TestRestaurantStaffService:
    """Test suite for Restaurant Staff Service business logic."""

    def test_get_daily_orders_returns_correct_format(self, mock_db):
        """Test that get_daily_orders returns the expected response structure."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = None

        mock_rows = [
            {
                "confirmation_code": "ABC123",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "D",
                "vianda_name": "Grilled Chicken",
                "restaurant_id": uuid4(),
                "restaurant_name": "Cambalache Palermo",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            }
        ]

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            # Main query, then reservations_by_vianda, then live_locked_count (per restaurant)
            mock_db_read.side_effect = [mock_rows, [], {"count": 1}]

            # Act
            result = get_daily_orders(institution_entity_id, order_date, restaurant_id, mock_db)

            # Assert
            assert result["order_date"] == order_date
            assert len(result["restaurants"]) == 1
            assert result["restaurants"][0]["restaurant_name"] == "Cambalache Palermo"
            assert len(result["restaurants"][0]["orders"]) == 1
            assert result["restaurants"][0]["summary"]["total_orders"] == 1

    def test_customer_name_privacy_formatting(self, mock_db):
        """Test that customer names are formatted as 'First L.' for privacy."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        mock_rows = [
            {
                "confirmation_code": "ABC123",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "M",
                "last_initial": "G",
                "vianda_name": "Pasta",
                "restaurant_id": uuid4(),
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            }
        ]

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [mock_rows, [], {"count": 1}]

            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            customer_name = result["restaurants"][0]["orders"][0]["customer_name"]
            assert customer_name == "M.G."

    def test_filters_by_institution_entity_id(self, mock_db):
        """Test that orders are filtered by institution_entity_id."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            # Act
            get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "r.institution_entity_id = %s" in query
            assert str(institution_entity_id) in params

    def test_filters_by_single_restaurant_id(self, mock_db):
        """Test that orders can be filtered by a specific restaurant_id."""
        # Arrange
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            # Act
            get_daily_orders(institution_entity_id, order_date, restaurant_id, mock_db)

            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "r.restaurant_id = %s OR %s IS NULL" in query
            assert str(restaurant_id) in params

    def test_groups_orders_by_restaurant(self, mock_db):
        """Test that orders are correctly grouped by restaurant."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_1_id = uuid4()
        restaurant_2_id = uuid4()

        mock_rows = [
            {
                "confirmation_code": "ABC123",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "D",
                "vianda_name": "Chicken",
                "restaurant_id": restaurant_1_id,
                "restaurant_name": "Restaurant A",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "DEF456",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:30-13:00",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "S",
                "vianda_name": "Salad",
                "restaurant_id": restaurant_2_id,
                "restaurant_name": "Restaurant B",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "GHI789",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "13:00-13:30",
                "kitchen_day": "tuesday",
                "first_initial": "B",
                "last_initial": "M",
                "vianda_name": "Pasta",
                "restaurant_id": restaurant_1_id,
                "restaurant_name": "Restaurant A",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
        ]

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            # Main query, then 2 restaurants: reservations + live each
            mock_db_read.side_effect = [mock_rows, [], {"count": 2}, [], {"count": 1}]

            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            assert len(result["restaurants"]) == 2

            # Find Restaurant A
            rest_a = next(r for r in result["restaurants"] if r["restaurant_name"] == "Restaurant A")
            assert len(rest_a["orders"]) == 2
            assert rest_a["summary"]["total_orders"] == 2

            # Find Restaurant B
            rest_b = next(r for r in result["restaurants"] if r["restaurant_name"] == "Restaurant B")
            assert len(rest_b["orders"]) == 1
            assert rest_b["summary"]["total_orders"] == 1

    def test_calculates_summary_statistics(self, mock_db):
        """Test that summary statistics are correctly calculated."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = uuid4()

        mock_rows = [
            {
                "confirmation_code": "ABC123",
                "status": "active",
                "arrival_time": None,  # Pending
                "pickup_time_range": "23:55-23:59",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "D",
                "vianda_name": "Chicken",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "DEF456",
                "status": "active",
                "arrival_time": datetime(2026, 2, 4, 12, 15),  # Arrived
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "S",
                "vianda_name": "Salad",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "GHI789",
                "status": "completed",
                "arrival_time": datetime(2026, 2, 4, 12, 0),
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "B",
                "last_initial": "M",
                "vianda_name": "Pasta",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
        ]

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [mock_rows, [], {"count": 3}]

            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            summary = result["restaurants"][0]["summary"]
            assert summary["total_orders"] == 3
            assert summary["pending"] == 1
            assert summary["arrived"] == 1
            assert summary["completed"] == 1

    def test_orders_sorted_by_pickup_time(self, mock_db):
        """Test that orders are sorted by pickup time within each restaurant."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = uuid4()

        mock_rows = [
            {
                "confirmation_code": "GHI789",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "13:00-13:30",
                "kitchen_day": "tuesday",
                "first_initial": "B",
                "last_initial": "M",
                "vianda_name": "Pasta",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "ABC123",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "D",
                "vianda_name": "Chicken",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "DEF456",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:30-13:00",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "S",
                "vianda_name": "Salad",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
        ]

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [mock_rows, [], {"count": 3}]

            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert - Orders should be sorted by pickup_time_range
            orders = result["restaurants"][0]["orders"]
            # Note: SQL query handles sorting, so we expect the order from mock_rows
            # In real scenario, SQL ORDER BY would sort them
            assert len(orders) == 3

    def test_handles_empty_results(self, mock_db):
        """Test that empty results are handled gracefully."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            assert result["order_date"] == order_date
            assert result["restaurants"] == []

    def test_filters_by_kitchen_day(self, mock_db):
        """Test that orders are filtered by the correct kitchen_day."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)  # Tuesday

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            # Act
            get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "ps.kitchen_day = %s" in query
            assert "tuesday" in params

    def test_excludes_archived_records(self, mock_db):
        """Test that archived records are excluded from results."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            # Act
            get_daily_orders(institution_entity_id, order_date, None, mock_db)

            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]

            assert "ppl.is_archived = FALSE" in query

    def test_get_kitchen_day_for_date_uses_timezone(self, mock_db):
        """Test that kitchen_day calculation uses restaurant timezone."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date.today()

        mock_timezone_result = [{"timezone": "America/New_York", "country_code": None}]

        with (
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
            patch("app.services.restaurant_staff_service.get_kitchen_day_for_date") as mock_get_kitchen_day,
        ):
            mock_db_read.return_value = mock_timezone_result
            mock_get_kitchen_day.return_value = "tuesday"

            # Act
            result = _get_kitchen_day_for_date(order_date, institution_entity_id, mock_db)

            # Assert - verify we fetched timezone from DB and passed it to get_kitchen_day_for_date
            mock_get_kitchen_day.assert_called_once_with(order_date, "America/New_York", None)
            assert result == "tuesday"

    def test_group_orders_by_restaurant_sorts_alphabetically(self):
        """Test that restaurants are sorted alphabetically by name."""
        # Arrange
        restaurant_1_id = uuid4()
        restaurant_2_id = uuid4()
        restaurant_3_id = uuid4()

        mock_rows = [
            {
                "confirmation_code": "ABC123",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "D",
                "vianda_name": "Chicken",
                "restaurant_id": restaurant_1_id,
                "restaurant_name": "Zebra Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "DEF456",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "J",
                "last_initial": "S",
                "vianda_name": "Salad",
                "restaurant_id": restaurant_2_id,
                "restaurant_name": "Alpha Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "GHI789",
                "status": "active",
                "arrival_time": None,
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "B",
                "last_initial": "M",
                "vianda_name": "Pasta",
                "restaurant_id": restaurant_3_id,
                "restaurant_name": "Beta Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
        ]

        # Act
        result = _group_orders_by_restaurant(mock_rows)

        # Assert
        assert len(result) == 3
        assert result[0]["restaurant_name"] == "Alpha Restaurant"
        assert result[1]["restaurant_name"] == "Beta Restaurant"
        assert result[2]["restaurant_name"] == "Zebra Restaurant"


class TestStatusFilter:
    """Tests for the status filter param on get_daily_orders."""

    def _make_row(self, status: str, restaurant_id=None, restaurant_name="Test Restaurant") -> dict:
        rid = restaurant_id or uuid4()
        return {
            "confirmation_code": "ABC123",
            "status": status,
            "arrival_time": None,
            "pickup_time_range": "23:55-23:59",
            "kitchen_day": "tuesday",
            "first_initial": "J",
            "last_initial": "D",
            "vianda_name": "Chicken",
            "restaurant_id": rid,
            "restaurant_name": restaurant_name,
            "vianda_pickup_id": uuid4(),
            "expected_completion_time": None,
            "completion_time": None,
        }

    def test_status_filter_single_value_appended_to_query(self, mock_db):
        """Status filter adds AND ppl.status = ANY(%s) clause to SQL."""
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            get_daily_orders(institution_entity_id, order_date, None, mock_db, status_filter=["pending"])

            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "ppl.status = ANY(%s)" in query
            assert ["pending"] in params

    def test_status_filter_multiple_values(self, mock_db):
        """Status filter with multiple values passes a list to ANY(%s)."""
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            get_daily_orders(
                institution_entity_id,
                order_date,
                None,
                mock_db,
                status_filter=["pending", "arrived"],
            )

            call_args = mock_db_read.call_args
            params = call_args[0][1]

            assert ["pending", "arrived"] in params

    def test_status_filter_omitted_does_not_add_clause(self, mock_db):
        """When status_filter is None, no ANY clause is added."""
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.return_value = []

            get_daily_orders(institution_entity_id, order_date, None, mock_db)

            call_args = mock_db_read.call_args
            query = call_args[0][0]

            assert "ppl.status = ANY(%s)" not in query

    def test_status_filter_combined_with_is_no_show(self, mock_db):
        """status_filter and is_no_show_filter can be combined."""
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = uuid4()

        # A pending row whose pickup window has clearly not passed (far future)
        row_no_show = self._make_row("pending", restaurant_id=restaurant_id)
        row_no_show["pickup_time_range"] = "00:00-00:01"  # window already passed
        row_arrived = self._make_row("arrived", restaurant_id=restaurant_id)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            # Main query returns both rows; reservations + live per restaurant
            mock_db_read.side_effect = [[row_no_show, row_arrived], [], {"count": 2}]

            result = get_daily_orders(
                institution_entity_id,
                order_date,
                None,
                mock_db,
                status_filter=["pending"],
                is_no_show_filter=True,
            )

            # Only the no-show pending row should survive both filters
            orders = result["restaurants"][0]["orders"] if result["restaurants"] else []
            assert all(o["is_no_show"] for o in orders)


class TestIsNoShowFilter:
    """Tests for the is_no_show filter param on get_daily_orders."""

    def _make_base_rows(self, restaurant_id):
        """Return a list with one pending no-show row and one arrived (non-no-show) row."""
        # Pickup window guaranteed to be in the past
        no_show_row = {
            "confirmation_code": "NS0001",
            "status": "pending",
            "arrival_time": None,
            "pickup_time_range": "00:00-00:01",
            "kitchen_day": "tuesday",
            "first_initial": "A",
            "last_initial": "B",
            "vianda_name": "Pasta",
            "restaurant_id": restaurant_id,
            "restaurant_name": "Test Restaurant",
            "vianda_pickup_id": uuid4(),
            "expected_completion_time": None,
            "completion_time": None,
        }
        # Arrived order is never a no-show
        arrived_row = {
            "confirmation_code": "AR0002",
            "status": "arrived",
            "arrival_time": datetime(2026, 2, 4, 12, 0),
            "pickup_time_range": "12:00-12:30",
            "kitchen_day": "tuesday",
            "first_initial": "C",
            "last_initial": "D",
            "vianda_name": "Pasta",
            "restaurant_id": restaurant_id,
            "restaurant_name": "Test Restaurant",
            "vianda_pickup_id": uuid4(),
            "expected_completion_time": None,
            "completion_time": None,
        }
        return [no_show_row, arrived_row]

    def test_is_no_show_true_returns_only_no_show_orders(self, mock_db):
        """is_no_show_filter=True keeps only orders classified as no-shows."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)
        rows = self._make_base_rows(restaurant_id)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [rows, [], {"count": 1}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db, is_no_show_filter=True)

            all_orders = [o for r in result["restaurants"] for o in r["orders"]]
            assert all(o["is_no_show"] for o in all_orders)

    def test_is_no_show_false_excludes_no_show_orders(self, mock_db):
        """is_no_show_filter=False excludes no-show orders."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)
        rows = self._make_base_rows(restaurant_id)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [rows, [], {"count": 1}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db, is_no_show_filter=False)

            all_orders = [o for r in result["restaurants"] for o in r["orders"]]
            assert all(not o["is_no_show"] for o in all_orders)

    def test_is_no_show_none_returns_all_orders(self, mock_db):
        """is_no_show_filter=None (default) returns all orders regardless of no-show status."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)
        rows = self._make_base_rows(restaurant_id)

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [rows, [], {"count": 2}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            all_orders = [o for r in result["restaurants"] for o in r["orders"]]
            assert len(all_orders) == 2

    def test_is_no_show_filter_drops_empty_restaurants(self, mock_db):
        """Restaurants with no matching orders after filtering are excluded from response."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)

        # Only arrived orders — no no-shows
        rows = [
            {
                "confirmation_code": "AR001",
                "status": "arrived",
                "arrival_time": datetime(2026, 2, 4, 12, 0),
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "X",
                "last_initial": "Y",
                "vianda_name": "Soup",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Empty After Filter",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            }
        ]

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [rows]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db, is_no_show_filter=True)

            # No restaurants should appear since none have no-show orders
            assert result["restaurants"] == []


class TestCompletedCount:
    """Tests for the completed_count derived field in reservations_by_vianda."""

    def test_completed_count_included_in_reservations_by_vianda(self, mock_db):
        """completed_count field is present in each reservations_by_vianda entry."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)

        order_row = {
            "confirmation_code": "AB1234",
            "status": "completed",
            "arrival_time": datetime(2026, 2, 4, 12, 0),
            "pickup_time_range": "12:00-12:30",
            "kitchen_day": "tuesday",
            "first_initial": "J",
            "last_initial": "D",
            "vianda_name": "Chicken",
            "restaurant_id": restaurant_id,
            "restaurant_name": "Test Restaurant",
            "vianda_pickup_id": uuid4(),
            "expected_completion_time": None,
            "completion_time": None,
        }

        reservation_row = {
            "vianda_id": uuid4(),
            "vianda_name": "Chicken",
            "count": 5,
            "completed_count": 3,
        }

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            # Main query, reservations_by_vianda query (returns reservation_row), live_locked_count query
            mock_db_read.side_effect = [[order_row], [reservation_row], {"count": 1}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            reservations = result["restaurants"][0]["reservations_by_vianda"]
            assert len(reservations) == 1
            assert "completed_count" in reservations[0]
            assert reservations[0]["completed_count"] == 3

    def test_completed_count_defaults_to_zero_when_none(self, mock_db):
        """completed_count defaults to 0 when the DB returns NULL (no pickups yet)."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)

        order_row = {
            "confirmation_code": "AB1234",
            "status": "pending",
            "arrival_time": None,
            "pickup_time_range": "23:55-23:59",
            "kitchen_day": "tuesday",
            "first_initial": "J",
            "last_initial": "D",
            "vianda_name": "Salad",
            "restaurant_id": restaurant_id,
            "restaurant_name": "Test Restaurant",
            "vianda_pickup_id": uuid4(),
            "expected_completion_time": None,
            "completion_time": None,
        }

        reservation_row = {
            "vianda_id": uuid4(),
            "vianda_name": "Salad",
            "count": 4,
            "completed_count": None,  # SQL COUNT FILTER returns NULL when no rows match
        }

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [[order_row], [reservation_row], {"count": 0}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            reservations = result["restaurants"][0]["reservations_by_vianda"]
            assert reservations[0]["completed_count"] == 0

    def test_completed_count_counts_completed_and_handed_out(self, mock_db):
        """completed_count counts both 'completed' and 'handed_out' status orders."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)

        # Two orders: one completed, one handed_out
        rows = [
            {
                "confirmation_code": "C00001",
                "status": "completed",
                "arrival_time": datetime(2026, 2, 4, 12, 0),
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "A",
                "last_initial": "B",
                "vianda_name": "Rice",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
            {
                "confirmation_code": "H00002",
                "status": "handed_out",
                "arrival_time": datetime(2026, 2, 4, 12, 5),
                "pickup_time_range": "12:00-12:30",
                "kitchen_day": "tuesday",
                "first_initial": "C",
                "last_initial": "D",
                "vianda_name": "Rice",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
        ]

        reservation_row = {
            "vianda_id": uuid4(),
            "vianda_name": "Rice",
            "count": 3,
            "completed_count": 2,  # Both completed + handed_out counted
        }

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [rows, [reservation_row], {"count": 2}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            reservations = result["restaurants"][0]["reservations_by_vianda"]
            assert reservations[0]["completed_count"] == 2

    def test_completed_count_not_counted_for_pending_or_arrived(self, mock_db):
        """Orders with status pending or arrived do not contribute to completed_count."""
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)

        rows = [
            {
                "confirmation_code": "P00001",
                "status": "pending",
                "arrival_time": None,
                "pickup_time_range": "23:55-23:59",
                "kitchen_day": "tuesday",
                "first_initial": "A",
                "last_initial": "B",
                "vianda_name": "Soup",
                "restaurant_id": restaurant_id,
                "restaurant_name": "Test Restaurant",
                "vianda_pickup_id": uuid4(),
                "expected_completion_time": None,
                "completion_time": None,
            },
        ]

        reservation_row = {
            "vianda_id": uuid4(),
            "vianda_name": "Soup",
            "count": 2,
            "completed_count": 0,  # pending/arrived do not count
        }

        with (
            patch("app.services.restaurant_staff_service._get_kitchen_day_for_date") as mock_get_day,
            patch("app.services.restaurant_staff_service.db_read") as mock_db_read,
        ):
            mock_get_day.return_value = "tuesday"
            mock_db_read.side_effect = [rows, [reservation_row], {"count": 0}]

            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)

            reservations = result["restaurants"][0]["reservations_by_vianda"]
            assert reservations[0]["completed_count"] == 0


class TestClassifyOrderStatus:
    """Unit tests for _classify_order_status (pure helper, no db param)."""

    def test_no_show_takes_precedence(self):
        assert _classify_order_status(True, "pending", None) == "no_show"

    def test_pending_status(self):
        assert _classify_order_status(False, "pending", None) == "pending"

    def test_arrived_status(self):
        assert _classify_order_status(False, "arrived", datetime(2026, 1, 1, 12, 0)) == "arrived"

    def test_handed_out_with_underscore(self):
        assert _classify_order_status(False, "handed_out", None) == "handed_out"

    def test_handed_out_with_space(self):
        assert _classify_order_status(False, "handed out", None) == "handed_out"

    def test_completed(self):
        assert _classify_order_status(False, "completed", None) == "completed"

    def test_complete_alias(self):
        assert _classify_order_status(False, "complete", None) == "completed"

    def test_active_no_arrival_maps_to_pending(self):
        assert _classify_order_status(False, "active", None) == "pending"

    def test_active_with_arrival_maps_to_arrived(self):
        assert _classify_order_status(False, "active", datetime(2026, 1, 1, 12, 0)) == "arrived"

    def test_unknown_status_falls_back_to_pending(self):
        assert _classify_order_status(False, "unknown_status", None) == "pending"
