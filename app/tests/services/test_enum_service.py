"""
Unit Tests for Enum Service

Tests for the enum service that provides centralized access to all system enum values.
"""

import unittest

from app.services.enum_service import EnumService, enum_service


class TestEnumService(unittest.TestCase):
    """Test suite for EnumService"""

    def test_get_all_enums_returns_dict(self):
        """Test that get_all_enums returns a dictionary"""
        enums = enum_service.get_all_enums()

        self.assertIsInstance(enums, dict)
        self.assertGreater(len(enums), 0, "Enums dictionary should not be empty")

    def test_all_enums_have_values(self):
        """Test that all enum types have at least one value (institution_type_assignable can be empty when no user context)"""
        enums = enum_service.get_all_enums()

        for enum_name, enum_values in enums.items():
            with self.subTest(enum=enum_name):
                self.assertIsInstance(enum_values, list, f"{enum_name} should be a list")
                if enum_name != "institution_type_assignable":
                    self.assertGreater(len(enum_values), 0, f"{enum_name} should have at least one value")
                # Ensure all values are strings
                for value in enum_values:
                    self.assertIsInstance(value, str, f"All values in {enum_name} should be strings")

    def test_get_enum_by_name_valid(self):
        """Test fetching a specific enum by name"""
        status_values = enum_service.get_enum_by_name("status")

        self.assertIsInstance(status_values, list)
        self.assertIn("active", status_values)
        self.assertIn("inactive", status_values)

    def test_get_enum_by_name_with_context_user(self):
        """Test that status with context=user returns only active and inactive"""
        status_values = enum_service.get_enum_by_name("status", context="user")
        self.assertIsInstance(status_values, list)
        self.assertEqual(set(status_values), {"active", "inactive"})
        self.assertNotIn("arrived", status_values)

    def test_get_enum_by_name_with_context_restaurant(self):
        """Test that status with context=restaurant returns only active, pending, inactive"""
        status_values = enum_service.get_enum_by_name("status", context="restaurant")
        self.assertIsInstance(status_values, list)
        self.assertEqual(set(status_values), {"active", "pending", "inactive"})
        self.assertNotIn("arrived", status_values)
        self.assertNotIn("processed", status_values)

    def test_get_enum_by_name_invalid(self):
        """Test that invalid enum name raises ValueError"""
        with self.assertRaises(ValueError) as context:
            enum_service.get_enum_by_name("invalid_enum_name")

        self.assertIn("Unknown enum type", str(context.exception))

    def test_status_enum_values(self):
        """Test that status enum has expected values"""
        enums = enum_service.get_all_enums()
        status_values = enums["status"]

        # Check for expected status values (general: Active, Pending, Inactive)
        expected_statuses = ["active", "pending", "inactive"]
        for status in expected_statuses:
            self.assertIn(status, status_values, f"Status enum should include '{status}'")

    def test_subscription_status_values(self):
        """Test that subscription_status enum has expected values"""
        enums = enum_service.get_all_enums()
        subscription_status_values = enums["subscription_status"]

        # Check for expected subscription status values
        expected_statuses = ["active", "on_hold", "pending", "cancelled"]
        for status in expected_statuses:
            self.assertIn(status, subscription_status_values, f"Subscription status enum should include '{status}'")

    def test_portion_size_display_values(self):
        """Test that portion_size_display enum has expected values"""
        enums = enum_service.get_all_enums()
        self.assertIn("portion_size_display", enums)
        portion_values = enums["portion_size_display"]
        expected = ["light", "standard", "large", "insufficient_reviews"]
        self.assertEqual(
            set(portion_values),
            set(expected),
            "portion_size_display should have light, standard, large, insufficient_reviews",
        )

    def test_dietary_flag_values(self):
        """Test that dietary_flag enum has all 7 dietary restriction values exposed via /enums/ (K1)."""
        enums = enum_service.get_all_enums()
        self.assertIn("dietary_flag", enums)
        dietary_values = enums["dietary_flag"]
        expected = {"vegan", "vegetarian", "gluten_free", "dairy_free", "nut_free", "halal", "kosher"}
        self.assertEqual(
            set(dietary_values),
            expected,
            "dietary_flag should expose all 7 DietaryFlag enum values",
        )

    def test_all_enums_keys_match_spec(self):
        """Test that all enum keys match the frontend specification"""
        enums = enum_service.get_all_enums()

        # Expected enum keys from frontend spec (includes context-scoped status keys)
        expected_keys = {
            "status",
            "status_user",
            "status_restaurant",
            "status_discretionary",
            "status_vianda_pickup",
            "status_bill",
            "address_type",
            "role_type",
            "institution_type",
            "institution_type_assignable",
            "role_name",
            "subscription_status",
            "method_type",
            "transaction_type",
            "street_type",
            "kitchen_day",
            "pickup_type",
            "discretionary_reason",
            "portion_size_display",
            "bill_resolution",
            "favorite_entity_type",
            "bill_payout_status",
            "dietary_flag",
        }

        actual_keys = set(enums.keys())

        # All expected keys should be present
        self.assertEqual(expected_keys, actual_keys, "Enum keys should match frontend specification")

    def test_role_type_values(self):
        """Test that role_type enum has expected values"""
        enums = enum_service.get_all_enums()
        role_type_values = enums["role_type"]

        # Check for expected role type values
        expected_roles = ["internal", "supplier", "customer", "employer"]
        self.assertEqual(len(role_type_values), len(expected_roles), "Should have exactly 3 role types")
        for role in expected_roles:
            self.assertIn(role, role_type_values, f"Role type enum should include '{role}'")

    def test_kitchen_day_values(self):
        """Test that kitchen_day enum has weekday values"""
        enums = enum_service.get_all_enums()
        kitchen_day_values = enums["kitchen_day"]

        # Check for expected weekdays (Monday through Friday)
        expected_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        self.assertEqual(len(kitchen_day_values), 5, "Should have exactly 5 kitchen days (weekdays)")
        for day in expected_days:
            self.assertIn(day, kitchen_day_values, f"Kitchen day enum should include '{day}'")

    def test_payment_method_type_values(self):
        """Test that method_type enum includes expected payment method providers"""
        enums = enum_service.get_all_enums()
        method_type_values = enums["method_type"]

        # Check for expected payment method providers (Stripe, Mercado Pago, PayU)
        expected_methods = ["stripe", "mercado_pago", "payu"]
        for method in expected_methods:
            self.assertIn(method, method_type_values, f"Payment method type enum should include '{method}'")

    def test_street_type_values(self):
        """Test that street_type enum includes common abbreviations"""
        enums = enum_service.get_all_enums()
        street_type_values = enums["street_type"]

        # Check for expected street type abbreviations
        expected_types = ["st", "ave", "blvd", "rd", "dr"]
        for street_type in expected_types:
            self.assertIn(street_type, street_type_values, f"Street type enum should include '{street_type}'")

    def test_get_assignable_institution_types_super_admin(self):
        """Super Admin gets all four institution types."""
        result = EnumService.get_assignable_institution_types(
            {
                "role_type": "internal",
                "role_name": "super_admin",
            }
        )
        self.assertEqual(set(result), {"internal", "supplier", "customer", "employer"})

    def test_get_assignable_institution_types_admin(self):
        """Admin gets Supplier, Employer only (no Internal, no Customer)."""
        result = EnumService.get_assignable_institution_types(
            {
                "role_type": "internal",
                "role_name": "admin",
            }
        )
        self.assertEqual(set(result), {"supplier", "employer"})
        self.assertNotIn("internal", result)
        self.assertNotIn("customer", result)

    def test_get_assignable_institution_types_supplier(self):
        """Supplier gets empty list (cannot create institutions)."""
        result = EnumService.get_assignable_institution_types(
            {
                "role_type": "supplier",
                "role_name": "admin",
            }
        )
        self.assertEqual(result, [])

    def test_enum_service_singleton_consistency(self):
        """Test that enum service returns consistent results across calls"""
        enums1 = enum_service.get_all_enums()
        enums2 = enum_service.get_all_enums()

        # Both calls should return the same data
        self.assertEqual(enums1.keys(), enums2.keys(), "Enum keys should be consistent across calls")

        for key in enums1:
            self.assertEqual(enums1[key], enums2[key], f"Values for '{key}' should be consistent across calls")


if __name__ == "__main__":
    unittest.main()
