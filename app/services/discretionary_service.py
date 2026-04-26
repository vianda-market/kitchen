"""
Discretionary Credit Service - Business Logic for Credit Request Management

This service handles the business logic for discretionary credit requests,
including creation, approval, rejection, and transaction processing.
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import HTTPException

from app.config import DiscretionaryReason
from app.config.enums import DiscretionaryStatus, Status
from app.dto.models import DiscretionaryDTO, DiscretionaryResolutionDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.crud_service import (
    discretionary_resolution_service,
    discretionary_service,
    restaurant_service,
    user_service,
)
from app.services.market_service import market_service
from app.utils.error_messages import entity_not_found
from app.utils.log import log_error, log_info


class DiscretionaryService:
    """Service for handling discretionary credit business logic"""

    def __init__(self):
        pass

    def create_discretionary_request(
        self,
        request_data: dict[str, Any],
        admin_user: dict[str, Any],
        db: psycopg2.extensions.connection,
        locale: str = "en",
    ) -> DiscretionaryDTO:
        """
        Create a discretionary credit request.

        Args:
            request_data: Request data including user_id, restaurant_id, category, reason, amount, comment
            admin_user: Admin user creating the request
            db: Database connection
            locale: Locale for error messages

        Returns:
            Created discretionary request DTO

        Raises:
            HTTPException: For validation errors or creation failures
        """
        try:
            # Validate request data
            self._validate_discretionary_request_data(request_data, locale)

            target_user = None
            restaurant = None
            # Validate target user exists (only for Client requests)
            if request_data.get("user_id"):
                target_user = user_service.get_by_id(request_data["user_id"], db)
                if not target_user:
                    raise entity_not_found("User", request_data["user_id"])

            # Validate restaurant exists (only for Supplier requests)
            if request_data.get("restaurant_id"):
                restaurant = restaurant_service.get_by_id(request_data["restaurant_id"], db)
                if not restaurant:
                    raise entity_not_found("Restaurant", request_data["restaurant_id"])

            # Optional: validate selected user/restaurant belongs to requested institution/market
            req_institution_id = request_data.get("institution_id")
            req_market_id = request_data.get("market_id")
            if request_data.get("user_id") and target_user:
                if req_institution_id is not None and str(target_user.institution_id) != str(req_institution_id):
                    raise envelope_exception(
                        ErrorCode.DISCRETIONARY_RECIPIENT_INSTITUTION_MISMATCH,
                        status=400,
                        locale=locale,
                    )
                if req_market_id is not None and str(target_user.market_id) != str(req_market_id):
                    raise envelope_exception(
                        ErrorCode.DISCRETIONARY_RECIPIENT_MARKET_MISMATCH,
                        status=400,
                        locale=locale,
                    )
            if request_data.get("restaurant_id") and restaurant:
                if req_institution_id is not None and str(restaurant.institution_id) != str(req_institution_id):
                    raise envelope_exception(
                        ErrorCode.DISCRETIONARY_RECIPIENT_INSTITUTION_MISMATCH,
                        status=400,
                        locale=locale,
                    )
                if req_market_id is not None:
                    market = market_service.get_by_id(req_market_id)
                    if not market:
                        raise envelope_exception(ErrorCode.MARKET_NOT_FOUND, status=400, locale=locale)
                    from app.services.entity_service import get_currency_metadata_id_for_restaurant

                    entity_currency_metadata_id = get_currency_metadata_id_for_restaurant(restaurant, db)
                    if str(entity_currency_metadata_id) != str(market.get("currency_metadata_id")):
                        raise envelope_exception(
                            ErrorCode.DISCRETIONARY_RECIPIENT_MARKET_MISMATCH,
                            status=400,
                            locale=locale,
                        )

            # Remove validation-only fields before persisting
            request_data = {k: v for k, v in request_data.items() if k not in ("institution_id", "market_id")}

            # Prepare request data
            request_data["status"] = DiscretionaryStatus.PENDING
            request_data["modified_by"] = admin_user["user_id"]

            # Create discretionary request
            discretionary_request = discretionary_service.create(request_data, db)
            if not discretionary_request:
                raise envelope_exception(ErrorCode.DISCRETIONARY_REQUEST_CREATION_FAILED, status=500, locale="en")

            log_info(
                f"Discretionary request created: {discretionary_request.discretionary_id} by admin {admin_user['user_id']}"
            )
            return discretionary_request

        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating discretionary request: {e}")
            raise envelope_exception(ErrorCode.DISCRETIONARY_REQUEST_CREATION_FAILED, status=500, locale="en") from None

    def approve_discretionary_request(
        self,
        discretionary_id: UUID,
        super_admin: dict[str, Any],
        db: psycopg2.extensions.connection,
        locale: str = "en",
    ) -> DiscretionaryResolutionDTO:
        """
        Approve a discretionary request and create the appropriate transaction.

        Args:
            discretionary_id: ID of the discretionary request
            super_admin: Super-admin user approving the request
            db: Database connection
            locale: Locale for error messages

        Returns:
            Discretionary resolution DTO

        Raises:
            HTTPException: For validation errors or processing failures
        """
        try:
            # Get the discretionary request
            discretionary_request = discretionary_service.get_by_id(discretionary_id, db)
            if not discretionary_request:
                raise entity_not_found("Discretionary request", discretionary_id)

            # Validate request is pending
            if discretionary_request.status != DiscretionaryStatus.PENDING:
                request_status = getattr(discretionary_request.status, "value", discretionary_request.status)
                raise envelope_exception(
                    ErrorCode.DISCRETIONARY_NOT_PENDING,
                    status=400,
                    locale=locale,
                    request_status=str(request_status),
                )

            # Create resolution record
            resolution_data = {
                "discretionary_id": discretionary_id,
                "resolution": DiscretionaryStatus.APPROVED,
                "resolved_by": super_admin["user_id"],
                "status": Status.ACTIVE,
            }

            resolution = discretionary_resolution_service.create(resolution_data, db)

            # Update discretionary request status
            discretionary_service.update(
                discretionary_id, {"status": DiscretionaryStatus.APPROVED, "approval_id": resolution.approval_id}, db
            )

            # Create appropriate transaction based on request type
            self._create_discretionary_transaction(discretionary_request, super_admin, db)

            log_info(f"Discretionary request {discretionary_id} approved by super-admin {super_admin['user_id']}")
            return resolution

        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error approving discretionary request {discretionary_id}: {e}")
            raise envelope_exception(ErrorCode.DISCRETIONARY_REQUEST_APPROVAL_FAILED, status=500, locale="en") from None

    def reject_discretionary_request(
        self,
        discretionary_id: UUID,
        super_admin: dict[str, Any],
        reason: str,
        db: psycopg2.extensions.connection,
        locale: str = "en",
    ) -> DiscretionaryResolutionDTO:
        """
        Reject a discretionary request.

        Args:
            discretionary_id: ID of the discretionary request
            super_admin: Super-admin user rejecting the request
            reason: Reason for rejection
            db: Database connection
            locale: Locale for error messages

        Returns:
            Discretionary resolution DTO

        Raises:
            HTTPException: For validation errors or processing failures
        """
        try:
            # Get the discretionary request
            discretionary_request = discretionary_service.get_by_id(discretionary_id, db)
            if not discretionary_request:
                raise entity_not_found("Discretionary request", discretionary_id)

            # Validate request is pending
            if discretionary_request.status != DiscretionaryStatus.PENDING:
                request_status = getattr(discretionary_request.status, "value", discretionary_request.status)
                raise envelope_exception(
                    ErrorCode.DISCRETIONARY_NOT_PENDING,
                    status=400,
                    locale=locale,
                    request_status=str(request_status),
                )

            # Create resolution record
            resolution_data = {
                "discretionary_id": discretionary_id,
                "resolution": DiscretionaryStatus.REJECTED,
                "resolved_by": super_admin["user_id"],
                "resolution_comment": reason,
                "status": Status.ACTIVE,
            }

            resolution = discretionary_resolution_service.create(resolution_data, db)

            # Update discretionary request status
            discretionary_service.update(
                discretionary_id, {"status": DiscretionaryStatus.REJECTED, "approval_id": resolution.approval_id}, db
            )

            log_info(
                f"Discretionary request {discretionary_id} rejected by super-admin {super_admin['user_id']}: {reason}"
            )
            return resolution

        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error rejecting discretionary request {discretionary_id}: {e}")
            raise envelope_exception(
                ErrorCode.DISCRETIONARY_REQUEST_REJECTION_FAILED, status=500, locale="en"
            ) from None

    def get_pending_requests(self, db: psycopg2.extensions.connection) -> list[DiscretionaryDTO]:
        """
        Get all pending discretionary requests for super-admin dashboard.

        Args:
            db: Database connection

        Returns:
            List of pending discretionary request DTOs
        """
        try:
            all_requests = discretionary_service.get_all(db)
            pending_requests = [req for req in all_requests if req.status == DiscretionaryStatus.PENDING]

            # Sort by creation date (oldest first)
            pending_requests.sort(key=lambda x: x.created_date)

            log_info(f"Retrieved {len(pending_requests)} pending discretionary requests")
            return pending_requests

        except Exception as e:
            log_error(f"Error retrieving pending discretionary requests: {e}")
            raise envelope_exception(ErrorCode.DISCRETIONARY_LIST_FAILED, status=500, locale="en") from None

    def get_requests_by_admin(self, admin_user_id: UUID, db: psycopg2.extensions.connection) -> list[DiscretionaryDTO]:
        """
        Get all discretionary requests created by a specific admin.

        Args:
            admin_user_id: ID of the admin user
            db: Database connection

        Returns:
            List of discretionary request DTOs created by the admin
        """
        try:
            all_requests = discretionary_service.get_all(db)
            admin_requests = [req for req in all_requests if req.modified_by == admin_user_id]

            # Sort by creation date (newest first)
            admin_requests.sort(key=lambda x: x.created_date, reverse=True)

            log_info(f"Retrieved {len(admin_requests)} discretionary requests for admin {admin_user_id}")
            return admin_requests

        except Exception as e:
            log_error(f"Error retrieving discretionary requests for admin {admin_user_id}: {e}")
            raise envelope_exception(ErrorCode.DISCRETIONARY_LIST_FAILED, status=500, locale="en") from None

    def _validate_discretionary_request_data(self, request_data: dict[str, Any], locale: str = "en") -> None:
        """
        Validate discretionary request data.

        Args:
            request_data: Request data to validate
            locale: Locale for error messages

        Raises:
            HTTPException: For validation errors
        """
        # Validate required fields (category and amount are always required, reason is optional)
        required_fields = ["category", "amount"]
        missing_fields = [field for field in required_fields if field not in request_data]

        if missing_fields:
            raise envelope_exception(
                ErrorCode.VALIDATION_FIELD_REQUIRED,
                status=400,
                locale=locale,
            )

        # Validate that either user_id or restaurant_id is provided (mutually exclusive)
        user_id = request_data.get("user_id")
        restaurant_id = request_data.get("restaurant_id")

        if not user_id and not restaurant_id:
            raise envelope_exception(
                ErrorCode.VALIDATION_DISCRETIONARY_RECIPIENT_REQUIRED,
                status=400,
                locale=locale,
            )

        if user_id and restaurant_id:
            raise envelope_exception(
                ErrorCode.VALIDATION_DISCRETIONARY_CONFLICTING_RECIPIENTS,
                status=400,
                locale=locale,
            )

        # Validate amount is positive
        if request_data["amount"] <= 0:
            raise envelope_exception(ErrorCode.DISCRETIONARY_INVALID_AMOUNT, status=400, locale=locale)

        # Validate category is a valid DiscretionaryReason enum
        category = request_data["category"]

        # Convert to enum if it's a string
        if isinstance(category, str):
            if not DiscretionaryReason.is_valid(category):
                raise envelope_exception(
                    ErrorCode.DISCRETIONARY_INVALID_CATEGORY,
                    status=400,
                    locale=locale,
                    category=category,
                )
            # Convert string to enum for further validation
            try:
                category = DiscretionaryReason(category)
                request_data["category"] = category
            except ValueError:
                raise envelope_exception(
                    ErrorCode.DISCRETIONARY_INVALID_CATEGORY,
                    status=400,
                    locale=locale,
                    category=category,
                ) from None

        # Validate restaurant_id is provided for restaurant-specific categories
        if DiscretionaryReason.requires_restaurant(category) and not restaurant_id:
            raise envelope_exception(
                ErrorCode.DISCRETIONARY_CATEGORY_REQUIRES_RESTAURANT,
                status=400,
                locale=locale,
                category=category.value if hasattr(category, "value") else str(category),
            )

    def _create_discretionary_transaction(
        self, discretionary_request: DiscretionaryDTO, super_admin: dict[str, Any], db: psycopg2.extensions.connection
    ) -> None:
        """
        Create the appropriate transaction based on discretionary request type.

        Note: Balance updates are handled automatically by existing services
        when transactions are created.

        Args:
            discretionary_request: The approved discretionary request
            super_admin: Super-admin user
            db: Database connection
        """
        try:
            from app.services.credit_loading_service import CreditLoadingService

            credit_loading_service = CreditLoadingService()

            if discretionary_request.restaurant_id:
                # Restaurant credit - create restaurant transaction
                credit_loading_service.create_restaurant_credit_transaction(
                    discretionary_request.restaurant_id,
                    discretionary_request.amount,
                    discretionary_request.discretionary_id,
                    super_admin["user_id"],
                    db,
                )
            else:
                # Client credit - create client transaction
                credit_loading_service.create_client_credit_transaction(
                    discretionary_request.user_id,
                    discretionary_request.amount,
                    discretionary_request.discretionary_id,
                    super_admin["user_id"],
                    db,
                )

        except Exception as e:
            log_error(
                f"Error creating discretionary transaction for request {discretionary_request.discretionary_id}: {e}"
            )
            raise envelope_exception(
                ErrorCode.DISCRETIONARY_TRANSACTION_CREATION_FAILED, status=500, locale="en"
            ) from None
