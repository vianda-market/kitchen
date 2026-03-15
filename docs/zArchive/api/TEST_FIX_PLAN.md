# Test Fix Plan - 44 Failing Tests

## Summary
After the enum migration, 44 tests are failing due to:
1. **UserDTO schema changes** (role_id → role_type + role_name)
2. **Status enum migration** (string literals → Status enum values)
3. **Geocoding behavior changes** (now non-blocking)
4. **Service import/name changes**
5. **Missing fields in test mocks** (status field)
6. **API signature changes** (scope parameter added)

---

## Category 1: UserDTO Schema Changes (7 errors)

### Issue
Tests are creating `UserDTO` with `role_id: UUID` but the schema now requires:
- `role_type: RoleType` (enum)
- `role_name: RoleName` (enum)

### Affected Tests
1. `test_discretionary_service.py::TestDiscretionaryService::test_create_discretionary_request_success` (ERROR)
2. `test_discretionary_service.py::TestDiscretionaryService::test_create_discretionary_request_with_restaurant_success` (ERROR)
3. `test_discretionary_service.py::TestDiscretionaryService::test_create_discretionary_request_restaurant_not_found` (ERROR)
4. `conftest.py::sample_user_dto` fixture (affects 3 tests)
5. `test_entity_service.py::TestEntityService::test_get_user_by_username_returns_user_when_found` (FAILED)

### Fix Plan
1. **Update `conftest.py` fixture**:
   - Remove `role_id=uuid4()`
   - Add `role_type=RoleType.CUSTOMER` and `role_name=RoleName.COMENSAL`
   - Import `RoleType, RoleName` from `app.config`

2. **Update `test_discretionary_service.py`**:
   - Fix `sample_user_dto` fixture (lines 88-105)
   - Replace `role_id=uuid4()` with `role_type=RoleType.CUSTOMER, role_name=RoleName.COMENSAL`

3. **Update `test_entity_service.py`**:
   - Fix `mock_user_data` dict (line 46)
   - Replace `"role_id": uuid4()` with `"role_type": RoleType.CUSTOMER, "role_name": RoleName.COMENSAL`

---

## Category 2: Status Enum Migration (12 errors)

### Issue
Tests expect string literals like `"Approved"`, `"Rejected"`, `"Paid"` but code now uses:
- `Status.PROCESSED` (instead of "Approved")
- `Status.CANCELLED` (instead of "Rejected")
- `Status.PROCESSED` (instead of "Paid")

### Affected Tests
1. `test_discretionary_service.py::test_approve_discretionary_request_success` - expects `"Approved"` but gets `Status.PROCESSED`
2. `test_discretionary_service.py::test_reject_discretionary_request_success` - expects `"Rejected"` but gets `Status.CANCELLED`
3. `test_entity_service.py::test_get_bills_by_status_filters_correctly` - uses `"Paid"` which is not a valid Status enum
4. `test_crud_service.py` - 8 tests missing `status` field in mock data for `PlateKitchenDaysDTO`

### Fix Plan
1. **Update `test_discretionary_service.py`**:
   - Line 352: Change expected status from `"Approved"` to `Status.PROCESSED`
   - Line 436: Change expected status from `"Rejected"` to `Status.CANCELLED`
   - Import `Status` from `app.config`

2. **Update `test_entity_service.py`**:
   - Line 266: Replace `status="Paid"` with `status=Status.PROCESSED`
   - Import `Status` from `app.config`

3. **Update `test_crud_service.py`**:
   - Add `status: Status.ACTIVE` to all mock data for `plate_kitchen_days` tests
   - Update mock return values in:
     - `test_get_all_no_scope` (line 240)
     - `test_get_all_global_scope` (line 265)
     - `test_get_all_supplier_scope` (line 288)
     - `test_get_by_id_no_scope` (line 330)
     - `test_get_by_id_supplier_scope` (line 355)
     - `test_create_with_foreign_key_validation` (line 540)
     - `test_update_with_foreign_key_validation` (line 595)
     - `test_update_fails_foreign_key_validation` (line 640)
     - `test_soft_delete_with_join_scoping` (line 665)

---

## Category 3: Address Service Geocoding Changes (3 errors)

### Issue
Geocoding is now **non-blocking** - it logs warnings but doesn't raise HTTPException on failure. Tests expect:
- Geocoding to be called
- HTTPException to be raised on failure

### Affected Tests
1. `test_address_service.py::test_create_address_with_geocoding_calls_api_for_restaurants` - expects API to be called
2. `test_address_service.py::test_create_address_with_geocoding_handles_api_failure` - expects HTTPException on failure
3. `test_address_service.py::test_validate_address_data_checks_required_fields` - error message changed

### Fix Plan
1. **Update `test_create_address_with_geocoding_calls_api_for_restaurants`**:
   - Check that geocoding is called only if address_type contains "Restaurant"
   - Use `AddressType.RESTAURANT.value` in test data

2. **Update `test_create_address_with_geocoding_handles_api_failure`**:
   - Remove `pytest.raises(HTTPException)` - geocoding failures no longer raise exceptions
   - Assert that address is created successfully even when geocoding fails
   - Optionally check for warning log

3. **Update `test_validate_address_data_checks_required_fields`**:
   - Update expected error message to match current validation (country code validation happens first)

---

## Category 4: Client Bill Service Import Issues (6 errors)

### Issue
Tests try to patch `app.services.client_bill_service.credit_currency_service` but:
- The service is imported from `app.services.credit_currency_service`
- It's not an attribute of `client_bill_service` module

### Affected Tests
1. `test_client_bill_service.py::test_create_client_bill_resolves_currency_code`
2. `test_client_bill_service.py::test_create_client_bill_applies_creation_rules`
3. `test_client_bill_service.py::test_resolve_currency_code_looks_up_currency`
4. `test_client_bill_service.py::test_resolve_currency_code_handles_missing_currency`
5. `test_client_bill_service.py::test_validate_bill_amount_validates_positive_amount`
6. `test_client_bill_service.py::test_validate_bill_amount_handles_missing_currency`

### Fix Plan
1. **Update patch paths**:
   - Change from: `patch('app.services.client_bill_service.credit_currency_service')`
   - Change to: `patch('app.services.credit_currency_service.credit_currency_service')`
   - Or patch the imported function: `patch('app.services.client_bill_service.resolve_currency_code')`

2. **Check actual imports** in `client_bill_service.py`:
   - Line 15: `from app.services.credit_currency_service import resolve_currency_code`
   - Line 134: `credit_currency_service.get_by_id(...)`
   - Need to check where `credit_currency_service` is imported from

---

## Category 5: Credit Loading Service Mock Issues (3 errors)

### Issue
1. Mock cursor doesn't properly simulate `cursor.description` (needs to be iterable)
2. Missing fixture `sample_credit_currency_dto`

### Affected Tests
1. `test_credit_loading_service.py::test_create_client_credit_transaction_success`
2. `test_credit_loading_service.py::test_create_restaurant_credit_transaction_service_error`
3. `test_credit_loading_service.py::test_create_client_credit_transaction_decimal_precision`

### Fix Plan
1. **Fix mock cursor setup**:
   - Mock `cursor.description` to return a list of tuples: `[('column_name',), ...]`
   - Example: `mock_cursor.description = [('subscription_id',), ('user_id',), ...]`

2. **Add missing fixture**:
   - Create `sample_credit_currency_dto` fixture in `test_credit_loading_service.py`
   - Or use existing fixture if available

---

## Category 6: CRUD Service Scope Parameter (2 errors)

### Issue
Tests expect `get_by_field()` to be called without `scope` parameter, but code now passes `scope=None` by default.

### Affected Tests
1. `test_entity_service.py::test_get_user_by_username_returns_none_when_not_found`
2. Similar pattern in other entity service tests

### Fix Plan
1. **Update mock assertions**:
   - Change from: `assert_called_once_with("username", username, mock_db)`
   - Change to: `assert_called_once_with("username", username, mock_db, scope=None)`

---

## Category 7: Geolocation Service Timezone Changes (5 errors)

### Issue
Tests expect specific timezone mappings that may have changed:
- Default timezone changed from `America/Argentina/Buenos_Aires` to `America/New_York`
- Some country/city mappings may have changed

### Affected Tests
1. `test_geolocation_service.py::test_get_timezone_from_location_returns_default_for_unknown_country`
2. `test_geolocation_service.py::test_get_timezone_from_location_handles_mexico_cities`
3. `test_geolocation_service.py::test_get_timezone_from_location_handles_spain_cities`
4. `test_geolocation_service.py::test_get_timezone_from_location_handles_bolivia_cities`
5. `test_geolocation_service.py::test_get_timezone_from_location_handles_case_sensitivity`

### Fix Plan
1. **Check actual timezone mappings** in `geolocation_service.py`
2. **Update test expectations** to match current implementation:
   - Update default timezone expectation
   - Update country/city mappings if they changed
   - Update case sensitivity expectations

---

## Category 8: Payment Method Service Query Format (1 error)

### Issue
Test expects query to start with `"UPDATE payment_method"` but actual query has leading whitespace/newlines.

### Affected Tests
1. `test_payment_method_service.py::test_link_payment_method_success`

### Fix Plan
1. **Update assertion**:
   - Change from: `assert call_args[0][0].startswith("UPDATE payment_method")`
   - Change to: `assert "UPDATE payment_method" in call_args[0][0]` or strip whitespace first

---

## Category 9: Plate Pickup Service Method Name (1 error)

### Issue
Test calls `_validate_qr_code_by_payload()` but method doesn't exist. Need to check actual method name.

### Affected Tests
1. `test_plate_pickup_service.py::test_scan_qr_code_validates_qr_code_not_found`

### Fix Plan
1. **Check actual method name** in `plate_pickup_service.py`
2. **Update test** to use correct method name or fix the service if method is missing

---

## Category 10: Plate Selection Service Restaurant Status (4 errors)

### Issue
Tests don't mock restaurant status properly, causing validation to fail before reaching the intended test scenario.

### Affected Tests
1. `test_plate_selection_service.py::test_create_plate_selection_with_transactions_handles_qr_code_not_found`
2. `test_plate_selection_service.py::test_create_plate_selection_with_transactions_handles_currency_not_found`
3. `test_plate_selection_service.py::test_create_plate_selection_with_transactions_handles_creation_failure`
4. `test_plate_selection_service.py::test_create_plate_selection_with_transactions_blocks_insufficient_credits`
5. `test_plate_selection_service.py::test_create_plate_selection_with_transactions_allows_exact_credits`

### Fix Plan
1. **Add restaurant status mock**:
   - Set `mock_restaurant.status = Status.ACTIVE` in all affected tests
   - Import `Status` from `app.config`

---

## Category 11: User Signup Service Role Changes (3 errors)

### Issue
Tests expect `role_id` but code now uses `role_type` and `role_name`. Also, `CUSTOMER_ROLE` constant was removed.

### Affected Tests
1. `test_user_signup_service.py::test_process_admin_user_creation_validates_data` - error message changed
2. `test_user_signup_service.py::test_process_admin_user_creation_validates_role_required` - expects `role_id` but needs `role_type` and `role_name`
3. `test_user_signup_service.py::test_get_signup_constants_returns_correct_values` - `CUSTOMER_ROLE` removed
4. `test_user_signup_service.py::test_apply_customer_signup_rules_sets_defaults` - expects `role_id` in user_data

### Fix Plan
1. **Update error message assertions**:
   - Change from: `"Missing required fields"` to actual message
   - Change from: `"Role ID is required"` to `"Role type and role name are required"`

2. **Update constants test**:
   - Remove `customer_role` assertion
   - Add assertions for `customer_role_type` and `customer_role_name` if they exist

3. **Update customer signup rules test**:
   - Change from: `assert user_data["role_id"] == ...`
   - Change to: `assert user_data["role_type"] == RoleType.CUSTOMER` and `assert user_data["role_name"] == RoleName.COMENSAL`

---

## Category 12: Discretionary Service Validation Order (2 errors)

### Issue
Validation order changed - category validation happens before reason validation.

### Affected Tests
1. `test_discretionary_service.py::test_create_discretionary_request_invalid_reason` - expects "Invalid reason" but gets "Invalid category"
2. `test_discretionary_service.py::test_create_discretionary_request_user_not_found` - category validation happens first

### Fix Plan
1. **Fix test data**:
   - Use valid category (`"Client"` or `"Supplier"`) before testing reason validation
   - Or update test to check category validation first, then reason

---

## Execution Order

1. **Phase 1: Schema Changes** (Categories 1, 2, 11)
   - Fix UserDTO fixtures and mocks
   - Fix Status enum usage
   - Fix role-related tests

2. **Phase 2: Service Changes** (Categories 3, 4, 5, 9)
   - Fix geocoding tests
   - Fix import/patch issues
   - Fix mock setup issues

3. **Phase 3: API Signature Changes** (Categories 6, 10)
   - Fix scope parameter assertions
   - Fix restaurant status mocks

4. **Phase 4: Minor Fixes** (Categories 7, 8, 12)
   - Fix timezone expectations
   - Fix query format assertions
   - Fix validation order

---

## Estimated Effort

- **Category 1**: 2 hours (7 tests)
- **Category 2**: 2 hours (12 tests)
- **Category 3**: 1 hour (3 tests)
- **Category 4**: 1 hour (6 tests)
- **Category 5**: 1 hour (3 tests)
- **Category 6**: 30 minutes (2 tests)
- **Category 7**: 1 hour (5 tests)
- **Category 8**: 15 minutes (1 test)
- **Category 9**: 30 minutes (1 test)
- **Category 10**: 1 hour (4 tests)
- **Category 11**: 1 hour (3 tests)
- **Category 12**: 30 minutes (2 tests)

**Total**: ~12 hours

