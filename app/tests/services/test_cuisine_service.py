"""Unit tests for cuisine_service business logic"""

import pytest
from unittest.mock import patch, call

from app.services import cuisine_service


class TestSearchCuisines:
    """Tests for cuisine_service.search_cuisines."""

    @patch("app.services.cuisine_service.db_read")
    def test_search_cuisines_no_filter(self, mock_db_read):
        """Without search query, returns all active cuisines."""
        mock_db_read.return_value = [
            {"cuisine_id": "aaa", "cuisine_name": "Italian", "slug": "italian"},
            {"cuisine_id": "bbb", "cuisine_name": "French", "slug": "french"},
        ]
        result = cuisine_service.search_cuisines(db=None)
        assert len(result) == 2
        assert result[0]["cuisine_name"] == "Italian"
        mock_db_read.assert_called_once()
        sql = mock_db_read.call_args[0][0]
        assert "ILIKE" not in sql

    @patch("app.services.cuisine_service.db_read")
    def test_search_cuisines_with_query(self, mock_db_read):
        """With search query, ILIKE params are passed."""
        mock_db_read.return_value = [
            {"cuisine_id": "aaa", "cuisine_name": "Italian", "slug": "italian"},
        ]
        result = cuisine_service.search_cuisines(db=None, search="ita")
        assert len(result) == 1
        mock_db_read.assert_called_once()
        sql = mock_db_read.call_args[0][0]
        params = mock_db_read.call_args[0][1]
        assert "ILIKE" in sql
        assert "%ita%" in params

    @patch("app.services.cuisine_service.db_read")
    def test_search_cuisines_empty_result(self, mock_db_read):
        """When db_read returns None, returns empty list."""
        mock_db_read.return_value = None
        result = cuisine_service.search_cuisines(db=None)
        assert result == []


class TestGenerateSlug:
    """Tests for cuisine_service._generate_slug."""

    @patch("app.services.cuisine_service.db_read")
    def test_generate_slug_basic(self, mock_db_read):
        """Basic name produces lowercase hyphenated slug with no collision."""
        mock_db_read.return_value = None  # No collision
        slug = cuisine_service._generate_slug("Italian Food", db=None)
        assert slug == "italian-food"
        mock_db_read.assert_called_once()

    @patch("app.services.cuisine_service.db_read")
    def test_generate_slug_collision(self, mock_db_read):
        """When base slug exists, appends -2 suffix."""
        # First call finds collision, second call finds no collision
        mock_db_read.side_effect = [{"slug": "italian"}, None]
        slug = cuisine_service._generate_slug("Italian", db=None)
        assert slug == "italian-2"
        assert mock_db_read.call_count == 2

    @patch("app.services.cuisine_service.db_read")
    def test_generate_slug_special_characters(self, mock_db_read):
        """Special characters are stripped and replaced with hyphens."""
        mock_db_read.return_value = None
        slug = cuisine_service._generate_slug("Café & Bistro!", db=None)
        assert slug == "caf-bistro"

    @patch("app.services.cuisine_service.db_read")
    def test_generate_slug_multiple_collisions(self, mock_db_read):
        """Multiple collisions increment suffix until free slug found."""
        mock_db_read.side_effect = [
            {"slug": "thai"},      # thai exists
            {"slug": "thai-2"},    # thai-2 exists
            None,                  # thai-3 is free
        ]
        slug = cuisine_service._generate_slug("Thai", db=None)
        assert slug == "thai-3"
        assert mock_db_read.call_count == 3
