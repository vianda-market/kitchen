# app/services/billing/institution_billing.py
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.config import Status
from app.config.enums import BillResolution
from app.config.market_config import MarketConfiguration
from app.dto.models import (
    InstitutionBillDTO,
    InstitutionSettlementDTO,
    RestaurantTransactionDTO,
)
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.billing.supplier_terms_resolution import (
    get_supplier_payment_frequency,
    resolve_effective_invoice_config,
)
from app.services.crud_service import (
    get_institution_entity_by_institution,
    get_institution_id_by_entity,
    get_institution_id_by_restaurant,
    get_settlement_by_restaurant_and_period,
    get_settlements_by_run_id,
    institution_bill_service,
    institution_settlement_service,
    is_holiday,
    plate_pickup_live_service,
    restaurant_balance_service,
    restaurant_transaction_service,
)
from app.utils.db import close_db_connection, db_read, get_db_connection
from app.utils.log import log_error, log_info, log_warning


def _is_supplier_payout_due(payment_frequency: str, today: date) -> bool:
    """Check if a supplier payout is due today based on payment_frequency.

    Follows the same pattern as employer_billing._is_billing_due().
    """
    if payment_frequency == "daily":
        return True
    if payment_frequency == "weekly":
        return today.weekday() == 0  # Monday
    if payment_frequency == "biweekly":
        return today.weekday() == 0 and today.isocalendar()[1] % 2 == 1  # Every other Monday (odd ISO weeks)
    if payment_frequency == "monthly":
        return today.day == 1
    return True


def _check_invoice_compliance(
    institution_id: UUID,
    institution_entity_id: UUID,
    db,
) -> bool:
    """Check if an entity passes the invoice compliance gate.

    Returns True if payout is allowed, False if held due to uninvoiced bills.
    """
    config = resolve_effective_invoice_config(institution_id, db, institution_entity_id=institution_entity_id)
    if not config["effective_require_invoice"]:
        return True

    hold_days = config["effective_invoice_hold_days"]
    row = db_read(
        """
        SELECT MIN(b.period_end) as oldest_unmatched
        FROM billing.institution_bill_info b
        WHERE b.institution_entity_id = %s
          AND b.is_archived = FALSE
          AND b.resolution = 'pending'
          AND NOT EXISTS (
            SELECT 1 FROM billing.bill_invoice_match m
            WHERE m.institution_bill_id = b.institution_bill_id
          )
        """,
        (str(institution_entity_id),),
        connection=db,
        fetch_one=True,
    )
    if not row or not row.get("oldest_unmatched"):
        return True  # No unmatched bills — compliant

    oldest = row["oldest_unmatched"]
    if isinstance(oldest, datetime):
        oldest = oldest.date()
    days_unmatched = (date.today() - oldest).days
    return days_unmatched <= hold_days


def _resolve_location_overrides(
    location_id: str | None,
    timezone_filter: str | None,
) -> tuple[str | None, str | None]:
    """Resolve market_override and timezone_filter from a location_id, if provided.

    Returns (market_override, timezone_filter). When location_id is None or the
    config lookup returns nothing, both output values fall back to the inputs.
    """
    from app.config.location_config import get_location_config

    if not location_id:
        return None, timezone_filter
    loc_config = get_location_config(location_id)
    if loc_config:
        return loc_config["market"], loc_config["timezone"]
    return None, timezone_filter


def _resolve_entity_country(
    entity_data: dict,
    market_override: str | None,
    country_code: str | None,
    connection: Any,
) -> str | None:
    """Resolve the country code for a single entity aggregate.

    Precedence: market_override → country_code → MarketDetectionService lookup.
    Returns None (with a warning logged) when the country cannot be determined.
    """
    entity_country = market_override or country_code
    if entity_country:
        return entity_country
    from app.services.market_detection import MarketDetectionService

    entity_country = MarketDetectionService.get_country_from_entity(entity_data["institution_entity_id"], connection)
    if not entity_country:
        log_warning(f"Could not detect country for entity {entity_data['institution_entity_id']}, skipping")
        return None
    return entity_country


def _resolve_effective_kitchen_day(kitchen_day: str, entity_country: str) -> str | None:
    """Return the kitchen day to bill for, or None if this entity should be skipped.

    When the nominal day is disabled for the market, falls back to Friday for
    weekend runs if Friday is enabled. Any other disabled day returns None.
    """
    if MarketConfiguration.is_kitchen_day_enabled(entity_country, kitchen_day):
        return kitchen_day
    if kitchen_day in ("saturday", "sunday"):
        if MarketConfiguration.is_kitchen_day_enabled(entity_country, "friday"):
            log_info(f"Using friday config for {entity_country} weekend billing")
            return "friday"
    return None


def _settle_entity_restaurants(
    entity_data: dict,
    bill_date: date,
    period_start: datetime,
    period_end: datetime,
    day_to_use: str,
    entity_country: str,
    settlement_run_id: UUID,
    system_user_id: UUID,
    connection: Any,
) -> tuple[int, Decimal]:
    """Create settlements for every restaurant belonging to one entity aggregate.

    Returns (count_created, total_amount) for the caller to accumulate.
    """
    count = 0
    total = Decimal("0.00")
    for restaurant_id in entity_data["restaurant_ids"]:
        settlement_number = f"SETT-{bill_date.isoformat()}-{str(restaurant_id)[:8]}"
        settlement = InstitutionBillingService.create_settlement_for_restaurant(
            restaurant_id,
            period_start,
            period_end,
            day_to_use,
            entity_country,
            settlement_number,
            system_user_id,
            settlement_run_id=settlement_run_id,
            connection=connection,
        )
        if settlement:
            count += 1
            if settlement.amount:
                total += settlement.amount
    return count, total


class InstitutionBillingService:
    """Service for generating and managing institution bills based on restaurant balances"""

    @staticmethod
    def _get_uncollected_transactions(
        restaurant_id: UUID, period_start: datetime, period_end: datetime, connection=None
    ) -> list[RestaurantTransactionDTO]:
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
                query, (str(restaurant_id), Status.PENDING, period_start, period_end), connection=connection
            )
            return [RestaurantTransactionDTO(**row) for row in results] if results else []
        except Exception as e:
            log_error(f"Error getting uncollected transactions for restaurant {restaurant_id}: {e}")
            return []

    @staticmethod
    def _close_pickup_record(
        plate_selection_id: UUID, system_user_id: UUID, connection, *, commit: bool = False
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
                query, (str(plate_selection_id), [Status.PENDING.value, Status.ARRIVED.value]), connection=connection
            )

            if not pickup_results:
                log_warning(f"No uncollected pickup record found for plate_selection_id {plate_selection_id}")
                return True  # Not an error - may have already been closed

            pickup_data = pickup_results[0]
            pickup_id = UUID(pickup_data["plate_pickup_id"])

            # Update pickup record to closed status
            update_data = {
                "status": Status.CANCELLED,  # Use CANCELLED for not collected
                "is_archived": True,  # Archive to prevent further operations
                "modified_by": system_user_id,
            }

            success = plate_pickup_live_service.update(pickup_id, update_data, connection, commit=commit)
            if success:
                log_info(
                    f"Closed pickup record {pickup_id} for plate_selection {plate_selection_id} (commit={'immediate' if commit else 'deferred'})"
                )
            else:
                log_warning(f"Failed to close pickup record {pickup_id} for plate_selection {plate_selection_id}")

            return success
        except Exception as e:
            log_error(f"Error closing pickup record for plate_selection_id {plate_selection_id}: {e}")
            return False

    @staticmethod
    def _close_transaction(transaction_id: UUID, system_user_id: UUID, connection, *, commit: bool = False) -> bool:
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
                "status": Status.COMPLETED,  # Mark as complete (billed)
                "was_collected": False,  # Keep as false (not collected)
                "modified_by": system_user_id,
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
    def create_settlement_for_restaurant(
        restaurant_id: UUID,
        period_start: datetime,
        period_end: datetime,
        kitchen_day: str,
        country_code: str,
        settlement_number: str,
        system_user_id: UUID,
        *,
        settlement_run_id: UUID | None = None,
        connection=None,
    ) -> InstitutionSettlementDTO | None:
        """
        Create one settlement for a restaurant (only when balance > 0).
        Closes uncollected transactions/pickups, captures balance, resets restaurant balance.
        Idempotent: returns existing settlement if one exists for this restaurant and period.
        """
        try:
            institution_id = get_institution_id_by_restaurant(restaurant_id, connection)
            if not institution_id:
                log_error(f"Institution not found for restaurant {restaurant_id}")
                return None
            institution_entity_id = get_institution_entity_by_institution(institution_id, connection)
            if not institution_entity_id:
                log_error(f"Institution entity not found for institution {institution_id}")
                return None

            balance_record = restaurant_balance_service.get_by_restaurant(restaurant_id, connection)
            if not balance_record:
                log_error(f"Restaurant balance not found for restaurant {restaurant_id}")
                return None
            if balance_record.balance <= 0:
                log_warning(f"Restaurant {restaurant_id} has no balance; skip settlement")
                return None

            existing = get_settlement_by_restaurant_and_period(restaurant_id, period_start, period_end, connection)
            if existing:
                log_info(f"Settlement already exists for restaurant {restaurant_id} period {period_start}–{period_end}")
                return existing

            uncollected_transactions = InstitutionBillingService._get_uncollected_transactions(
                restaurant_id, period_start, period_end, connection
            )
            for transaction in uncollected_transactions:
                if transaction.plate_selection_id:
                    success = InstitutionBillingService._close_pickup_record(
                        transaction.plate_selection_id, system_user_id, connection, commit=False
                    )
                    if not success:
                        connection.rollback()
                        log_error(f"Failed to close pickup for transaction {transaction.transaction_id}")
                        return None
            for transaction in uncollected_transactions:
                success = InstitutionBillingService._close_transaction(
                    transaction.transaction_id, system_user_id, connection, commit=False
                )
                if not success:
                    connection.rollback()
                    log_error(f"Failed to close transaction {transaction.transaction_id}")
                    return None

            balance_event_id = restaurant_balance_service.get_current_event_id(restaurant_id, connection)
            settlement_data = {
                "institution_entity_id": institution_entity_id,
                "restaurant_id": restaurant_id,
                "period_start": period_start,
                "period_end": period_end,
                "kitchen_day": kitchen_day,
                "amount": balance_record.balance,
                "currency_code": balance_record.currency_code,
                "currency_metadata_id": balance_record.currency_metadata_id,
                "transaction_count": balance_record.transaction_count,
                "balance_event_id": balance_event_id,
                "settlement_number": settlement_number,
                "settlement_run_id": settlement_run_id,
                "country_code": country_code,
                "status": Status.ACTIVE,
                "modified_by": system_user_id,
            }
            settlement_record = institution_settlement_service.create(settlement_data, connection, commit=False)
            if not settlement_record:
                connection.rollback()
                log_error(f"Failed to create settlement for restaurant {restaurant_id}")
                return None

            balance_reset = restaurant_balance_service.reset_balance(restaurant_id, connection, commit=False)
            if not balance_reset:
                connection.rollback()
                log_error(f"Failed to reset restaurant balance for restaurant {restaurant_id}")
                return None

            connection.commit()
            log_info(
                f"Created settlement {settlement_record.settlement_id} for restaurant {restaurant_id}, "
                f"amount={settlement_record.amount} {settlement_record.currency_code}"
            )
            return settlement_record
        except Exception as e:
            log_error(f"Error creating settlement for restaurant {restaurant_id}: {e}")
            if connection:
                connection.rollback()
            return None

    @staticmethod
    def run_phase1_settlements(
        bill_date: date,
        system_user_id: UUID,
        country_code: str | None = None,
        location_id: str | None = None,
        timezone_filter: str | None = None,
        connection=None,
    ) -> dict:
        """
        Phase 1: Create one settlement per restaurant with balance > 0 for the period.
        No global balance reset; each restaurant's balance is reset when its settlement is created.
        When location_id is provided, timezone_filter and market are resolved from location config;
        only restaurants in that timezone are processed. Returns dict with settlements_created, etc.
        """
        from uuid import uuid4

        try:
            market_override, timezone_filter = _resolve_location_overrides(location_id, timezone_filter)
            kitchen_day = InstitutionBillingService._get_kitchen_day_for_date(bill_date)
            log_info(f"Phase 1 settlements: kitchen day {kitchen_day}, date {bill_date}")
            restaurants = InstitutionBillingService._get_restaurants_with_balances(
                connection=connection,
                timezone_filter=timezone_filter,
            )
            log_info(f"Phase 1: Found {len(restaurants) if restaurants else 0} restaurants with balance > 0")
            if not restaurants:
                log_info("Phase 1: No restaurants with balance > 0")
                return {
                    "settlements_created": 0,
                    "total_amount": 0.0,
                    "settlement_run_id": None,
                    "kitchen_day": kitchen_day,
                    "country_code": market_override or country_code,
                }
            settlement_run_id = uuid4()
            entity_aggregates = InstitutionBillingService._aggregate_restaurants_by_entity(restaurants)
            settlements_created = 0
            total_amount = Decimal("0.00")
            period_start, period_end = None, None
            for entity_data in entity_aggregates:
                try:
                    entity_country = _resolve_entity_country(entity_data, market_override, country_code, connection)
                    if not entity_country:
                        continue
                    day_to_use = _resolve_effective_kitchen_day(kitchen_day, entity_country)
                    if day_to_use is None:
                        continue
                    if is_holiday(entity_country, bill_date, connection):
                        log_info(f"National holiday for {entity_country} on {bill_date}, skipping entity")
                        continue
                    period_start, period_end = InstitutionBillingService._get_market_kitchen_day_period(
                        bill_date, day_to_use, entity_country
                    )
                    count, amount = _settle_entity_restaurants(
                        entity_data,
                        bill_date,
                        period_start,
                        period_end,
                        day_to_use,
                        entity_country,
                        settlement_run_id,
                        system_user_id,
                        connection,
                    )
                    settlements_created += count
                    total_amount += amount
                except Exception as e:
                    log_error(f"Error creating settlements for entity {entity_data['institution_entity_id']}: {e}")
                    continue
            log_info(f"Phase 1 complete: {settlements_created} settlements, total {total_amount}")
            resolved_country = market_override or country_code
            return {
                "settlements_created": settlements_created,
                "total_amount": float(total_amount),
                "settlement_run_id": str(settlement_run_id),
                "kitchen_day": kitchen_day,
                "country_code": resolved_country,
                "period_start": period_start.isoformat() if period_start else None,
                "period_end": period_end.isoformat() if period_end else None,
            }
        except Exception as e:
            log_error(f"Error in Phase 1 settlements: {e}")
            if connection:
                connection.rollback()
            return {
                "settlements_created": 0,
                "total_amount": 0.0,
                "settlement_run_id": None,
                "kitchen_day": None,
                "country_code": country_code,
                "error": str(e),
            }

    @staticmethod
    def run_phase2_bills_and_payout(settlement_run_id: UUID, system_user_id: UUID, connection=None) -> dict:
        """
        Phase 2: For each entity that has settlements in this run, create one bill
        (amount = sum of that entity's settlements), link settlements to the bill,
        then later tax doc + payout (stub for now).
        No bill for entities with zero settlements (Phase 1 already created only balance > 0).
        """
        try:
            settlements = get_settlements_by_run_id(settlement_run_id, connection)
            if not settlements:
                log_info("Phase 2: No settlements for this run")
                return {"bills_created": 0, "total_amount": 0.0}
            by_entity: dict[UUID, list[InstitutionSettlementDTO]] = {}
            for s in settlements:
                by_entity.setdefault(s.institution_entity_id, []).append(s)
            bills_created = 0
            total_amount = Decimal("0.00")
            for institution_entity_id, entity_settlements in by_entity.items():
                institution_id = get_institution_id_by_entity(institution_entity_id, connection)
                if not institution_id:
                    log_warning(f"Institution not found for entity {institution_entity_id}, skipping")
                    continue
                # Payment frequency gate: skip bill creation if not due today
                freq = get_supplier_payment_frequency(
                    institution_id, connection, institution_entity_id=institution_entity_id
                )
                today = date.today()
                if not _is_supplier_payout_due(freq, today):
                    log_info(
                        f"Skipping bill for entity {institution_entity_id}: payment_frequency={freq}, not due on {today}"
                    )
                    continue
                amount = sum(s.amount for s in entity_settlements)
                transaction_count = sum(s.transaction_count for s in entity_settlements)
                first = entity_settlements[0]
                bill_data = {
                    "institution_id": institution_id,
                    "institution_entity_id": institution_entity_id,
                    "currency_metadata_id": first.currency_metadata_id,
                    "transaction_count": transaction_count,
                    "amount": amount,
                    "currency_code": first.currency_code,
                    "period_start": first.period_start,
                    "period_end": first.period_end,
                    "status": Status.PENDING,
                    "resolution": BillResolution.PENDING.value,
                    "modified_by": system_user_id,
                }
                commit = connection is None
                bill = institution_bill_service.create(bill_data, connection, commit=commit)
                if not bill:
                    log_error(f"Failed to create bill for entity {institution_entity_id}")
                    continue
                for s in entity_settlements:
                    institution_settlement_service.update(
                        s.settlement_id,
                        {"institution_bill_id": bill.institution_bill_id},
                        connection,
                        commit=commit,
                    )
                bills_created += 1
                total_amount += amount
                log_info(f"Created bill {bill.institution_bill_id} for entity {institution_entity_id}, amount={amount}")
            log_info(f"Phase 2 complete: {bills_created} bills created, total {total_amount}")
            return {
                "bills_created": bills_created,
                "total_amount": float(total_amount),
            }
        except Exception as e:
            log_error(f"Error in Phase 2 bills: {e}")
            if connection:
                connection.rollback()
            return {"bills_created": 0, "total_amount": 0.0, "error": str(e)}

    @staticmethod
    def _get_bill_entity_id(bill) -> UUID | None:
        """Extract institution_entity_id from a bill (DTO or dict)."""
        if isinstance(bill, dict):
            return bill.get("institution_entity_id")
        return getattr(bill, "institution_entity_id", None)

    @staticmethod
    def _get_bill_institution_id(bill) -> UUID | None:
        """Extract institution_id from a bill (DTO or dict)."""
        if isinstance(bill, dict):
            return bill.get("institution_id")
        return getattr(bill, "institution_id", None)

    @staticmethod
    def _check_phase1_result(phase1: dict, own_conn: bool, connection) -> dict | None:
        """Check phase1 result for errors or zero settlements. Returns early-exit dict or None to continue."""
        if phase1.get("error"):
            return {"phase": "phase1", "error": phase1["error"], "settlements_created": 0}
        if phase1.get("settlements_created", 0) == 0:
            if own_conn:
                connection.commit()
            return {
                "settlements_created": 0,
                "bills_created": 0,
                "bills_paid": 0,
                "settlement_run_id": phase1.get("settlement_run_id"),
                "message": "No restaurants had balance > 0. Check restaurant_balance_info has balance > 0 for at least one restaurant (e.g. after Post QR Code Scan).",
            }
        if not phase1.get("settlement_run_id"):
            log_error("Missing settlement_run_id from Phase 1")
            if own_conn:
                connection.rollback()
            return {
                "phase": "phase1",
                "error": "Missing settlement_run_id",
                "settlements_created": phase1.get("settlements_created", 0),
            }
        return None

    @staticmethod
    def _process_bill_payouts(
        bill_ids: list,
        country_code: str,
        gw,
        system_user_id: UUID,
        connection,
    ) -> tuple[int, list[dict]]:
        """Process tax docs and payouts for each bill. Returns (bills_paid, paid_bill_details)."""
        from app.services.billing.tax_doc_service import issue_tax_doc_for_bill

        bills_paid = 0
        paid_bill_details: list[dict] = []
        for bill_id in bill_ids:
            bill = institution_bill_service.get_by_id(bill_id, connection)
            if not bill:
                continue
            issue_tax_doc_for_bill(bill_id, country_code, connection)
            entity_id = InstitutionBillingService._get_bill_entity_id(bill)
            if not entity_id:
                log_warning(f"Bill {bill_id} has no institution_entity_id; skipping payout")
                continue
            bill_institution_id = InstitutionBillingService._get_bill_institution_id(bill)
            if bill_institution_id and not _check_invoice_compliance(bill_institution_id, entity_id, connection):
                log_warning(
                    f"Payout held for bill {bill_id}: entity {entity_id} has unmatched bills exceeding invoice hold threshold"
                )
                continue
            try:
                payout_result = gw.execute_supplier_payout(
                    institution_bill_id=UUID(str(bill_id)),
                    entity_id=UUID(str(entity_id)),
                    current_user_id=system_user_id,
                    db=connection,
                )
            except HTTPException as e:
                log_warning(f"Payout skipped for bill {bill_id}: {e.detail}")
                continue
            except Exception as e:
                log_warning(f"Payout failed for bill {bill_id}: {e}")
                continue
            institution_bill_service.mark_paid(bill_id, system_user_id, connection)
            bills_paid += 1
            paid_bill_details.append(
                {
                    "institution_bill_id": str(bill_id),
                    "bill_payout_id": str(payout_result.get("bill_payout_id", "")),
                    "provider_transfer_id": payout_result.get("provider_transfer_id"),
                }
            )
        return bills_paid, paid_bill_details

    @staticmethod
    def run_daily_settlement_bill_and_payout(
        bill_date: date,
        system_user_id: UUID,
        country_code: str | None = None,
        location_id: str | None = None,
        connection=None,
    ) -> dict:
        """
        Full pipeline: Phase 1 (settlements per restaurant), Phase 2 (one bill per entity),
        then for each bill: issue tax doc stub, trigger payout (mock/live), set payout fields, mark_paid.
        When location_id is provided, only restaurants in that location's timezone are processed.
        """
        from app.config.settings import settings

        def _get_connect_gw():
            if (settings.SUPPLIER_PAYOUT_PROVIDER or "mock").lower() == "stripe":
                from app.services.payment_provider.stripe import connect_gateway

                return connect_gateway
            from app.services.payment_provider.stripe import connect_mock

            return connect_mock

        own_conn = connection is None
        if own_conn:
            connection = get_db_connection()
        try:
            phase1 = InstitutionBillingService.run_phase1_settlements(
                bill_date=bill_date,
                system_user_id=system_user_id,
                country_code=country_code,
                location_id=location_id,
                connection=connection,
            )
            early_result = InstitutionBillingService._check_phase1_result(phase1, own_conn, connection)
            if early_result is not None:
                return early_result
            settlement_run_id = UUID(phase1["settlement_run_id"])
            phase2 = InstitutionBillingService.run_phase2_bills_and_payout(
                settlement_run_id=settlement_run_id,
                system_user_id=system_user_id,
                connection=connection,
            )
            if phase2.get("error"):
                return {
                    "phase": "phase2",
                    "error": phase2["error"],
                    "settlements_created": phase1["settlements_created"],
                }
            # Commit Phase 1 + Phase 2 so settlements and bills are persisted (API uses shared connection that does not auto-commit)
            if not own_conn:
                connection.commit()
            settlements = get_settlements_by_run_id(settlement_run_id, connection)
            bill_ids = [s.institution_bill_id for s in settlements if s.institution_bill_id]
            cc = phase1.get("country_code") or country_code or "US"
            gw = _get_connect_gw()
            bills_paid, paid_bill_details = InstitutionBillingService._process_bill_payouts(
                bill_ids,
                cc,
                gw,
                system_user_id,
                connection,
            )
            if own_conn:
                connection.commit()
            return {
                "settlements_created": phase1["settlements_created"],
                "bills_created": phase2.get("bills_created", 0),
                "bills_paid": bills_paid,
                "bill_ids": [str(b) for b in bill_ids],
                "paid_bills": paid_bill_details,
                "settlement_run_id": phase1.get("settlement_run_id"),
                "total_amount": phase2.get("total_amount", 0.0),
            }
        except Exception as e:
            log_error(f"Pipeline error: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if own_conn and connection:
                close_db_connection(connection)

    @staticmethod
    def get_settlement_report_by_run_id(settlement_run_id: UUID, connection=None) -> dict:
        """
        Minimal settlement report for a run: list of settlements (per restaurant) and
        per-entity summary. JSON-serializable payload; PDF/formal report can be added later.
        """
        settlements = get_settlements_by_run_id(settlement_run_id, connection)
        if not settlements:
            return {"settlement_run_id": str(settlement_run_id), "settlements": [], "by_entity": {}}
        by_entity: dict[str, list[dict]] = {}
        total_amount = Decimal("0.00")
        for s in settlements:
            total_amount += s.amount
            row = {
                "settlement_id": str(s.settlement_id),
                "restaurant_id": str(s.restaurant_id),
                "institution_entity_id": str(s.institution_entity_id),
                "period_start": s.period_start.isoformat() if s.period_start else None,
                "period_end": s.period_end.isoformat() if s.period_end else None,
                "amount": float(s.amount),
                "currency_code": s.currency_code,
                "settlement_number": s.settlement_number,
                "institution_bill_id": str(s.institution_bill_id) if s.institution_bill_id else None,
            }
            key = str(s.institution_entity_id)
            by_entity.setdefault(key, []).append(row)
        by_entity_summary = {
            eid: {"count": len(rows), "amount": sum(r["amount"] for r in rows)} for eid, rows in by_entity.items()
        }
        return {
            "settlement_run_id": str(settlement_run_id),
            "settlements": [
                {
                    "settlement_id": str(s.settlement_id),
                    "restaurant_id": str(s.restaurant_id),
                    "amount": float(s.amount),
                    "currency_code": s.currency_code,
                    "settlement_number": s.settlement_number,
                    "institution_bill_id": str(s.institution_bill_id) if s.institution_bill_id else None,
                }
                for s in settlements
            ],
            "by_entity": by_entity_summary,
            "total_settlements": len(settlements),
            "total_amount": float(total_amount),
        }

    @staticmethod
    def get_settlement_report_by_bill_id(institution_bill_id: UUID, connection=None) -> dict:
        """Minimal report for one bill: its settlements (restaurant-level lines)."""
        query = """
            SELECT * FROM institution_settlement
            WHERE institution_bill_id = %s
            ORDER BY restaurant_id
        """
        results = db_read(query, (str(institution_bill_id),), connection=connection)
        if not results:
            return {"institution_bill_id": str(institution_bill_id), "settlements": []}
        total = sum(float(r["amount"]) for r in results)
        return {
            "institution_bill_id": str(institution_bill_id),
            "settlements": [
                {
                    "settlement_id": str(r["settlement_id"]),
                    "restaurant_id": str(r["restaurant_id"]),
                    "amount": float(r["amount"]),
                    "currency_code": r.get("currency_code"),
                    "settlement_number": r.get("settlement_number"),
                }
                for r in results
            ],
            "total_amount": total,
        }

    @staticmethod
    def _get_kitchen_day_for_date(target_date: date) -> str:
        """Get the kitchen day name for a given date. Delegates to kitchen_day_service."""
        from app.services.kitchen_day_service import date_to_kitchen_day

        return date_to_kitchen_day(target_date)

    @staticmethod
    def _get_market_kitchen_day_period(
        target_date: date, kitchen_day: str, country_code: str
    ) -> tuple[datetime, datetime]:
        """
        Get the billing period for a kitchen day based on market-specific configuration.
        Period starts at the beginning of the day and ends when the kitchen closes in local time.
        """
        # Start: Beginning of the target date in UTC
        period_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)

        # End: When the kitchen closes in local time, converted to UTC
        # Convert date to datetime for the market config call
        target_datetime = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)
        kitchen_close_utc = MarketConfiguration.get_kitchen_close_utc(country_code, target_datetime, kitchen_day)

        if not kitchen_close_utc:
            # Fallback: use end of day if kitchen close time not configured
            period_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=UTC)
            log_warning(f"No kitchen close time configured for {country_code} {kitchen_day}, using end of day")
        else:
            period_end = kitchen_close_utc

        return period_start, period_end

    @staticmethod
    def is_kitchen_day_active(kitchen_day: str, current_time: datetime | None = None, country_code: str = "AR") -> bool:
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
            current_time = datetime.now(UTC)

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
        return InstitutionBillingService._get_kitchen_day_for_date(datetime.now(UTC).date())

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
        current_time = datetime.now(UTC)
        current_day = current_time.date()
        current_kitchen_day = InstitutionBillingService._get_kitchen_day_for_date(current_day)

        billing_run_utc = MarketConfiguration.get_billing_run_utc(country_code, current_time, current_kitchen_day)
        if not billing_run_utc:
            return False

        billing_window_start = billing_run_utc
        billing_window_end = billing_run_utc + timedelta(minutes=5)
        return billing_window_start <= current_time <= billing_window_end

    @staticmethod
    def should_generate_bills_now_for_location(location_id: str) -> bool:
        """
        Check if it's time to generate bills for a location (uses location's timezone).
        For US-Eastern vs US-Pacific, each has different UTC billing run time.
        """
        from app.config.location_config import get_location_config

        loc = get_location_config(location_id)
        if not loc:
            return False
        current_time = datetime.now(UTC)
        current_day = current_time.date()
        current_kitchen_day = InstitutionBillingService._get_kitchen_day_for_date(current_day)
        billing_run_utc = MarketConfiguration.get_billing_run_utc_for_timezone(
            loc["market"], loc["timezone"], current_time, current_kitchen_day
        )
        if not billing_run_utc:
            return False
        billing_window_start = billing_run_utc
        billing_window_end = billing_run_utc + timedelta(minutes=5)
        return billing_window_start <= current_time <= billing_window_end

    @staticmethod
    def _get_restaurants_with_balances(
        connection=None,
        timezone_filter: str | None = None,
    ) -> list[dict]:
        """Get restaurants that have balance data. When timezone_filter is set, only include restaurants whose address has that timezone."""
        try:
            base_select = """
                SELECT
                    r.restaurant_id,
                    r.institution_id,
                    r.institution_entity_id,
                    ie.currency_metadata_id,
                    rb.transaction_count,
                    rb.balance,
                    rb.currency_code
                FROM restaurant_info r
                INNER JOIN institution_entity_info ie ON r.institution_entity_id = ie.institution_entity_id
                INNER JOIN restaurant_balance_info rb ON r.restaurant_id = rb.restaurant_id
            """
            if timezone_filter:
                base_select += """
                INNER JOIN address_info a ON r.address_id = a.address_id
                """
            base_select += """
                WHERE r.is_archived = %s
                AND rb.is_archived = %s
                AND rb.balance > 0
            """
            params: list = [False, False]
            if timezone_filter:
                base_select += " AND TRIM(COALESCE(a.timezone, '')) = %s"
                params.append(timezone_filter)
            base_select += " ORDER BY r.institution_entity_id, r.restaurant_id"

            results = db_read(base_select, tuple(params), connection=connection)
            if results:
                out = []
                for row in results:
                    try:
                        if isinstance(row, dict):
                            out.append(
                                {
                                    "restaurant_id": row["restaurant_id"]
                                    if isinstance(row.get("restaurant_id"), UUID)
                                    else UUID(str(row["restaurant_id"])),
                                    "institution_id": row["institution_id"]
                                    if isinstance(row.get("institution_id"), UUID)
                                    else UUID(str(row["institution_id"])),
                                    "institution_entity_id": row["institution_entity_id"]
                                    if isinstance(row.get("institution_entity_id"), UUID)
                                    else UUID(str(row["institution_entity_id"])),
                                    "currency_metadata_id": row["currency_metadata_id"]
                                    if isinstance(row.get("currency_metadata_id"), UUID)
                                    else UUID(str(row["currency_metadata_id"])),
                                    "transaction_count": row["transaction_count"],
                                    "balance": Decimal(str(row["balance"])),
                                    "currency_code": row["currency_code"],
                                }
                            )
                        else:
                            # fallback if row is tuple (e.g. legacy path)
                            out.append(
                                {
                                    "restaurant_id": row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                                    "institution_id": row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
                                    "institution_entity_id": row[2] if isinstance(row[2], UUID) else UUID(str(row[2])),
                                    "currency_metadata_id": row[3] if isinstance(row[3], UUID) else UUID(str(row[3])),
                                    "transaction_count": row[4],
                                    "balance": Decimal(str(row[5])),
                                    "currency_code": row[6],
                                }
                            )
                    except (KeyError, TypeError, IndexError) as e:
                        log_error(f"Error parsing restaurant row (dict={isinstance(row, dict)}): {e}")
                        continue
                return out
            return []

        except Exception as e:
            log_error(f"Error getting restaurants with balances: {e}")
            return []

    @staticmethod
    def _aggregate_restaurants_by_entity(restaurants: list[dict]) -> list[dict]:
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
                    "currency_metadata_id": restaurant["currency_metadata_id"],
                    "total_balance": Decimal("0.00"),
                    "total_transactions": 0,
                    "currency_code": restaurant["currency_code"],
                    "restaurant_count": 0,
                    "restaurant_ids": [],
                }

            # Aggregate balances and transaction counts
            entity_aggregates[entity_id]["total_balance"] += restaurant["balance"]
            entity_aggregates[entity_id]["total_transactions"] += restaurant["transaction_count"]
            entity_aggregates[entity_id]["restaurant_count"] += 1
            entity_aggregates[entity_id]["restaurant_ids"].append(restaurant["restaurant_id"])

        return list(entity_aggregates.values())

    @staticmethod
    def get_bills_by_institution(
        institution_id: UUID,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        connection=None,
    ) -> list[InstitutionBillDTO]:
        """Get bills for an institution with optional status and date filtering"""
        try:
            return institution_bill_service.get_by_institution(
                institution_id, status, start_date, end_date, connection=connection
            )
        except Exception as e:
            log_error(f"Error getting bills for institution {institution_id}: {e}")
            return []

    @staticmethod
    def get_pending_bills(connection=None) -> list[InstitutionBillDTO]:
        """Get all pending bills across all institutions"""
        try:
            return institution_bill_service.get_pending(connection)
        except Exception as e:
            log_error(f"Error getting pending bills: {e}")
            return []

    @staticmethod
    def cancel_bill(bill_id: UUID, user_id: UUID, connection=None, locale: str = "en") -> dict:
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
                raise envelope_exception(ErrorCode.BILLING_BILL_NOT_FOUND, status=404, locale=locale)

            if bill.status == Status.PROCESSED:
                raise envelope_exception(ErrorCode.BILLING_BILL_ALREADY_PAID, status=400, locale=locale)

            if bill.status == Status.CANCELLED:
                raise envelope_exception(ErrorCode.BILLING_BILL_ALREADY_CANCELLED, status=400, locale=locale)

            # 2. Update bill to cancelled/rejected status
            bill_update_data = {
                "status": Status.CANCELLED,
                "resolution": BillResolution.REJECTED.value,
                "modified_by": user_id,
            }

            updated_bill = institution_bill_service.update(bill_id, bill_update_data, connection)
            if not updated_bill:
                log_error(f"Failed to cancel bill {bill_id}")
                raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)

            log_info(f"Cancelled bill {bill_id}")

            return {
                "bill_id": bill_id,
                "status": Status.CANCELLED.value,  # Return enum value as string
                "resolution": BillResolution.REJECTED.value,
                "message": "Bill cancelled successfully",
            }

        except Exception as e:
            log_error(f"Error cancelling bill {bill_id}: {e}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale) from None

    @staticmethod
    def get_bill_summary_by_institution(
        institution_id: UUID, start_date: date, end_date: date, connection=None
    ) -> dict:
        """Get billing summary for an institution"""
        try:
            period_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=UTC)
            period_end = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=UTC)

            bills = institution_bill_service.get_by_institution_and_period(
                institution_id, period_start, period_end, connection
            )

            total_amount = sum((bill.amount or Decimal("0.00")) for bill in bills)
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
                "pending_amount": float(sum((bill.amount or Decimal("0.00")) for bill in pending_bills)),
                "paid_amount": float(sum((bill.amount or Decimal("0.00")) for bill in paid_bills)),
            }

        except Exception as e:
            log_error(f"Error getting bill summary for institution {institution_id}: {e}")
            return {}

    @staticmethod
    def _reduce_restaurant_balances(
        restaurant_ids: list[UUID],
        bill_amount: Decimal,
        currency_metadata_id: UUID,
        currency_code: str,
        system_user_id: UUID,
        connection=None,
    ):
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
            total_current_balance = Decimal("0.00")
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
                        final_balance = max(Decimal("0.00"), current_balance - reduction_amount)
                        reduction_needed = current_balance - final_balance

                        if reduction_needed > 0:
                            # Update the restaurant balance
                            restaurant_balance_service.update_with_monetary_amount(
                                restaurant_id,
                                -reduction_needed,  # Negative amount to reduce balance
                                currency_code=currency_code,
                                db=connection,
                            )

                            log_info(
                                f"Reduced balance for restaurant {restaurant_id}: "
                                f"${current_balance} → ${final_balance} (reduced by ${reduction_needed})"
                            )

                log_info(
                    f"Successfully reduced restaurant balances by ${bill_amount} across {len(restaurant_ids)} restaurants"
                )

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
                SELECT rb.restaurant_id, rb.balance, rb.currency_code, rb.currency_metadata_id
                FROM restaurant_balance_info rb
                WHERE rb.is_archived = %s AND rb.balance > 0
            """

            results = db_read(query, (False,), connection=connection)
            if not results:
                log_info("No restaurant balances to reset for new day")
                return

            reset_count = 0
            total_reset_amount = Decimal("0.00")

            for row in results:
                # db_read returns list of dicts (column names as keys)
                if isinstance(row, dict):
                    restaurant_id = (
                        row["restaurant_id"]
                        if isinstance(row.get("restaurant_id"), UUID)
                        else UUID(str(row["restaurant_id"]))
                    )
                    current_balance = Decimal(str(row["balance"]))
                    currency_code = row["currency_code"]
                    (
                        row["currency_metadata_id"]
                        if isinstance(row.get("currency_metadata_id"), UUID)
                        else UUID(str(row["currency_metadata_id"]))
                    )
                else:
                    restaurant_id = row[0]
                    current_balance = Decimal(str(row[1]))
                    currency_code = row[2]
                    row[3]

                try:
                    # Reset balance to 0
                    restaurant_balance_service.update_with_monetary_amount(
                        restaurant_id,
                        -float(current_balance),  # Negative amount to reduce to 0
                        currency_code=currency_code,
                        db=connection,
                    )

                    reset_count += 1
                    total_reset_amount += current_balance

                    log_info(
                        f"Reset balance for restaurant {restaurant_id}: ${current_balance} → $0.00 ({currency_code})"
                    )

                except Exception as e:
                    log_error(f"Error resetting balance for restaurant {restaurant_id}: {e}")
                    continue

            log_info(
                f"Daily balance reset complete: {reset_count} restaurants reset, "
                f"${total_reset_amount} total amount reset"
            )

        except Exception as e:
            log_error(f"Error in daily balance reset: {e}")
            # Don't fail the billing process if balance reset fails
