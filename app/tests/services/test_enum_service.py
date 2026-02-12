"""
Unit Tests for Enum Service

Tests for the enum service that provides centralized access to all system enum values.
"""

import unittest
from app.services.enum_service import enum_service, EnumService


class TestEnumService(unittest.TestCase):
    """Test suite for EnumService"""

    def test_get_all_enums_returns_dict(self):
        """Test that get_all_enums returns a dictionary"""
        enums = enum_service.get_all_enums()
        
        self.assertIsInstance(enums, dict)
        self.assertGreater(len(enums), 0, "Enums dictionary should not be empty")

    def test_all_enums_have_values(self):
        """Test that all enum types have at least one value"""
        enums = enum_service.get_all_enums()
        
        for enum_name, enum_values in enums.items():
            with self.subTest(enum=enum_name):
                self.assertIsInstance(enum_values, list, f"{enum_name} should be a list")
                self.assertGreater(len(enum_values), 0, f"{enum_name} should have at least one value")
                # Ensure all values are strings
                for value in enum_values:
                    self.assertIsInstance(value, str, f"All values in {enum_name} should be strings")

    def test_get_enum_by_name_valid(self):
        """Test fetching a specific enum by name"""
        status_values = enum_service.get_enum_by_name('status')
        
        self.assertIsInstance(status_values, list)
        self.assertIn('Active', status_values)
        self.assertIn('Inactive', status_values)

    def test_get_enum_by_name_invalid(self):
        """Test that invalid enum name raises ValueError"""
        with self.assertRaises(ValueError) as context:
            enum_service.get_enum_by_name('invalid_enum_name')
        
        self.assertIn("Unknown enum type", str(context.exception))

    def test_status_enum_values(self):
        """Test that status enum has expected values"""
        enums = enum_service.get_all_enums()
        status_values = enums['status']
        
        # Check for expected status values
        expected_statuses = ['Active', 'Inactive', 'Pending', 'Cancelled']
        for status in expected_statuses:
            self.assertIn(status, status_values, f"Status enum should include '{status}'")

    def test_subscription_status_values(self):
        """Test that subscription_status enum has expected values"""
        enums = enum_service.get_all_enums()
        subscription_status_values = enums['subscription_status']
        
        # Check for expected subscription status values
        expected_statuses = ['Active', 'On Hold', 'Pending', 'Expired', 'Cancelled']
        for status in expected_statuses:
            self.assertIn(status, subscription_status_values, 
                         f"Subscription status enum should include '{status}'")

    def test_all_enums_keys_match_spec(self):
        """Test that all enum keys match the frontend specification"""
        enums = enum_service.get_all_enums()
        
        # Expected enum keys from frontend spec
        expected_keys = {
            'status', 'address_type', 'role_type', 'role_name',
            'subscription_status', 'method_type', 'account_type',
            'transaction_type', 'street_type', 'kitchen_day',
            'pickup_type', 'discretionary_reason'
        }
        
        actual_keys = set(enums.keys())
        
        # All expected keys should be present
        self.assertEqual(expected_keys, actual_keys, 
                        "Enum keys should match frontend specification")

    def test_role_type_values(self):
        """Test that role_type enum has expected values"""
        enums = enum_service.get_all_enums()
        role_type_values = enums['role_type']
        
        # Check for expected role type values
        expected_roles = ['Employee', 'Supplier', 'Customer']
        self.assertEqual(len(role_type_values), len(expected_roles), 
                        "Should have exactly 3 role types")
        for role in expected_roles:
            self.assertIn(role, role_type_values, 
                         f"Role type enum should include '{role}'")

    def test_kitchen_day_values(self):
        """Test that kitchen_day enum has weekday values"""
        enums = enum_service.get_all_enums()
        kitchen_day_values = enums['kitchen_day']
        
        # Check for expected weekdays (Monday through Friday)
        expected_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        self.assertEqual(len(kitchen_day_values), 5, 
                        "Should have exactly 5 kitchen days (weekdays)")
        for day in expected_days:
            self.assertIn(day, kitchen_day_values, 
                         f"Kitchen day enum should include '{day}'")

    def test_payment_method_type_values(self):
        """Test that method_type enum includes expected payment methods"""
        enums = enum_service.get_all_enums()
        method_type_values = enums['method_type']
        
        # Check for expected payment methods
        expected_methods = ['Credit Card', 'Debit Card', 'Bank Transfer', 'Cash', 'Mercado Pago']
        for method in expected_methods:
            self.assertIn(method, method_type_values, 
                         f"Payment method type enum should include '{method}'")

    def test_street_type_values(self):
        """Test that street_type enum includes common abbreviations"""
        enums = enum_service.get_all_enums()
        street_type_values = enums['street_type']
        
        # Check for expected street type abbreviations
        expected_types = ['St', 'Ave', 'Blvd', 'Rd', 'Dr']
        for street_type in expected_types:
            self.assertIn(street_type, street_type_values, 
                         f"Street type enum should include '{street_type}'")

    def test_enum_service_singleton_consistency(self):
        """Test that enum service returns consistent results across calls"""
        enums1 = enum_service.get_all_enums()
        enums2 = enum_service.get_all_enums()
        
        # Both calls should return the same data
        self.assertEqual(enums1.keys(), enums2.keys(), 
                        "Enum keys should be consistent across calls")
        
        for key in enums1.keys():
            self.assertEqual(enums1[key], enums2[key], 
                           f"Values for '{key}' should be consistent across calls")


if __name__ == '__main__':
    unittest.main()
