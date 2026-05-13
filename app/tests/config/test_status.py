"""
Unit tests for STATUS_CONTEXTS vianda and plan entries.

Verifies that:
1. get_by_context("vianda") returns only catalog-visibility values (active, inactive).
2. get_by_context("plan") returns only offering-state values (active, inactive).
3. Billing-only value (processed) is absent from both contexts.
4. Pickup-lifecycle values (pending, arrived, handed_out, completed, cancelled)
   are absent from both contexts.
"""

import unittest

from app.config.enums.status import Status


class TestStatusContextPlate(unittest.TestCase):
    """Tests for STATUS_CONTEXTS["vianda"]."""

    def setUp(self) -> None:
        self.values = Status.get_by_context("vianda")

    def test_vianda_context_returns_list(self) -> None:
        self.assertIsInstance(self.values, list)

    def test_vianda_context_has_active(self) -> None:
        self.assertIn("active", self.values)

    def test_vianda_context_has_inactive(self) -> None:
        self.assertIn("inactive", self.values)

    def test_vianda_context_exact_members(self) -> None:
        """vianda context must contain exactly active and inactive — no more, no less."""
        self.assertEqual(set(self.values), {"active", "inactive"})

    def test_vianda_context_excludes_processed(self) -> None:
        """processed is billing-only and must not appear in vianda context."""
        self.assertNotIn("processed", self.values)

    def test_vianda_context_excludes_pickup_lifecycle_states(self) -> None:
        """Pickup-lifecycle values do not apply to vianda_info catalog records."""
        for value in ("pending", "arrived", "handed_out", "completed", "cancelled"):
            with self.subTest(value=value):
                self.assertNotIn(value, self.values)


class TestStatusContextPlan(unittest.TestCase):
    """Tests for STATUS_CONTEXTS["plan"]."""

    def setUp(self) -> None:
        self.values = Status.get_by_context("plan")

    def test_plan_context_returns_list(self) -> None:
        self.assertIsInstance(self.values, list)

    def test_plan_context_has_active(self) -> None:
        self.assertIn("active", self.values)

    def test_plan_context_has_inactive(self) -> None:
        self.assertIn("inactive", self.values)

    def test_plan_context_exact_members(self) -> None:
        """plan context must contain exactly active and inactive — no more, no less."""
        self.assertEqual(set(self.values), {"active", "inactive"})

    def test_plan_context_excludes_processed(self) -> None:
        """processed is billing-only and must not appear in plan context."""
        self.assertNotIn("processed", self.values)

    def test_plan_context_excludes_pickup_lifecycle_states(self) -> None:
        """Pickup-lifecycle values do not apply to plan_info offering records."""
        for value in ("pending", "arrived", "handed_out", "completed", "cancelled"):
            with self.subTest(value=value):
                self.assertNotIn(value, self.values)


class TestStatusContextUnknown(unittest.TestCase):
    """Confirms unknown context still returns empty list (no regression)."""

    def test_unknown_context_returns_empty(self) -> None:
        self.assertEqual(Status.get_by_context("nonexistent_context"), [])


if __name__ == "__main__":
    unittest.main()
