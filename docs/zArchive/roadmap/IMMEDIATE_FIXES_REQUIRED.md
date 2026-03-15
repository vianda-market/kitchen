# Immediate Fixes Required - UPDATED

## Critical: Functions with Same Name, Different Logic

### 1. `get_all_by_user_address_city()` - TWO DIFFERENT IMPLEMENTATIONS

**Line 1031-1041:** Queries by restaurant address_id
```python
WHERE a.address_id = %s  # Restaurant's address
```

**Line 1632-1650:** Queries by user's city name  
```python
# Gets city from user address, then finds plates in that city
WHERE a.city = %s
```

**❌ Problem:** Same name, different logic - Python uses the LAST one  
**✅ Fix:** Rename for clarity

```python
# Line 1031: Rename to:
def get_plates_by_restaurant_address(address_id: UUID, db) -> List[PlateDTO]:
    """Get all plates for restaurants at this address"""
    
# Line 1632: Rename to:  
def get_plates_by_user_city(user_address_id: UUID, db) -> List[PlateDTO]:
    """Get all plates in same city as user's address"""
```

---

### 2. `get_all_active_for_today_by_user_address_city()` - TWO DIFFERENT IMPLEMENTATIONS

**Line 1043-1056:** Simple query with kitchen days
```python
AND a.address_id = %s  # Restaurant address
AND pkd.kitchen_day = UPPER(TO_CHAR(CURRENT_DATE, 'DAY'))
```

**Line 1652-1694:** Complex logic with date service and holiday checking
```python
# Uses get_effective_current_day() for complex date logic
# Different implementation, more sophisticated
```

**❌ Problem:** Same name, vastly different logic  
**✅ Fix:** Rename for clarity

```python
# Line 1043: Rename to:
def get_active_plates_today_by_restaurant_address(address_id: UUID, db) -> List[PlateDTO]:
    """Get active plates for today at restaurant address"""
    
# Line 1652: Rename to:
def get_active_plates_today_by_user_city(address_id: UUID, db) -> List[PlateDTO]:
    """Get active plates for today in user's city (with holiday logic)"""
```

---

### 3. `get_by_plate_selection_id()` - EXACT DUPLICATES ✅

**Lines 1271 & 1696:** Identical implementation  
**✅ Action:** Remove line 1696 (exact duplicate)

---

### 4. `mark_collected()` vs `mark_transaction_as_collected()` - CHECK NEEDED

**Line 1702:** `mark_collected()`  
**Line 1736:** `mark_transaction_as_collected()`  

**🔄 Action:** Check if these are the same or different

---

## Revised Action Plan

### Step 1: Remove Exact Duplicate (5 min)
- [ ] Remove `get_by_plate_selection_id()` at line 1696

### Step 2: Rename Conflicting Functions (15 min)
- [ ] Rename line 1031 → `get_plates_by_restaurant_address()`
- [ ] Rename line 1632 → `get_plates_by_user_city()`
- [ ] Rename line 1043 → `get_active_plates_today_by_restaurant_address()`
- [ ] Rename line 1652 → `get_active_plates_today_by_user_city()`

### Step 3: Fix Naming Conflicts from Option B (15 min)
- [ ] Rename line 1386 → `get_payment_attempts_by_institution_entity()`
- [ ] Rename line 1611 → `get_institution_entities_by_institution()`

### Step 4: Update Callers (15 min)
- [ ] Search for all usages
- [ ] Update import statements
- [ ] Update function calls

### Step 5: Test (10 min)
- [ ] Run Postman collections
- [ ] Check for any errors
- [ ] Verify no regressions

**Total Time:** ~1 hour
