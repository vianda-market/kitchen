"""
Unit tests for zipcode metrics service (lead flow).

Covers: exact match, no match, default country, response shape.
"""

import unittest
from unittest.mock import patch, MagicMock

from app.services.zipcode_metrics_service import get_zipcode_metrics


class TestZipcodeMetricsService(unittest.TestCase):
    """Test get_zipcode_metrics with mocked db_read."""

    def setUp(self):
        self.mock_conn = MagicMock()

    @patch("app.services.zipcode_metrics_service.db_read")
    def test_exact_match_returns_count_and_center(self, mock_db_read):
        """When requested zip matches a postal_code, return that zip's count and optional center."""
        def db_read_side_effect(query, values, connection=None, fetch_one=False):
            if "DISTINCT a.postal_code" in query:
                return [{"postal_code": "12345"}, {"postal_code": "67890"}]
            if "COUNT(DISTINCT" in query:
                return {"cnt": 2} if fetch_one else None
            if "AVG(g.latitude)" in query:
                return {"lat": 40.5, "lng": -74.0} if fetch_one else None
            return [] if not fetch_one else None
        mock_db_read.side_effect = db_read_side_effect
        result = get_zipcode_metrics("12345", "US", self.mock_conn)
        self.assertEqual(result["requested_zipcode"], "12345")
        self.assertEqual(result["matched_zipcode"], "12345")
        self.assertEqual(result["restaurant_count"], 2)
        self.assertTrue(result["has_coverage"])
        self.assertIsNotNone(result["center"])
        self.assertEqual(result["center"]["lat"], 40.5)
        self.assertEqual(result["center"]["lng"], -74.0)

    @patch("app.services.zipcode_metrics_service.db_read")
    def test_no_match_uses_first_postal_code(self, mock_db_read):
        """When no exact match, fallback to first postal_code; count for that matched zip."""
        def db_read_side_effect(query, values, connection=None, fetch_one=False):
            if "DISTINCT a.postal_code" in query:
                return [{"postal_code": "11111"}, {"postal_code": "99999"}]
            if "COUNT(DISTINCT" in query:
                return {"cnt": 1} if fetch_one else None
            if "AVG(g.latitude)" in query:
                return {"lat": 40.0, "lng": -73.0} if fetch_one else None
            return [] if not fetch_one else None
        mock_db_read.side_effect = db_read_side_effect
        result = get_zipcode_metrics("55555", "US", self.mock_conn)
        self.assertEqual(result["requested_zipcode"], "55555")
        self.assertEqual(result["matched_zipcode"], "11111")
        self.assertEqual(result["restaurant_count"], 1)
        self.assertTrue(result["has_coverage"])

    @patch("app.services.zipcode_metrics_service.db_read")
    def test_no_data_in_country_returns_zero_coverage(self, mock_db_read):
        """When no postal_codes in country, return requested as matched, count 0, no center."""
        def db_read_side_effect(query, values, connection=None, fetch_one=False):
            if "DISTINCT a.postal_code" in query:
                return []
            if "COUNT(DISTINCT" in query:
                return {"cnt": 0} if fetch_one else None
            return [] if not fetch_one else None
        mock_db_read.side_effect = db_read_side_effect
        result = get_zipcode_metrics("12345", "US", self.mock_conn)
        self.assertEqual(result["requested_zipcode"], "12345")
        self.assertEqual(result["matched_zipcode"], "12345")
        self.assertEqual(result["restaurant_count"], 0)
        self.assertFalse(result["has_coverage"])
        self.assertIsNone(result["center"])

    @patch("app.services.zipcode_metrics_service.db_read")
    def test_service_uses_country_code_as_given(self, mock_db_read):
        """Service uses country_code as received; no normalization (route applies default/normalize)."""
        def db_read_side_effect(query, values, connection=None, fetch_one=False):
            self.assertEqual(values[0], "US")
            if "DISTINCT a.postal_code" in query:
                return []
            if "COUNT(DISTINCT" in query:
                return {"cnt": 0} if fetch_one else None
            return [] if not fetch_one else None
        mock_db_read.side_effect = db_read_side_effect
        result = get_zipcode_metrics("12345", "US", self.mock_conn)
        self.assertEqual(result["matched_zipcode"], "12345")
        self.assertEqual(result["restaurant_count"], 0)

    @patch("app.services.zipcode_metrics_service.db_read")
    def test_service_passes_through_country_code(self, mock_db_read):
        """Service passes country_code to queries as-is (caller passes already-normalized)."""
        def db_read_side_effect(query, values, connection=None, fetch_one=False):
            self.assertEqual(values[0], "AR")
            if "DISTINCT a.postal_code" in query:
                return []
            if "COUNT(DISTINCT" in query:
                return {"cnt": 0} if fetch_one else None
            return [] if not fetch_one else None
        mock_db_read.side_effect = db_read_side_effect
        get_zipcode_metrics("1234", "AR", self.mock_conn)

    @patch("app.services.zipcode_metrics_service.db_read")
    def test_visibility_queries_require_active_qr_code(self, mock_db_read):
        """Leads/explorer visibility excludes restaurants without active QR code; queries include qr_code EXISTS."""
        def db_read_side_effect(query, values, connection=None, fetch_one=False):
            # All queries used for zipcode metrics should include qr_code filter
            self.assertIn("qr_code", query, "Visibility queries must filter by active QR code")
            self.assertIn("Active", query, "QR code filter must require status Active")
            if "DISTINCT a.postal_code" in query:
                return []
            if "COUNT(DISTINCT" in query:
                return {"cnt": 0} if fetch_one else None
            return [] if not fetch_one else None
        mock_db_read.side_effect = db_read_side_effect
        get_zipcode_metrics("12345", "US", self.mock_conn)
        # Verify db_read was called (at least for postal codes query)
        self.assertGreaterEqual(mock_db_read.call_count, 1)
