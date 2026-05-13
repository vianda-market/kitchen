"""
Unit tests for restaurant explorer service (B2C by-city: viandas with image_url/savings, restaurants with address).
"""

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from freezegun import freeze_time

from app.services.restaurant_explorer_service import (
    _compute_savings_pct,
    get_allowed_kitchen_days_sorted_by_date,
    get_coworker_pickup_windows,
    get_pickup_windows_for_kitchen_day,
    get_restaurants_by_city,
    get_viandas_for_restaurants,
)


class TestGetPlatesForRestaurants:
    """get_viandas_for_restaurants returns vianda_id, product_name, price, credit, kitchen_day, image_url; savings set to 0 (computed in get_restaurants_by_city from credit_cost_local_currency)."""

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_returns_image_url_and_savings_placeholder_from_product_and_vianda(self, mock_db_read):
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": pid,
                "product_name": "Grilled Chicken",
                "price": 12.5,
                "credit": 2,
                "kitchen_day": "wednesday",
                "image_url": "http://localhost:8000/static/products/abc.jpg",
            }
        ]
        mock_db = MagicMock()

        result = get_viandas_for_restaurants([rid], "wednesday", mock_db)

        assert rid in result
        viandas = result[rid]
        assert len(viandas) == 1
        assert viandas[0]["vianda_id"] == pid
        assert viandas[0]["product_name"] == "Grilled Chicken"
        assert viandas[0]["price"] == 12.5
        assert viandas[0]["credit"] == 2
        assert viandas[0]["kitchen_day"] == "wednesday"
        assert viandas[0]["image_url"] == "http://localhost:8000/static/products/abc.jpg"
        assert viandas[0]["savings"] == 0  # Computed in get_restaurants_by_city from credit_cost_local_currency

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_savings_zero_when_no_credit_cost_local_currency(self, mock_db_read):
        rid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": uuid4(),
                "product_name": "Pasta",
                "price": 10.0,
                "credit": 1,
                "kitchen_day": "monday",
                "image_url": None,
            }
        ]
        mock_db = MagicMock()

        result = get_viandas_for_restaurants([rid], "monday", mock_db)

        assert result[rid][0]["savings"] == 0
        assert result[rid][0]["image_url"] is None

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_empty_image_url_becomes_none(self, mock_db_read):
        rid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": uuid4(),
                "product_name": "Salad",
                "price": 8.0,
                "credit": 1,
                "kitchen_day": "friday",
                "image_url": "",
            }
        ]
        mock_db = MagicMock()

        result = get_viandas_for_restaurants([rid], "friday", mock_db)

        assert result[rid][0]["image_url"] is None
        assert result[rid][0]["savings"] == 0

    def test_returns_empty_dict_for_invalid_kitchen_day(self):
        mock_db = MagicMock()
        assert get_viandas_for_restaurants([uuid4()], "sunday", mock_db) == {}
        assert get_viandas_for_restaurants([uuid4()], "Invalid", mock_db) == {}

    def test_returns_empty_dict_for_empty_restaurant_ids(self):
        mock_db = MagicMock()
        assert get_viandas_for_restaurants([], "monday", mock_db) == {}

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_insufficient_reviews_when_review_count_below_5(self, mock_db_read, mock_get_aggregates):
        """When review_count < 5, portion_size is insufficient_reviews and averages are null."""
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": pid,
                "product_name": "New Vianda",
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

        result = get_viandas_for_restaurants([rid], "wednesday", mock_db)

        p = result[rid][0]
        assert p["portion_size"] == "insufficient_reviews"
        assert p["average_stars"] is None
        assert p["average_portion_size"] is None
        assert p["review_count"] == 3

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_bucketed_when_review_count_ge_5(self, mock_db_read, mock_get_aggregates):
        """When review_count >= 5, portion_size is bucketed from average_portion_size."""
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": pid,
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

        result = get_viandas_for_restaurants([rid], "wednesday", mock_db)

        p = result[rid][0]
        assert p["portion_size"] == "standard"  # 2.1 -> standard
        assert p["average_stars"] == 4.2
        assert p["average_portion_size"] == 2.1
        assert p["review_count"] == 15

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_light_and_large_buckets(self, mock_db_read, mock_get_aggregates):
        """portion_size light (avg<1.5) and large (avg>=2.5) buckets."""
        rid = uuid4()
        pid_light = uuid4()
        pid_large = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": pid_light,
                "product_name": "Small",
                "price": 8.0,
                "credit": 1,
                "kitchen_day": "monday",
                "image_url": None,
            },
            {
                "restaurant_id": rid,
                "vianda_id": pid_large,
                "product_name": "Big",
                "price": 15.0,
                "credit": 2,
                "kitchen_day": "monday",
                "image_url": None,
            },
        ]
        mock_get_aggregates.return_value = {
            str(pid_light): {"average_stars": 4.0, "average_portion_size": 1.2, "review_count": 10},
            str(pid_large): {"average_stars": 4.5, "average_portion_size": 2.8, "review_count": 20},
        }
        mock_db = MagicMock()

        result = get_viandas_for_restaurants([rid], "monday", mock_db)

        viandas_by_pid = {str(p["vianda_id"]): p for p in result[rid]}
        assert viandas_by_pid[str(pid_light)]["portion_size"] == "light"
        assert viandas_by_pid[str(pid_large)]["portion_size"] == "large"

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_portion_size_insufficient_reviews_when_no_aggregates(self, mock_db_read, mock_get_aggregates):
        """When vianda has no aggregates, portion_size stays insufficient_reviews."""
        rid = uuid4()
        pid = uuid4()
        mock_db_read.return_value = [
            {
                "restaurant_id": rid,
                "vianda_id": pid,
                "product_name": "New",
                "price": 10.0,
                "credit": 1,
                "kitchen_day": "tuesday",
                "image_url": None,
            },
        ]
        mock_get_aggregates.return_value = {}
        mock_db = MagicMock()

        result = get_viandas_for_restaurants([rid], "tuesday", mock_db)

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

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.favorite_service.get_favorite_ids")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_is_recommended_and_sort_order_when_user_id_present(
        self, mock_db_read, mock_get_favorite_ids, mock_get_vianda_review_aggregates
    ):
        """When user_id present, is_recommended set from favorites; recommended items sorted first."""
        rid_a = uuid4()
        rid_b = uuid4()
        pid1 = uuid4()
        pid2 = uuid4()
        pid3 = uuid4()
        user_id = uuid4()

        mock_get_vianda_review_aggregates.return_value = {}
        mock_get_favorite_ids.return_value = {
            "vianda_ids": [pid1],
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
                {
                    "restaurant_id": rid_a,
                    "vianda_id": pid1,
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "wednesday",
                    "image_url": None,
                },
                {
                    "restaurant_id": rid_a,
                    "vianda_id": pid2,
                    "product_name": "Salad",
                    "price": 8.0,
                    "credit": 1,
                    "kitchen_day": "wednesday",
                    "image_url": None,
                },
                {
                    "restaurant_id": rid_b,
                    "vianda_id": pid3,
                    "product_name": "Soup",
                    "price": 6.0,
                    "credit": 1,
                    "kitchen_day": "wednesday",
                    "image_url": None,
                },
            ],
            [],  # vol_query (has_volunteer)
            [],  # reserved_query (user has no reserved viandas)
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            kitchen_day="wednesday",
            user_id=user_id,
        )

        restaurants = result["restaurants"]
        assert len(restaurants) == 2

        # Both restaurants recommended: A has favorited vianda, B is favorited
        for r in restaurants:
            assert "is_recommended" in r
            assert "is_favorite" in r

        # Beta Bistro (favorited restaurant) should be first (recommended, score 5)
        # Alpha Restaurant (has favorited vianda) also recommended (score 5)
        # Tie-break by name: Alpha before Beta
        assert restaurants[0]["name"] == "Alpha Restaurant"
        assert restaurants[1]["name"] == "Beta Bistro"

        # Alpha: vianda pid1 favorited -> recommended; pid2 not
        alpha = next(r for r in restaurants if r["restaurant_id"] == rid_a)
        viandas_a = alpha["viandas"]
        assert len(viandas_a) == 2
        pasta = next(p for p in viandas_a if p["vianda_id"] == pid1)
        salad = next(p for p in viandas_a if p["vianda_id"] == pid2)
        assert pasta["is_recommended"] is True
        assert pasta["is_favorite"] is True
        assert salad["is_recommended"] is False
        assert salad["is_favorite"] is False
        # Recommended vianda first
        assert viandas_a[0]["vianda_id"] == pid1

        # Beta: restaurant favorited -> all viandas recommended
        beta = next(r for r in restaurants if r["restaurant_id"] == rid_b)
        assert beta["is_recommended"] is True
        assert beta["is_favorite"] is True
        assert beta["viandas"][0]["is_recommended"] is True

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
        """When user_id is None, all viandas have is_already_reserved=False and existing_vianda_selection_id=None."""
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
                {
                    "restaurant_id": rid,
                    "vianda_id": pid1,
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
                {
                    "restaurant_id": rid,
                    "vianda_id": pid2,
                    "product_name": "Salad",
                    "price": 8.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
            ],
            [],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            kitchen_day="monday",
        )

        viandas = result["restaurants"][0]["viandas"]
        assert len(viandas) == 2
        for p in viandas:
            assert p["is_already_reserved"] is False
            assert p["existing_vianda_selection_id"] is None

    @patch("app.services.favorite_service.get_favorite_ids")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_is_already_reserved_true_for_reserved_vianda(self, mock_db_read, mock_get_favorite_ids):
        """When user has vianda_selection for vianda X and kitchen_day Monday, vianda X has is_already_reserved=True and existing_vianda_selection_id set; other viandas have False."""
        rid = uuid4()
        pid_reserved = uuid4()
        pid_other = uuid4()
        user_id = uuid4()
        vianda_selection_id = uuid4()

        mock_get_favorite_ids.return_value = {"vianda_ids": [], "restaurant_ids": []}
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
                {
                    "restaurant_id": rid,
                    "vianda_id": pid_reserved,
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
                {
                    "restaurant_id": rid,
                    "vianda_id": pid_other,
                    "product_name": "Salad",
                    "price": 8.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
            ],
            [],
            [{"vianda_id": pid_reserved, "vianda_selection_id": vianda_selection_id}],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        with patch("app.services.recommendation_service.apply_recommendation"):
            result = get_restaurants_by_city(
                "Buenos Aires",
                "AR",
                mock_db,
                kitchen_day="monday",
                user_id=user_id,
            )

        viandas = result["restaurants"][0]["viandas"]
        pasta = next(p for p in viandas if p["vianda_id"] == pid_reserved)
        salad = next(p for p in viandas if p["vianda_id"] == pid_other)
        assert pasta["is_already_reserved"] is True
        assert pasta["existing_vianda_selection_id"] == str(vianda_selection_id)
        assert salad["is_already_reserved"] is False
        assert salad["existing_vianda_selection_id"] is None

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_has_volunteer_false_when_all_volunteers_opted_out(self, mock_db_read):
        """has_volunteer is False when vol_query returns empty (all volunteers have coworkers_can_see_my_orders or can_participate_in_vianda_pickups=false)."""
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
                {
                    "restaurant_id": rid,
                    "vianda_id": uuid4(),
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
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
                {
                    "restaurant_id": rid,
                    "vianda_id": uuid4(),
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
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
        employer_entity_id = uuid4()
        employer_address_id = uuid4()
        mock_get_favorite_ids.return_value = {"vianda_ids": [], "restaurant_ids": []}
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
                {
                    "restaurant_id": rid,
                    "vianda_id": uuid4(),
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
            ],
            [],  # vol_query
            [],  # coworker_offer_query - no other coworker offers
            [],  # coworker_request_query - exclude self leaves none
            [],  # reserved_query
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            kitchen_day="monday",
            user_id=user_id,
            employer_entity_id=employer_entity_id,
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
        employer_entity_id = uuid4()
        employer_address_id = uuid4()
        mock_get_favorite_ids.return_value = {"vianda_ids": [], "restaurant_ids": []}
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
                {
                    "restaurant_id": rid,
                    "vianda_id": uuid4(),
                    "product_name": "Pasta",
                    "price": 10.0,
                    "credit": 1,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
            ],
            [],  # vol_query
            [],  # coworker_offer_query
            [{"restaurant_id": rid}],  # coworker_request_query - other coworker has request
            [],  # reserved_query
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            kitchen_day="monday",
            user_id=user_id,
            employer_entity_id=employer_entity_id,
            employer_address_id=employer_address_id,
        )

        assert result["restaurants"][0]["has_coworker_request"] is True


class TestGetCoworkerPickupWindows:
    """get_coworker_pickup_windows returns pickup windows from coworkers (offer/request)."""

    @patch("app.services.restaurant_explorer_service.get_pickup_windows_for_kitchen_day")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_returns_empty_when_no_employer(self, mock_db_read, mock_get_windows):
        """When user has no employer, returns empty list."""
        mock_db_read.side_effect = [{"employer_entity_id": None, "employer_address_id": None}]
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
            {"employer_entity_id": uuid4(), "employer_address_id": None},
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
            "11:30-11:45",
            "11:45-12:00",
            "12:00-12:15",
            "12:15-12:30",
            "12:30-12:45",
        ]
        mock_db_read.side_effect = [
            {"employer_entity_id": uuid4(), "employer_address_id": None},
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


# ---------------------------------------------------------------------------
# K2: cuisine filter
# ---------------------------------------------------------------------------


class TestCuisineFilter:
    """K2 — cuisine filter on /restaurants/by-city (restaurant-level, multi-select OR logic)."""

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_cuisine_filter_passed_to_query(self, mock_db_read):
        """cuisine_filter param is accepted by get_restaurants_by_city without error."""
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "Trattoria Roma",
                    "cuisine_name": "Italian",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.6,
                    "lng": -58.4,
                    "tagline": None,
                    "pickup_instructions": None,
                }
            ],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db, cuisine_filter=["Italian"])

        assert len(result["restaurants"]) == 1
        assert result["restaurants"][0]["cuisine_name"] == "Italian"

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_no_cuisine_filter_returns_all(self, mock_db_read):
        """Without cuisine_filter, all restaurants are returned."""
        rid_a, rid_b = uuid4(), uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid_a,
                    "name": "A",
                    "cuisine_name": "Italian",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.6,
                    "lng": -58.4,
                    "tagline": None,
                    "pickup_instructions": None,
                },
                {
                    "restaurant_id": rid_b,
                    "name": "B",
                    "cuisine_name": "Mexican",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.7,
                    "lng": -58.5,
                    "tagline": None,
                    "pickup_instructions": None,
                },
            ],
            {"lat": -34.65, "lng": -58.45},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db)

        assert len(result["restaurants"]) == 2


# ---------------------------------------------------------------------------
# K3: max_credits filter (drop-on-empty-viandas)
# ---------------------------------------------------------------------------


class TestMaxCreditsFilter:
    """K3 — max_credits vianda-level filter; restaurants with empty vianda list are dropped."""

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_restaurants_with_no_surviving_viandas_dropped(self, mock_db_read, mock_aggregates):
        """When max_credits=3, restaurant A (credit=3) survives; restaurant B (credit=7) is dropped."""
        rid_a, rid_b = uuid4(), uuid4()
        pid_a = uuid4()
        mock_aggregates.return_value = {}
        mock_db_read.side_effect = [
            # _match_city_in_country
            [{"city": "Buenos Aires"}],
            # _query_city_restaurants returns both restaurants
            [
                {
                    "restaurant_id": rid_a,
                    "name": "A",
                    "cuisine_name": "Italian",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.6,
                    "lng": -58.4,
                    "tagline": None,
                    "pickup_instructions": None,
                },
                {
                    "restaurant_id": rid_b,
                    "name": "B",
                    "cuisine_name": "Mexican",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.7,
                    "lng": -58.5,
                    "tagline": None,
                    "pickup_instructions": None,
                },
            ],
            # get_viandas_for_restaurants — only A's vianda survives max_credits filter (handled in SQL)
            [
                {
                    "restaurant_id": rid_a,
                    "vianda_id": pid_a,
                    "product_name": "Cheap Vianda",
                    "price": 5.0,
                    "credit": 3,
                    "kitchen_day": "monday",
                    "image_url": None,
                }
            ],
            # vol_query
            [],
            # center
            {"lat": -34.65, "lng": -58.45},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            kitchen_day="monday",
            max_credits=3,
        )

        rids = [r["restaurant_id"] for r in result["restaurants"]]
        assert rid_a in rids
        assert rid_b not in rids, "Restaurant B should be dropped: no viandas survive max_credits=3"

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_no_max_credits_returns_both_restaurants(self, mock_db_read, mock_aggregates):
        """When max_credits is absent, all restaurants are returned (backward compatible)."""
        rid_a, rid_b = uuid4(), uuid4()
        mock_aggregates.return_value = {}
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid_a,
                    "name": "A",
                    "cuisine_name": "Italian",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.6,
                    "lng": -58.4,
                    "tagline": None,
                    "pickup_instructions": None,
                },
                {
                    "restaurant_id": rid_b,
                    "name": "B",
                    "cuisine_name": "Mexican",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.7,
                    "lng": -58.5,
                    "tagline": None,
                    "pickup_instructions": None,
                },
            ],
            [
                {
                    "restaurant_id": rid_a,
                    "vianda_id": uuid4(),
                    "product_name": "P1",
                    "price": 8.0,
                    "credit": 7,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
                {
                    "restaurant_id": rid_b,
                    "vianda_id": uuid4(),
                    "product_name": "P2",
                    "price": 5.0,
                    "credit": 3,
                    "kitchen_day": "monday",
                    "image_url": None,
                },
            ],
            [],
            {"lat": -34.65, "lng": -58.45},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city("Buenos Aires", "AR", mock_db, kitchen_day="monday")

        assert len(result["restaurants"]) == 2


# ---------------------------------------------------------------------------
# K4: dietary filter (array overlap, drop-on-empty-viandas)
# ---------------------------------------------------------------------------


class TestDietaryFilter:
    """K4 — dietary filter uses PostgreSQL array overlap (&&); uses direct SQL, not filter_builder."""

    @patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates")
    @patch("app.services.restaurant_explorer_service.db_read")
    def test_dietary_filter_drops_restaurant_with_no_matching_viandas(self, mock_db_read, mock_aggregates):
        """Restaurant with no viandas surviving dietary filter is dropped (drop-on-empty-viandas)."""
        rid_a, rid_b = uuid4(), uuid4()
        pid_a = uuid4()
        mock_aggregates.return_value = {}
        # Simulate SQL already applied the && filter: only A's vegan vianda comes back
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid_a,
                    "name": "A-Vegan",
                    "cuisine_name": "Vegan",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.6,
                    "lng": -58.4,
                    "tagline": None,
                    "pickup_instructions": None,
                },
                {
                    "restaurant_id": rid_b,
                    "name": "B-Gluten",
                    "cuisine_name": "Gluten",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.7,
                    "lng": -58.5,
                    "tagline": None,
                    "pickup_instructions": None,
                },
            ],
            # vianda query with && dietary filter: only A's vegan vianda
            [
                {
                    "restaurant_id": rid_a,
                    "vianda_id": pid_a,
                    "product_name": "VeganPlate",
                    "price": 8.0,
                    "credit": 2,
                    "kitchen_day": "monday",
                    "image_url": None,
                }
            ],
            [],  # vol_query
            {"lat": -34.65, "lng": -58.45},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            kitchen_day="monday",
            dietary_filter=["vegan"],
        )

        rids = [r["restaurant_id"] for r in result["restaurants"]]
        assert rid_a in rids
        assert rid_b not in rids, "Restaurant B has no surviving viandas after dietary filter — should be dropped"

    def test_get_viandas_for_restaurants_passes_dietary_filter_param(self):
        """get_viandas_for_restaurants accepts dietary_filter without raising errors."""
        mock_db = MagicMock()
        mock_db.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
        with patch("app.services.restaurant_explorer_service.db_read") as mock_db_read:
            with patch("app.services.restaurant_explorer_service.get_vianda_review_aggregates") as mock_agg:
                mock_db_read.return_value = []
                mock_agg.return_value = {}
                result = get_viandas_for_restaurants([uuid4()], "monday", mock_db, dietary_filter=["vegan"])
                assert result == {}


# ---------------------------------------------------------------------------
# K5: distance filter (geo_filter validation)
# ---------------------------------------------------------------------------


class TestDistanceFilter:
    """K5 — geo_filter (lat/lng/radius_km) validation; SQL applied in _query_city_restaurants."""

    @patch("app.services.restaurant_explorer_service.db_read")
    def test_geo_filter_accepted_by_get_restaurants_by_city(self, mock_db_read):
        """geo_filter param accepted without error; service calls _query_city_restaurants with it."""
        rid = uuid4()
        mock_db_read.side_effect = [
            [{"city": "Buenos Aires"}],
            [
                {
                    "restaurant_id": rid,
                    "name": "Nearby",
                    "cuisine_name": "Pizza",
                    "postal_code": None,
                    "city": "Buenos Aires",
                    "street_type": None,
                    "street_name": None,
                    "building_number": None,
                    "lat": -34.6,
                    "lng": -58.4,
                    "tagline": None,
                    "pickup_instructions": None,
                }
            ],
            {"lat": -34.6, "lng": -58.4},
        ]
        mock_db = MagicMock()

        result = get_restaurants_by_city(
            "Buenos Aires",
            "AR",
            mock_db,
            geo_filter=(-34.6, -58.4, 5.0),
        )

        assert len(result["restaurants"]) == 1
