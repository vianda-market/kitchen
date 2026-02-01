# Service Consolidation Analysis - 25 Functions

**Created:** 2026-01-30  
**Status:** Analysis Complete - Ready for Implementation

## Executive Summary

Analyzed 25 standalone functions in `crud_service.py` to determine which should be consolidated into service classes. **Recommendation: Convert 19 functions, keep 6 as standalone utilities.**

---

## Categorization

### Category 1: HIGH PRIORITY - Clear Service Ownership (13 functions)

These functions operate on a single entity and have an existing service class.

#### A. Institution Bill Service (4 functions)

**Service Instance:** `institution_bill_service = CRUDService(...)`

| Line | Function | Current Purpose | Should Be Method? | Reasoning |
|------|----------|-----------------|-------------------|-----------|
| 973 | `get_by_entity_and_period()` | Bills by entity + date range | ✅ YES | Entity-specific query |
| 984 | `get_pending_bills()` | Get all pending bills | ✅ YES | Entity-specific filter |
| 990 | `mark_paid()` | Mark bill as paid | ✅ YES | Entity state management |
| 1018 | `get_by_institution_and_period()` | Bills by institution + date | ✅ YES | Entity-specific query |

**Why Consolidate:**
- All operate on `institution_bill_info` table
- Part of bill lifecycle (create → pending → paid)
- Service already exists, just missing these methods
- Improves discoverability: `institution_bill_service.mark_paid()`

**Proposed Service Methods:**
```python
class CRUDService:
    # Add to institution_bill_service instance:
    
    def get_by_entity_and_period(
        self, entity_id: UUID, period_start: datetime, 
        period_end: datetime, db
    ) -> Optional[T]:
        """Get bill for specific entity and period"""
        
    def get_pending(self, db) -> List[T]:
        """Get all pending bills"""
        
    def mark_paid(
        self, bill_id: UUID, payment_id: UUID, 
        modified_by: UUID, db
    ) -> bool:
        """Mark bill as paid"""
        
    def get_by_institution_and_period(
        self, institution_id: UUID, period_start: datetime,
        period_end: datetime, db
    ) -> List[T]:
        """Get bills by institution and period"""
```

---

#### B. Institution Payment Attempt Service (4 functions)

**Service Instance:** `institution_payment_attempt_service = CRUDService(...)`

| Line | Function | Current Purpose | Should Be Method? | Reasoning |
|------|----------|-----------------|-------------------|-----------|
| 1402 | `get_by_institution_bill()` | Attempts by bill | ✅ YES | Entity-specific query |
| 1430 | `get_pending_by_institution_entity()` | Pending by entity | ✅ YES | Entity-specific filter |
| 1446 | `mark_complete()` | Mark attempt complete | ✅ YES | Entity state management |
| 1456 | `mark_failed()` | Mark attempt failed | ✅ YES | Entity state management |
| 1466 | `undelete()` | Unarchive attempt | ✅ YES | Entity state management |

**Why Consolidate:**
- All operate on `institution_payment_attempt_info` table
- Part of payment attempt lifecycle
- State transitions (pending → complete/failed)
- Service already exists

**Proposed Service Methods:**
```python
class CRUDService:
    # Add to institution_payment_attempt_service instance:
    
    def get_by_institution_bill(
        self, bill_id: UUID, db, scope=None
    ) -> List[T]:
        """Get payment attempts for a bill"""
        
    def get_pending_by_institution_entity(
        self, entity_id: UUID, db
    ) -> List[T]:
        """Get pending attempts for entity"""
        
    def mark_complete(self, payment_id: UUID, db) -> bool:
        """Mark payment attempt as complete"""
        
    def mark_failed(self, payment_id: UUID, db) -> bool:
        """Mark payment attempt as failed"""
        
    def undelete(self, payment_id: UUID, db) -> bool:
        """Restore archived payment attempt"""
```

---

#### C. Restaurant Balance Service (5 functions)

**Service Instance:** `restaurant_balance_service = CRUDService(...)`

| Line | Function | Current Purpose | Should Be Method? | Reasoning |
|------|----------|-----------------|-------------------|-----------|
| 1477 | `get_by_restaurant()` | Balance by restaurant | ✅ YES | Entity-specific query |
| 1483 | `update_balance_with_monetary_amount()` | Update with currency | ✅ YES | Entity state update |
| 1497 | `get_current_balance_event_id()` | Current balance event | ✅ YES | Entity-specific query |
| 1510 | `reset_restaurant_balance()` | Reset balance | ✅ YES | Entity state reset |
| 1540 | `create_restaurant_balance_record()` | Initialize balance | ✅ YES | Entity initialization |

**Why Consolidate:**
- All operate on `restaurant_balance` table
- Balance management operations
- Should be grouped together
- Makes API clearer: `restaurant_balance_service.reset_balance()`

**Proposed Service Methods:**
```python
class CRUDService:
    # Add to restaurant_balance_service instance:
    
    def get_by_restaurant(
        self, restaurant_id: UUID, db
    ) -> Optional[T]:
        """Get balance for restaurant"""
        
    def update_with_monetary_amount(
        self, restaurant_id: UUID, amount: float, 
        currency_code: str, db
    ) -> bool:
        """Update balance with currency conversion"""
        
    def get_current_event_id(
        self, restaurant_id: UUID, db
    ) -> Optional[UUID]:
        """Get ID of current balance event"""
        
    def reset_balance(
        self, restaurant_id: UUID, db, commit=True
    ) -> bool:
        """Reset restaurant balance to zero"""
        
    def create_balance_record(
        self, restaurant_id: UUID, credit_currency_id: UUID,
        currency_code: str, modified_by: UUID, db, commit=True
    ) -> bool:
        """Initialize balance record for new restaurant"""
```

---

### Category 2: MEDIUM PRIORITY - Partial Consolidation (6 functions)

These could be consolidated but have some cross-entity aspects.

#### D. Restaurant Transaction Helpers (4 functions)

**Service Instance:** `restaurant_transaction_service = CRUDService(...)`

| Line | Function | Current Purpose | Should Be Method? | Reasoning |
|------|----------|-----------------|-------------------|-----------|
| 1702 | `mark_collected()` | Mark transaction collected | 🟡 MAYBE | State management, but used in complex flows |
| 1714 | `update_final_amount()` | Update transaction amount | ✅ YES | Simple entity update |
| 1725 | `update_transaction_arrival_time()` | Update arrival time | ✅ YES | Simple entity update |
| 1271 | `get_by_plate_selection_id()` | Transaction by selection | ✅ YES | Entity-specific query |

**Why Consolidate (Partial):**
- All operate on `restaurant_transaction` table
- Simple updates fit service pattern
- `mark_collected()` is used in complex business logic (might stay standalone)

**Proposed Service Methods:**
```python
class CRUDService:
    # Add to restaurant_transaction_service instance:
    
    def get_by_plate_selection(
        self, plate_selection_id: UUID, db
    ) -> Optional[T]:
        """Get transaction by plate selection"""
        
    def update_final_amount(
        self, transaction_id: UUID, final_amount: float,
        modified_by: UUID, db
    ) -> bool:
        """Update final transaction amount"""
        
    def update_arrival_time(
        self, transaction_id: UUID, arrival_time: datetime,
        modified_by: UUID, db
    ) -> bool:
        """Update customer arrival time"""
        
    def mark_collected(
        self, transaction_id: UUID, collected_timestamp: datetime,
        modified_by: UUID, db
    ) -> bool:
        """Mark transaction as collected"""
```

---

#### E. Other Entity-Specific Queries (2 functions)

| Line | Function | Entity | Should Be Method? | Reasoning |
|------|----------|--------|-------------------|-----------|
| 1129 | `get_by_restaurant_id()` | QR Code | ✅ YES | Add to `qr_code_service` |
| 1143 | `get_by_user_id()` | Subscription | ✅ YES | Add to `subscription_service` |
| 1379 | `get_by_payment_id()` | Client Bill | ✅ YES | Add to `client_bill_service` |
| 1061 | `get_by_code()` | Credit Currency | ✅ YES | Add to `credit_currency_service` |
| 1625 | `get_by_restaurant_and_day()` | Kitchen Days | ✅ YES | Add to related service |
| 1759 | `get_by_address_id()` | Geolocation | ✅ YES | Add to `geolocation_service` |

**Why Consolidate:**
- Each has a corresponding service instance
- Simple entity-specific queries
- Improves API consistency

---

### Category 3: KEEP STANDALONE - Cross-Entity Utilities (6 functions)

These should remain standalone as they're cross-entity or pure utilities.

| Line | Function | Keep Standalone? | Reasoning |
|------|----------|------------------|-----------|
| 961 | `get_institution_id_by_restaurant()` | ✅ YES | Cross-entity lookup (restaurant → institution) |
| 967 | `get_institution_entity_by_institution()` | ✅ YES | Cross-entity lookup (institution → entity) |
| 1118 | `validate_routing_number()` | ✅ YES | Pure validation utility, no database |
| 1123 | `validate_account_number()` | ✅ YES | Pure validation utility, no database |
| 1618 | `is_holiday()` | ✅ YES | Could add to `national_holiday_service`, but ok standalone |
| 1753 | `find_matching_preferences()` | ✅ YES | Complex matching logic across entities |

**Why Keep Standalone:**
- Cross-entity relationships
- Pure validation (no state)
- Complex queries spanning multiple entities
- Used in many different contexts

---

### Category 4: BUSINESS LOGIC - Keep Standalone (6 functions)

Complex multi-step operations that span multiple services.

| Line | Function | Keep Standalone? | Reasoning |
|------|----------|-----------------|-----------|
| 1149 | `update_balance()` | ✅ YES | Complex subscription balance logic |
| 1180 | `mark_plate_selection_complete()` | ✅ YES | Multi-entity transaction |
| 1213 | `create_with_conservative_balance_update()` | ✅ YES | Atomic create + balance update |
| 1277 | `update_balance_on_transaction_creation()` | ✅ YES | Cross-service business rule |
| 1308 | `update_balance_on_arrival()` | ✅ YES | Cross-service business rule |
| 1338 | `mark_collected_with_balance_update()` | ✅ YES | Atomic collection + balance update |

**Why Keep Standalone:**
- Coordinate multiple services
- Business logic not tied to single entity
- Transaction boundaries across entities
- Complex error handling

---

## Summary by Action

### ✅ Convert to Service Methods: 19 functions

| Service | Functions to Add | Priority |
|---------|------------------|----------|
| `institution_bill_service` | 4 methods | HIGH |
| `institution_payment_attempt_service` | 5 methods (incl. renamed one) | HIGH |
| `restaurant_balance_service` | 5 methods | HIGH |
| `restaurant_transaction_service` | 4 methods | MEDIUM |
| `qr_code_service` | 1 method | LOW |
| `subscription_service` | 1 method | LOW |
| `client_bill_service` | 1 method | LOW |
| `credit_currency_service` | 1 method | LOW |
| `geolocation_service` | 1 method | LOW |

### ✅ Keep Standalone: 12 functions

- **Cross-entity lookups:** 2 functions
- **Pure utilities:** 2 functions
- **Complex business logic:** 6 functions
- **Other standalone:** 2 functions

---

## Benefits of Consolidation

### 1. Improved Discoverability
```python
# Before: Where is mark_paid function?
mark_paid(bill_id, payment_id, modified_by, db)

# After: Obviously in the bill service!
institution_bill_service.mark_paid(bill_id, payment_id, modified_by, db)
```

### 2. Better IDE Support
- Autocomplete shows all available methods
- Jump to definition works correctly
- Easier to find related operations

### 3. Consistent API
```python
# All services follow same pattern
service.get_by_id()
service.get_all()
service.create()
service.update()
service.mark_paid()      # ← New method
service.mark_complete()  # ← New method
```

### 4. Easier Testing
```python
# Mock the service, not individual functions
mock_bill_service = Mock(spec=CRUDService)
mock_bill_service.mark_paid.return_value = True
```

### 5. Clear Ownership
- Each entity's operations in one place
- Easy to see all available operations
- Natural place for new methods

---

## Risks and Mitigations

### Risk 1: Breaking Changes
**Mitigation:** Keep old functions as wrappers initially
```python
# Old function becomes wrapper
def mark_paid(bill_id, payment_id, modified_by, db):
    """DEPRECATED: Use institution_bill_service.mark_paid() instead"""
    return institution_bill_service.mark_paid(bill_id, payment_id, modified_by, db)
```

### Risk 2: Method Namespace Pollution
**Mitigation:** Only add methods that truly belong to that entity

### Risk 3: Testing Complexity
**Mitigation:** Update tests incrementally, verify behavior unchanged

---

## Non-Goals

**We are NOT:**
- ❌ Changing any business logic
- ❌ Modifying function signatures (initially)
- ❌ Refactoring complex operations
- ❌ Combining multiple functions

**We ARE:**
- ✅ Moving functions to their natural home
- ✅ Improving code organization
- ✅ Maintaining backward compatibility (initially)
- ✅ Making code more discoverable

---

## Next Steps

See [SERVICE_CONSOLIDATION_ROADMAP.md](./SERVICE_CONSOLIDATION_ROADMAP.md) for implementation plan.

---

## Appendix: Function Reference

### Functions to Convert (19)

```
Institution Bill Service:
  ✓ get_by_entity_and_period (973)
  ✓ get_pending_bills (984)
  ✓ mark_paid (990)
  ✓ get_by_institution_and_period (1018)

Institution Payment Attempt Service:
  ✓ get_by_institution_bill (1402)
  ✓ get_pending_by_institution_entity (1430)
  ✓ mark_complete (1446)
  ✓ mark_failed (1456)
  ✓ undelete (1466)

Restaurant Balance Service:
  ✓ get_by_restaurant (1477)
  ✓ update_balance_with_monetary_amount (1483)
  ✓ get_current_balance_event_id (1497)
  ✓ reset_restaurant_balance (1510)
  ✓ create_restaurant_balance_record (1540)

Restaurant Transaction Service:
  ✓ get_by_plate_selection_id (1271)
  ✓ mark_collected (1702)
  ✓ update_final_amount (1714)
  ✓ update_transaction_arrival_time (1725)

Other Services:
  ✓ get_by_restaurant_id → qr_code_service (1129)
  ✓ get_by_user_id → subscription_service (1143)
  ✓ get_by_payment_id → client_bill_service (1379)
  ✓ get_by_code → credit_currency_service (1061)
  ✓ get_by_address_id → geolocation_service (1759)
  ✓ get_by_restaurant_and_day → kitchen_days_service (1625)
```

### Functions to Keep Standalone (12)

```
Cross-Entity Lookups:
  • get_institution_id_by_restaurant (961)
  • get_institution_entity_by_institution (967)

Pure Utilities:
  • validate_routing_number (1118)
  • validate_account_number (1123)

Complex Business Logic:
  • update_balance (1149)
  • mark_plate_selection_complete (1180)
  • create_with_conservative_balance_update (1213)
  • update_balance_on_transaction_creation (1277)
  • update_balance_on_arrival (1308)
  • mark_collected_with_balance_update (1338)

Other Standalone:
  • is_holiday (1618)
  • find_matching_preferences (1753)
```
