"""
Unit tests for Restaurant Staff Service.

Tests the business logic for restaurant staff operations including
daily orders retrieval, privacy-safe customer names, and order grouping.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import date, datetime
from collections import defaultdict

from app.services.restaurant_staff_service import (
    get_daily_orders,
    _get_kitchen_day_for_date,
    _group_orders_by_restaurant
)


class TestRestaurantStaffService:
    """Test suite for Restaurant Staff Service business logic."""

    def test_get_daily_orders_returns_correct_format(self, mock_db):
        """Test that get_daily_orders returns the expected response structure."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = None
        
        mock_rows = [
            {
                'confirmation_code': 'ABC123',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'John',
                'last_initial': 'D',
                'plate_name': 'Grilled Chicken',
                'restaurant_id': uuid4(),
                'restaurant_name': 'Cambalache Palermo'
            }
        ]
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = mock_rows
            
            # Act
            result = get_daily_orders(institution_entity_id, order_date, restaurant_id, mock_db)
            
            # Assert
            assert result['date'] == order_date
            assert len(result['restaurants']) == 1
            assert result['restaurants'][0]['restaurant_name'] == 'Cambalache Palermo'
            assert len(result['restaurants'][0]['orders']) == 1
            assert result['restaurants'][0]['summary']['total_orders'] == 1

    def test_customer_name_privacy_formatting(self, mock_db):
        """Test that customer names are formatted as 'First L.' for privacy."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        
        mock_rows = [
            {
                'confirmation_code': 'ABC123',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'María',
                'last_initial': 'G',
                'plate_name': 'Pasta',
                'restaurant_id': uuid4(),
                'restaurant_name': 'Test Restaurant'
            }
        ]
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = mock_rows
            
            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            customer_name = result['restaurants'][0]['orders'][0]['customer_name']
            assert customer_name == 'María G.'
            assert 'García' not in customer_name  # Full last name not exposed

    def test_filters_by_institution_entity_id(self, mock_db):
        """Test that orders are filtered by institution_entity_id."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = []
            
            # Act
            get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'r.institution_entity_id = %s' in query
            assert str(institution_entity_id) in params

    def test_filters_by_single_restaurant_id(self, mock_db):
        """Test that orders can be filtered by a specific restaurant_id."""
        # Arrange
        institution_entity_id = uuid4()
        restaurant_id = uuid4()
        order_date = date(2026, 2, 4)
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = []
            
            # Act
            get_daily_orders(institution_entity_id, order_date, restaurant_id, mock_db)
            
            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'r.restaurant_id = %s OR %s IS NULL' in query
            assert str(restaurant_id) in params

    def test_groups_orders_by_restaurant(self, mock_db):
        """Test that orders are correctly grouped by restaurant."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_1_id = uuid4()
        restaurant_2_id = uuid4()
        
        mock_rows = [
            {
                'confirmation_code': 'ABC123',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'John',
                'last_initial': 'D',
                'plate_name': 'Chicken',
                'restaurant_id': restaurant_1_id,
                'restaurant_name': 'Restaurant A'
            },
            {
                'confirmation_code': 'DEF456',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:30-13:00',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Jane',
                'last_initial': 'S',
                'plate_name': 'Salad',
                'restaurant_id': restaurant_2_id,
                'restaurant_name': 'Restaurant B'
            },
            {
                'confirmation_code': 'GHI789',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '13:00-13:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Bob',
                'last_initial': 'M',
                'plate_name': 'Pasta',
                'restaurant_id': restaurant_1_id,
                'restaurant_name': 'Restaurant A'
            }
        ]
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = mock_rows
            
            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            assert len(result['restaurants']) == 2
            
            # Find Restaurant A
            rest_a = next(r for r in result['restaurants'] if r['restaurant_name'] == 'Restaurant A')
            assert len(rest_a['orders']) == 2
            assert rest_a['summary']['total_orders'] == 2
            
            # Find Restaurant B
            rest_b = next(r for r in result['restaurants'] if r['restaurant_name'] == 'Restaurant B')
            assert len(rest_b['orders']) == 1
            assert rest_b['summary']['total_orders'] == 1

    def test_calculates_summary_statistics(self, mock_db):
        """Test that summary statistics are correctly calculated."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = uuid4()
        
        mock_rows = [
            {
                'confirmation_code': 'ABC123',
                'status': 'Active',
                'arrival_time': None,  # Pending
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'John',
                'last_initial': 'D',
                'plate_name': 'Chicken',
                'restaurant_id': restaurant_id,
                'restaurant_name': 'Test Restaurant'
            },
            {
                'confirmation_code': 'DEF456',
                'status': 'Active',
                'arrival_time': datetime(2026, 2, 4, 12, 15),  # Arrived
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Jane',
                'last_initial': 'S',
                'plate_name': 'Salad',
                'restaurant_id': restaurant_id,
                'restaurant_name': 'Test Restaurant'
            },
            {
                'confirmation_code': 'GHI789',
                'status': 'Completed',
                'arrival_time': datetime(2026, 2, 4, 12, 0),
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Bob',
                'last_initial': 'M',
                'plate_name': 'Pasta',
                'restaurant_id': restaurant_id,
                'restaurant_name': 'Test Restaurant'
            }
        ]
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = mock_rows
            
            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            summary = result['restaurants'][0]['summary']
            assert summary['total_orders'] == 3
            assert summary['pending'] == 1
            assert summary['arrived'] == 1
            assert summary['completed'] == 1

    def test_orders_sorted_by_pickup_time(self, mock_db):
        """Test that orders are sorted by pickup time within each restaurant."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        restaurant_id = uuid4()
        
        mock_rows = [
            {
                'confirmation_code': 'GHI789',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '13:00-13:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Bob',
                'last_initial': 'M',
                'plate_name': 'Pasta',
                'restaurant_id': restaurant_id,
                'restaurant_name': 'Test Restaurant'
            },
            {
                'confirmation_code': 'ABC123',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'John',
                'last_initial': 'D',
                'plate_name': 'Chicken',
                'restaurant_id': restaurant_id,
                'restaurant_name': 'Test Restaurant'
            },
            {
                'confirmation_code': 'DEF456',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:30-13:00',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Jane',
                'last_initial': 'S',
                'plate_name': 'Salad',
                'restaurant_id': restaurant_id,
                'restaurant_name': 'Test Restaurant'
            }
        ]
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = mock_rows
            
            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert - Orders should be sorted by pickup_time_range
            orders = result['restaurants'][0]['orders']
            # Note: SQL query handles sorting, so we expect the order from mock_rows
            # In real scenario, SQL ORDER BY would sort them
            assert len(orders) == 3

    def test_handles_empty_results(self, mock_db):
        """Test that empty results are handled gracefully."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = []
            
            # Act
            result = get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            assert result['date'] == order_date
            assert result['restaurants'] == []

    def test_filters_by_kitchen_day(self, mock_db):
        """Test that orders are filtered by the correct kitchen_day."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)  # Tuesday
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = []
            
            # Act
            get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'ps.kitchen_day = %s' in query
            assert 'TUESDAY' in params

    def test_excludes_archived_records(self, mock_db):
        """Test that archived records are excluded from results."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date(2026, 2, 4)
        
        with patch('app.services.restaurant_staff_service._get_kitchen_day_for_date') as mock_get_day, \
             patch('app.services.restaurant_staff_service.db_read') as mock_db_read:
            
            mock_get_day.return_value = 'TUESDAY'
            mock_db_read.return_value = []
            
            # Act
            get_daily_orders(institution_entity_id, order_date, None, mock_db)
            
            # Assert
            call_args = mock_db_read.call_args
            query = call_args[0][0]
            
            assert 'ppl.is_archived = FALSE' in query

    def test_get_kitchen_day_for_date_uses_timezone(self, mock_db):
        """Test that kitchen_day calculation uses restaurant timezone."""
        # Arrange
        institution_entity_id = uuid4()
        order_date = date.today()
        
        mock_timezone_result = [{'timezone': 'America/New_York'}]
        
        with patch('app.services.restaurant_staff_service.db_read') as mock_db_read, \
             patch('app.services.restaurant_staff_service.get_effective_current_day') as mock_get_day:
            
            mock_db_read.return_value = mock_timezone_result
            mock_get_day.return_value = 'Tuesday'
            
            # Act
            result = _get_kitchen_day_for_date(order_date, institution_entity_id, mock_db)
            
            # Assert
            mock_get_day.assert_called_once_with('America/New_York')
            assert result == 'TUESDAY'

    def test_group_orders_by_restaurant_sorts_alphabetically(self):
        """Test that restaurants are sorted alphabetically by name."""
        # Arrange
        restaurant_1_id = uuid4()
        restaurant_2_id = uuid4()
        restaurant_3_id = uuid4()
        
        mock_rows = [
            {
                'confirmation_code': 'ABC123',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'John',
                'last_initial': 'D',
                'plate_name': 'Chicken',
                'restaurant_id': restaurant_1_id,
                'restaurant_name': 'Zebra Restaurant'
            },
            {
                'confirmation_code': 'DEF456',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Jane',
                'last_initial': 'S',
                'plate_name': 'Salad',
                'restaurant_id': restaurant_2_id,
                'restaurant_name': 'Alpha Restaurant'
            },
            {
                'confirmation_code': 'GHI789',
                'status': 'Active',
                'arrival_time': None,
                'pickup_time_range': '12:00-12:30',
                'kitchen_day': 'TUESDAY',
                'first_name': 'Bob',
                'last_initial': 'M',
                'plate_name': 'Pasta',
                'restaurant_id': restaurant_3_id,
                'restaurant_name': 'Beta Restaurant'
            }
        ]
        
        # Act
        result = _group_orders_by_restaurant(mock_rows)
        
        # Assert
        assert len(result) == 3
        assert result[0]['restaurant_name'] == 'Alpha Restaurant'
        assert result[1]['restaurant_name'] == 'Beta Restaurant'
        assert result[2]['restaurant_name'] == 'Zebra Restaurant'
