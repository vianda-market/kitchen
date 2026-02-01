# app/routes/institution_bank_account.py
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
from uuid import UUID
from app.dto.models import InstitutionBankAccountDTO
from app.services.crud_service import (
    institution_bank_account_service,
    institution_entity_service,
    get_active_accounts,
)
from app.utils.db import db_read
from app.services.bank_account_service import bank_account_business_service
from app.schemas.institution_bank_account import (
    InstitutionBankAccountCreateSchema,
    InstitutionBankAccountUpdateSchema,
    InstitutionBankAccountResponseSchema,
    InstitutionBankAccountMinimalCreateSchema,
)
from app.schemas.consolidated_schemas import InstitutionBankAccountEnrichedResponseSchema
from app.services.entity_service import get_enriched_institution_bank_accounts
from fastapi import Query
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.utils.query_params import include_archived_query, institution_entity_filter, institution_filter
from app.utils.error_messages import bank_account_not_found, institution_entity_not_found
from app.services.error_handling import handle_business_operation
from app.security.institution_scope import InstitutionScope
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_BANK_ACCOUNT
import psycopg2.extensions

router = APIRouter(
    prefix="/institution-bank-accounts",
    tags=["Institution Bank Accounts"],
    dependencies=[Depends(oauth2_scheme)]
)


def _require_entity_access(
    institution_entity_id: UUID,
    db: psycopg2.extensions.connection,
    scope: InstitutionScope
):
    entity = institution_entity_service.get_by_id(institution_entity_id, db, scope=scope)
    if not entity:
        raise institution_entity_not_found()
    return entity


def _require_bank_account(
    bank_account_id: UUID,
    db: psycopg2.extensions.connection,
    scope: InstitutionScope
) -> InstitutionBankAccountDTO:
    bank_account = institution_bank_account_service.get_by_id(bank_account_id, db)
    if not bank_account:
        raise bank_account_not_found()

    if scope and not scope.is_global:
        _require_entity_access(bank_account.institution_entity_id, db, scope)

    return bank_account


def _list_accounts_for_scope(
    scope: InstitutionScope,
    db: psycopg2.extensions.connection
) -> List[InstitutionBankAccountDTO]:
    if scope.is_global:
        return institution_bank_account_service.get_all(db)

    if not scope.institution_id:
        return []

    try:
        institution_uuid = UUID(scope.institution_id)
    except ValueError:
        return []

    # Use explicit query for bank accounts by institution
    query = """
        SELECT iba.* FROM institution_bank_account iba
        JOIN institution_entity_info ie ON iba.institution_entity_id = ie.institution_entity_id
        WHERE ie.institution_id = %s AND iba.is_archived = FALSE
    """
    results = db_read(query, (str(institution_uuid),), connection=db)
    return [InstitutionBankAccountDTO(**row) for row in results]

# GET /institution-bank-accounts/{bank_account_id}?include_archived={...}
@router.get("/{bank_account_id}", response_model=InstitutionBankAccountResponseSchema)
def get_bank_account(
    bank_account_id: UUID,
    include_archived: bool = include_archived_query("bank accounts"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a bank account by ID with optional archived records"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)
    _ = include_archived  # Parameter retained for backward compatibility
    return _require_bank_account(bank_account_id, db, scope)

# GET /institution-bank-accounts/?include_archived={...}&institution_entity_id={...}&institution_id={...}
@router.get("/", response_model=List[InstitutionBankAccountResponseSchema])
def get_all_bank_accounts(
    include_archived: bool = include_archived_query("bank accounts"),
    institution_entity_id: Optional[UUID] = Query(None, description="Filter by institution entity ID"),
    institution_id: Optional[UUID] = Query(None, description="Filter by institution ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all bank accounts with optional filtering"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)

    def _get_bank_accounts():
        if institution_entity_id:
            _require_entity_access(institution_entity_id, db, scope)
            # Use explicit query for bank accounts by institution entity
            query = "SELECT * FROM institution_bank_account WHERE institution_entity_id = %s AND is_archived = FALSE"
            results = db_read(query, (str(institution_entity_id),), connection=db)
            bank_accounts = [InstitutionBankAccountDTO(**row) for row in results]
            log_info(f"Retrieved bank accounts for institution entity: {institution_entity_id}")
        elif institution_id:
            if scope.is_global or scope.matches(institution_id):
                # Use explicit query for bank accounts by institution
                query = """
                    SELECT iba.* FROM institution_bank_account iba
                    JOIN institution_entity_info ie ON iba.institution_entity_id = ie.institution_entity_id
                    WHERE ie.institution_id = %s AND iba.is_archived = FALSE
                """
                results = db_read(query, (str(institution_id),), connection=db)
                bank_accounts = [InstitutionBankAccountDTO(**row) for row in results]
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: institution mismatch")
            log_info(f"Retrieved bank accounts for institution: {institution_id}")
        else:
            bank_accounts = _list_accounts_for_scope(scope, db)
            log_info("Retrieved scoped bank accounts list")
        
        return bank_accounts
    
    return handle_business_operation(_get_bank_accounts, "bank account retrieval")

@router.get("/enriched/", response_model=List[InstitutionBankAccountEnrichedResponseSchema])
def get_enriched_institution_bank_accounts_endpoint(
    include_archived: bool = Query(False, description="Include archived accounts if true"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all institution bank accounts with enriched data (institution name, entity name, country).
    Returns an array of enriched institution bank account records.
    
    Scoping:
    - Employees: See all institution bank accounts
    - Suppliers: See bank accounts for entities in their institution
    - Customers: See bank accounts for entities in their institution (if applicable)"""
    
    def _get_enriched_accounts():
        scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)
        return get_enriched_institution_bank_accounts(
            db,
            scope=scope,
            include_archived=include_archived
        )
    
    return handle_business_operation(_get_enriched_accounts, "enriched institution bank accounts retrieval")

# GET /institution-bank-accounts/active/{institution_entity_id}
@router.get("/active/{institution_entity_id}", response_model=List[InstitutionBankAccountResponseSchema])
def get_active_bank_accounts(
    institution_entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all active bank accounts for a specific institution entity"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)
    _require_entity_access(institution_entity_id, db, scope)

    def _get_active_bank_accounts():
        bank_accounts = get_active_accounts(institution_entity_id, db, scope=scope)
        log_info(f"Retrieved active bank accounts for institution entity: {institution_entity_id}")
        return bank_accounts
    
    return handle_business_operation(_get_active_bank_accounts, "active bank account retrieval")

# POST /institution-bank-accounts/ – Create a new bank account
@router.post("/", response_model=InstitutionBankAccountResponseSchema, status_code=status.HTTP_201_CREATED)
def create_bank_account(
    bank_account_create: InstitutionBankAccountCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new bank account"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)

    def _create_bank_account():
        data = bank_account_create.dict()
        _require_entity_access(data["institution_entity_id"], db, scope)

        data["modified_by"] = current_user["user_id"]

        new_account = institution_bank_account_service.create(data, db, scope=scope)
        if not new_account:
            raise HTTPException(status_code=500, detail="Failed to create bank account")

        log_info(f"Created bank account {new_account.bank_account_id}")
        return new_account

    return handle_business_operation(
        _create_bank_account,
        "bank account creation",
        "Bank account created successfully"
    )


# POST /institution-bank-accounts/minimal – Create a bank account with minimal fields (auto-populate others)
@router.post("/minimal", response_model=InstitutionBankAccountResponseSchema, status_code=status.HTTP_201_CREATED)
def create_minimal_bank_account(
    bank_account_create: InstitutionBankAccountMinimalCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new minimal bank account"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)

    def _create_minimal_bank_account():
        data = bank_account_create.dict()
        entity = _require_entity_access(data["institution_entity_id"], db, scope)
        data["modified_by"] = current_user["user_id"]
        
        # Auto-populate address_id if not provided
        if not data.get("address_id"):
            data["address_id"] = entity.address_id
            log_info(f"Auto-populated address_id from institution entity: {data['address_id']}")
        
        new_bank_account = institution_bank_account_service.create(data, db, scope=scope)
        if not new_bank_account:
            raise HTTPException(status_code=500, detail="Failed to create bank account")
        
        log_info(f"Created minimal bank account: {new_bank_account.bank_account_id}")
        return new_bank_account
    
    return handle_business_operation(
        _create_minimal_bank_account,
        "minimal bank account creation",
        "Minimal bank account created successfully"
    )

# PUT /institution-bank-accounts/{bank_account_id} – Update an existing bank account
@router.put("/{bank_account_id}", response_model=InstitutionBankAccountResponseSchema)
def update_bank_account(
    bank_account_id: UUID,
    bank_account_update: InstitutionBankAccountUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an existing bank account"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)
    existing_account = _require_bank_account(bank_account_id, db, scope)

    def _update_bank_account():
        update_data = bank_account_update.dict(exclude_unset=True)
        if "institution_entity_id" in update_data:
            new_entity_id = update_data["institution_entity_id"]
            if new_entity_id != existing_account.institution_entity_id:
                _require_entity_access(new_entity_id, db, scope)

        update_data["modified_by"] = current_user["user_id"]

        updated = institution_bank_account_service.update(bank_account_id, update_data, db, scope=scope)
        if not updated:
            raise bank_account_not_found()
        log_info(f"Updated bank account {bank_account_id}")
        return updated

    return handle_business_operation(
        _update_bank_account,
        "bank account update",
        "Bank account updated successfully"
    )

# DELETE /institution-bank-accounts/{bank_account_id} – Delete (soft-delete) a bank account
@router.delete("/{bank_account_id}", response_model=dict)
def delete_bank_account(
    bank_account_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete a bank account"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)
    _require_bank_account(bank_account_id, db, scope)

    def _delete():
        success = institution_bank_account_service.soft_delete(
            bank_account_id,
            current_user["user_id"],
            db,
            scope=scope
        )
        if not success:
            raise bank_account_not_found()
        log_info(f"Deleted bank account {bank_account_id}")
        return {"detail": "Bank account deleted successfully"}

    return handle_business_operation(_delete, "bank account deletion")

# POST /institution-bank-accounts/{bank_account_id}/validate – Validate bank account details
@router.post("/{bank_account_id}/validate", response_model=dict)
def validate_bank_account(
    bank_account_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Validate the format of a bank account's routing and account numbers"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BANK_ACCOUNT, current_user)
    _require_bank_account(bank_account_id, db, scope)

    def _validate_bank_account():
        return bank_account_business_service.validate_bank_account(bank_account_id, db)
    
    return handle_business_operation(_validate_bank_account, "bank account validation") 