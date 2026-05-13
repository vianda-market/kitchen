# Function Cleanup Action Plan

**Created:** 2026-01-30  
**Priority:** High  
**Estimated Effort:** 4-6 hours

## Immediate Actions Required

### 1. Remove Confirmed Duplicates ⚠️ CRITICAL

#### Duplicate Functions to Remove:

| Function | Lines | Action |
|----------|-------|--------|
| `get_all_by_user_address_city()` | 1031, 1632 | ✅ Keep 1031, remove 1632 |
| `get_all_active_for_today_by_user_address_city()` | 1043, 1652 | ✅ Keep 1043, remove 1652 |
| `get_by_vianda_selection_id()` | 1271, 1696 | ✅ Keep 1271, remove 1696 |
| `mark_collected()` / `mark_transaction_as_collected()` | 1702, 1736 | ✅ Keep 1702, remove 1736 |

**Steps:**
1. Search codebase for callers of functions to be removed
2. Update callers to use the kept version
3. Remove duplicate functions
4. Test affected endpoints

---

### 2. Fix Naming Conflicts (High Priority)

#### Functions with Same Name, Different Entities:

**A. `get_by_institution_entity()`**
- Line 1068: Returns `List[InstitutionBankAccountDTO]` ✅ FIXED (workaround)
- Line 1386: Returns `List[InstitutionPaymentAttemptDTO]` 🔄 TODO

**Action:**
```python
# Rename line 1386 to:
def get_payment_attempts_by_institution_entity(
    institution_entity_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None
) -> List[InstitutionPaymentAttemptDTO]:
    # ... existing implementation
```

**B. `get_by_institution()`**
- Line 1084: Returns `List[InstitutionBankAccountDTO]` ✅ FIXED (workaround)
- Line 1611: Returns `List[InstitutionEntityDTO]` 🔄 TODO

**Action:**
```python
# Rename line 1611 to:
def get_institution_entities_by_institution(
    institution_id: UUID,
    db: psycopg2.extensions.connection
) -> List[InstitutionEntityDTO]:
    # ... existing implementation
```

---

### 3. Consolidate into Service Classes (Medium Priority)

#### Add Methods to Existing Services:

**Institution Payment Attempt Service:**
```python
class CRUDService:
    # Add methods:
    def get_by_institution_entity(self, institution_entity_id, db, scope=None)
    def get_by_institution_bill(self, institution_bill_id, db, scope=None)
    def get_pending_by_institution_entity(self, institution_entity_id, db)
    def mark_complete(self, payment_id, db)
    def mark_failed(self, payment_id, db)
    def undelete(self, payment_id, db)
```

**Institution Bill Service:**
```python
class CRUDService:
    # Add methods:
    def get_by_entity_and_period(self, entity_id, period_start, period_end, db)
    def get_pending_bills(self, db)
    def mark_paid(self, bill_id, payment_id, modified_by, db)
    def get_by_institution_and_period(self, institution_id, period_start, period_end, db)
```

**Restaurant Balance Service:**
```python
class CRUDService:
    # Add methods:
    def get_by_restaurant(self, restaurant_id, db)
    def get_current_balance_event_id(self, restaurant_id, db)
    def update_balance_with_monetary_amount(self, restaurant_id, amount, currency_code, db)
    def reset_balance(self, restaurant_id, db, commit=True)
    def create_balance_record(self, restaurant_id, credit_currency_id, currency_code, modified_by, db, commit=True)
```

**Restaurant Transaction Service:**
```python
class CRUDService:
    # Add methods:
    def get_by_vianda_selection_id(self, vianda_selection_id, db)
    def mark_collected(self, transaction_id, collected_timestamp, modified_by, db)
    def update_final_amount(self, transaction_id, final_amount, modified_by, db)
    def update_arrival_time(self, transaction_id, arrival_time, modified_by, db)
```

---

## Implementation Order

### Phase 1: Critical Fixes (Week 1)
- [x] Fix bank account naming conflicts ✅ DONE
- [ ] Remove 4 confirmed duplicate functions
- [ ] Rename payment attempt `get_by_institution_entity()` 
- [ ] Rename institution entity `get_by_institution()`
- [ ] Update all callers
- [ ] Test end-to-end

### Phase 2: Service Consolidation (Week 2)
- [ ] Add methods to `institution_payment_attempt_service`
- [ ] Add methods to `institution_bill_service`
- [ ] Add methods to `restaurant_balance_service`
- [ ] Add methods to `restaurant_transaction_service`
- [ ] Update callers to use service methods
- [ ] Remove redundant standalone functions

### Phase 3: Documentation (Week 3)
- [ ] Update API documentation
- [ ] Document service class patterns
- [ ] Create coding guidelines
- [ ] Add examples to developer docs

---

## Testing Checklist

For each change:
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Postman collection runs successfully
- [ ] No new linter warnings
- [ ] Performance not degraded

---

## Risk Assessment

| Change | Risk Level | Mitigation |
|--------|------------|------------|
| Remove duplicates | 🟡 Medium | Search all callers first, update tests |
| Rename functions | 🟢 Low | Clear naming reduces confusion |
| Add service methods | 🟢 Low | Non-breaking, adds new paths |
| Remove standalone functions | 🟡 Medium | Do after service methods proven stable |

---

## Success Criteria

1. ✅ No naming conflicts in `crud_service.py`
2. ✅ No duplicate function definitions
3. ✅ All entity operations use service classes where applicable
4. ✅ Standalone functions only for cross-entity or unique utilities
5. ✅ All tests passing
6. ✅ Postman collections working

---

## Related Files

- [Code Organization Cleanup](./CODE_ORGANIZATION_CLEANUP.md) - Full audit
- [Service Architecture](../services/SERVICE_ARCHITECTURE.md) - Patterns
- [Testing Strategy](../testing/TESTING_ROADMAP.md) - Testing approach
