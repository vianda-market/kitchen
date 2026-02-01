"""
Discretionary Credit Service - Business Logic for Credit Request Management

This service handles the business logic for discretionary credit requests,
including creation, approval, rejection, and transaction processing.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime
import psycopg2.extensions
from fastapi import HTTPException

from app.dto.models import (
    DiscretionaryDTO, DiscretionaryResolutionDTO, 
    ClientTransactionDTO, RestaurantTransactionDTO,
    UserDTO, RestaurantDTO
)
from app.services.crud_service import (
    discretionary_service, discretionary_resolution_service,
    client_transaction_service, restaurant_transaction_service,
    user_service, restaurant_service, subscription_service
)
from app.utils.log import log_info, log_warning, log_error
from app.utils.error_messages import entity_not_found
from app.config import Status, DiscretionaryReason


class DiscretionaryService:
    """Service for handling discretionary credit business logic"""
    
    def __init__(self):
        pass
    
    def create_discretionary_request(
        self, 
        request_data: Dict[str, Any], 
        admin_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> DiscretionaryDTO:
        """
        Create a discretionary credit request.
        
        Args:
            request_data: Request data including user_id, restaurant_id, category, reason, amount, comment
            admin_user: Admin user creating the request
            db: Database connection
            
        Returns:
            Created discretionary request DTO
            
        Raises:
            HTTPException: For validation errors or creation failures
        """
        try:
            # Validate request data
            self._validate_discretionary_request_data(request_data)
            
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
            
            # Prepare request data
            request_data["status"] = Status.PENDING
            request_data["modified_by"] = admin_user["user_id"]
            
            # Create discretionary request
            discretionary_request = discretionary_service.create(request_data, db)
            if not discretionary_request:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to persist discretionary request in database"
                )
            
            log_info(f"Discretionary request created: {discretionary_request.discretionary_id} by admin {admin_user['user_id']}")
            return discretionary_request
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating discretionary request: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create discretionary request: {str(e)}"
            )
    
    def approve_discretionary_request(
        self, 
        discretionary_id: UUID, 
        super_admin: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> DiscretionaryResolutionDTO:
        """
        Approve a discretionary request and create the appropriate transaction.
        
        Args:
            discretionary_id: ID of the discretionary request
            super_admin: Super-admin user approving the request
            db: Database connection
            
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
            if discretionary_request.status != Status.PENDING:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot approve request with status: {discretionary_request.status}"
                )
            
            # Create resolution record
            resolution_data = {
                "discretionary_id": discretionary_id,
                "resolution": "Approved",
                "resolved_by": super_admin["user_id"],
                "status": Status.ACTIVE
            }
            
            resolution = discretionary_resolution_service.create(resolution_data, db)
            
            # Update discretionary request status
            discretionary_service.update(
                discretionary_id,
                {"status": Status.PROCESSED, "approval_id": resolution.approval_id},
                db
            )
            
            # Create appropriate transaction based on request type
            self._create_discretionary_transaction(discretionary_request, super_admin, db)
            
            log_info(f"Discretionary request {discretionary_id} approved by super-admin {super_admin['user_id']}")
            return resolution
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error approving discretionary request {discretionary_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to approve discretionary request")
    
    def reject_discretionary_request(
        self, 
        discretionary_id: UUID, 
        super_admin: Dict[str, Any], 
        reason: str,
        db: psycopg2.extensions.connection
    ) -> DiscretionaryResolutionDTO:
        """
        Reject a discretionary request.
        
        Args:
            discretionary_id: ID of the discretionary request
            super_admin: Super-admin user rejecting the request
            reason: Reason for rejection
            db: Database connection
            
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
            if discretionary_request.status != Status.PENDING:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot reject request with status: {discretionary_request.status}"
                )
            
            # Create resolution record
            resolution_data = {
                "discretionary_id": discretionary_id,
                "resolution": "Rejected",
                "resolved_by": super_admin["user_id"],
                "resolution_comment": reason,
                "status": Status.ACTIVE
            }
            
            resolution = discretionary_resolution_service.create(resolution_data, db)
            
            # Update discretionary request status
            discretionary_service.update(
                discretionary_id,
                {"status": Status.CANCELLED, "approval_id": resolution.approval_id},
                db
            )
            
            log_info(f"Discretionary request {discretionary_id} rejected by super-admin {super_admin['user_id']}: {reason}")
            return resolution
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error rejecting discretionary request {discretionary_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to reject discretionary request")
    
    def get_pending_requests(
        self, 
        db: psycopg2.extensions.connection
    ) -> List[DiscretionaryDTO]:
        """
        Get all pending discretionary requests for super-admin dashboard.
        
        Args:
            db: Database connection
            
        Returns:
            List of pending discretionary request DTOs
        """
        try:
            all_requests = discretionary_service.get_all(db)
            pending_requests = [req for req in all_requests if req.status == Status.PENDING]
            
            # Sort by creation date (oldest first)
            pending_requests.sort(key=lambda x: x.created_date)
            
            log_info(f"Retrieved {len(pending_requests)} pending discretionary requests")
            return pending_requests
            
        except Exception as e:
            log_error(f"Error retrieving pending discretionary requests: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve pending requests")
    
    def get_requests_by_admin(
        self, 
        admin_user_id: UUID, 
        db: psycopg2.extensions.connection
    ) -> List[DiscretionaryDTO]:
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
            raise HTTPException(status_code=500, detail="Failed to retrieve admin requests")
    
    def _validate_discretionary_request_data(self, request_data: Dict[str, Any]) -> None:
        """
        Validate discretionary request data.
        
        Args:
            request_data: Request data to validate
            
        Raises:
            HTTPException: For validation errors
        """
        # Validate required fields (category, reason, amount are always required)
        required_fields = ["category", "reason", "amount"]
        missing_fields = [field for field in required_fields if field not in request_data]
        
        if missing_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate that either user_id or restaurant_id is provided
        user_id = request_data.get("user_id")
        restaurant_id = request_data.get("restaurant_id")
        
        if not user_id and not restaurant_id:
            raise HTTPException(
                status_code=400,
                detail="Either user_id (for Client) or restaurant_id (for Supplier) must be provided"
            )
        
        # Validate amount is positive
        if request_data["amount"] <= 0:
            raise HTTPException(
                status_code=400, 
                detail="Amount must be greater than 0"
            )
        
        # Validate category
        valid_categories = ["Client", "Supplier"]
        if request_data["category"] not in valid_categories:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        
        # Enforce category based on user_id/restaurant_id relationship
        user_id = request_data.get("user_id")
        restaurant_id = request_data.get("restaurant_id")
        category = request_data["category"]
        
        if user_id and not restaurant_id:
            # Client request: must have category "Client"
            if category != "Client":
                raise HTTPException(
                    status_code=400,
                    detail="Category must be 'Client' when user_id is set and restaurant_id is null"
                )
        elif restaurant_id:
            # Supplier request: must have category "Supplier"
            if category != "Supplier":
                raise HTTPException(
                    status_code=400,
                    detail="Category must be 'Supplier' when restaurant_id is set"
                )
        else:
            # Both null is invalid
            raise HTTPException(
                status_code=400,
                detail="Either user_id (for Client) or restaurant_id (for Supplier) must be provided"
            )
        
        # Validate reason based on category (using enum)
        reason = request_data.get("reason")
        if reason:
            # Convert enum to string if needed
            reason_str = reason.value if isinstance(reason, DiscretionaryReason) else str(reason)
            
            if not DiscretionaryReason.is_valid_for_category(reason_str, category):
                valid_reasons = DiscretionaryReason.get_valid_for_category(category)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid reason for {category} category. Must be one of: {', '.join(valid_reasons)}"
                )
    
    def _create_discretionary_transaction(
        self, 
        discretionary_request: DiscretionaryDTO, 
        super_admin: Dict[str, Any], 
        db: psycopg2.extensions.connection
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
                    db
                )
            else:
                # Client credit - create client transaction
                credit_loading_service.create_client_credit_transaction(
                    discretionary_request.user_id,
                    discretionary_request.amount,
                    discretionary_request.discretionary_id,
                    super_admin["user_id"],
                    db
                )
                
        except Exception as e:
            log_error(f"Error creating discretionary transaction for request {discretionary_request.discretionary_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create discretionary transaction")
