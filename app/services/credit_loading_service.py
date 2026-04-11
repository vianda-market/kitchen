"""
Credit Loading Service - Business Logic for Discretionary Transaction Creation

This service handles the business logic for creating discretionary transactions
that feed into the existing balance management system. The existing services
handle balance updates automatically when transactions are created.
"""

from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
import psycopg2.extensions
from fastapi import HTTPException

from app.dto.models import (
    ClientTransactionDTO, RestaurantTransactionDTO
)
from app.services.crud_service import (
    client_transaction_service,
    restaurant_service,
    credit_currency_service,
    create_with_conservative_balance_update
)
from app.utils.log import log_info, log_error, log_warning
from app.utils.error_messages import entity_not_found
from app.config import Status


class CreditLoadingService:
    """Service for handling discretionary credit transaction creation"""
    
    def __init__(self):
        pass
    
    def create_client_credit_transaction(
        self, 
        user_id: UUID, 
        amount: Decimal, 
        discretionary_id: UUID, 
        modified_by: UUID,
        db: psycopg2.extensions.connection
    ) -> ClientTransactionDTO:
        """
        Create client credit transaction for discretionary credits and update subscription balance.
        
        Note: Subscription status activation (Pending -> Active) is handled automatically
        by the database trigger subscription_status_activation_trigger() when balance
        transitions from <= 0 to > 0 for Pending subscriptions.
        
        Args:
            user_id: User ID to load credits for
            amount: Amount of credits to load (positive)
            discretionary_id: ID of the discretionary request
            modified_by: User ID making the change
            db: Database connection
            
        Returns:
            Created client transaction DTO
            
        Raises:
            HTTPException: For validation errors or creation failures
        """
        try:
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))

            # Validate amount is positive
            if amount <= 0:
                raise HTTPException(status_code=400, detail="Credit amount must be positive")
            
            # Create client transaction
            transaction_data = {
                "user_id": user_id,
                "source": "discretionary",
                "discretionary_id": discretionary_id,
                "credit": amount,  # Allow partial credits
                "status": Status.ACTIVE,
                "modified_by": modified_by
            }
            
            client_transaction = client_transaction_service.create(transaction_data, db)
            
            # Update subscription balance (trigger will automatically activate status if Pending -> positive balance)
            from app.services.crud_service import subscription_service, update_balance
            subscription = subscription_service.get_by_user(user_id, db)
            if subscription:
                success = update_balance(subscription.subscription_id, float(amount), db)
                if success:
                    log_info(f"Updated subscription balance for user {user_id}: added {amount} credits via discretionary {discretionary_id}")
                else:
                    log_warning(f"Failed to update subscription balance for user {user_id}")
            else:
                log_warning(f"Subscription not found for user {user_id}")
            
            log_info(f"Created client credit transaction: {client_transaction.transaction_id} for user {user_id} via discretionary {discretionary_id}")
            return client_transaction
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating client credit transaction for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create client credit transaction")
    
    def create_restaurant_credit_transaction(
        self, 
        restaurant_id: UUID, 
        amount: Decimal, 
        discretionary_id: UUID, 
        modified_by: UUID,
        db: psycopg2.extensions.connection
    ) -> RestaurantTransactionDTO:
        """
        Create restaurant credit transaction for discretionary credits.
        
        Note: Balance updates are handled automatically by existing services
        when restaurant transactions are created.
        
        Args:
            restaurant_id: Restaurant ID to load credits for
            amount: Amount of credits to load (positive)
            discretionary_id: ID of the discretionary request
            modified_by: User ID making the change
            db: Database connection
            
        Returns:
            Created restaurant transaction DTO
            
        Raises:
            HTTPException: For validation errors or creation failures
        """
        try:
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))

            # Validate amount is positive
            if amount <= 0:
                raise HTTPException(status_code=400, detail="Credit amount must be positive")
            
            restaurant = restaurant_service.get_by_id(restaurant_id, db)
            if not restaurant:
                raise entity_not_found("Restaurant", restaurant_id)
            from app.services.entity_service import get_currency_metadata_id_for_restaurant
            currency_metadata_id = get_currency_metadata_id_for_restaurant(restaurant, db)
            currency = credit_currency_service.get_by_id(currency_metadata_id, db)
            if not currency:
                raise HTTPException(status_code=404, detail="Credit currency not found for restaurant")

            now = datetime.now(timezone.utc)
            
            transaction_data = {
                "restaurant_id": restaurant_id,
                "plate_selection_id": None,
                "discretionary_id": discretionary_id,
                "currency_metadata_id": currency_metadata_id,
                "was_collected": False,
                "ordered_timestamp": now,
                "collected_timestamp": None,
                "arrival_time": None,
                "completion_time": None,
                "expected_completion_time": None,
                "transaction_type": "Discretionary",
                "credit": amount,  # Allow partial credits
                "no_show_discount": None,
                "currency_code": currency.currency_code,
                "final_amount": amount,
                "is_archived": False,
                "status": Status.PENDING,
                "created_date": now,
                "modified_by": modified_by,
                "modified_date": now
            }
            
            restaurant_transaction = create_with_conservative_balance_update(transaction_data, db)
            
            log_info(f"Created restaurant credit transaction: {restaurant_transaction.transaction_id} for restaurant {restaurant_id} via discretionary {discretionary_id}")
            return restaurant_transaction
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating restaurant credit transaction for restaurant {restaurant_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create restaurant credit transaction")
