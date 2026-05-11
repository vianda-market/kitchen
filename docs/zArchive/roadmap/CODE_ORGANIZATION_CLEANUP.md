# Code Organization Cleanup Roadmap

**Last Updated:** 2026-01-30  
**Status:** In Progress

## Overview

This document tracks the consolidation of redundant standalone functions into class-based services to improve code maintainability, reduce naming conflicts, and establish consistent patterns.

---

## Current Service Classes

### 1. CRUDService (Generic Base Class)
**Location:** `app/services/crud_service.py`

**Purpose:** Generic CRUD operations for database entities

**Service Instances:**
- `institution_bank_account_service` - Bank account operations
- `institution_payment_attempt_service` - Payment attempt operations  
- `institution_entity_service` - Institution entity operations
- `institution_service` - Institution operations
- `user_service` - User operations
- `restaurant_service` - Restaurant operations
- `product_service` - Product operations
- `plan_service` - Plan operations
- `credit_currency_service` - Credit currency operations
- `address_service` - Address operations
- `geolocation_service` - Geolocation operations
- `qr_code_service` - QR code operations
- `payment_method_service` - Payment method operations
- `plate_service` - Plate operations
- `employer_service` - Employer operations
- `restaurant_balance_service` - Restaurant balance operations
- `restaurant_transaction_service` - Restaurant transaction operations
- `national_holiday_service` - National holiday operations
- `restaurant_holiday_service` - Restaurant holiday operations
- `subscription_service` - Subscription operations
- `client_bill_service` - Client bill operations
- `institution_bill_service` - Institution bill operations
- `plate_selection_service` - Plate selection operations
- `plate_pickup_service` - Plate pickup operations
- `discretionary_service` - Discretionary credit operations

**Common Methods:**
- `get_by_id(record_id, db, scope=None)`
- `get_all(db, limit=None, scope=None, include_archived=False)`
- `create(data, db, scope=None)`
- `update(record_id, data, db, scope=None)`
- `soft_delete(record_id, modified_by, db, scope=None)`

### 2. EnrichedService (Enhanced Query Class)
**Location:** `app/services/enriched_service.py`

**Purpose:** Complex queries with JOINs for enriched data

**Service Instances:**
- `_user_enriched_service` - Users with institution/role details
- `_institution_entity_enriched_service` - Entities with institution/address
- `_address_enriched_service` - Addresses with user/institution context

**Methods:**
- `get_enriched(db, select_fields, joins, scope, include_archived)`
- `get_enriched_by_id(entity_id, db, select_fields, joins, scope, include_archived)`

### 3. Specialized Service Classes
**Location:** Various in `app/services/`

- `BankAccountBusinessService` - Business logic for bank accounts
- `CreditValidationService` - Credit validation logic
- `EntityScopingService` - Security scoping for entities
- `InstitutionScope` - Institution-level access control

---

## Redundant Standalone Functions

### ✅ FIXED: Institution Bank Account Functions

**Problem:** Naming collision between bank account and payment attempt functions

**Redundant Functions (REMOVED):**
- ❌ `get_by_institution_entity()` (line 1068) - FOR BANK ACCOUNTS
- ❌ `get_by_institution()` (line 1084) - FOR BANK ACCOUNTS

**Replaced With:**
- ✅ Direct SQL queries in route (temporary workaround)
- 🔄 TODO: Add methods to `CRUDService` class if needed

**Files Modified:**
- `app/routes/institution_bank_account.py` - Uses explicit queries
- `app/routes/crud_routes.py` - Disabled auto-generated route

---

### 🔄 TO REVIEW: Institution Payment Attempt Functions

**Location:** `app/services/crud_service.py`

**Standalone Functions:**
- `get_by_institution_entity()` (line 1386) - FOR PAYMENT ATTEMPTS
- Should be moved to `institution_payment_attempt_service` methods

**Action Required:**
1. Add `get_by_institution_entity()` method to `CRUDService` class
2. Remove standalone function
3. Update all callers to use service instance

---

### 🔄 TO REVIEW: Institution Entity Functions

**Location:** `app/services/crud_service.py`

**Standalone Functions:**
- `get_by_institution()` (line 1611) - FOR INSTITUTION ENTITIES
- Returns `List[InstitutionEntityDTO]`

**Service Instance Available:**
- `institution_entity_service` (CRUDService instance)

**Action Required:**
1. Check if `get_by_institution()` is needed as a method
2. Remove standalone function if redundant
3. Update callers

---

### 🔄 TO REVIEW: All Standalone Functions (49 total)

**Location:** `app/services/crud_service.py`

#### Category A: Redundant with Service Classes (HIGH PRIORITY)

| Line | Function | Entity | Service Available | Action |
|------|----------|--------|-------------------|--------|
| 1068 | `get_by_institution_entity()` | Bank Account | ✅ `institution_bank_account_service` | ✅ REMOVED (workaround) |
| 1084 | `get_by_institution()` | Bank Account | ✅ `institution_bank_account_service` | ✅ REMOVED (workaround) |
| 1386 | `get_by_institution_entity()` | Payment Attempt | ✅ `institution_payment_attempt_service` | 🔄 ADD METHOD & REMOVE |
| 1611 | `get_by_institution()` | Institution Entity | ✅ `institution_entity_service` | 🔄 ADD METHOD & REMOVE |
| 1102 | `get_active_accounts()` | Bank Account | ✅ `institution_bank_account_service` | 🔄 ADD METHOD & REMOVE |

#### Category B: Lookup Utilities (Cross-Entity)

| Line | Function | Purpose | Keep/Consolidate |
|------|----------|---------|------------------|
| 961 | `get_institution_id_by_restaurant()` | Get parent institution | ✅ KEEP (cross-entity lookup) |
| 967 | `get_institution_entity_by_institution()` | Get entity from institution | ✅ KEEP (cross-entity lookup) |
| 1061 | `get_by_code()` | Get currency by code | 🔄 CONSIDER: Add to `credit_currency_service` |
| 1129 | `get_by_restaurant_id()` | Get QR by restaurant | 🔄 CONSIDER: Add to `qr_code_service` |
| 1143 | `get_by_user_id()` | Get subscription by user | 🔄 CONSIDER: Add to `subscription_service` |
| 1759 | `get_by_address_id()` | Get geolocation by address | 🔄 CONSIDER: Add to `geolocation_service` |

#### Category C: Business Logic (Transactions/Complex Operations)

| Line | Function | Purpose | Keep/Consolidate |
|------|----------|---------|------------------|
| 1149 | `update_balance()` | Update subscription balance | ✅ KEEP (complex business logic) |
| 1180 | `mark_plate_selection_complete()` | Complete selection | ✅ KEEP (multi-step business logic) |
| 1213 | `create_with_conservative_balance_update()` | Create + balance update | ✅ KEEP (atomic operation) |
| 1277 | `update_balance_on_transaction_creation()` | Balance on create | ✅ KEEP (business rule) |
| 1308 | `update_balance_on_arrival()` | Balance on arrival | ✅ KEEP (business rule) |
| 1338 | `mark_collected_with_balance_update()` | Collect + balance | ✅ KEEP (atomic operation) |
| 1483 | `update_balance_with_monetary_amount()` | Balance with currency | ✅ KEEP (business rule) |
| 1510 | `reset_restaurant_balance()` | Reset balance | ✅ KEEP (complex operation) |
| 1540 | `create_restaurant_balance_record()` | Init balance record | ✅ KEEP (initialization logic) |

#### Category D: Validation Utilities

| Line | Function | Purpose | Keep/Consolidate |
|------|----------|---------|------------------|
| 1118 | `validate_routing_number()` | Routing number validation | ✅ KEEP (pure utility) |
| 1123 | `validate_account_number()` | Account number validation | ✅ KEEP (pure utility) |
| 1618 | `is_holiday()` | Check if date is holiday | 🔄 CONSIDER: Add to `national_holiday_service` |

#### Category E: Query Helpers (By Specific Criteria)

| Line | Function | Purpose | Keep/Consolidate |
|------|----------|---------|------------------|
| 973 | `get_by_entity_and_period()` | Bills by entity/period | ✅ KEEP (complex query) |
| 984 | `get_pending_bills()` | Get pending bills | 🔄 CONSIDER: Add to `institution_bill_service` |
| 990 | `mark_paid()` | Mark bill as paid | 🔄 CONSIDER: Add to `institution_bill_service` |
| 1018 | `get_by_institution_and_period()` | Bills by institution/period | 🔄 CONSIDER: Add to `institution_bill_service` |
| 1031 | `get_all_by_user_address_city()` | Plates by user location | ✅ KEEP (complex spatial query) |
| 1043 | `get_all_active_for_today_by_user_address_city()` | Active plates by location/date | ✅ KEEP (complex query) |
| 1136 | `get_all_by_user()` | Plate selections by user | 🔄 CONSIDER: Add to `plate_selection_service` |
| 1271 | `get_by_plate_selection_id()` | Transaction by selection | 🔄 CONSIDER: Add to `restaurant_transaction_service` |
| 1379 | `get_by_payment_id()` | Bill by payment | 🔄 CONSIDER: Add to `client_bill_service` |
| 1402 | `get_by_institution_bill()` | Payment attempts by bill | 🔄 CONSIDER: Add to `institution_payment_attempt_service` |
| 1430 | `get_pending_by_institution_entity()` | Pending payments by entity | 🔄 CONSIDER: Add to `institution_payment_attempt_service` |
| 1477 | `get_by_restaurant()` | Balance by restaurant | 🔄 CONSIDER: Add to `restaurant_balance_service` |
| 1497 | `get_current_balance_event_id()` | Current balance event | 🔄 CONSIDER: Add to `restaurant_balance_service` |
| 1625 | `get_by_restaurant_and_day()` | Kitchen days by restaurant/day | 🔄 CONSIDER: Add to related service |
| 1632 | `get_all_by_user_address_city()` | Plates by location (duplicate?) | ⚠️ CHECK: Duplicate of line 1031? |
| 1652 | `get_all_active_for_today_by_user_address_city()` | Active plates (duplicate?) | ⚠️ CHECK: Duplicate of line 1043? |
| 1696 | `get_by_plate_selection_id()` | Transaction by selection (duplicate?) | ⚠️ CHECK: Duplicate of line 1271? |
| 1753 | `find_matching_preferences()` | Find pickup preferences | ✅ KEEP (complex matching logic) |
| 1771 | `get_plates_by_credit_currency_id()` | Plates by currency | ✅ KEEP (specific query) |

#### Category F: State Management Helpers

| Line | Function | Purpose | Keep/Consolidate |
|------|----------|---------|------------------|
| 1446 | `mark_complete()` | Mark payment complete | 🔄 CONSIDER: Add to `institution_payment_attempt_service` |
| 1456 | `mark_failed()` | Mark payment failed | 🔄 CONSIDER: Add to `institution_payment_attempt_service` |
| 1466 | `undelete()` | Undelete payment | 🔄 CONSIDER: Add to `institution_payment_attempt_service` |
| 1702 | `mark_collected()` | Mark transaction collected | 🔄 CONSIDER: Add to `restaurant_transaction_service` |
| 1714 | `update_final_amount()` | Update transaction amount | 🔄 CONSIDER: Add to `restaurant_transaction_service` |
| 1725 | `update_transaction_arrival_time()` | Update arrival time | 🔄 CONSIDER: Add to `restaurant_transaction_service` |
| 1736 | `mark_transaction_as_collected()` | Mark collected (duplicate?) | ⚠️ CHECK: Duplicate of line 1702? |

### Summary by Action

- **✅ Already Fixed:** 2 functions (bank account conflicts)
- **🔄 High Priority (Redundant):** 3 functions with existing services
- **🔄 Consider Adding to Services:** 25 functions (can improve organization)
- **✅ Keep Standalone:** 15 functions (unique business logic or cross-entity)
- **⚠️ Check for Duplicates:** 4 potential duplicate functions

---

## Cleanup Strategy

### Phase 1: Remove Immediate Duplicates ✅ DONE
- [x] Fixed bank account function conflicts
- [x] Disabled conflicting auto-generated routes

### Phase 2: Audit All Standalone Functions 🔄 IN PROGRESS
- [ ] List all standalone functions in `crud_service.py`
- [ ] Map each to corresponding service class (if exists)
- [ ] Identify truly unique utilities vs duplicates

### Phase 3: Consolidate or Rename 📋 PLANNED
- [ ] Add missing methods to service classes
- [ ] Remove redundant standalone functions
- [ ] Rename remaining standalone functions for clarity
- [ ] Update all callers

### Phase 4: Establish Naming Convention 📋 PLANNED
- [ ] Service class methods: `service_instance.verb_object()`
- [ ] Standalone utilities: `verb_object_by_context()` (descriptive)
- [ ] Document when to use each pattern

---

## Benefits of Cleanup

1. **Eliminate naming conflicts** - No more duplicate function names
2. **Consistent patterns** - Clear when to use service vs standalone
3. **Better IDE support** - Autocomplete works correctly
4. **Easier testing** - Service instances are easier to mock
5. **Clearer ownership** - Each entity has one authoritative service

---

## Guidelines Going Forward

### Use Service Classes When:
- Operating on a specific database table/entity
- Need to share configuration across operations
- Part of standard CRUD operations

### Use Standalone Functions When:
- Cross-entity utilities (e.g., `get_institution_id_by_restaurant`)
- Pure business logic with no direct DB access
- Complex queries that don't fit CRUD pattern

### Naming Convention:
- **Service methods:** `service.get_by_parent()`, `service.get_active()`
- **Standalone utilities:** `get_{entity}_by_{context}()`
- **Be specific:** Avoid generic names like `get_by_institution()`

---

## Related Documentation

- [Database Schema](../database/SCHEMA.md)
- [Service Architecture](../services/SERVICE_ARCHITECTURE.md)
- [Testing Strategy](../testing/TESTING_ROADMAP.md)
