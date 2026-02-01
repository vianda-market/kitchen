"""
Bank Account Business Logic Service

This service contains all business logic related to bank account operations,
including validation, formatting, and business rule enforcement.
"""

from uuid import UUID
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
import psycopg2.extensions

from app.dto.models import InstitutionBankAccountDTO, InstitutionEntityDTO
from app.services.crud_service import (
    institution_bank_account_service, 
    institution_entity_service,
    get_by_institution_entity,
    get_by_institution,
    get_active_accounts,
    validate_routing_number,
    validate_account_number
)
from app.utils.log import log_info, log_warning
from app.utils.error_messages import bank_account_not_found, institution_entity_not_found
from app.config import Status


class BankAccountBusinessService:
    """Service for handling bank account business logic"""
    
    def __init__(self):
        pass
    
    def validate_bank_account(
        self, 
        bank_account_id: UUID, 
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Validate bank account routing and account numbers.
        
        Args:
            bank_account_id: Bank account ID
            db: Database connection
            
        Returns:
            Dictionary containing validation results
            
        Raises:
            HTTPException: For validation failures
        """
        # Get bank account
        bank_account = institution_bank_account_service.get_by_id(bank_account_id, db)
        if not bank_account:
            raise bank_account_not_found()
        
        # Validate routing number
        routing_valid = validate_routing_number(bank_account.routing_number)
        
        # Validate account number
        account_valid = validate_account_number(bank_account.account_number)
        
        # Build validation result
        validation_result = {
            "bank_account_id": str(bank_account_id),
            "routing_number": bank_account.routing_number,
            "account_number": self._mask_account_number(bank_account.account_number),
            "routing_number_valid": routing_valid,
            "account_number_valid": account_valid,
            "overall_valid": routing_valid and account_valid,
            "validation_notes": []
        }
        
        # Add validation notes
        if not routing_valid:
            validation_result["validation_notes"].append("Routing number format is invalid")
        if not account_valid:
            validation_result["validation_notes"].append("Account number format is invalid")
        
        # Add additional business rule validations
        self._add_business_validation_notes(bank_account, validation_result)
        
        log_info(f"Validated bank account: {bank_account_id}")
        return validation_result
    
    def create_bank_account(
        self, 
        account_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> InstitutionBankAccountDTO:
        """
        Create a new bank account with validation.
        
        Args:
            account_data: Bank account data dictionary
            current_user: Current user information
            db: Database connection
            
        Returns:
            Created bank account DTO
            
        Raises:
            HTTPException: For validation or creation failures
        """
        # Validate account data
        self._validate_account_data(account_data)
        
        # Set modified_by field
        account_data["modified_by"] = current_user["user_id"]
        
        # Apply business rules
        self._apply_account_creation_rules(account_data)
        
        # Create the bank account
        bank_account = institution_bank_account_service.create(account_data, db)
        if not bank_account:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create bank account"
            )
        
        log_info(f"Bank account created: {bank_account}")
        return bank_account
    
    def create_minimal_bank_account(
        self, 
        account_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> InstitutionBankAccountDTO:
        """
        Create a minimal bank account with auto-populated fields.
        
        Args:
            account_data: Minimal bank account data dictionary
            current_user: Current user information
            db: Database connection
            
        Returns:
            Created bank account DTO
            
        Raises:
            HTTPException: For validation or creation failures
        """
        # Auto-populate missing fields
        self._auto_populate_minimal_account(account_data, db)
        
        # Create using standard creation logic
        return self.create_bank_account(account_data, current_user, db)
    
    def get_bank_accounts_by_institution(
        self, 
        institution_id: UUID, 
        include_archived: bool = False, 
        db: psycopg2.extensions.connection = None
    ) -> List[InstitutionBankAccountDTO]:
        """
        Get all bank accounts for an institution.
        
        Args:
            institution_id: Institution ID
            include_archived: Whether to include archived accounts
            db: Database connection
            
        Returns:
            List of bank account DTOs
        """
        accounts = get_by_institution(institution_id, db)
        
        if not include_archived:
            accounts = [account for account in accounts if not account.is_archived]
        
        return accounts
    
    def get_active_bank_accounts(
        self, 
        institution_entity_id: Optional[UUID] = None, 
        db: psycopg2.extensions.connection = None
    ) -> List[InstitutionBankAccountDTO]:
        """
        Get all active bank accounts, optionally filtered by institution entity.
        
        Args:
            institution_entity_id: Optional institution entity ID filter
            db: Database connection
            
        Returns:
            List of active bank account DTOs
        """
        if institution_entity_id:
            return get_by_institution_entity(institution_entity_id, db)
        else:
            return get_active_accounts(db)
    
    def update_bank_account(
        self, 
        account_id: UUID, 
        account_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> InstitutionBankAccountDTO:
        """
        Update an existing bank account.
        
        Args:
            account_id: Bank account ID
            account_data: Updated account data dictionary
            current_user: Current user information
            db: Database connection
            
        Returns:
            Updated bank account DTO
            
        Raises:
            HTTPException: For validation or update failures
        """
        # Validate account data
        self._validate_account_data(account_data, is_update=True)
        
        # Set modified_by field
        account_data["modified_by"] = current_user["user_id"]
        
        # Apply business rules
        self._apply_account_update_rules(account_data)
        
        # Update the bank account
        updated_account = institution_bank_account_service.update(account_id, account_data, db)
        if not updated_account:
            raise bank_account_not_found()
        
        log_info(f"Bank account updated: {updated_account}")
        return updated_account
    
    def _validate_account_data(self, account_data: Dict[str, Any], is_update: bool = False) -> None:
        """
        Validate bank account data.
        
        Args:
            account_data: Account data dictionary
            is_update: Whether this is an update operation
            
        Raises:
            HTTPException: For validation failures
        """
        required_fields = ["routing_number", "account_number"]
        if not is_update:
            required_fields.append("institution_entity_id")
        
        missing_fields = [field for field in required_fields if not account_data.get(field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate routing number format
        routing_number = account_data.get("routing_number", "")
        if not validate_routing_number(routing_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid routing number format"
            )
        
        # Validate account number format
        account_number = account_data.get("account_number", "")
        if not validate_account_number(account_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid account number format"
            )
        
        # Validate institution_entity_id if provided
        if "institution_entity_id" in account_data:
            try:
                UUID(str(account_data["institution_entity_id"]))
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid institution_entity_id format"
                )
    
    def _apply_account_creation_rules(self, account_data: Dict[str, Any]) -> None:
        """
        Apply business rules for account creation.
        
        Args:
            account_data: Account data dictionary (modified in place)
        """
        # Set default values
        account_data.setdefault("is_archived", False)
        account_data.setdefault("status", Status.ACTIVE)
        
        # Ensure routing and account numbers are strings
        if "routing_number" in account_data:
            account_data["routing_number"] = str(account_data["routing_number"]).strip()
        
        if "account_number" in account_data:
            account_data["account_number"] = str(account_data["account_number"]).strip()
        
        # Set creation timestamp if not provided
        if "created_date" not in account_data:
            from datetime import datetime
            account_data["created_date"] = datetime.utcnow()
        
        log_info("Applied bank account creation business rules")
    
    def _apply_account_update_rules(self, account_data: Dict[str, Any]) -> None:
        """
        Apply business rules for account updates.
        
        Args:
            account_data: Account data dictionary (modified in place)
        """
        # Ensure routing and account numbers are strings if being updated
        if "routing_number" in account_data:
            account_data["routing_number"] = str(account_data["routing_number"]).strip()
        
        if "account_number" in account_data:
            account_data["account_number"] = str(account_data["account_number"]).strip()
        
        # Set update timestamp
        from datetime import datetime
        account_data["modified_date"] = datetime.utcnow()
        
        log_info("Applied bank account update business rules")
    
    def _auto_populate_minimal_account(
        self, 
        account_data: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> None:
        """
        Auto-populate missing fields for minimal account creation.
        
        Args:
            account_data: Account data dictionary (modified in place)
            db: Database connection
        """
        # If institution_entity_id is provided, validate it exists
        if "institution_entity_id" in account_data:
            entity = institution_entity_service.get_by_id(account_data["institution_entity_id"], db)
            if not entity:
                raise institution_entity_not_found()
        
        # Set default values for minimal creation
        account_data.setdefault("account_type", "Checking")
        account_data.setdefault("is_primary", False)
        account_data.setdefault("is_archived", False)
        account_data.setdefault("status", Status.ACTIVE)
        
        log_info("Auto-populated minimal bank account fields")
    
    def _mask_account_number(self, account_number: str) -> str:
        """
        Mask account number for security (show only last 4 digits).
        
        Args:
            account_number: Full account number
            
        Returns:
            Masked account number
        """
        if len(account_number) <= 4:
            return "*" * len(account_number)
        
        return "*" * (len(account_number) - 4) + account_number[-4:]
    
    def _add_business_validation_notes(
        self, 
        bank_account: InstitutionBankAccountDTO, 
        validation_result: Dict[str, Any]
    ) -> None:
        """
        Add additional business rule validation notes.
        
        Args:
            bank_account: Bank account DTO
            validation_result: Validation result dictionary (modified in place)
        """
        # Check if account is archived
        if bank_account.is_archived:
            validation_result["validation_notes"].append("Account is archived")
        
        # Check account status
        if bank_account.status != Status.ACTIVE:
            validation_result["validation_notes"].append(f"Account status is {bank_account.status}")
        
        # Add routing number format notes
        routing = bank_account.routing_number
        if len(routing) != 9:
            validation_result["validation_notes"].append("Routing number should be 9 digits")
        
        # Add account number format notes
        account = bank_account.account_number
        if len(account) < 4:
            validation_result["validation_notes"].append("Account number should be at least 4 digits")
        
        # Add security note about masked display
        validation_result["security_note"] = "Account number is masked for security"


# Create service instance
bank_account_business_service = BankAccountBusinessService()
