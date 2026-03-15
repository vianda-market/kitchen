# Plate Pickup QR Code System - Implementation Roadmap

## Overview
This roadmap tracks the implementation of the QR code-based plate pickup system with company matching and pickup window constraints.

**Created**: 2025-01-24
**Status**: In Progress

---

## ✅ Completed Items

1. **QR Code Database Schema** - Simplified from `qr_code_info` to `qr_code`
2. **QR Code Generation Service** - Atomic image generation with local storage
3. **QR Code API Endpoints** - Creation, retrieval, deletion
4. **Payload Auto-Generation** - Only `restaurant_id` required for creation
5. **GET /plate-pickup/pending** - Now returns company-matched orders with order_count and pickup window
6. **POST /plate-pickup/scan-qr** - Simplified QR scanning with 4 error cases and confirmation code
7. **Completion Deprecation** - Marked `POST /plate-pickup/{pickup_id}/complete` as deprecated

---

## 🔄 Current Sprint - Plate Pickup QR Code Flow

### Phase 1: List Active QR Codes (Priority: HIGH) - ✅ COMPLETED

**Goal**: Customer sees their pending orders before scanning QR code

**Tasks**:
- [ ] Update `GET /plate-pickup/pending` response schema
  - Rename `order_type` to `order_count` (x1, x2, x3, etc.)
  - Add `pickup_window` with 15-minute window constrained to 11:30-14:30 local time
  - Show restaurant name, qr_code_id, total_orders, and plate details
- [ ] Implement company matching query
  - Query for user's own orders + orders they're picking up for others + orders others are picking up for them
  - Use efficient JOINs with pickup_preferences table
- [ ] Calculate pickup window with constraints
  - Get restaurant timezone from address
  - Round to nearest 15-minute slot within 11:30-14:30 window
  - Return window in local timezone
- [ ] Optimize query for scalability
  - Add proper indexes
  - Minimize columns in initial count query
  - Use efficient string aggregation for order details

### Phase 2: QR Code Scan (Priority: HIGH) - ✅ COMPLETED

**Goal**: Fast, simplified QR code scanning with no window enforcement

**Tasks**:
- [ ] Update `POST /plate-pickup/scan-qr` to use `qr_code_payload` instead of `qr_code_id`
- [ ] Implement four error cases:
  1. ✅ Success - person has at least 1 plate to pickup
  2. ❌ Error - person is in wrong restaurant
  3. ❌ Error - person does not have an active pickup
  4. ❌ Error - scanned QR code not recognized
- [ ] Remove window enforcement logic (informational only)
- [ ] Generate confirmation code (alphanumeric: ABC123 format)
- [ ] Update orders to 'Arrived' status with arrival_time
- [ ] Trigger pay-on-arrival balance update

### Phase 3: Confirmation Code System (Priority: MEDIUM) - ✅ COMPLETED

**Goal**: Restaurant staff can verify orders using confirmation codes

**Tasks Completed**:
- [x] Add `confirmation_code` column to `plate_pickup_live` table
- [x] Implement confirmation code generation (alphanumeric, 6 characters)
- [x] Update response to include confirmation_code after QR scan

**Remaining Tasks**:
- [ ] Create internal API for restaurant staff queries (future)
- [ ] Store confirmation_code with order for staff verification

---

## 🗑️ Deprecation Plan - Completion Endpoint

### Status: DEPRECATED (Short-term)

**Endpoint**: `POST /plate-pickup/{pickup_id}/complete`

**Deprecation Date**: 2025-01-24
**Removal Date**: TBD (Future sprint)

### Rationale:
- Manual completion endpoint is no longer needed
- Testing should use `POST /institution-bills/generate-daily-bills` which automatically completes orders
- Production uses cron job to complete orders when kitchen days close
- Keeping endpoint marked as deprecated for backward compatibility during transition

### Migration Path:

**For Testing (Postman)**:
1. Remove "Confirm Delivery" step from Postman collection
2. Use "Generate Daily Bills" step instead
3. Bills will automatically complete any pending orders before creating bills

**For Production**:
- Cron job handles completion automatically
- No manual completion needed

### Deletion Checklist:
- [ ] Remove endpoint from `app/routes/plate_pickup.py`
- [ ] Remove `complete_order` service method from `app/services/plate_pickup_service.py`
- [ ] Update Postman collection to remove completion step
- [ ] Remove from API documentation
- [ ] Update roadmap to mark as removed

---

## 📋 Future Sprints - Backlog Items

### Plate Registration Revisit

**Context**: Currently assumes one plate per restaurant per day. Need to support multiple plates.

**Tasks**:
- [ ] Review `plate_info` table unique constraints
- [ ] Determine if `(restaurant_id, kitchen_day, product_id)` should be unique
- [ ] Update plate registration logic to allow multiple plates per restaurant per day
- [ ] Update UI/API to show all available plates for a restaurant/day
- [ ] Test plate selection with multiple options

### Institution Scoping & RBAC Enforcement

**Context**: Non-employee roles must only see and act on records tied to their institution (users, entities, addresses, restaurants, products, plates, QR codes). Employees retain global visibility. Vianda Platform UI needs to respect these rules and FastAPI must enforce them server-side.

**Tasks**:
- [ ] Catalogue all endpoints touching institution-scoped resources and note current behaviour (list/detail/mutate).
- [ ] Add institution-aware filters to service/CRUD helpers (e.g., accept `institution_id` from JWT claims) so non-employee roles default to scoped queries.
- [ ] Guard mutations (`POST/PUT/PATCH/DELETE`) with institution ownership checks; escalate to backend changes where raw SQL bypasses CRUD helpers.
- [ ] Implement automated tests (unit + Postman) covering success/fail cases for scoped vs. employee roles.
- [ ] Update Vianda Platform auth context to feed `institutionId` into API calls and hide cross-institution navigation for non-employees.
- [ ] Document the scoping contract in backend/FE READMEs to keep future features compliant.
  - ✅ Design doc: `docs/api/INSTITUTION_SCOPING_DESIGN.md`

### Order Count Logic Enhancement

**Context**: Current counting might not accurately reflect quantities

**Tasks**:
- [ ] Review order counting logic in GET /plate-pickup/pending
- [ ] Clarify difference between:
  - `order_count` (x1, x2, x3) - number of plates for this person
  - `total_orders` - total count of all plates
- [ ] Update to show quantities correctly based on plate selection count
- [ ] Optimize database queries for scalability
- [ ] Add proper indexing for company matching queries

### Window Display & Matching

**Context**: Pickup window is informational, not enforced

**Tasks**:
- [ ] Ensure window display in UI is informational only
- [ ] Remove any window enforcement logic from QR scan
- [ ] Use window for schedule matching in company matching algorithm
- [ ] Display window in local restaurant timezone
- [ ] Add UI messaging about pickup window flexibility

### Restaurant Staff Interface (Future)

**Goal**: Restaurant staff can query daily orders with confirmation codes

**Tasks**:
- [ ] Design staff API endpoints
- [ ] Implement `GET /restaurant/{restaurant_id}/daily-orders`
- [ ] Return orders with confirmation codes
- [ ] Filter by date range
- [ ] Add pagination for scalability
- [ ] Implement authentication/authorization for restaurant staff

### Performance & Scalability Optimization

**Context**: System needs to handle lunch-time traffic spikes

**Tasks**:
- [ ] Audit all database queries for scalability
- [ ] Implement query performance monitoring
- [ ] Add database connection pooling optimization
- [ ] Create query execution time alerts
- [ ] Implement caching for frequently accessed data
- [ ] Add indexes for company matching queries:
  - `idx_plate_pickup_restaurant_status`
  - `idx_plate_pickup_user_status`
  - `idx_pickup_preferences_user`
  - `idx_pickup_preferences_matched`

### Testing & Documentation

**Tasks**:
- [ ] Create E2E test for complete pickup flow
- [ ] Test company matching scenarios
- [ ] Test QR code scan error cases
- [ ] Document API endpoints
- [ ] Create Postman collection for testing
- [ ] Add API documentation with examples

---

## 🎯 Success Criteria

### QR Code Scan Success
- Customer can scan QR code at restaurant
- System validates QR code existence
- System validates restaurant match
- System updates order status to 'Arrived'
- System triggers pay-on-arrival balance update
- Customer receives confirmation code

### Company Matching Success
- Customers can pick up orders for colleagues
- Orders show correct order_count (x1, x2, x3)
- Pickup preferences work correctly
- Multiple orders are grouped properly

### Performance Success
- Query response time < 100ms even with high concurrency
- No database connection pool exhaustion
- Proper error handling and graceful degradation
- Scalable to handle lunch-time traffic spikes

---

## 📝 Notes

### Technical Decisions
- **QR Code Format**: `"restaurant_id:{uuid}"` - simple and clear
- **Confirmation Code**: 6-character alphanumeric (e.g., "ABC123")
- **Pickup Window**: 15 minutes, constrained to 11:30-14:30 local time
- **Window Enforcement**: Informational only, not enforced during QR scan
- **Order Count**: Showed as x1, x2, x3 based on company matching

### Business Rules
- **One Order Per Day**: Customer can only have 1 order per day (enforced by business logic)
- **Company Matching**: Orders within ±15 minutes can be matched for pickup
- **Pickup Window**: 11:30 AM - 2:30 PM local time, 15-minute windows
- **Pay-on-Arrival**: Full payment only when customer actually arrives (QR scan)
- **Restaurant Timezone**: Use restaurant's local timezone for all time calculations

### MVP Bill Resolution System (✅ Completed)
**Implementation Date**: 2025-10-28

Implemented manual payment recording and bill cancellation:
- ✅ `POST /institution-bills/{bill_id}/record-payment` - Record manual bank payments
- ✅ `POST /institution-bills/{bill_id}/cancel` - Cancel bills administratively
- ✅ Updated `GET /institution-bills/` to explicitly filter by status
- ✅ Added Postman collection endpoints for payment recording
- ✅ Validation: Cannot pay cancelled bills, cannot cancel paid bills
- ✅ Failed bills are retryable (resolution remains 'Failed' until paid)
- ✅ No soft deletion (all bills retained for audit)

**Post-MVP Roadmap**:
- [ ] `POST /institution-bills/{bill_id}/mark-failed` - Mark payment as failed
- [ ] Automated bank integration to replace manual payment recording
- [ ] Enhanced payment retry logic with exponential backoff

### Known Issues
- Plate registration currently limits to one plate per restaurant per day
- Pickup window calculation needs timezone awareness
- Company matching queries need optimization for scalability
- Confirmation code should be unique per day, not globally unique

---

## 🔗 Related Files

- `app/services/qr_code_service.py` - Atomic QR code operations
- `app/services/qr_code_generation_service.py` - Image generation
- `app/services/plate_pickup_service.py` - Pickup business logic
- `app/routes/plate_pickup.py` - API endpoints
- `app/db/schema.sql` - Database schema
- `app/dto/models.py` - Data transfer objects

---

**Last Updated**: 2025-10-28

