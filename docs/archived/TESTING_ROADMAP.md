# Testing Roadmap

## Overview
This document outlines the comprehensive unit testing strategy for the refactored codebase, following the testing standards established in `CLAUDE.md`.

## Testing Strategy Decision

**Route Testing**: We have decided to **skip route unit testing** and rely on:
- **Service Layer Tests**: Comprehensive business logic testing (113 tests)
- **Postman E2E Tests**: Full HTTP stack testing with real authentication and database

**Rationale**:
- Routes are now thin controllers with minimal logic
- Service layer tests provide comprehensive business logic coverage
- Postman provides better e2e testing than route unit tests
- Route unit tests require complex mocking with minimal value

## Testing Standards Summary
1. **Minimize asserts per concept** - Test one concept per test function
2. **Fast execution** - Tests should complete in milliseconds
3. **Independent tests** - No shared state between tests
4. **Repeatable in any environment** - Consistent across dev/staging/prod
5. **Self-validating** - Boolean output (pass/fail)
6. **Test-Driven Development** - Write tests before production code
7. **Mock external dependencies** - Database, APIs, file system
8. **Test business logic, not framework code** - Focus on service functions
9. **Use descriptive test names** - Clear description of what is being tested
10. **Arrange-Act-Assert pattern** - Clear setup, execution, verification

## Priority 1: Business Logic Services (High Impact)

### 1. **User Signup Service** - `app/services/user_signup_service.py`
**Priority: HIGH** - Core authentication and user creation logic

**Test Functions Needed:**
- `test_process_customer_signup_validates_required_fields()`
- `test_process_customer_signup_hashes_password()`
- `test_process_customer_signup_applies_customer_rules()`
- `test_process_admin_user_creation_validates_data()`
- `test_process_admin_user_creation_generates_temp_password()`
- `test_validate_signup_data_rejects_invalid_email()`
- `test_validate_signup_data_rejects_weak_password()`
- `test_apply_customer_signup_rules_sets_defaults()`

### 2. **Plate Pickup Service** - `app/services/plate_pickup_service.py`
**Priority: HIGH** - Complex multi-service validation logic

**Test Functions Needed:**
- `test_scan_qr_code_validates_pickup_record_ownership()`
- `test_scan_qr_code_validates_qr_code_exists()`
- `test_scan_qr_code_validates_restaurant_match()`
- `test_scan_qr_code_calculates_completion_time()`
- `test_scan_qr_code_updates_pickup_status()`
- `test_scan_qr_code_updates_restaurant_balance()`
- `test_complete_order_validates_status()`
- `test_complete_order_updates_transactions()`
- `test_delete_pickup_record_validates_authorization()`

### 3. **Address Service** - `app/services/address_service.py`
**Priority: HIGH** - Geocoding integration and timezone calculation

**Test Functions Needed:**
- `test_create_address_with_geocoding_sets_timezone()`
- `test_create_address_with_geocoding_calls_api_for_restaurants()`
- `test_create_address_with_geocoding_handles_api_failure()`
- `test_validate_address_data_checks_required_fields()`
- `test_validate_address_data_validates_country_code()`
- `test_update_address_with_geocoding_regeocodes_on_location_change()`
- `test_build_full_address_string_formats_correctly()`

### 4. **Client Bill Service** - `app/services/client_bill_service.py`
**Priority: MEDIUM** - Currency resolution and bill processing

**Test Functions Needed:**
- `test_create_client_bill_resolves_currency_code()`
- `test_create_client_bill_validates_bill_data()`
- `test_create_client_bill_applies_creation_rules()`
- `test_resolve_currency_code_looks_up_currency()`
- `test_resolve_currency_code_handles_missing_currency()`
- `test_calculate_bill_total_applies_tax_and_discount()`
- `test_validate_bill_data_checks_required_fields()`

### 5. **Bank Account Service** - `app/services/bank_account_service.py`
**Priority: MEDIUM** - Complex validation and security logic

**Test Functions Needed:**
- `test_validate_bank_account_checks_routing_number()`
- `test_validate_bank_account_checks_account_number()`
- `test_validate_bank_account_masks_account_number()`
- `test_validate_bank_account_adds_business_notes()`
- `test_create_bank_account_validates_data()`
- `test_create_bank_account_applies_creation_rules()`
- `test_auto_populate_minimal_account_sets_defaults()`

## Priority 2: Core Services (Medium Impact)

### 6. **Plate Selection Service** - `app/services/plate_selection_service.py`
**Priority: MEDIUM** - Complex business logic for plate selection

**Test Functions Needed:**
- `test_create_plate_selection_with_transactions_validates_data()`
- `test_create_plate_selection_with_transactions_creates_records()`
- `test_create_plate_selection_with_transactions_updates_balances()`
- `test_determine_target_kitchen_day_finds_available_day()`
- `test_validate_plate_selection_data_checks_constraints()`

### 7. **Entity Service** - `app/services/entity_service.py`
**Priority: MEDIUM** - Entity-specific business logic

**Test Functions Needed:**
- `test_get_user_by_username_queries_database()`
- `test_get_user_by_email_queries_database()`
- `test_create_user_with_validation_processes_data()`
- `test_create_employer_with_address_creates_both_entities()`
- `test_get_geolocation_by_address_id_returns_coordinates()`

### 8. **Error Handling Service** - `app/services/error_handling.py`
**Priority: MEDIUM** - Centralized error handling logic

**Test Functions Needed:**
- `test_handle_service_call_returns_result_on_success()`
- `test_handle_service_call_raises_http_exception_on_failure()`
- `test_handle_database_operation_logs_errors()`
- `test_handle_business_operation_wraps_exceptions()`
- `test_handle_get_by_id_returns_entity()`
- `test_handle_get_by_id_raises_404_on_not_found()`

## Priority 3: Utility Services (Lower Impact)

### 9. **CRUD Service** - `app/services/crud_service.py`
**Priority: LOW** - Generic CRUD operations (test key methods)

**Test Functions Needed:**
- `test_crud_service_get_by_id_returns_dto()`
- `test_crud_service_get_by_id_returns_none_on_not_found()`
- `test_crud_service_create_returns_new_dto()`
- `test_crud_service_update_modifies_existing_dto()`
- `test_crud_service_soft_delete_marks_archived()`

### 10. **Utility Functions** - `app/utils/`
**Priority: LOW** - Pure utility functions

**Test Functions Needed:**
- `test_get_timezone_from_location_returns_correct_timezone()`
- `test_call_geocode_api_returns_coordinates()`
- `test_call_geocode_api_handles_api_failure()`
- `test_include_archived_query_returns_query_object()`
- `test_entity_not_found_returns_http_exception()`

## Priority 4: Business Logic Services (Lower Impact)

### 11. **Billing Services** - `app/services/billing.py`, `app/services/billing/`
**Priority: LOW** - Billing business logic

**Test Functions Needed:**
- `test_process_completed_bill_updates_status()`
- `test_institution_billing_calculates_amounts()`

### 12. **Market Detection** - `app/services/market_detection.py`
**Priority: LOW** - Market detection logic

**Test Functions Needed:**
- `test_get_country_from_entity_returns_country()`
- `test_get_country_from_restaurant_returns_country()`

### 13. **Cron Services** - `app/services/cron/`
**Priority: LOW** - Scheduled job logic

**Test Functions Needed:**
- `test_archival_job_processes_eligible_records()`
- `test_billing_events_generates_bills()`

## Test Structure

### Directory Structure
```
app/tests/
├── services/
│   ├── test_user_signup_service.py
│   ├── test_plate_pickup_service.py
│   ├── test_address_service.py
│   ├── test_client_bill_service.py
│   ├── test_bank_account_service.py
│   ├── test_plate_selection_service.py
│   ├── test_entity_service.py
│   ├── test_error_handling.py
│   └── test_crud_service.py
├── utils/
│   ├── test_date.py
│   ├── test_geolocation.py
│   ├── test_query_params.py
│   └── test_error_messages.py
└── conftest.py  # Shared fixtures and mocks
```

### Test Dependencies
```python
# requirements-test.txt
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-mock>=3.10.0
httpx>=0.24.0  # For testing FastAPI
```

### Mock Strategy
- **Database connections**: Mock `psycopg2.extensions.connection`
- **External APIs**: Mock `requests` or `httpx` calls
- **File system**: Mock file operations
- **Time/Date**: Mock `datetime` for consistent testing
- **Logging**: Mock logging calls to avoid noise

## Implementation Order

### Phase 1: Core Business Logic (Week 1)
1. User Signup Service
2. Plate Pickup Service
3. Address Service

### Phase 2: Supporting Services (Week 2)
4. Client Bill Service
5. Bank Account Service
6. Plate Selection Service

### Phase 3: Infrastructure (Week 3)
7. Entity Service
8. Error Handling Service
9. CRUD Service

### Phase 4: Utilities (Week 4)
10. Utility Functions
11. Billing Services
12. Market Detection
13. Cron Services

## Success Metrics

### Coverage Targets
- **Business Logic Services**: 90%+ coverage
- **Core Services**: 85%+ coverage
- **Utility Functions**: 80%+ coverage
- **Overall**: 85%+ coverage

### Performance Targets
- **Unit tests**: < 100ms per test
- **Full test suite**: < 30 seconds
- **CI/CD integration**: < 2 minutes

### Quality Targets
- **Zero flaky tests** - All tests must be deterministic
- **Clear test names** - Test purpose obvious from name
- **Minimal assertions** - One concept per test
- **Fast feedback** - Tests run on every commit

## Next Steps

1. **Set up test infrastructure** - Create test directory structure
2. **Install test dependencies** - Add pytest and mocking libraries
3. **Create shared fixtures** - Database mocks, common test data
4. **Start with Priority 1** - Begin with User Signup Service tests
5. **Implement TDD workflow** - Write tests before production code
6. **Integrate with CI/CD** - Run tests on every commit
7. **Monitor coverage** - Track test coverage metrics
8. **Refactor based on tests** - Use tests to guide refactoring

This testing roadmap ensures comprehensive coverage of all business logic while maintaining fast, reliable, and maintainable tests.
