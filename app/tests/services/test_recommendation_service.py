"""
Unit tests for recommendation service.

MVP: vianda favorited, restaurant favorited, both, neither, no user_id.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.recommendation_service import (
    _compute_restaurant_score,
    _compute_vianda_score,
    apply_recommendation,
)


class TestComputePlateScore:
    """_compute_vianda_score returns correct weight for vianda/restaurant favorited."""

    def test_vianda_favorited_returns_vianda_weight(self):
        vianda = {"vianda_id": uuid4()}
        fav_vianda_ids = {str(vianda["vianda_id"])}
        fav_restaurant_ids = set()
        rid = uuid4()
        score = _compute_vianda_score(vianda, fav_vianda_ids, fav_restaurant_ids, rid)
        assert score == 10  # WEIGHT_VIANDA_FAVORITED

    def test_restaurant_favorited_returns_restaurant_weight(self):
        vianda = {"vianda_id": uuid4()}
        fav_vianda_ids = set()
        fav_restaurant_ids = {str(uuid4())}
        rid_str = list(fav_restaurant_ids)[0]
        score = _compute_vianda_score(vianda, fav_vianda_ids, fav_restaurant_ids, rid_str)
        assert score == 5  # WEIGHT_RESTAURANT_FAVORITED

    def test_neither_favorited_returns_zero(self):
        vianda = {"vianda_id": uuid4()}
        fav_vianda_ids = set()
        fav_restaurant_ids = set()
        score = _compute_vianda_score(vianda, fav_vianda_ids, fav_restaurant_ids, uuid4())
        assert score == 0

    def test_vianda_favorited_takes_precedence_over_restaurant(self):
        vianda = {"vianda_id": uuid4()}
        fav_vianda_ids = {str(vianda["vianda_id"])}
        fav_restaurant_ids = {str(uuid4())}
        score = _compute_vianda_score(vianda, fav_vianda_ids, fav_restaurant_ids, list(fav_restaurant_ids)[0])
        assert score == 10  # Vianda favorited wins


class TestComputeRestaurantScore:
    """_compute_restaurant_score returns correct weight for restaurant/vianda favorited."""

    def test_restaurant_favorited_returns_weight(self):
        restaurant = {"restaurant_id": uuid4()}
        fav_restaurant_ids = {str(restaurant["restaurant_id"])}
        viandas = [{"vianda_id": uuid4()}]
        fav_vianda_ids = set()
        score = _compute_restaurant_score(restaurant, fav_restaurant_ids, viandas, fav_vianda_ids)
        assert score == 5

    def test_any_vianda_favorited_returns_weight(self):
        pid = uuid4()
        restaurant = {"restaurant_id": uuid4()}
        fav_restaurant_ids = set()
        viandas = [{"vianda_id": pid}]
        fav_vianda_ids = {str(pid)}
        score = _compute_restaurant_score(restaurant, fav_restaurant_ids, viandas, fav_vianda_ids)
        assert score == 5

    def test_neither_returns_zero(self):
        restaurant = {"restaurant_id": uuid4()}
        fav_restaurant_ids = set()
        viandas = [{"vianda_id": uuid4()}]
        fav_vianda_ids = set()
        score = _compute_restaurant_score(restaurant, fav_restaurant_ids, viandas, fav_vianda_ids)
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
                "viandas": [{"vianda_id": pid, "product_name": "Vianda A"}],
            }
        ]
        mock_db = MagicMock()

        apply_recommendation(restaurants, None, mock_db)

        assert restaurants[0]["is_recommended"] is False
        assert restaurants[0]["_recommendation_score"] == 0
        assert restaurants[0]["viandas"][0]["is_recommended"] is False
        assert restaurants[0]["viandas"][0]["_recommendation_score"] == 0

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_vianda_favorited_sets_recommended(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "viandas": [{"vianda_id": pid, "product_name": "Vianda A"}],
            }
        ]
        mock_get_fav.return_value = {"vianda_ids": [pid], "restaurant_ids": []}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db)

        assert restaurants[0]["viandas"][0]["is_recommended"] is True
        assert restaurants[0]["viandas"][0]["_recommendation_score"] == 10
        assert restaurants[0]["is_recommended"] is True  # Restaurant has favorited vianda

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_restaurant_favorited_sets_recommended_on_viandas(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "viandas": [{"vianda_id": pid, "product_name": "Vianda A"}],
            }
        ]
        mock_get_fav.return_value = {"vianda_ids": [], "restaurant_ids": [rid]}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db)

        assert restaurants[0]["is_recommended"] is True
        assert restaurants[0]["viandas"][0]["is_recommended"] is True
        assert restaurants[0]["viandas"][0]["_recommendation_score"] == 5

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_neither_favorited_sets_not_recommended(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "viandas": [{"vianda_id": pid, "product_name": "Vianda A"}],
            }
        ]
        mock_get_fav.return_value = {"vianda_ids": [], "restaurant_ids": []}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db)

        assert restaurants[0]["is_recommended"] is False
        assert restaurants[0]["viandas"][0]["is_recommended"] is False

    @patch("app.services.recommendation_service.get_favorite_ids")
    def test_uses_favorite_ids_when_provided(self, mock_get_fav):
        rid = uuid4()
        pid = uuid4()
        user_id = uuid4()
        restaurants = [
            {
                "restaurant_id": rid,
                "name": "Test",
                "viandas": [{"vianda_id": pid, "product_name": "Vianda A"}],
            }
        ]
        fav = {"vianda_ids": [pid], "restaurant_ids": []}
        mock_db = MagicMock()

        apply_recommendation(restaurants, user_id, mock_db, favorite_ids=fav)

        mock_get_fav.assert_not_called()
        assert restaurants[0]["viandas"][0]["is_recommended"] is True
