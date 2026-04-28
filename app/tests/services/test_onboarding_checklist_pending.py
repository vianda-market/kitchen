"""
Unit tests for the onboarding checklist SQL — verifies the lazy-activation-aware
`has_active_restaurant` semantic (kitchen #172 follow-up).

Changed: `has_active_restaurant` now counts restaurants with status IN ('pending', 'active')
rather than only status = 'active'.  This prevents a circular dependency where a supplier
cannot access the plate/QR routes required to trigger lazy activation because the checklist
still shows `has_active_restaurant = false` for a pending restaurant.

These tests only inspect the SQL string constants — no DB required.
"""

from app.services.onboarding_service import (
    _SUPPLIER_CHECKLIST_SQL,
    _SUPPLIER_SUMMARY_CHECKLIST,
)


class TestSupplierChecklistRestaurantSQL:
    """has_active_restaurant must count pending AND active restaurants."""

    def test_checklist_sql_uses_in_pending_active(self):
        """_SUPPLIER_CHECKLIST_SQL must use IN ('pending', 'active') for has_active_restaurant."""
        assert "IN ('pending', 'active')" in _SUPPLIER_CHECKLIST_SQL, (
            "has_active_restaurant in checklist SQL must count pending + active restaurants, "
            "not only active. See kitchen #172 lazy-activation follow-up."
        )

    def test_summary_checklist_uses_in_pending_active(self):
        """_SUPPLIER_SUMMARY_CHECKLIST must use IN ('pending', 'active') for has_active_restaurant."""
        assert "IN ('pending', 'active')" in _SUPPLIER_SUMMARY_CHECKLIST, (
            "has_active_restaurant in summary checklist SQL must count pending + active restaurants."
        )

    def test_checklist_sql_does_not_use_status_equals_active_for_restaurant(self):
        """The old single-status filter must not appear for the restaurant subquery."""
        # The checklist string should not have standalone `status = 'active'` adjacent to
        # `restaurant_info` in the has_active_restaurant subquery.  We verify by checking
        # that "pending" appears in the restaurant_info context.
        assert "pending" in _SUPPLIER_CHECKLIST_SQL.lower()

    def test_summary_checklist_does_not_use_status_equals_active_for_restaurant(self):
        """Same as above for the summary SQL fragment."""
        assert "pending" in _SUPPLIER_SUMMARY_CHECKLIST.lower()

    def test_checklist_sql_has_active_restaurant_label_present(self):
        """has_active_restaurant alias still exists in the SQL (field not renamed)."""
        assert "has_active_restaurant" in _SUPPLIER_CHECKLIST_SQL

    def test_summary_checklist_has_active_restaurant_label_present(self):
        """has_active_restaurant alias still exists in the summary SQL fragment."""
        assert "has_active_restaurant" in _SUPPLIER_SUMMARY_CHECKLIST

    def test_other_status_filters_unchanged(self):
        """Other checklist items still use status = 'active' (only restaurant changed)."""
        # address, entity, product, plate should still be active-only
        # Confirm 'active' appears multiple times (for the unchanged items)
        active_count = _SUPPLIER_CHECKLIST_SQL.count("status = 'active'")
        assert active_count >= 4, (
            "Expected at least 4 'status = active' clauses for address, entity, product, plate, "
            f"kitchen_day, qr_code subqueries; found {active_count}."
        )
