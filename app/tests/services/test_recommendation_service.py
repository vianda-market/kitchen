"""
Unit tests for recommendation service.

MVP: plate favorited, restaurant favorited, both, neither, no user_id.
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from app.services.recommendation_service import (
    apply_recommendation,
    _compute_plate_score,
    _compute_restaurant_score,
)


class TestComputePlateScore:
    """_compute_plate_score returns correct weight for plate/restaurant favorited."""

    def test_plate_favorited_returns_plate_weight(self):
        plate = {"plate_id": uuid4()}
        fav_plate_ids = {str(plate["plate_id"])}
        fav_restaurant_ids = set()
        rid = uuid4()
        score = _compute_plate_score(plate, fav_plate_ids, fav_restaurant_ids, rid)
        assert score == 10  # WEIGHT_PLATE_FAVORITED

    def test_restaurant_favorited_returns_restaurant_weight(self):
        plate = {"plate_id": uuid4()}
        fav_plate_ids = set()
        fav_restaurant_ids = {str(uuid4())}
        rid_str = list(fav_restaurant_ids)[0]
        score = _compute_plate_score(plate, fav_plate_ids, fav_restaurant_ids, rid_str)
        assert score == 5  # WEIGHT_RESTAURANT_FAVORITED

    def test_neither_favorited_returns_zero(self):
        plate = {"plate_id": uuid4()}
        fav_plate_ids = set()
        fav_restaurant_ids = set()
        score = _compute_plate_score(plate, fav_plate_ids, fav_restaurant_ids, uuid4())
        assert score == 0

    def test_plate_favorited_takes_precedence_over_restaurant(self):
        plate = {"plate_id": uuid4()}
        fav_plate_ids = {str(plate["plate_id"])}
        fav_restaurant_ids = {str(uuid4())}
        score = _compute_plate_score(plate, fav_plate_ids, fav_restaurant_ids, list(fav_restaurant_ids)[0])
        assert score == 10  # Plate favorited wins


class TestComputeRestaurantScore:
    """_compute_restaurant_score returns correct weight for restaurant/plate favorited."""

    def test_restaurant_favorited_returns_weight(self):
        restaurant = {"restaurant_id": uuid4()}
        fav_restaurant_ids = {str(restaurant["restaurant_id"])}
        plates = [{"plate_id": uuid4()}]
        fav_plate_ids = set()
        score = _compute_restaurant_score(restaurant, fav_restaurant_ids, plates, fav_plate_ids)
        assert score == 5

    def test_any_plate_favorited_returns_weight(self):
        pid = uuid4()
        restaurant = {"restaurant_id": uuid4()}
        fav_restaurant_ids = set()
        plates = [{"plate_id": pid}]
        fav_plate_ids = {str(pid)}
        score = _compute_restaurant_score(restaurant, fav_restaurant_ids, plates, fav_plate_ids)
        assert score == 5

    def test_neither_returns_zero(self):
        restaurant = {"restaurant_id": uuid4()}
        fav_restaurant_ids = set()
        plates = [{"plate_id": uuid4()}]
        fav_plate_ids = set()
        score = _compute_restaurant_score(restaurant, fav_restaurant_ids, plates, fav_plate_ids)
        assert score == 0


class TestApplyRecommendation:
    """apply_recommendation sets is_recommended and _recommendation_score."""

    def test_no_user_id_sets_all_false(self):
        rid = uuid4()
        pid = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "plates": [{"plate_id": pid, "product_name": "Plate A"}],
            }
        ]
        mock_db = MagicMock()

        apply_recommendation(restaurants, None, mock_db)

        assert restaurants[0]["is_recommended"] is False
        assert restaurants[0]["_recommendation_score"] == 0
        assert restaurants[0]["plates"][0]["is_recommended"] is False
        assert restaurants[0]["plates"][0]["_recommendation_score"] == 0

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_plate_favorited_sets_recommended(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "plates": [{"plate_id": pid, "product_name": "Plate A"}],
            }
        ]
        mock_get_fav.return_value = {"plate_ids": [pid], "restaurant_ids": []}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db)

        assert restaurants[0]["plates"][0]["is_recommended"] is True
        assert restaurants[0]["plates"][0]["_recommendation_score"] == 10
        assert restaurants[0]["is_recommended"] is True  # Restaurant has favorited plate

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_restaurant_favorited_sets_recommended_on_plates(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "plates": [{"plate_id": pid, "product_name": "Plate A"}],
            }
        ]
        mock_get_fav.return_value = {"plate_ids": [], "restaurant_ids": [rid]}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db)

        assert restaurants[0]["is_recommended"] is True
        assert restaurants[0]["plates"][0]["is_recommended"] is True
        assert restaurants[0]["plates"][0]["_recommendation_score"] == 5

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_neither_favorited_sets_not_recommended(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "plates": [{"plate_id": pid, "product_name": "Plate A"}],
            }
        ]
        mock_get_fav.return_value = {"plate_ids": [], "restaurant_ids": []}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db)

        assert restaurants[0]["is_recommended"] is False
        assert restaurants[0]["plates"][0]["is_recommended"] is False

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_uses_favorite_ids_when_provided(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "plates": [{"plate_id": pid, "product_name": "Plate A"}],
            }
        ]
        fav = {"plate_ids": [pid], "restaurant_ids": []}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db, favorite_ids=fav)

        mock_get_fav.assert_not_called()
        assert restaurants[0]["plates"][0]["is_recommended"] is True
