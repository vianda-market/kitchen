"""
Unit tests for restaurant explorer service (B2C by-city: plates with image_url/savings, restaurants with address).
"""

import pytest
from freezegun import freeze_time
from unittest.mock import patch, MagicMock
from uuid import uuid4

from datetime import date

from app.services.restaurant_explorer_service import (
    _compute_savings_pct,
    get_allowed_kitchen_days_sorted_by_date,
    get_coworker_pickup_windows,
    get_pickup_windows_for_kitchen_day,
    get_plates_for_restaurants,
    get_restaurants_by_city,
)


class TestGetPlatesForRestaurants:
    """get_plates_for_restaurants returns plate_id, product_name, price, credit, kitchen_day, image_url; savings set to 0 (computed in get_restaurants_by_city from credit_cost_local_currency)."""

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_returns_image_url_and_savings_placeholder_from_product_and_plate(self, mock_db_read):
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "plate_id": pid,
                "product_name": "Grilled Chicken",
                "price": 12.5,
                "credit": 2,
                "kitchen_day": "wednesday",
                "image_url": "http://localhost:8000/static/products/abc.jpg",
            }
        ]
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "wednesday", mock_db)

        assert rid in result
        plates = result[rid]
        assert len(plates) == 1
        assert plates[0]["plate_id"] == pid
        assert plates[0]["product_name"] == "Grilled Chicken"
        assert plates[0]["price"] == 12.5
        assert plates[0]["credit"] == 2
        assert plates[0]["kitchen_day"] == "wednesday"
        assert plates[0]["image_url"] == "http://localhost:8000/static/products/abc.jpg"
        assert plates[0]["savings"] == 0  # Computed in get_restaurants_by_city from credit_cost_local_currency

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_savings_zero_when_no_credit_cost_local_currency(self, mock_db_read):
        rid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "plate_id": uuid4(),
                "product_name": "Pasta",
                "price": 10.0,
                "credit": 1,
                "kitchen_day": "monday",
                "image_url": None,
            }
        ]
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "monday", mock_db)

        assert result[rid][0]["savings"] == 0
        assert result[rid][0]["image_url"] is None

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_empty_image_url_becomes_none(self, mock_db_read):
        rid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "plate_id": uuid4(),
                "product_name": "Salad",
                "price": 8.0,
                "credit": 1,
                "kitchen_day": "friday",
                "image_url": "",
            }
        ]
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "friday", mock_db)

        assert result[rid][0]["image_url"] is None
        assert result[rid][0]["savings"] == 0

    def test_returns_empty_dict_for_invalid_kitchen_day(self):
        mock_db = MagicMock()
        assert get_plates_for_restaurants([uuid4()], "sunday", mock_db) == {}
        assert get_plates_for_restaurants([uuid4()], "Invalid", mock_db) == {}

    def test_returns_empty_dict_for_empty_restaurant_ids(self):
        mock_db = MagicMock()
        assert get_plates_for_restaurants([], "monday", mock_db) == {}

    @patch("app.services.restaurant_explorer_service.get_plate_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_insufficient_reviews_when_review_count_below_5(
        self, mock_db_read, mock_get_aggregates
    ):
        """When review_count < 5, portion_size is insufficient_reviews and averages are null."""
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "plate_id": pid,
                "product_name": "New Plate",
                "price": 10.0,
                "credit": 1,
                "kitchen_day": "wednesday",
                "image_url": None,
            }
        ]
        mock_get_aggregates.return_value = {
            str(pid): {
                "average_stars": 4.5,
                "average_portion_size": 2.0,
                "review_count": 3,
            }
        }
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "wednesday", mock_db)

        p = result[rid][0]
        assert p["portion_size"] == "insufficient_reviews"
        assert p["average_stars"] is None
        assert p["average_portion_size"] is None
        assert p["review_count"] == 3

    @patch("app.services.restaurant_explorer_service.get_plate_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_bucketed_when_review_count_ge_5(
        self, mock_db_read, mock_get_aggregates
    ):
        """When review_count >= 5, portion_size is bucketed from average_portion_size."""
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "plate_id": pid,
                "product_name": "Grilled Chicken",
                "price": 12.0,
                "credit": 2,
                "kitchen_day": "wednesday",
                "image_url": None,
            }
        ]
        mock_get_aggregates.return_value = {
            str(pid): {
                "average_stars": 4.2,
                "average_portion_size": 2.1,
                "review_count": 15,
            }
        }
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "wednesday", mock_db)

        p = result[rid][0]
        assert p["portion_size"] == "standard"  # 2.1 -> standard
        assert p["average_stars"] == 4.2
        assert p["average_portion_size"] == 2.1
        assert p["review_count"] == 15

    @patch("app.services.restaurant_explorer_service.get_plate_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_light_and_large_buckets(
        self, mock_db_read, mock_get_aggregates
    ):
        """portion_size light (avg<1.5) and large (avg>=2.5) buckets."""
        rid = uuid4()
        pid_light = uuid4()
        pid_large = uuid4()
        mock_db_read.return_value = [
            {"restaurant_id": rid, "plate_id": pid_light, "product_name": "Small", "price": 8.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            {"restaurant_id": rid, "plate_id": pid_large, "product_name": "Big", "price": 15.0, "credit": 2, "kitchen_day": "monday", "image_url": None},
        ]
        mock_get_aggregates.return_value = {
            str(pid_light): {"average_stars": 4.0, "average_portion_size": 1.2, "review_count": 10},
            str(pid_large): {"average_stars": 4.5, "average_portion_size": 2.8, "review_count": 20},
        }
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "monday", mock_db)

        plates_by_pid = {str(p["plate_id"]): p for p in result[rid]}
        assert plates_by_pid[str(pid_light)]["portion_size"] == "light"
        assert plates_by_pid[str(pid_large)]["portion_size"] == "large"

    @patch("app.services.restaurant_explorer_service.get_plate_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_insufficient_reviews_when_no_aggregates(
        self, mock_db_read, mock_get_aggregates
    ):
        """When plate has no aggregates, portion_size stays insufficient_reviews."""
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {"restaurant_id": rid, "plate_id": pid, "product_name": "New", "price": 10.0, "credit": 1, "kitchen_day": "tuesday", "image_url": None},
        ]
        mock_get_aggregates.return_value = {}
        mock_db = MagicMock()

        result = get_plates_for_restaurants([rid], "tuesday", mock_db)

        p = result[rid][0]
        assert p["portion_size"] == "insufficient_reviews"
        assert p["average_stars"] is None
        assert p["average_portion_size"] is None
        assert p["review_count"] == 0


class TestGetRestaurantsByCity:
    """get_restaurants_by_city returns restaurants with street_type, street_name, building_number from address."""

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_restaurants_include_address_fields(self, mock_db_read):
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db)

        assert "restaurants" in result
        assert len(result["restaurants"]) == 1
        r = result["restaurants"][0]
        assert r["restaurant_id"] == rid
        assert r["name"] == "La Cocina"
        assert r["street_type"] == "Av"
        assert r["street_name"] == "Santa Fe"
        assert r["building_number"] == "1234"
        assert r["is_favorite"] is False
        assert r["is_recommended"] is False
        assert r["is_recommended"] is False  # No user_id => no recommendations

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_restaurant_address_fields_optional_none(self, mock_db_read):
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Córdoba"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "El Buen Sabor",
                    "cuisine": None,
                    "postal_code": None,
                    "city": "Córdoba",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": None,
                    "lng": None,
                }
            ],
            None,
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Córdoba", "AR", mock_db)

        r = result["restaurants"][0]
        assert r["street_type"] is None
        assert r["street_name"] is None
        assert r["building_number"] is None
        assert result["city"] == "Córdoba"

    @patch("app.services.restaurant_explorer_service.get_plate_review_aggregates")
    @patch("app.services.favorite_service.get_favorite_ids")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_is_recommended_and_sort_order_when_user_id_present(
        self, mock_db_read, mock_get_favorite_ids, mock_get_plate_review_aggregates
    ):
        """When user_id present, is_recommended set from favorites; recommended items sorted first."""
        rid_a = uuid4()
        rid_b = uuid4()
        pid1 = uuid4()
        pid2 = uuid4()
        pid3 = uuid4()
        user_id = uuid4()

        mock_get_plate_review_aggregates.return_value = {}
        mock_get_favorite_ids.return_value = {
            "plate_ids": [pid1],
            "restaurant_ids": [rid_b],
        }
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid_a,
                    "name": "Alpha Restaurant",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "100",
                    "lat": -34.6,
                    "lng": -58.4,
                },
                {
                    "restaurant_id": rid_b,
                    "name": "Beta Bistro",
                    "cuisine": "French",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Corrientes",
                    "building_number": "200",
                    "lat": -34.6,
                    "lng": -58.4,
                },
            ],
            [
                {"restaurant_id": rid_a, "plate_id": pid1, "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "wednesday", "image_url": None},
                {"restaurant_id": rid_a, "plate_id": pid2, "product_name": "Salad", "price": 8.0, "credit": 1, "kitchen_day": "wednesday", "image_url": None},
                {"restaurant_id": rid_b, "plate_id": pid3, "product_name": "Soup", "price": 6.0, "credit": 1, "kitchen_day": "wednesday", "image_url": None},
            ],
            [],  # vol_query (has_volunteer)
            [],  # reserved_query (user has no reserved plates)
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires", "AR", mock_db,
            kitchen_day="wednesday",
            user_id=user_id,
        )

        restaurants = result["restaurants"]
        assert len(restaurants) == 2

        # Both restaurants recommended: A has favorited plate, B is favorited
        for r in restaurants:
            assert "is_recommended" in r
            assert "is_favorite" in r

        # Beta Bistro (favorited restaurant) should be first (recommended, score 5)
        # Alpha Restaurant (has favorited plate) also recommended (score 5)
        # Tie-break by name: Alpha before Beta
        assert restaurants[0]["name"] == "Alpha Restaurant"
        assert restaurants[1]["name"] == "Beta Bistro"

        # Alpha: plate pid1 favorited -> recommended; pid2 not
        alpha = next(r for r in restaurants if r["restaurant_id"] == rid_a)
        plates_a = alpha["plates"]
        assert len(plates_a) == 2
        pasta = next(p for p in plates_a if p["plate_id"] == pid1)
        salad = next(p for p in plates_a if p["plate_id"] == pid2)
        assert pasta["is_recommended"] is True
        assert pasta["is_favorite"] is True
        assert salad["is_recommended"] is False
        assert salad["is_favorite"] is False
        # Recommended plate first
        assert plates_a[0]["plate_id"] == pid1

        # Beta: restaurant favorited -> all plates recommended
        beta = next(r for r in restaurants if r["restaurant_id"] == rid_b)
        assert beta["is_recommended"] is True
        assert beta["is_favorite"] is True
        assert beta["plates"][0]["is_recommended"] is True

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_is_recommended_false_when_no_user_id(self, mock_db_read):
        """When user_id absent, is_recommended and is_favorite are False."""
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db)

        r = result["restaurants"][0]
        assert r["is_favorite"] is False
        assert r["is_recommended"] is False

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_is_already_reserved_false_when_no_user_id(self, mock_db_read):
        """When user_id is None, all plates have is_already_reserved=False and existing_plate_selection_id=None."""
        rid = uuid4()
        pid1 = uuid4()
        pid2 = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            [
                {"restaurant_id": rid, "plate_id": pid1, "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
                {"restaurant_id": rid, "plate_id": pid2, "product_name": "Salad", "price": 8.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            ],
            [],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires", "AR", mock_db,
            kitchen_day="monday",
        )

        plates = result["restaurants"][0]["plates"]
        assert len(plates) == 2
        for p in plates:
            assert p["is_already_reserved"] is False
            assert p["existing_plate_selection_id"] is None

    @patch("app.services.favorite_service.get_favorite_ids")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_is_already_reserved_true_for_reserved_plate(self, mock_db_read, mock_get_favorite_ids):
        """When user has plate_selection for plate X and kitchen_day Monday, plate X has is_already_reserved=True and existing_plate_selection_id set; other plates have False."""
        rid = uuid4()
        pid_reserved = uuid4()
        pid_other = uuid4()
        user_id = uuid4()
        plate_selection_id = uuid4()

        mock_get_favorite_ids.return_value = {"plate_ids": [], "restaurant_ids": []}
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            [
                {"restaurant_id": rid, "plate_id": pid_reserved, "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
                {"restaurant_id": rid, "plate_id": pid_other, "product_name": "Salad", "price": 8.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            ],
            [],
            [{"plate_id": pid_reserved, "plate_selection_id": plate_selection_id}],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        with patch("app.services.recommendation_service.apply_recommendation"):
            result = get_restaurants_by_city(
                "Buenos Aires", "AR", mock_db,
                kitchen_day="monday",
                user_id=user_id,
            )

        plates = result["restaurants"][0]["plates"]
        pasta = next(p for p in plates if p["plate_id"] == pid_reserved)
        salad = next(p for p in plates if p["plate_id"] == pid_other)
        assert pasta["is_already_reserved"] is True
        assert pasta["existing_plate_selection_id"] == str(plate_selection_id)
        assert salad["is_already_reserved"] is False
        assert salad["existing_plate_selection_id"] is None

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_has_volunteer_false_when_all_volunteers_opted_out(self, mock_db_read):
        """has_volunteer is False when vol_query returns empty (all volunteers have coworkers_can_see_my_orders or can_participate_in_plate_pickups=false)."""
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            [
                {"restaurant_id": rid, "plate_id": uuid4(), "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            ],
            [],  # vol_query returns empty - no volunteers with both prefs True
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db, kitchen_day="monday")

        assert result["restaurants"][0]["has_volunteer"] is False

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_has_volunteer_true_when_participating_volunteer_exists(self, mock_db_read):
        """has_volunteer is True when at least one volunteer has both preferences True."""
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            [
                {"restaurant_id": rid, "plate_id": uuid4(), "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            ],
            [{"restaurant_id": rid}],  # vol_query returns this restaurant - has volunteer with prefs True
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db, kitchen_day="monday")

        assert result["restaurants"][0]["has_volunteer"] is True

    @patch("app.services.recommendation_service.apply_recommendation")
    @patch("app.services.favorite_service.get_favorite_ids")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_has_coworker_request_false_when_only_current_user_has_request(
        self, mock_db_read, mock_get_favorite_ids, mock_apply_recommendation
    ):
        """When only the current user has pickup_intent=request, has_coworker_request is False (exclude self)."""
        rid = uuid4()
        user_id = uuid4()
        employer_id = uuid4()
        employer_address_id = uuid4()
        mock_get_favorite_ids.return_value = {"plate_ids": [], "restaurant_ids": []}
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            [
                {"restaurant_id": rid, "plate_id": uuid4(), "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            ],
            [],  # vol_query
            [],  # coworker_offer_query - no other coworker offers
            [],  # coworker_request_query - exclude self leaves none
            [],  # reserved_query
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires", "AR", mock_db,
            kitchen_day="monday",
            user_id=user_id,
            employer_id=employer_id,
            employer_address_id=employer_address_id,
        )

        assert result["restaurants"][0]["has_coworker_request"] is False
        assert result["restaurants"][0]["has_coworker_offer"] is False

    @patch("app.services.recommendation_service.apply_recommendation")
    @patch("app.services.favorite_service.get_favorite_ids")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_has_coworker_request_true_when_other_coworker_has_request(
        self, mock_db_read, mock_get_favorite_ids, mock_apply_recommendation
    ):
        """When another coworker has pickup_intent=request, has_coworker_request is True."""
        rid = uuid4()
        user_id = uuid4()
        employer_id = uuid4()
        employer_address_id = uuid4()
        mock_get_favorite_ids.return_value = {"plate_ids": [], "restaurant_ids": []}
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "La Cocina",
                    "cuisine": "Italian",
                    "postal_code": "C1234",
                    "city": "Buenos Aires",
                    "street_type": "Av",
                    "street_name": "Santa Fe",
                    "building_number": "1234",
                    "lat": -34.6,
                    "lng": -58.4,
                }
            ],
            [
                {"restaurant_id": rid, "plate_id": uuid4(), "product_name": "Pasta", "price": 10.0, "credit": 1, "kitchen_day": "monday", "image_url": None},
            ],
            [],  # vol_query
            [],  # coworker_offer_query
            [{"restaurant_id": rid}],  # coworker_request_query - other coworker has request
            [],  # reserved_query
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires", "AR", mock_db,
            kitchen_day="monday",
            user_id=user_id,
            employer_id=employer_id,
            employer_address_id=employer_address_id,
        )

        assert result["restaurants"][0]["has_coworker_request"] is True


class TestGetCoworkerPickupWindows:
    """get_coworker_pickup_windows returns pickup windows from coworkers (offer/request)."""

    @patch("app.services.restaurant_explorer_service.get_pickup_windows_for_kitchen_day")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_returns_empty_when_no_employer(self, mock_db_read, mock_get_windows):
        """When user has no employer, returns empty list."""
        mock_db_read.side_effect = [{"employer_id": None, "employer_address_id": None}]
        mock_db = MagicMock()
        result = get_coworker_pickup_windows(uuid4(), "monday", uuid4(), mock_db)
        assert result == []

    @patch("app.services.restaurant_explorer_service.get_pickup_windows_for_kitchen_day")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_offer_only(self, mock_db_read, mock_get_windows):
        """When coworker has offer only, returns that window."""
        rid = uuid4()
        uid = uuid4()
        mock_get_windows.return_value = ["11:30-11:45", "11:45-12:00", "12:00-12:15"]
        mock_db_read.side_effect = [
            {"employer_id": uuid4(), "employer_address_id": None},
            {"country_code": "AR"},
            [{"pickup_time_range": "12:00-12:15", "pickup_intent": "offer", "flexible_on_time": False}],
        ]
        mock_db = MagicMock()
        result = get_coworker_pickup_windows(rid, "monday", uid, mock_db)
        assert len(result) == 1
        assert result[0]["pickup_time_range"] == "12:00-12:15"
        assert result[0]["intent"] == "offer"
        assert result[0]["flexible_on_time"] is None

    @patch("app.services.restaurant_explorer_service.get_pickup_windows_for_kitchen_day")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_request_with_flexible_on_time_expands(self, mock_db_read, mock_get_windows):
        """When pickup_intent=request and flexible_on_time=true, expands ±30 min."""
        rid = uuid4()
        uid = uuid4()
        mock_get_windows.return_value = [
            "11:30-11:45", "11:45-12:00", "12:00-12:15", "12:15-12:30", "12:30-12:45",
        ]
        mock_db_read.side_effect = [
            {"employer_id": uuid4(), "employer_address_id": None},
            {"country_code": "AR"},
            [{"pickup_time_range": "12:00-12:15", "pickup_intent": "request", "flexible_on_time": True}],
        ]
        mock_db = MagicMock()
        result = get_coworker_pickup_windows(rid, "monday", uid, mock_db)
        assert len(result) >= 1
        windows = [r["pickup_time_range"] for r in result]
        assert "12:00-12:15" in windows
        assert "11:45-12:00" in windows or "12:15-12:30" in windows
        original = next(r for r in result if r["pickup_time_range"] == "12:00-12:15")
        assert original["flexible_on_time"] is True

    @patch("app.services.restaurant_explorer_service.get_pickup_windows_for_kitchen_day")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_invalid_kitchen_day_returns_empty(self, mock_db_read, mock_get_windows):
        """When kitchen_day is invalid (e.g. Sunday), returns empty."""
        mock_db = MagicMock()
        result = get_coworker_pickup_windows(uuid4(), "sunday", uuid4(), mock_db)
        assert result == []
        mock_db_read.assert_not_called()


class TestGetPickupWindowsForKitchenDay:
    """get_pickup_windows_for_kitchen_day returns 15-min windows from market business_hours (11:30–13:30)."""

    def test_ar_monday_returns_windows_11_30_to_13_30(self):
        """AR market: Monday 11:30–13:30 yields 8 windows."""
        target = date(2026, 3, 9)  # Monday
        windows = get_pickup_windows_for_kitchen_day("AR", "monday", target)
        assert len(windows) == 8
        assert windows[0] == "11:30-11:45"
        assert windows[-1] == "13:15-13:30"

    def test_us_friday_same_hours(self):
        """US market: same business hours as AR."""
        target = date(2026, 3, 13)  # Friday
        windows = get_pickup_windows_for_kitchen_day("US", "friday", target)
        assert "11:30-11:45" in windows
        assert "12:00-12:15" in windows
        assert "13:15-13:30" in windows

    def test_unknown_country_returns_empty(self):
        """Unknown country code returns empty list."""
        target = date(2026, 3, 9)
        assert get_pickup_windows_for_kitchen_day("XX", "monday", target) == []

    def test_invalid_kitchen_day_returns_empty(self):
        """Invalid kitchen_day (e.g. Sunday) returns empty."""
        target = date(2026, 3, 9)
        assert get_pickup_windows_for_kitchen_day("AR", "sunday", target) == []


class TestGetAllowedKitchenDaysSortedByDate:
    """Kitchen day close filter: today excluded when kitchen has closed (after 1:30 PM local)."""

    @freeze_time("2026-03-06 17:51:00")  # 5:51 PM UTC = 2:51 PM Buenos Aires (UTC-3)
    def test_friday_after_close_excludes_today_ar(self):
        """When AR market, Friday 2:51 PM local: Friday excluded, first item is Monday."""
        tz = "America/Argentina/Buenos_Aires"
        items = get_allowed_kitchen_days_sorted_by_date(tz, country_code="AR")
        assert len(items) >= 1
        assert items[0]["kitchen_day"] == "monday"
        assert items[0]["date"] == "2026-03-09"
        fridays = [i for i in items if i["kitchen_day"] == "friday"]
        assert not any(i["date"] == "2026-03-06" for i in fridays)

    @freeze_time("2026-03-06 16:00:00")  # 4 PM UTC = 1 PM Buenos Aires (before 1:30 PM close)
    def test_friday_before_close_includes_today_ar(self):
        """When AR market, Friday 1 PM local: Friday included as first item."""
        tz = "America/Argentina/Buenos_Aires"
        items = get_allowed_kitchen_days_sorted_by_date(tz, country_code="AR")
        assert len(items) >= 1
        assert items[0]["kitchen_day"] == "friday"
        assert items[0]["date"] == "2026-03-06"

    @freeze_time("2026-03-06 17:51:00")  # Friday 2:51 PM Buenos Aires
    def test_unknown_market_includes_today(self):
        """When country_code has no MarketConfiguration (e.g. XX), today is included (fallback)."""
        tz = "America/Argentina/Buenos_Aires"
        items = get_allowed_kitchen_days_sorted_by_date(tz, country_code="XX")
        assert len(items) >= 1
        assert items[0]["kitchen_day"] == "friday"
        assert items[0]["date"] == "2026-03-06"

    @freeze_time("2026-03-06 17:51:00")
    def test_country_code_omitted_includes_today(self):
        """When country_code is omitted, today is included (backward compatible)."""
        tz = "America/Argentina/Buenos_Aires"
        items = get_allowed_kitchen_days_sorted_by_date(tz)
        assert len(items) >= 1
        assert items[0]["kitchen_day"] == "friday"
        assert items[0]["date"] == "2026-03-06"

    @freeze_time("2026-03-07 17:51:00")  # Saturday 2:51 PM Buenos Aires
    def test_weekend_first_item_monday(self):
        """On Saturday, first item is Monday (weekends not in list)."""
        tz = "America/Argentina/Buenos_Aires"
        items = get_allowed_kitchen_days_sorted_by_date(tz, country_code="AR")
        assert len(items) >= 1
        assert items[0]["kitchen_day"] == "monday"
        assert items[0]["date"] == "2026-03-09"


class TestComputeSavingsPct:
    """Unit tests for savings formula: (price - credit * credit_cost_local_currency) / price * 100, clamped to 0-100."""

    def test_normal_savings(self):
        # price=10, credit=1, credit_cost_local_currency=8 -> (10-8)/10*100 = 20%
        assert _compute_savings_pct(10.0, 1, 8.0) == 20

    def test_price_zero_returns_zero(self):
        assert _compute_savings_pct(0.0, 1, 5.0) == 0

    def test_credit_zero_full_price_no_savings(self):
        # price=10, credit=0, credit_cost_local_currency=5 -> 100%
        assert _compute_savings_pct(10.0, 0, 5.0) == 100

    def test_credit_cost_local_currency_zero_full_savings(self):
        # price=10, credit=2, credit_cost_local_currency=0 -> 100%
        assert _compute_savings_pct(10.0, 2, 0.0) == 100

    def test_clamped_to_100(self):
        # e.g. credit_cost_local_currency negative or very high could give >100
        assert _compute_savings_pct(10.0, 1, 0.0) == 100
        assert _compute_savings_pct(10.0, 0, 100.0) == 100

    def test_clamped_to_zero(self):
        # cost more than price -> negative savings -> 0
        assert _compute_savings_pct(10.0, 2, 10.0) == 0  # 2*10=20 > 10


class TestGetPickupWindowsForKitchenDay:
    """get_pickup_windows_for_kitchen_day returns 15-min windows from market business_hours (11:30-13:30)."""

    def test_ar_monday_returns_windows_1130_to_1330(self):
        """AR market: Monday 11:30-13:30 yields 8 windows."""
        target = date(2026, 3, 9)  # Monday
        windows = get_pickup_windows_for_kitchen_day("AR", "monday", target)
        assert len(windows) == 8
        assert windows[0] == "11:30-11:45"
        assert windows[1] == "11:45-12:00"
        assert windows[-1] == "13:15-13:30"

    def test_us_friday_same_windows(self):
        """US market: same business hours (11:30-13:30)."""
        target = date(2026, 3, 13)  # Friday
        windows = get_pickup_windows_for_kitchen_day("US", "friday", target)
        assert "11:30-11:45" in windows
        assert "12:00-12:15" in windows
        assert "13:15-13:30" in windows

    def test_unknown_country_returns_empty(self):
        """Unknown country code returns empty list."""
        windows = get_pickup_windows_for_kitchen_day("XX", "monday", date(2026, 3, 9))
        assert windows == []

    def test_invalid_kitchen_day_returns_empty(self):
        """Invalid kitchen_day (e.g. Saturday) returns empty (not in business_hours)."""
        windows = get_pickup_windows_for_kitchen_day("AR", "saturday", date(2026, 3, 14))
        assert windows == []
