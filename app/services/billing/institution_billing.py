# app/services/billing/institution_billing.py
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException
from app.dto.models import InstitutionBillDTO
from app.services.crud_service import (
    institution_bill_service,
    get_institution_id_by_restaurant,
    get_institution_entity_by_institution
)
from app.dto.models import RestaurantBalanceDTO, RestaurantDTO, CreditCurrencyDTO
from app.services.crud_service import (
    restaurant_balance_service, 
    restaurant_service, 
    credit_currency_service,
    is_holiday
)
from app.config.market_config import MarketConfiguration
from app.config import Status
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_read
from app.dto.models import RestaurantTransactionDTO, PlatePickupLiveDTO
from app.services.crud_service import (
    restaurant_transaction_service,
    plate_pickup_live_service
)

class InstitutionBillingService:
    """Service for generating and managing institution bills based on restaurant balances"""
    
    @staticmethod
    def _get_uncollected_transactions(
        restaurant_id: UUID,
        period_start: datetime,
        period_end: datetime,
        connection=None
    ) -> List[RestaurantTransactionDTO]:
        """
        Get all uncollected restaurant transactions for a restaurant within a period.
        
        Args:
            restaurant_id: Restaurant ID
            period_start: Start of the billing period
            period_end: End of the billing period
            connection: Database connection
            
        Returns:
            List of uncollected RestaurantTransactionDTO objects
        """
        try:
            query = """
                SELECT rt.* 
                FROM restaurant_transaction rt
                WHERE rt.restaurant_id = %s
                AND rt.was_collected = FALSE
                AND rt.status = %s
                AND rt.is_archived = FALSE
                AND rt.ordered_timestamp >= %s
                AND rt.ordered_timestamp < %s
                ORDER BY rt.ordered_timestamp
            """
            results = db_read(
                query,
                (str(restaurant_id), Status.PENDING, period_start, period_end),
                connection=connection
            )
            return [RestaurantTransactionDTO(**row) for row in results] if results else []
        except Exception as e:
            log_error(f"Error getting uncollected transactions for restaurant {restaurant_id}: {e}")
            return []
    
    @staticmethod
    def _close_pickup_record(
        plate_selection_id: UUID,
        system_user_id: UUID,
        connection,
        *,
        commit: bool = False
    ) -> bool:
        """
        Close a pickup record that was not collected (prevent claiming after hours).
        
        Args:
            plate_selection_id: Plate selection ID to find the pickup record
            system_user_id: System user ID for modification tracking
            connection: Database connection
            commit: Whether to commit immediately (default: False for atomic transactions)
            
        Returns:
            True if pickup record closed successfully, False otherwise
        """
        try:
            # Find pickup record by plate_selection_id
            # Use tuple for IN clause with psycopg2
            query = """
                SELECT * FROM plate_pickup_live
                WHERE plate_selection_id = %s
                AND is_archived = FALSE
                AND status = ANY(%s)
            """
            pickup_results = db_read(
                query,
                (str(plate_selection_id), [Status.PENDING.value, Status.ARRIVED.value]),
                connection=connection
            )
            
            if not pickup_results:
                log_warning(f"No uncollected pickup record found for plate_selection_id {plate_selection_id}")
                return True  # Not an error - may have already been closed
            
            pickup_data = pickup_results[0]
            pickup_id = UUID(pickup_data['plate_pickup_id'])
            
            # Update pickup record to closed status
            update_data = {
                "status": Status.CANCELLED,  # Use CANCELLED for not collected
                "is_archived": True,  # Archive to prevent further operations
                "modified_by": system_user_id
            }
            
            success = plate_pickup_live_service.update(pickup_id, update_data, connection, commit=commit)
            if success:
                log_info(f"Closed pickup record {pickup_id} for plate_selection {plate_selection_id} (commit={'immediate' if commit else 'deferred'})")
            else:
                log_warning(f"Failed to close pickup record {pickup_id} for plate_selection {plate_selection_id}")
            
            return success
        except Exception as e:
            log_error(f"Error closing pickup record for plate_selection_id {plate_selection_id}: {e}")
            return False
    
    @staticmethod
    def _close_transaction(
        transaction_id: UUID,
        system_user_id: UUID,
        connection,
        *,
        commit: bool = False
    ) -> bool:
        """
        Close a transaction that was not collected (move to bill).
        
        Args:
            transaction_id: Restaurant transaction ID
            system_user_id: System user ID for modification tracking
            connection: Database connection
            commit: Whether to commit immediately (default: False for atomic transactions)
            
        Returns:
            True if transaction closed successfully, False otherwise
        """
        try:
            # Update transaction to complete status (billed)
            update_data = {
                "status": Status.COMPLETE,  # Mark as complete (billed)
                "was_collected": False,  # Keep as false (not collected)
                "modified_by": system_user_id
            }
            
            success = restaurant_transaction_service.update(transaction_id, update_data, connection, commit=commit)
            if success:
                log_info(f"Closed transaction {transaction_id} (commit={'immediate' if commit else 'deferred'})")
            else:
                log_warning(f"Failed to close transaction {transaction_id}")
            
            return success
        except Exception as e:
            log_error(f"Error closing transaction {transaction_id}: {e}")
            return False
    
    @staticmethod
    def create_bill_for_restaurant(restaurant_id: UUID, period_start: datetime, period_end: datetime, 
                                 system_user_id: UUID, status: Status = Status.PENDING, resolution: str = "Pending", 
                                 connection=None) -> Optional[InstitutionBillDTO]:
        """
        Create a bill for a single restaurant using the unified logic.
        This method encapsulates the same logic as the create_institution_bill API endpoint.
        
        Args:
            restaurant_id: The restaurant to create a bill for
            period_start: Start of the billing period
            period_end: End of the billing period
            system_user_id: User ID for system operations
            status: Bill status (default: "Pending")
            resolution: Bill resolution (default: "Pending")
            connection: Database connection
            
        Returns:
            Created bill or None if failed
        """
        try:
            # Get institution and entity IDs based on restaurant
            institution_id = get_institution_id_by_restaurant(restaurant_id, connection)
            if not institution_id:
                log_error(f"Institution not found for restaurant {restaurant_id}")
                return None
            
            institution_entity_id = get_institution_entity_by_institution(institution_id, connection)
            if not institution_entity_id:
                log_error(f"Institution entity not found for institution {institution_id}")
                return None
            
            # Get restaurant balance data
            balance_record = restaurant_balance_service.get_by_restaurant(restaurant_id, connection)
            if not balance_record:
                log_error(f"Restaurant balance not found for restaurant {restaurant_id}")
                return None
            
            if balance_record.balance <= 0:
                log_warning(f"Restaurant {restaurant_id} has no balance to bill")
                return None
            
            # Create bill data using current balance
            bill_data = {
                "institution_id": institution_id,
                "institution_entity_id": institution_entity_id,
                "restaurant_id": restaurant_id,
                "credit_currency_id": balance_record.credit_currency_id,
                "transaction_count": balance_record.transaction_count,
                "amount": balance_record.balance,  # Use current balance
                "currency_code": balance_record.currency_code,
                "period_start": period_start,
                "period_end": period_end,
                "status": status,
                "resolution": resolution,
                "modified_by": system_user_id
            }
            
            # ============================================================
            # ATOMIC OPERATIONS: All use commit=False, single commit at end
            # ============================================================
            
            # 1. Get uncollected transactions for this period
            uncollected_transactions = InstitutionBillingService._get_uncollected_transactions(
                restaurant_id, period_start, period_end, connection
            )
            
            # 2. Close uncollected pickup records (commit=False for atomic transaction)
            for transaction in uncollected_transactions:
                if transaction.plate_selection_id:
                    success = InstitutionBillingService._close_pickup_record(
                        transaction.plate_selection_id,
                        system_user_id,
                        connection,
                        commit=False
                    )
                    if not success:
                        connection.rollback()
                        log_error(f"Failed to close pickup record for transaction {transaction.transaction_id}")
                        return None
            
            # 3. Close uncollected transactions (commit=False for atomic transaction)
            for transaction in uncollected_transactions:
                success = InstitutionBillingService._close_transaction(
                    transaction.transaction_id,
                    system_user_id,
                    connection,
                    commit=False
                )
                if not success:
                    connection.rollback()
                    log_error(f"Failed to close transaction {transaction.transaction_id}")
                    return None
            
            # 4. Create the bill (commit=False for atomic transaction)
            bill_record = institution_bill_service.create(bill_data, connection, commit=False)
            if not bill_record:
                connection.rollback()
                log_error(f"Failed to create institution bill for restaurant {restaurant_id}")
                return None
            
            # 5. Get the current balance event_id BEFORE reset (this is the event that had the balance)
            balance_event_id_before_reset = restaurant_balance_service.get_current_event_id(restaurant_id, connection)
            
            # 6. Update the bill with the balance_event_id (commit=False for atomic transaction)
            if balance_event_id_before_reset:
                bill_update_data = {"balance_event_id": balance_event_id_before_reset}
                success = institution_bill_service.update(
                    bill_record.institution_bill_id,
                    bill_update_data,
                    connection,
                    commit=False
                )
                if not success:
                    connection.rollback()
                    log_error(f"Failed to update bill {bill_record.institution_bill_id} with balance_event_id")
                    return None
                log_info(f"Updated bill {bill_record.institution_bill_id} with balance_event_id {balance_event_id_before_reset} (balance before reset, commit deferred)")
            
            # 7. Reset restaurant balance to zero (commit=False for atomic transaction)
            balance_reset = restaurant_balance_service.reset_balance(restaurant_id, connection, commit=False)
            if not balance_reset:
                connection.rollback()
                log_error(f"Failed to reset restaurant balance for restaurant {restaurant_id}")
                return None
            
            # 8. Commit all operations atomically
            connection.commit()
            
            log_info(
                f"Created bill {bill_record.institution_bill_id} for restaurant {restaurant_id}, "
                f"closed {len(uncollected_transactions)} uncollected transactions/pickups, "
                f"balance reset to $0.00 (atomic transaction)"
            )
            return bill_record
            
        except Exception as e:
            log_error(f"Error creating bill for restaurant {restaurant_id}: {e}")
            return None

    @staticmethod
    def generate_daily_bills(bill_date: date, system_user_id: UUID, country_code: Optional[str] = None, connection=None) -> Dict:
        """
        Generate institution bills for all restaurants for a specific date.
        Bills are generated when kitchen days close, not at midnight.
        Country is automatically detected from restaurant address if not provided.
        
        Args:
            bill_date: The date to generate bills for
            system_user_id: User ID for system operations
            country_code: Optional country code override (if not provided, detected from restaurant address)
            
        Returns:
            Dict with statistics: {"bills_created": int, "total_amount": Decimal, "restaurants_processed": int}
        """
        try:
            # Get the kitchen day for this date
            kitchen_day = InstitutionBillingService._get_kitchen_day_for_date(bill_date)
            
            # Note: Bill generation is allowed on any day (including weekends)
            # Weekend restrictions only apply to customer ordering, not backend billing operations
            log_info(f"Generating bills for kitchen day: {kitchen_day}")
            
            # Get all restaurants with balance data FIRST (before resetting balances)
            restaurants = InstitutionBillingService._get_restaurants_with_balances(connection=connection)
            
            # Reset restaurant balances to 0 at the start of a new kitchen day
            # This ensures clean daily accounting and prevents balance accumulation
            # Skip reset in development mode to allow testing with existing balances
            from app.config.settings import settings
            if not settings.DEV_OVERRIDE_DAY:
                InstitutionBillingService._reset_restaurant_balances_for_new_day(bill_date, system_user_id, connection=connection)
            else:
                log_info("🔧 DEV MODE: Skipping restaurant balance reset to allow testing with existing balances")
            
            # Aggregate restaurants by institution_entity_id
            entity_aggregates = InstitutionBillingService._aggregate_restaurants_by_entity(restaurants)
            
            bills_created = 0
            total_amount = Decimal('0.00')
            restaurants_processed = 0
            
            for entity_data in entity_aggregates:
                try:
                    # Auto-detect country from entity address if not provided
                    entity_country = country_code
                    if not entity_country:
                        from app.services.market_detection import MarketDetectionService
                        entity_country = MarketDetectionService.get_country_from_entity(
                            entity_data["institution_entity_id"], connection
                        )
                        
                        if not entity_country:
                            log_warning(f"Could not detect country for entity {entity_data['institution_entity_id']}, skipping")
                            continue
                    
                    # Check if kitchen day is enabled for this market
                    # For weekend billing, use Friday's configuration as fallback
                    if not MarketConfiguration.is_kitchen_day_enabled(entity_country, kitchen_day):
                        if kitchen_day in ['Saturday', 'Sunday']:
                            # Use Friday's configuration for weekend billing
                            fallback_day = 'Friday'
                            if MarketConfiguration.is_kitchen_day_enabled(entity_country, fallback_day):
                                log_info(f"Kitchen day '{kitchen_day}' not configured for {entity_country}, using {fallback_day} configuration for billing")
                                kitchen_day = fallback_day
                            else:
                                log_info(f"Kitchen day '{kitchen_day}' is disabled for market {entity_country} and no fallback available")
                                continue
                        else:
                            log_info(f"Kitchen day '{kitchen_day}' is disabled for market {entity_country}")
                            continue
                    
                    # Check for national holidays for this specific entity's country
                    from app.services.crud_service import national_holiday_service
                    if is_holiday(entity_country, bill_date, connection):
                        log_info(f"Date {bill_date} is a national holiday for {entity_country}, skipping entity {entity_data['institution_entity_id']}")
                        continue
                    
                    # Define period based on market-specific kitchen day closure
                    period_start, period_end = InstitutionBillingService._get_market_kitchen_day_period(
                        bill_date, kitchen_day, entity_country
                    )
                    
                    # Process each restaurant individually using the unified logic
                    for restaurant_id in entity_data["restaurant_ids"]:
                        bill = InstitutionBillingService.create_bill_for_restaurant(
                            restaurant_id, period_start, period_end, system_user_id, connection=connection
                        )
                        
                        if bill:
                            bills_created += 1
                            if bill.amount:
                                total_amount += bill.amount
                            restaurants_processed += 1
                            
                            log_info(f"Created bill {bill.institution_bill_id} for restaurant {restaurant_id} "
                                   f"in market {entity_country}: ${bill.amount} {bill.currency_code}")
                
                except Exception as e:
                    log_error(f"Error creating bill for entity {entity_data['institution_entity_id']}: {e}")
                    continue
            
            log_info(f"Kitchen day '{kitchen_day}' bill generation complete: {bills_created} bills created, "
                   f"${total_amount} total, {restaurants_processed} restaurants processed")
            
            return {
                "bills_created": bills_created,
                "total_amount": float(total_amount),
                "restaurants_processed": restaurants_processed,
                "kitchen_day": kitchen_day,
                "country_code": country_code,
                "period_start": period_start.isoformat() if 'period_start' in locals() else None,
                "period_end": period_end.isoformat() if 'period_end' in locals() else None
            }
            
        except Exception as e:
            log_error(f"Error in daily bill generation: {e}")
            return {"bills_created": 0, "total_amount": 0.0, "restaurants_processed": 0}

    @staticmethod
    def _get_kitchen_day_for_date(target_date: date) -> str:
        """Get the kitchen day name for a given date"""
        # Check for dev override first
        from app.config.settings import settings
        if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
            override_day = settings.DEV_OVERRIDE_DAY.strip().title()
            valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            if override_day in valid_days:
                log_info(f"🔧 DEV OVERRIDE: Using {override_day} instead of actual day for date {target_date}")
                return override_day
        
        # Map date to day of week
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_index = target_date.weekday()  # Monday = 0, Sunday = 6
        return day_names[day_index]

    @staticmethod
    def _get_market_kitchen_day_period(target_date: date, kitchen_day: str, country_code: str) -> tuple[datetime, datetime]:
        """
        Get the billing period for a kitchen day based on market-specific configuration.
        Period starts at the beginning of the day and ends when the kitchen closes in local time.
        """
        # Start: Beginning of the target date in UTC
        period_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        
        # End: When the kitchen closes in local time, converted to UTC
        # Convert date to datetime for the market config call
        target_datetime = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        kitchen_close_utc = MarketConfiguration.get_kitchen_close_utc(country_code, target_datetime, kitchen_day)
        
        if not kitchen_close_utc:
            # Fallback: use end of day if kitchen close time not configured
            period_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            log_warning(f"No kitchen close time configured for {country_code} {kitchen_day}, using end of day")
        else:
            period_end = kitchen_close_utc
        
        return period_start, period_end

    @staticmethod
    def is_kitchen_day_active(kitchen_day: str, current_time: Optional[datetime] = None, country_code: str = "AR") -> bool:
        """
        Check if a kitchen day is currently active (before closure time) for a specific market.
        
        Args:
            kitchen_day: Day of the week (Monday, Tuesday, etc.)
            current_time: Time to check (defaults to now)
            country_code: Country code for market-specific timing
            
        Returns:
            True if kitchen day is active, False if closed
        """
        if not current_time:
            current_time = datetime.now(timezone.utc)
            
        # Get today's date
        today = current_time.date()
        
        # Check if today matches the kitchen day
        today_kitchen_day = InstitutionBillingService._get_kitchen_day_for_date(today)
        if today_kitchen_day != kitchen_day:
            return False
            
        # Check if we're before closure time using market config
        kitchen_close_utc = MarketConfiguration.get_kitchen_close_utc(country_code, current_time, kitchen_day)
        if not kitchen_close_utc:
            return False
            
        return current_time < kitchen_close_utc

    @staticmethod
    def get_current_kitchen_day() -> str:
        """Get the current kitchen day name"""
        return InstitutionBillingService._get_kitchen_day_for_date(datetime.now(timezone.utc).date())

    @staticmethod
    def should_generate_bills_now(country_code: str = "AR") -> bool:
        """
        Check if it's time to generate bills (kitchen day has just closed) for a specific market.
        This can be used for real-time billing triggers.
        
        Args:
            country_code: Country code for market-specific timing
            
        Returns:
            True if bills should be generated now
        """
        current_time = datetime.now(timezone.utc)
        current_day = current_time.date()
        current_kitchen_day = InstitutionBillingService._get_kitchen_day_for_date(current_day)
        
        # Get billing run time for today using market config
        billing_run_utc = MarketConfiguration.get_billing_run_utc(country_code, current_time, current_kitchen_day)
        if not billing_run_utc:
            return False
        
        # Check if we're within 5 minutes after billing run time (billing window)
        billing_window_start = billing_run_utc
        billing_window_end = billing_run_utc + timedelta(minutes=5)
        
        return billing_window_start <= current_time <= billing_window_end

    @staticmethod
    def _get_restaurants_with_balances(connection=None) -> List[Dict]:
        """Get all restaurants that have balance data, grouped by institution_entity_id"""
        try:
            query = """
                SELECT 
                    r.restaurant_id,
                    r.institution_id,
                    r.institution_entity_id,
                    r.credit_currency_id,
                    rb.transaction_count,
                    rb.balance,
                    rb.currency_code
                FROM restaurant_info r
                INNER JOIN restaurant_balance_info rb ON r.restaurant_id = rb.restaurant_id
                WHERE r.is_archived = %s 
                AND rb.is_archived = %s
                AND rb.balance > 0
                ORDER BY r.institution_entity_id, r.restaurant_id
            """
            
            results = db_read(query, (False, False), connection=connection)
            if results:
                return [
                    {
                        "restaurant_id": UUID(row[0]),
                        "institution_id": UUID(row[1]),
                        "institution_entity_id": UUID(row[2]),
                        "credit_currency_id": UUID(row[3]),
                        "transaction_count": row[4],
                        "balance": Decimal(str(row[5])),
                        "currency_code": row[6]
                    }
                    for row in results
                ]
            return []
            
        except Exception as e:
            log_error(f"Error getting restaurants with balances: {e}")
            return []

    @staticmethod
    def _create_bill_for_entity(entity_data: Dict, period_start: datetime, 
                               period_end: datetime, system_user_id: UUID, connection=None) -> Optional[InstitutionBillDTO]:
        """
        Create a bill for an institution entity's aggregated balance during a specific period.
        
        Args:
            entity_data: Aggregated entity data including total balance and transaction count
            period_start: Start of billing period
            period_end: End of billing period
            system_user_id: User ID for system operations
            
        Returns:
            InstitutionBill instance or None if creation failed
        """
        try:
            # Check if a bill already exists for this entity and period
            existing_bill = institution_bill_service.get_by_entity_and_period(
                entity_data["institution_entity_id"], period_start, period_end, connection
            )
            
            if existing_bill:
                log_info(f"Bill already exists for entity {entity_data['institution_entity_id']} "
                        f"period {period_start} to {period_end}")
                return existing_bill
            
            # Create new bill for the institution entity
            bill_data = {
                "institution_id": entity_data["institution_id"],
                "institution_entity_id": entity_data["institution_entity_id"],
                "restaurant_id": entity_data["restaurant_ids"][0],  # Use first restaurant as primary
                "credit_currency_id": entity_data["credit_currency_id"],
                "period_start": period_start,
                "period_end": period_end,
                "amount": entity_data["total_balance"],
                "currency_code": entity_data["currency_code"],
                "transaction_count": entity_data["total_transactions"],
                "status": Status.PENDING,
                "resolution": "Pending",
                "modified_by": system_user_id
            }
            
            bill = institution_bill_service.create(bill_data, connection)
            log_info(f"Created bill {bill.institution_bill_id} for entity {entity_data['institution_entity_id']}: "
                    f"${bill.amount} ({bill.transaction_count} transactions, {entity_data['restaurant_count']} restaurants)")
            
            return bill
            
        except Exception as e:
            log_error(f"Error creating bill for entity {entity_data['institution_entity_id']}: {e}")
            return None

    @staticmethod
    def _aggregate_restaurants_by_entity(restaurants: List[Dict]) -> List[Dict]:
        """
        Aggregate restaurant balances by institution_entity_id.
        Multiple restaurants owned by the same entity will have their balances combined.
        
        Args:
            restaurants: List of restaurant data
            
        Returns:
            List of aggregated entity data
        """
        entity_aggregates = {}
        
        for restaurant in restaurants:
            entity_id = restaurant["institution_entity_id"]
            
            if entity_id not in entity_aggregates:
                entity_aggregates[entity_id] = {
                    "institution_entity_id": entity_id,
                    "institution_id": restaurant["institution_id"],
                    "credit_currency_id": restaurant["credit_currency_id"],
                    "total_balance": Decimal('0.00'),
                    "total_transactions": 0,
                    "currency_code": restaurant["currency_code"],
                    "restaurant_count": 0,
                    "restaurant_ids": []
                }
            
            # Aggregate balances and transaction counts
            entity_aggregates[entity_id]["total_balance"] += restaurant["balance"]
            entity_aggregates[entity_id]["total_transactions"] += restaurant["transaction_count"]
            entity_aggregates[entity_id]["restaurant_count"] += 1
            entity_aggregates[entity_id]["restaurant_ids"].append(restaurant["restaurant_id"])
        
        return list(entity_aggregates.values())

    @staticmethod
    def get_bills_by_institution(institution_id: UUID, status: Optional[str] = None, 
                               start_date: Optional[date] = None, end_date: Optional[date] = None, 
                               connection=None) -> List[InstitutionBillDTO]:
        """Get bills for an institution with optional status and date filtering"""
        try:
            return institution_bill_service.get_by_institution(
                institution_id, status, start_date, end_date, connection=connection
            )
        except Exception as e:
            log_error(f"Error getting bills for institution {institution_id}: {e}")
            return []

    @staticmethod
    def get_pending_bills(connection=None) -> List[InstitutionBillDTO]:
        """Get all pending bills across all institutions"""
        try:
            return institution_bill_service.get_pending(connection)
        except Exception as e:
            log_error(f"Error getting pending bills: {e}")
            return []

    @staticmethod
    def mark_bill_paid(bill_id: UUID, payment_id: UUID, modified_by: UUID, connection=None) -> bool:
        """Mark a bill as paid"""
        try:
            return institution_bill_service.mark_paid(bill_id, payment_id, modified_by, connection)
        except Exception as e:
            log_error(f"Error marking bill {bill_id} as paid: {e}")
            return False
    
    @staticmethod
    def record_manual_payment(bill_id: UUID, bank_account_id: UUID, external_transaction_id: str, transaction_result: str, user_id: UUID, connection=None) -> Dict:
        """
        Record a manual payment for a bill (MVP - manual bank payments).
        Creates payment_attempt and marks bill as paid atomically.
        
        Args:
            bill_id: UUID of the bill to mark as paid
            bank_account_id: UUID of the bank account used for payment
            external_transaction_id: Transaction ID from the bank
            transaction_result: Result of the transaction (default "Approved")
            user_id: User ID performing the operation
            connection: Database connection
            
        Returns:
            Dict with payment_id and updated bill info
        """
        from app.services.crud_service import institution_payment_attempt_service, institution_bill_service
        from datetime import datetime
        
        try:
            # 1. Validate bill exists and is not already paid/cancelled
            bill = institution_bill_service.get_by_id(bill_id, connection)
            if not bill:
                raise HTTPException(status_code=404, detail=f"Bill {bill_id} not found")
            
            if bill.status == Status.PROCESSED:
                raise HTTPException(status_code=400, detail="Bill is already paid")
            
            if bill.status == Status.CANCELLED:
                raise HTTPException(status_code=400, detail="Cannot pay a cancelled bill")
            
            # 2. Create payment attempt record
            payment_data = {
                "institution_entity_id": bill.institution_entity_id,
                "bank_account_id": bank_account_id,
                "institution_bill_id": bill_id,
                "credit_currency_id": bill.credit_currency_id,
                "amount": bill.amount,
                "currency_code": bill.currency_code,
                "transaction_result": transaction_result,
                "external_transaction_id": external_transaction_id,
                "status": Status.COMPLETE,
                "resolution_date": datetime.utcnow()
            }
            
            payment_attempt = institution_payment_attempt_service.create(payment_data, connection)
            if not payment_attempt:
                raise HTTPException(status_code=500, detail="Failed to create payment attempt")
            
            # 3. Update bill to mark as paid
            bill_update_data = {
                "status": Status.PROCESSED,
                "resolution": "Paid",
                "payment_id": payment_attempt.payment_id,
                "modified_by": user_id
            }
            
            updated_bill = institution_bill_service.update(bill_id, bill_update_data, connection)
            if not updated_bill:
                raise HTTPException(status_code=500, detail="Failed to update bill")
            
            log_info(f"Recorded manual payment for bill {bill_id}: payment_id={payment_attempt.payment_id}, external_txn={external_transaction_id}")
            
            return {
                "payment_id": payment_attempt.payment_id,
                "bill_id": bill_id,
                "status": Status.PROCESSED.value,  # Return enum value as string
                "resolution": "Paid",
                "external_transaction_id": external_transaction_id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error recording manual payment for bill {bill_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to record payment: {str(e)}")
    
    @staticmethod
    def cancel_bill(bill_id: UUID, user_id: UUID, connection=None) -> Dict:
        """
        Cancel a bill (MVP - for administrative corrections).
        Cannot cancel already paid bills.
        
        Args:
            bill_id: UUID of the bill to cancel
            user_id: User ID performing the operation
            connection: Database connection
            
        Returns:
            Dict with cancellation confirmation
        """
        from app.services.crud_service import institution_bill_service
        
        try:
            # 1. Validate bill exists and is not paid
            bill = institution_bill_service.get_by_id(bill_id, connection)
            if not bill:
                raise HTTPException(status_code=404, detail=f"Bill {bill_id} not found")
            
            if bill.status == Status.PROCESSED:
                raise HTTPException(status_code=400, detail="Cannot cancel a paid bill")
            
            if bill.status == Status.CANCELLED:
                raise HTTPException(status_code=400, detail="Bill is already cancelled")
            
            # 2. Update bill to cancelled status
            bill_update_data = {
                "status": Status.CANCELLED,
                "resolution": "Cancelled",
                "modified_by": user_id
            }
            
            updated_bill = institution_bill_service.update(bill_id, bill_update_data, connection)
            if not updated_bill:
                raise HTTPException(status_code=500, detail="Failed to cancel bill")
            
            log_info(f"Cancelled bill {bill_id}")
            
            return {
                "bill_id": bill_id,
                "status": Status.CANCELLED.value,  # Return enum value as string
                "resolution": "Cancelled",
                "message": "Bill cancelled successfully"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error cancelling bill {bill_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to cancel bill: {str(e)}")

    @staticmethod
    def get_bill_summary_by_institution(institution_id: UUID, start_date: date, end_date: date, connection=None) -> Dict:
        """Get billing summary for an institution"""
        try:
            period_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            period_end = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            
            bills = institution_bill_service.get_by_institution_and_period(institution_id, period_start, period_end, connection)
            
            total_amount = sum((bill.amount or Decimal('0.00')) for bill in bills)
            total_transactions = sum((bill.transaction_count or 0) for bill in bills)
            pending_bills = [bill for bill in bills if bill.status == Status.PENDING]
            paid_bills = [bill for bill in bills if bill.status == Status.PROCESSED]
            
            return {
                "institution_id": str(institution_id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total_bills": len(bills),
                "total_amount": float(total_amount),
                "total_transactions": total_transactions,
                "pending_bills": len(pending_bills),
                "paid_bills": len(paid_bills),
                "pending_amount": float(sum((bill.amount or Decimal('0.00')) for bill in pending_bills)),
                "paid_amount": float(sum((bill.amount or Decimal('0.00')) for bill in paid_bills))
            }
            
        except Exception as e:
            log_error(f"Error getting bill summary for institution {institution_id}: {e}")
            return {} 

    @staticmethod
    def _reduce_restaurant_balances(restaurant_ids: List[UUID], bill_amount: Decimal, credit_currency_id: UUID, currency_code: str, system_user_id: UUID, connection=None):
        """
        Reduce restaurant balances after successful billing to ensure daily balance starts from 0.
        
        Args:
            restaurant_ids: List of restaurant IDs that were billed
            bill_amount: Total amount that was billed
            system_user_id: User ID for system operations
            connection: Database connection to use
        """
        try:
            
            # Get current balances for all restaurants
            total_current_balance = Decimal('0.00')
            restaurant_balances = {}
            
            for restaurant_id in restaurant_ids:
                balance_record = restaurant_balance_service.get_by_restaurant(restaurant_id, connection)
                if balance_record and balance_record.balance > 0:
                    total_current_balance += balance_record.balance
                    restaurant_balances[restaurant_id] = balance_record.balance
            
            if total_current_balance == 0:
                log_info("No restaurant balances to reduce - already at 0")
                return
            
            # Calculate reduction ratio to distribute bill amount proportionally
            if total_current_balance > 0:
                # Reduce each restaurant's balance proportionally
                for restaurant_id, current_balance in restaurant_balances.items():
                    if current_balance > 0:
                        # Calculate proportional reduction
                        reduction_ratio = current_balance / total_current_balance
                        reduction_amount = bill_amount * reduction_ratio
                        
                        # Ensure we don't reduce below 0
                        final_balance = max(Decimal('0.00'), current_balance - reduction_amount)
                        reduction_needed = current_balance - final_balance
                        
                        if reduction_needed > 0:
                            # Update the restaurant balance
                            restaurant_balance_service.update_with_monetary_amount(
                                restaurant_id,
                                -reduction_needed,  # Negative amount to reduce balance
                                currency_code=currency_code,
                                db=connection
                            )
                            
                            log_info(f"Reduced balance for restaurant {restaurant_id}: "
                                   f"${current_balance} → ${final_balance} (reduced by ${reduction_needed})")
                
                log_info(f"Successfully reduced restaurant balances by ${bill_amount} across {len(restaurant_ids)} restaurants")
            
        except Exception as e:
            log_error(f"Error reducing restaurant balances after billing: {e}")
            # Don't fail the billing process if balance reduction fails
            # The balance will be corrected in the next billing cycle

    @staticmethod
    def _reset_restaurant_balances_for_new_day(bill_date: date, system_user_id: UUID, connection=None):
        """
        Reset all restaurant balances to 0 at the start of a new kitchen day.
        This ensures clean daily accounting and prevents balance accumulation.
        
        Args:
            bill_date: Date to reset balances for
            system_user_id: User ID for system operations
        """
        try:
            
            # Get all restaurants with non-zero balances
            query = """
                SELECT rb.restaurant_id, rb.balance, rb.currency_code, rb.credit_currency_id
                FROM restaurant_balance_info rb
                WHERE rb.is_archived = %s AND rb.balance > 0
            """
            
            results = db_read(query, (False,), connection=connection)
            if not results:
                log_info("No restaurant balances to reset for new day")
                return
            
            reset_count = 0
            total_reset_amount = Decimal('0.00')
            
            for row in results:
                restaurant_id = row[0]
                current_balance = Decimal(str(row[1]))
                currency_code = row[2]
                credit_currency_id = row[3]
                
                try:
                    # Reset balance to 0
                    restaurant_balance_service.update_with_monetary_amount(
                        restaurant_id,
                        -float(current_balance),  # Negative amount to reduce to 0
                        currency_code=currency_code,
                        db=connection
                    )
                    
                    reset_count += 1
                    total_reset_amount += current_balance
                    
                    log_info(f"Reset balance for restaurant {restaurant_id}: "
                           f"${current_balance} → $0.00 ({currency_code})")
                    
                except Exception as e:
                    log_error(f"Error resetting balance for restaurant {restaurant_id}: {e}")
                    continue
            
            log_info(f"Daily balance reset complete: {reset_count} restaurants reset, "
                    f"${total_reset_amount} total amount reset")
            
        except Exception as e:
            log_error(f"Error in daily balance reset: {e}")
            # Don't fail the billing process if balance reset fails 