"""
Restaurant Staff Service - Business Logic for Restaurant Staff Operations

This service provides functionality for restaurant staff to view and manage
daily orders, including privacy-safe customer information and order aggregation.

Business Rules:
- Customer names displayed as "First L." format for privacy
- Orders filtered by institution_entity_id for Suppliers
- Orders grouped by restaurant with summary statistics
- Only active (non-archived) orders shown
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional
from uuid import UUID
import psycopg2.extensions
from collections import defaultdict

from app.services.date_service import get_effective_current_day
from app.services.crud_service import restaurant_service
from app.utils.log import log_info, log_warning
from app.utils.db import db_read


def get_daily_orders(
    user_institution_entity_id: UUID,
    order_date: date,
    restaurant_id: Optional[UUID],
    db: psycopg2.extensions.connection
) -> Dict[str, Any]:
    """
    Get today's orders for restaurant(s) within an institution entity.
    
    Args:
        user_institution_entity_id: User's institution entity ID for scoping
        order_date: Date to query orders for
        restaurant_id: Optional specific restaurant filter
        db: Database connection
        
    Returns:
        Dictionary with date and list of restaurants with their orders
        
    Example:
        {
            "date": "2026-02-04",
            "restaurants": [
                {
                    "restaurant_id": "uuid",
                    "restaurant_name": "Cambalache Palermo",
                    "orders": [...],
                    "summary": {"total_orders": 15, "pending": 10, ...}
                }
            ]
        }
    """
    
    # 1. Determine kitchen_day from date (using first restaurant's timezone)
    kitchen_day = _get_kitchen_day_for_date(order_date, user_institution_entity_id, db)
    
    log_info(f"Fetching daily orders for institution_entity_id={user_institution_entity_id}, "
             f"date={order_date}, kitchen_day={kitchen_day}, restaurant_id={restaurant_id}")
    
    # 2. Query all orders for the institution_entity (optionally filtered by restaurant)
    query = """
        SELECT 
            ppl.confirmation_code,
            ppl.status,
            ppl.arrival_time,
            ps.pickup_time_range,
            ps.kitchen_day,
            u.first_name,
            UPPER(SUBSTRING(u.last_name, 1, 1)) AS last_initial,
            prod.name AS plate_name,
            r.restaurant_id,
            r.name AS restaurant_name
        FROM plate_pickup_live ppl
        INNER JOIN plate_selection ps ON ppl.plate_selection_id = ps.plate_selection_id
        INNER JOIN user_info u ON ppl.user_id = u.user_id
        INNER JOIN plate_info pl ON ppl.plate_id = pl.plate_id
        INNER JOIN product_info prod ON pl.product_id = prod.product_id
        INNER JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
        WHERE r.institution_entity_id = %s
          AND ps.kitchen_day = %s
          AND ppl.is_archived = FALSE
          AND (r.restaurant_id = %s OR %s IS NULL)
        ORDER BY r.name ASC, ps.pickup_time_range ASC, u.last_name ASC
    """
    
    params = [
        str(user_institution_entity_id),
        kitchen_day,
        str(restaurant_id) if restaurant_id else None,
        str(restaurant_id) if restaurant_id else None
    ]
    
    # 3. Execute query
    rows = db_read(query, params, db)
    
    if not rows:
        log_info(f"No orders found for institution_entity_id={user_institution_entity_id}, "
                f"kitchen_day={kitchen_day}")
        return {
            "order_date": order_date,
            "restaurants": []
        }
    
    # 4. Group orders by restaurant and calculate summary statistics
    restaurants_data = _group_orders_by_restaurant(rows)
    
    log_info(f"Retrieved {len(rows)} orders across {len(restaurants_data)} restaurant(s)")
    
    return {
        "order_date": order_date,
        "restaurants": restaurants_data
    }


def _get_kitchen_day_for_date(
    order_date: date, 
    institution_entity_id: UUID,
    db: psycopg2.extensions.connection
) -> str:
    """
    Get kitchen_day enum value for a given date using restaurant timezone.
    
    Args:
        order_date: The date to convert to kitchen_day
        institution_entity_id: Institution entity ID to get timezone from
        db: Database connection
        
    Returns:
        Uppercase day name (e.g., 'TUESDAY')
    """
    
    # Get timezone from first restaurant in this institution_entity
    query = """
        SELECT a.timezone
        FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        WHERE r.institution_entity_id = %s
          AND r.is_archived = FALSE
        LIMIT 1
    """
    
    result = db_read(query, [str(institution_entity_id)], db)
    
    if not result or not result[0].get('timezone'):
        log_warning(f"No timezone found for institution_entity_id={institution_entity_id}, "
                   f"using default timezone")
        timezone_str = 'America/Argentina/Buenos_Aires'
    else:
        timezone_str = result[0]['timezone']
    
    # If order_date is today, use get_effective_current_day
    # Otherwise, just get the day name from the date
    if order_date == date.today():
        kitchen_day = get_effective_current_day(timezone_str)
    else:
        # For past/future dates, just use the weekday name
        kitchen_day = order_date.strftime('%A')
    
    # Return as Title Case to match kitchen_day enum ('Monday', 'Tuesday', etc.)
    return kitchen_day.title()


def _group_orders_by_restaurant(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group orders by restaurant and calculate summary statistics.
    
    Args:
        rows: List of order rows from database query
        
    Returns:
        List of restaurant dictionaries with orders and summary
    """
    
    # Group by restaurant_id
    restaurants_dict = defaultdict(lambda: {
        'restaurant_id': None,
        'restaurant_name': None,
        'orders': [],
        'summary': {
            'total_orders': 0,
            'pending': 0,
            'arrived': 0,
            'completed': 0
        }
    })
    
    for row in rows:
        restaurant_id = row['restaurant_id']
        
        # Set restaurant info (first time we see this restaurant)
        if restaurants_dict[restaurant_id]['restaurant_id'] is None:
            restaurants_dict[restaurant_id]['restaurant_id'] = restaurant_id
            restaurants_dict[restaurant_id]['restaurant_name'] = row['restaurant_name']
        
        # Format customer name for privacy: "First L."
        customer_name = f"{row['first_name']} {row['last_initial']}."
        
        # Add order to restaurant's order list
        order = {
            'customer_name': customer_name,
            'plate_name': row['plate_name'],
            'confirmation_code': row['confirmation_code'],
            'status': row['status'],
            'arrival_time': row['arrival_time'],
            'pickup_time_range': row['pickup_time_range'],
            'kitchen_day': row['kitchen_day']
        }
        
        restaurants_dict[restaurant_id]['orders'].append(order)
        
        # Update summary statistics
        summary = restaurants_dict[restaurant_id]['summary']
        summary['total_orders'] += 1
        
        # Categorize by status
        status = row['status'].lower()
        if status == 'active' and row['arrival_time'] is None:
            summary['pending'] += 1
        elif status == 'active' and row['arrival_time'] is not None:
            summary['arrived'] += 1
        elif status == 'completed':
            summary['completed'] += 1
        else:
            # Default to pending for unknown statuses
            summary['pending'] += 1
    
    # Convert to list and maintain alphabetical order by restaurant name
    restaurants_list = list(restaurants_dict.values())
    restaurants_list.sort(key=lambda x: x['restaurant_name'])
    
    return restaurants_list
