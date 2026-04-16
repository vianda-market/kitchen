"""
Unit tests for market_service: is_global_market, reject_global_market_for_entity.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.market_service import (
    GLOBAL_MARKET_ID,
    is_global_market,
    reject_global_market_for_entity,
)


class TestIsGlobalMarket:
    def test_returns_true_for_global_market_id(self):
        assert is_global_market(GLOBAL_MARKET_ID) is True

    def test_returns_false_for_none(self):
        assert is_global_market(None) is False

    def test_returns_false_for_other_uuid(self):
        assert is_global_market(uuid4()) is False


class TestRejectGlobalMarketForEntity:
    def test_raises_400_when_market_id_is_global(self):
        with pytest.raises(HTTPException) as exc_info:
            reject_global_market_for_entity(GLOBAL_MARKET_ID, "plan")
        assert exc_info.value.status_code == 400
        assert "Global Marketplace" in exc_info.value.detail
        assert "plan" in exc_info.value.detail

    def test_does_not_raise_when_market_id_is_none(self):
        reject_global_market_for_entity(None, "plan")

    def test_does_not_raise_when_market_id_is_non_global(self):
        reject_global_market_for_entity(uuid4(), "plan")

    def test_entity_name_in_detail(self):
        with pytest.raises(HTTPException) as exc_info:
            reject_global_market_for_entity(GLOBAL_MARKET_ID, "subscription")
        assert "subscription" in exc_info.value.detail
