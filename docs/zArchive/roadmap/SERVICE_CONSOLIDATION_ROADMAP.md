# Service Consolidation Implementation Roadmap

**Created:** 2026-01-30  
**Status:** Ready for Implementation  
**Dependencies:** [SERVICE_CONSOLIDATION_ANALYSIS.md](./SERVICE_CONSOLIDATION_ANALYSIS.md)

## Executive Summary

**Goal:** Consolidate 19 standalone functions into their appropriate service classes to improve code organization and discoverability.

**Timeline:** 3 phases over 3-5 days  
**Breaking Changes:** None (using deprecation wrappers)  
**Testing Required:** Unit tests for each converted function

---

## Implementation Strategy

### Three-Phase Approach

```
Phase 1: HIGH PRIORITY (13 functions)
  ├── Institution Bill Service (4 methods)
  ├── Payment Attempt Service (5 methods)
  └── Restaurant Balance Service (5 methods)
  
Phase 2: MEDIUM PRIORITY (4 functions)
  └── Restaurant Transaction Service (4 methods)
  
Phase 3: LOW PRIORITY (2 functions)
  ├── QR Code Service (1 method)
  ├── Subscription Service (1 method)
  ├── Client Bill Service (1 method)
  ├── Credit Currency Service (1 method)
  └── Geolocation Service (1 method)
```

---

## Phase 1: Core Services (HIGH PRIORITY)

**Estimated Time:** 2-3 days  
**Functions:** 13  
**Risk:** Medium (these are used in billing flows)

### Step 1A: Institution Bill Service

**Files to Modify:**
- `app/services/crud_service.py` (add methods, keep wrappers)
- Caller files (TBD after grep search)
- Tests (create/update)

**Methods to Add:**

```python
# In CRUDService class, used by institution_bill_service instance

def get_by_entity_and_period(
    self, 
    entity_id: UUID, 
    period_start: datetime, 
    period_end: datetime, 
    db: psycopg2.extensions.connection
) -> Optional[T]:
    """Get bill for specific entity and billing period
    
    Args:
        entity_id: Institution entity UUID
        period_start: Start of billing period
        period_end: End of billing period
        db: Database connection
        
    Returns:
        Bill DTO if found, None otherwise
    """
    query = f"""
        SELECT * FROM {self.table_name}
        WHERE institution_entity_id = %s
        AND period_start = %s
        AND period_end = %s
        AND is_archived = FALSE
    """
    result = db_read(query, (str(entity_id), period_start, period_end), 
                     connection=db, fetch_one=True)
    return self.dto_class(**result) if result else None


def get_pending(self, db: psycopg2.extensions.connection) -> List[T]:
    """Get all pending bills
    
    Returns:
        List of bills with status 'Pending'
    """
    query = f"""
        SELECT * FROM {self.table_name}
        WHERE status = 'Pending'
        AND is_archived = FALSE
        ORDER BY period_end ASC
    """
    results = db_read(query, connection=db)
    return [self.dto_class(**row) for row in results]


def mark_paid(
    self,
    bill_id: UUID,
    payment_id: UUID,
    modified_by: UUID,
    db: psycopg2.extensions.connection
) -> bool:
    """Mark bill as paid
    
    Args:
        bill_id: Bill UUID
        payment_id: Payment attempt UUID
        modified_by: User making the change
        db: Database connection
        
    Returns:
        True if successful, False otherwise
    """
    update_data = {
        'status': 'Paid',
        'payment_id': str(payment_id),
        'modified_by': str(modified_by)
    }
    return self.update(bill_id, update_data, db, commit=True)


def get_by_institution_and_period(
    self,
    institution_id: UUID,
    period_start: datetime,
    period_end: datetime,
    db: psycopg2.extensions.connection
) -> List[T]:
    """Get bills by institution and period
    
    Joins through institution_entity to get all bills for institution.
    
    Args:
        institution_id: Institution UUID
        period_start: Start of billing period
        period_end: End of billing period
        db: Database connection
        
    Returns:
        List of bills for institution in period
    """
    query = f"""
        SELECT ib.* FROM {self.table_name} ib
        JOIN institution_entity_info ie ON ib.institution_entity_id = ie.institution_entity_id
        WHERE ie.institution_id = %s
        AND ib.period_start = %s
        AND ib.period_end = %s
        AND ib.is_archived = FALSE
        ORDER BY ie.entity_name, ib.created_date
    """
    results = db_read(query, (str(institution_id), period_start, period_end), 
                     connection=db)
    return [self.dto_class(**row) for row in results]
```

**Deprecation Wrappers:**

```python
# Keep at bottom of crud_service.py for backward compatibility

def get_by_entity_and_period(entity_id, period_start, period_end, db):
    """DEPRECATED: Use institution_bill_service.get_by_entity_and_period()
    
    This function will be removed in a future version.
    """
    return institution_bill_service.get_by_entity_and_period(
        entity_id, period_start, period_end, db
    )

def get_pending_bills(db):
    """DEPRECATED: Use institution_bill_service.get_pending()"""
    return institution_bill_service.get_pending(db)

def mark_paid(bill_id, payment_id, modified_by, db):
    """DEPRECATED: Use institution_bill_service.mark_paid()"""
    return institution_bill_service.mark_paid(bill_id, payment_id, modified_by, db)

def get_by_institution_and_period(institution_id, period_start, period_end, db):
    """DEPRECATED: Use institution_bill_service.get_by_institution_and_period()"""
    return institution_bill_service.get_by_institution_and_period(
        institution_id, period_start, period_end, db
    )
```

**Testing Checklist:**
- [ ] Test `get_by_entity_and_period()` with valid entity
- [ ] Test with non-existent entity (should return None)
- [ ] Test `get_pending()` returns only pending bills
- [ ] Test `mark_paid()` updates status correctly
- [ ] Test `get_by_institution_and_period()` joins correctly
- [ ] Test all deprecated wrappers still work

**Caller Update Process:**
1. Run `grep -r "get_by_entity_and_period\|get_pending_bills\|mark_paid\|get_by_institution_and_period" app/`
2. For each caller, update import and call
3. Test caller still works
4. Document in PR

---

### Step 1B: Institution Payment Attempt Service

**Methods to Add:** 5  
**Similar Process:**
1. Add methods to `CRUDService` class
2. Create deprecation wrappers
3. Update callers incrementally
4. Test thoroughly

**Method Signatures:**

```python
def get_by_institution_bill(self, bill_id: UUID, db, scope=None) -> List[T]:
    """Get payment attempts for a specific bill"""

def get_pending_by_institution_entity(self, entity_id: UUID, db) -> List[T]:
    """Get pending payment attempts for entity"""

def mark_complete(self, payment_id: UUID, db) -> bool:
    """Mark payment attempt as complete"""

def mark_failed(self, payment_id: UUID, db) -> bool:
    """Mark payment attempt as failed"""

def undelete(self, payment_id: UUID, db) -> bool:
    """Restore archived payment attempt"""
```

---

### Step 1C: Restaurant Balance Service

**Methods to Add:** 5  
**Key Consideration:** Balance operations are critical - extra testing required

**Method Signatures:**

```python
def get_by_restaurant(self, restaurant_id: UUID, db) -> Optional[T]:
    """Get balance for restaurant"""

def update_with_monetary_amount(self, restaurant_id: UUID, amount: float, 
                                currency_code: str, db) -> bool:
    """Update balance with currency conversion"""

def get_current_event_id(self, restaurant_id: UUID, db) -> Optional[UUID]:
    """Get ID of current balance event"""

def reset_balance(self, restaurant_id: UUID, db, commit=True) -> bool:
    """Reset restaurant balance to zero"""

def create_balance_record(self, restaurant_id: UUID, credit_currency_id: UUID,
                         currency_code: str, modified_by: UUID, db, 
                         commit=True) -> bool:
    """Initialize balance record for new restaurant"""
```

**Extra Testing Required:**
- [ ] Balance calculations remain correct
- [ ] Currency conversions work
- [ ] Transaction atomicity maintained
- [ ] No race conditions in balance updates

---

## Phase 2: Transaction Service (MEDIUM PRIORITY)

**Estimated Time:** 1 day  
**Functions:** 4  
**Risk:** Low (simple updates)

### Step 2A: Restaurant Transaction Service

**Methods to Add:**

```python
def get_by_plate_selection(self, plate_selection_id: UUID, db) -> Optional[T]:
    """Get transaction by plate selection"""

def update_final_amount(self, transaction_id: UUID, final_amount: float,
                       modified_by: UUID, db) -> bool:
    """Update final transaction amount"""

def update_arrival_time(self, transaction_id: UUID, arrival_time: datetime,
                       modified_by: UUID, db) -> bool:
    """Update customer arrival time"""

def mark_collected(self, transaction_id: UUID, collected_timestamp: datetime,
                  modified_by: UUID, db) -> bool:
    """Mark transaction as collected"""
```

**Note:** `mark_collected()` is used in complex business logic - keep wrapper indefinitely

---

## Phase 3: Miscellaneous Services (LOW PRIORITY)

**Estimated Time:** 1 day  
**Functions:** 5  
**Risk:** Very Low (simple lookups)

### Individual Service Updates

**Pattern for each:**
1. Add single method to service class
2. Create deprecation wrapper
3. Update callers (if any)
4. Test

**Services to Update:**
- `qr_code_service.get_by_restaurant()` - line 1129
- `subscription_service.get_by_user()` - line 1143
- `client_bill_service.get_by_payment()` - line 1379
- `credit_currency_service.get_by_code()` - line 1061
- `geolocation_service.get_by_address()` - line 1759

---

## Implementation Checklist (Per Phase)

### Before Starting
- [ ] Create feature branch: `feature/service-consolidation-phase-{N}`
- [ ] Read through current implementation of functions
- [ ] Identify all callers with grep
- [ ] Review existing service class structure

### During Implementation
- [ ] Add methods to service class
- [ ] Keep original functions as deprecation wrappers
- [ ] Add DEPRECATED docstrings
- [ ] Update callers incrementally
- [ ] Add/update unit tests for each method
- [ ] Check linter passes
- [ ] Test locally with Postman collections

### After Implementation
- [ ] Run full unit test suite
- [ ] Run integration tests
- [ ] Run all Postman collections
- [ ] Document changes in CHANGELOG
- [ ] Create PR with clear description
- [ ] Code review
- [ ] Merge to main

---

## Testing Strategy

### Unit Tests (Required)

For each new service method:

```python
def test_institution_bill_service_get_by_entity_and_period(db_connection):
    """Test getting bill by entity and period"""
    # Setup
    entity_id = create_test_entity(db_connection)
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 1, 31)
    bill = create_test_bill(entity_id, period_start, period_end, db_connection)
    
    # Execute
    result = institution_bill_service.get_by_entity_and_period(
        entity_id, period_start, period_end, db_connection
    )
    
    # Assert
    assert result is not None
    assert result.institution_entity_id == entity_id
    assert result.period_start == period_start
    assert result.period_end == period_end
    
    # Cleanup
    cleanup_test_data(db_connection)


def test_deprecated_wrapper_still_works(db_connection):
    """Ensure backward compatibility"""
    # Old way should still work
    from app.services.crud_service import get_by_entity_and_period
    
    entity_id = create_test_entity(db_connection)
    result = get_by_entity_and_period(entity_id, period_start, period_end, db_connection)
    
    assert result is not None  # Should still work!
```

### Integration Tests

```python
def test_bill_lifecycle_with_service_methods(db_connection):
    """Test full bill lifecycle using new service methods"""
    # Create entity
    entity_id = create_test_entity(db_connection)
    
    # Create bill
    bill = institution_bill_service.create({...}, db_connection)
    
    # Verify it's pending
    pending_bills = institution_bill_service.get_pending(db_connection)
    assert bill.bill_id in [b.bill_id for b in pending_bills]
    
    # Mark paid
    payment_id = create_test_payment(db_connection)
    success = institution_bill_service.mark_paid(
        bill.bill_id, payment_id, admin_user_id, db_connection
    )
    assert success
    
    # Verify no longer pending
    pending_bills = institution_bill_service.get_pending(db_connection)
    assert bill.bill_id not in [b.bill_id for b in pending_bills]
```

### Postman Collections

Run these after each phase:
- `INSTITUTION_BANK_ACCOUNT_POSTMAN_COLLECTION.json`
- `E2E Plate Selection.postman_collection.json`
- `DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`

---

## Rollback Plan

If issues arise during any phase:

### Immediate Rollback
```bash
# Revert the branch
git checkout main
git branch -D feature/service-consolidation-phase-{N}

# Old functions still work as wrappers
```

### Partial Rollback
```python
# Remove service method, keep wrapper
# Wrapper calls old implementation directly
def mark_paid(bill_id, payment_id, modified_by, db):
    """Temporary direct implementation during rollback"""
    # Original implementation here
```

---

## Success Metrics

### Phase 1 Complete When:
- [ ] 13 methods added to 3 service classes
- [ ] All 13 deprecation wrappers in place
- [ ] All callers updated (or wrappers working)
- [ ] All unit tests passing
- [ ] All Postman collections passing
- [ ] No regressions in production

### Phase 2 Complete When:
- [ ] 4 methods added to transaction service
- [ ] Wrappers in place
- [ ] Tests passing

### Phase 3 Complete When:
- [ ] 5 methods added to various services
- [ ] All tests passing
- [ ] Documentation updated

### Final Success Criteria:
- [ ] 19 functions consolidated
- [ ] Zero breaking changes
- [ ] Code is more organized
- [ ] Better IDE autocomplete
- [ ] Easier to find entity operations

---

## Timeline

### Week 1
- **Day 1-2:** Phase 1A (Institution Bill Service)
- **Day 3-4:** Phase 1B (Payment Attempt Service)
- **Day 5:** Phase 1C (Restaurant Balance Service)

### Week 2
- **Day 1:** Phase 2 (Restaurant Transaction Service)
- **Day 2:** Phase 3 (Miscellaneous Services)
- **Day 3:** Final testing and documentation

---

## Code Review Guidelines

### What Reviewers Should Check:

1. **Method Signatures**
   - [ ] Match service class conventions
   - [ ] Return types correct
   - [ ] Error handling appropriate

2. **Deprecation Wrappers**
   - [ ] Still work correctly
   - [ ] Have clear deprecation message
   - [ ] Link to new method

3. **Tests**
   - [ ] Cover happy path
   - [ ] Cover error cases
   - [ ] Test backward compatibility

4. **Documentation**
   - [ ] Docstrings complete
   - [ ] Examples clear
   - [ ] Updated CODING_GUIDELINES.md

5. **No Logic Changes**
   - [ ] Behavior identical to original
   - [ ] No "improvements" mixed in
   - [ ] Pure refactor only

---

## Future Work (Not in This Roadmap)

**After consolidation complete, consider:**
- Remove deprecation wrappers (breaking change - needs version bump)
- Add more service methods for complex operations
- Create specialized service classes (e.g., `BillingService`)
- Refactor complex business logic functions
- Add caching to frequently-used service methods

---

## Questions & Answers

### Q: Why keep deprecation wrappers?
**A:** Zero breaking changes. Callers work immediately, update incrementally.

### Q: What if a service doesn't exist yet?
**A:** Create it following the pattern of existing services (e.g., `institution_bill_service`).

### Q: Can we modify the function logic?
**A:** No! Pure refactor only. Behavior must remain identical.

### Q: What if tests fail?
**A:** Roll back that specific method, investigate, fix, re-apply.

### Q: How long keep wrappers?
**A:** Minimum 6 months, remove in major version bump with migration guide.

---

## References

- [SERVICE_CONSOLIDATION_ANALYSIS.md](./SERVICE_CONSOLIDATION_ANALYSIS.md) - Detailed analysis
- [CODING_GUIDELINES.md](../CODING_GUIDELINES.md) - Coding standards
- [CODE_ORGANIZATION_CLEANUP.md](./CODE_ORGANIZATION_CLEANUP.md) - Original audit

---

## Approval Required Before Starting

**Checklist:**
- [ ] User reviewed analysis document
- [ ] User approved roadmap
- [ ] Timeline acceptable
- [ ] Testing strategy agreed
- [ ] Ready to begin Phase 1A

**Once approved, proceed with Phase 1A: Institution Bill Service**
