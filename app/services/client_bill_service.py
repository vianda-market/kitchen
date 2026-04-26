"""
Client Bill Business Logic Service

This service contains all business logic related to client bill operations,
including currency resolution, validation, and bill processing.
"""

from datetime import UTC
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.dto.models import ClientBillDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.credit_currency_service import resolve_currency_code
from app.services.crud_service import client_bill_service, credit_currency_service
from app.utils.error_messages import client_bill_not_found
from app.utils.log import log_info


class ClientBillBusinessService:
    """Service for handling client bill business logic"""

    def __init__(self):
        pass

    # Client bills are not created via this service. They are created only when a payment
    # completes via subscription_payment (create_and_process_bill_for_subscription_payment in
    # subscription_action_service). Every bill is linked to a subscription_payment_id.

    def update_client_bill(
        self, bill_id: UUID, bill_data: dict[str, Any], current_user: dict[str, Any], db: psycopg2.extensions.connection
    ) -> ClientBillDTO:
        """
        Update an existing client bill.

        Args:
            bill_id: Client bill ID
            bill_data: Updated bill data dictionary
            current_user: Current user information
            db: Database connection

        Returns:
            Updated client bill DTO

        Raises:
            HTTPException: For validation or update failures
        """
        # Validate bill data
        self._validate_bill_data(bill_data)

        # Set modified_by field
        bill_data["modified_by"] = current_user["user_id"]

        # Resolve currency code if currency_metadata_id is being updated
        if "currency_metadata_id" in bill_data:
            self._resolve_currency_code(bill_data, db)

        # Apply business rules
        self._apply_bill_update_rules(bill_data)

        # Update the client bill
        updated_bill = client_bill_service.update(bill_id, bill_data, db)
        if not updated_bill:
            raise client_bill_not_found()

        log_info(f"Client bill updated: {updated_bill}")
        return updated_bill

    def get_client_bill_with_currency(self, bill_id: UUID, db: psycopg2.extensions.connection) -> dict[str, Any] | None:
        """
        Get client bill with associated currency information.

        Args:
            bill_id: Client bill ID
            db: Database connection

        Returns:
            Dictionary with bill and currency data, or None if not found
        """
        # Get client bill
        bill = client_bill_service.get_by_id(bill_id, db)
        if not bill:
            return None

        # Get currency information
        currency = credit_currency_service.get_by_id(bill.currency_metadata_id, db)

        result = {"bill": bill, "currency": currency}

        return result

    def validate_bill_amount(self, amount: float, currency_id: UUID, db: psycopg2.extensions.connection) -> bool:
        """
        Validate bill amount against currency constraints.

        Args:
            amount: Bill amount
            currency_id: Credit currency ID
            db: Database connection

        Returns:
            True if amount is valid, False otherwise
        """
        # Get currency information
        currency = credit_currency_service.get_by_id(currency_id, db)
        if not currency:
            return False

        # Basic validation - amount must be positive
        if amount <= 0:
            return False

        # Additional currency-specific validations can be added here
        # For example, minimum/maximum amounts per currency

        return True

    def calculate_bill_total(
        self, base_amount: float, tax_rate: float | None = None, discount_amount: float | None = None
    ) -> dict[str, float]:
        """
        Calculate bill total with tax and discount.

        Args:
            base_amount: Base bill amount
            tax_rate: Tax rate (as decimal, e.g., 0.08 for 8%)
            discount_amount: Discount amount to subtract

        Returns:
            Dictionary with calculated amounts
        """
        subtotal = base_amount

        # Apply discount
        if discount_amount and discount_amount > 0:
            subtotal = max(0, subtotal - discount_amount)

        # Calculate tax
        tax_amount = 0.0
        if tax_rate and tax_rate > 0:
            tax_amount = subtotal * tax_rate

        total = subtotal + tax_amount

        return {
            "base_amount": base_amount,
            "discount_amount": discount_amount or 0.0,
            "subtotal": subtotal,
            "tax_rate": tax_rate or 0.0,
            "tax_amount": tax_amount,
            "total": total,
        }

    def _validate_bill_data(self, bill_data: dict[str, Any]) -> None:
        """
        Validate client bill data.

        Args:
            bill_data: Bill data dictionary

        Raises:
            HTTPException: For validation failures
        """
        required_fields = ["currency_metadata_id", "amount"]
        missing_fields = [field for field in required_fields if not bill_data.get(field)]

        if missing_fields:
            raise envelope_exception(
                ErrorCode.VALIDATION_FIELD_REQUIRED, status=400, locale="en", field=", ".join(missing_fields)
            )

        # Validate amount
        amount = bill_data.get("amount", 0)
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise envelope_exception(ErrorCode.CREDIT_AMOUNT_MUST_BE_POSITIVE, status=400, locale="en")

        # Validate currency_metadata_id format
        try:
            UUID(str(bill_data["currency_metadata_id"]))
        except (ValueError, TypeError):
            raise envelope_exception(ErrorCode.VALIDATION_INVALID_FORMAT, status=400, locale="en") from None

    def _resolve_currency_code(self, bill_data: dict[str, Any], db: psycopg2.extensions.connection) -> None:
        """
        Resolve currency code from credit currency ID using centralized service.

        Args:
            bill_data: Bill data dictionary (modified in place)
            db: Database connection

        Raises:
            HTTPException: For currency resolution failures
        """
        resolve_currency_code(bill_data, db)

    def _apply_bill_update_rules(self, bill_data: dict[str, Any]) -> None:
        """
        Apply business rules for bill updates.

        Args:
            bill_data: Bill data dictionary (modified in place)
        """
        # Ensure amount is properly formatted if being updated
        if "amount" in bill_data:
            bill_data["amount"] = float(bill_data["amount"])

        # Set update timestamp
        from datetime import datetime

        bill_data["modified_date"] = datetime.now(UTC)

        log_info("Applied bill update business rules")

    def get_bills_by_status(self, status: str, db: psycopg2.extensions.connection) -> list[ClientBillDTO]:
        """
        Get all client bills by status.

        Args:
            status: Bill status to filter by
            db: Database connection

        Returns:
            List of client bill DTOs
        """
        # This would typically be implemented in the CRUD service
        # For now, we'll use the generic get_all and filter
        all_bills = client_bill_service.get_all(db)
        return [bill for bill in all_bills if bill.status == status]

    def get_bills_by_currency(self, currency_id: UUID, db: psycopg2.extensions.connection) -> list[ClientBillDTO]:
        """
        Get all client bills for a specific currency.

        Args:
            currency_id: Credit currency ID
            db: Database connection

        Returns:
            List of client bill DTOs
        """
        # This would typically be implemented in the CRUD service
        # For now, we'll use the generic get_all and filter
        all_bills = client_bill_service.get_all(db)
        return [bill for bill in all_bills if bill.currency_metadata_id == currency_id]


# Create service instance
client_bill_business_service = ClientBillBusinessService()
