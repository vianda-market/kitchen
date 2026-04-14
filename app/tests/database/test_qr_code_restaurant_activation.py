"""
Database tests for QR code restaurant activation: auto-deactivation trigger.

When the last active QR code for a restaurant is archived, deleted, or set to Inactive,
the restaurant_auto_deactivate_on_qr_code trigger sets the restaurant to Inactive.

Requires trigger.sql to be applied (run build_kitchen_db.sh to rebuild).
"""

import pytest
from uuid import uuid4

from app.tests.database.conftest import db_transaction
from app.tests.database.test_data.expected_seed_data import (
    SEED_SUPERADMIN_USER_ID,
    SEED_INSTITUTION_VIANDA_ID,
)


def _trigger_exists(cursor) -> bool:
    """Check if restaurant_auto_deactivate_on_qr_code trigger exists."""
    cursor.execute("""
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'restaurant_auto_deactivate_on_qr_code'
        LIMIT 1
    """)
    return cursor.fetchone() is not None


def _create_restaurant_with_qr_code(cursor, modified_by: str) -> tuple:
    """
    Create minimal restaurant + address + institution_entity + qr_code.
    Returns (restaurant_id, qr_code_id).
    """
    address_id = str(uuid4())
    inst_entity_id = str(uuid4())
    restaurant_id = str(uuid4())
    qr_code_id = str(uuid4())

    # address_info: country_code XG (Global market from seed).
    # city_metadata_id references the Global synthetic city_metadata row from reference_data.sql.
    cursor.execute(
        """
        INSERT INTO address_info (
            address_id, institution_id, user_id, address_type, country_code,
            province, city, postal_code, street_type, street_name, building_number,
            timezone, city_metadata_id, is_archived, status, modified_by
        ) VALUES (%s, %s, %s, ARRAY['restaurant']::address_type_enum[], 'XG',
            'Prov', 'City', '12345', 'st'::street_type_enum, 'Main', '1',
            'UTC', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', FALSE, 'active'::status_enum, %s)
        """,
        (address_id, str(SEED_INSTITUTION_VIANDA_ID), modified_by, modified_by),
    )

    # institution_entity_info (for restaurant FK)
    cursor.execute(
        """
        INSERT INTO institution_entity_info (
            institution_entity_id, institution_id, address_id, currency_metadata_id,
            tax_id, name, is_archived, status, modified_by
        ) VALUES (%s, %s, %s, '55555555-5555-5555-5555-555555555555',
            'TAX1', 'Test Entity', FALSE, 'active'::status_enum, %s)
        """,
        (inst_entity_id, str(SEED_INSTITUTION_VIANDA_ID), address_id, modified_by),
    )

    # restaurant_info (status Active - we will test trigger deactivating it)
    cursor.execute(
        """
        INSERT INTO restaurant_info (
            restaurant_id, institution_id, institution_entity_id, address_id,
            name, is_archived, status, modified_by
        ) VALUES (%s, %s, %s, %s, 'QR Test Restaurant', FALSE, 'active'::status_enum, %s)
        """,
        (restaurant_id, str(SEED_INSTITUTION_VIANDA_ID), inst_entity_id, address_id, modified_by),
    )

    # qr_code (Active - trigger will fire when we set to Inactive)
    cursor.execute(
        """
        INSERT INTO qr_code (
            qr_code_id, restaurant_id, qr_code_payload, qr_code_image_url,
            image_storage_path, is_archived, status, modified_by
        ) VALUES (%s, %s, %s, 'http://example.com/qr.png', '/qr.png',
            FALSE, 'active'::status_enum, %s)
        """,
        (qr_code_id, restaurant_id, f"restaurant_id:{restaurant_id}", modified_by),
    )

    return restaurant_id, qr_code_id


class TestQRCodeAutoDeactivationTrigger:
    """Trigger restaurant_auto_deactivate_on_qr_code deactivates restaurant when last QR goes inactive."""

    def test_setting_last_qr_to_inactive_deactivates_restaurant(self, db_transaction):
        """When the only active QR code is set to Inactive, restaurant becomes Inactive."""
        cursor = db_transaction.cursor()
        if not _trigger_exists(cursor):
            pytest.skip("Trigger restaurant_auto_deactivate_on_qr_code not installed; run build_kitchen_db.sh")
        modified_by = str(SEED_SUPERADMIN_USER_ID)
        try:
            restaurant_id, qr_code_id = _create_restaurant_with_qr_code(cursor, modified_by)

            cursor.execute(
                "SELECT status FROM restaurant_info WHERE restaurant_id = %s",
                (restaurant_id,),
            )
            assert cursor.fetchone()[0] == "active"

            cursor.execute(
                """
                UPDATE qr_code SET status = 'inactive'::status_enum
                WHERE qr_code_id = %s
                """,
                (qr_code_id,),
            )

            cursor.execute(
                "SELECT status FROM restaurant_info WHERE restaurant_id = %s",
                (restaurant_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "inactive", "Trigger should set restaurant to Inactive when last QR goes Inactive"
        finally:
            cursor.close()

    def test_archiving_last_qr_deactivates_restaurant(self, db_transaction):
        """When the only active QR code is archived, restaurant becomes Inactive."""
        cursor = db_transaction.cursor()
        if not _trigger_exists(cursor):
            pytest.skip("Trigger restaurant_auto_deactivate_on_qr_code not installed; run build_kitchen_db.sh")
        modified_by = str(SEED_SUPERADMIN_USER_ID)
        try:
            restaurant_id, qr_code_id = _create_restaurant_with_qr_code(cursor, modified_by)

            cursor.execute(
                "UPDATE qr_code SET is_archived = TRUE WHERE qr_code_id = %s",
                (qr_code_id,),
            )

            cursor.execute(
                "SELECT status FROM restaurant_info WHERE restaurant_id = %s",
                (restaurant_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "inactive", "Trigger should set restaurant to Inactive when last QR is archived"
        finally:
            cursor.close()
