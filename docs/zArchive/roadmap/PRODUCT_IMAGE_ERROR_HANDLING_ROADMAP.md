# Product Image Error Handling Strategy & Roadmap

## Current State

### ✅ Implemented
- **Default placeholder**: All products are seeded with `static/placeholders/product_default.png` at creation
- **Placeholder constants**: Centralized in `consolidated_schemas.py`:
  - `PLACEHOLDER_IMAGE_PATH = "static/placeholders/product_default.png"`
  - `PLACEHOLDER_IMAGE_URL = "http://localhost:8000/static/placeholders/product_default.png"`
  - `PLACEHOLDER_IMAGE_CHECKSUM = "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c"`
- **`has_image` flag**: Enriched product API includes `has_image` field:
  - `TRUE` if product has custom uploaded image (path != placeholder)
  - `FALSE` if product uses default placeholder

### ⚠️ Current Gaps
- No validation that placeholder file exists at creation
- No check if uploaded image file is reachable
- No alerts when placeholder is missing/unreachable
- No automatic fallback if placeholder is deleted after product creation

---

## Error Scenarios

### Scenario 1: Product Creation Without Image
**Current Behavior**: 
- Product is created with default placeholder path/URL/checksum
- No validation that placeholder file exists

**Risk**: 
- If placeholder file doesn't exist, product will have broken image link
- UI will show broken image or error

**Recommended Handling**: ✅ **Auto-apply default at creation**
- At product creation, if no image is provided, automatically set placeholder values
- This is already happening in the schema defaults, but we should add explicit validation

---

### Scenario 2: Default Placeholder File Missing
**Current Behavior**: 
- Product references placeholder path, but file doesn't exist
- No alert or fallback mechanism

**Risk**: 
- Broken image links across all products using placeholder
- Poor user experience

**Recommended Handling**: ⚠️ **Alert but don't block**
- Monitor placeholder file existence (health check endpoint)
- Log warning/alert when placeholder is missing
- UI should gracefully handle missing images (show placeholder icon or text)
- Consider: Should we auto-copy placeholder from backup location if missing?

---

### Scenario 3: Custom Uploaded Image Missing/Deleted
**Current Behavior**: 
- Product has custom image path, but file doesn't exist
- No validation or recovery mechanism

**Risk**: 
- Broken image link for specific product
- User sees broken image instead of placeholder

**Recommended Handling**: ⚠️ **Alert and optionally auto-fallback**
- Option A (Conservative): Log error, alert, but leave path as-is (UI handles gracefully)
- Option B (Proactive): Auto-fallback to placeholder if custom image is missing, update DB, and alert

---

### Scenario 4: Image Upload Failure
**Current Behavior**: 
- Upload endpoint validates file and saves to disk
- If save fails, exception is raised

**Risk**: 
- Product may be left in inconsistent state
- Partial file writes could leave orphaned files

**Recommended Handling**: ✅ **Transaction rollback + cleanup**
- Ensure image save happens in transaction if possible
- Clean up any partial files if save fails
- Return error before updating product record

---

## Recommended Error Handling Strategy

### Phase 1: Product Creation Validation (HIGH PRIORITY)

**Goal**: Ensure every product always has a valid image reference at creation time.

**Implementation**:
1. **Validation at Creation**:
   - If no image provided → auto-apply placeholder values
   - Verify placeholder file exists (or create it if missing)
   - If placeholder is missing and cannot be created → **ERROR: Cannot create product without valid image**

2. **Database Constraints**:
   - Keep `image_storage_path` as NOT NULL (already enforced)
   - Keep default value as placeholder path (already enforced)

3. **Service Layer**:
   ```python
   def create_product_with_image_validation(product_data, db):
       # If no image provided, set placeholder
       if not product_data.get('image_storage_path'):
           placeholder_path, placeholder_url, placeholder_checksum = get_placeholder_metadata()
           product_data['image_storage_path'] = placeholder_path
           product_data['image_url'] = placeholder_url
           product_data['image_checksum'] = placeholder_checksum
       
       # Validate that the referenced image file exists
       validate_image_file_exists(product_data['image_storage_path'])
       
       return create_product(product_data, db)
   ```

**Error Handling**:
- If placeholder file doesn't exist → **Create it from embedded default** or **ERROR**
- If custom image path provided but file missing → **ERROR: Image file not found**

---

### Phase 2: Placeholder Health Monitoring (MEDIUM PRIORITY)

**Goal**: Detect and alert when placeholder file is missing or unreachable.

**Implementation**:
1. **Health Check Endpoint** (optional but recommended):
   ```python
   @router.get("/health/placeholder-image")
   def check_placeholder_image():
       """Health check for placeholder image availability"""
       placeholder_exists = os.path.exists("static/placeholders/product_default.png")
       return {
           "placeholder_available": placeholder_exists,
           "path": "static/placeholders/product_default.png"
       }
   ```

2. **Startup Validation**:
   - On application startup, verify placeholder file exists
   - Log warning if missing
   - Optionally: Auto-create placeholder from embedded asset if missing

3. **Monitoring/Alerts** (Future):
   - Periodic health checks
   - Alerting system (email, Slack, etc.) when placeholder is missing
   - Dashboard showing placeholder availability

**Error Handling**:
- If placeholder missing at startup → **LOG WARNING** (don't block startup)
- Optionally: Auto-copy placeholder from backup location
- If placeholder missing during product creation → **ERROR: Cannot create product without valid placeholder**

---

### Phase 3: Image File Validation (MEDIUM PRIORITY)

**Goal**: Validate that image files exist when retrieving products.

**Implementation**:
1. **Optional Validation Service**:
   ```python
   def validate_product_image_exists(product: ProductDTO) -> bool:
       """Check if product image file exists on disk"""
       if product.is_placeholder(product.image_storage_path):
           return os.path.exists(product.image_storage_path)
       else:
           return os.path.exists(product.image_storage_path)
   ```

2. **Enriched Endpoint Enhancement** (Optional):
   - Add `image_exists: bool` field alongside `has_image`
   - Computed in SQL or Python: `file_exists(image_storage_path)`
   - Note: File system checks in SQL are not recommended, so this would need Python logic

**Error Handling**:
- If custom image missing → **LOG WARNING**, but don't change DB
- UI can check `image_exists` flag to show appropriate fallback
- Optionally: Background job to auto-fallback missing custom images to placeholder

---

### Phase 4: Auto-Recovery & Background Jobs (LOW PRIORITY)

**Goal**: Automatically recover from missing image scenarios.

**Implementation**:
1. **Background Job** (Cron):
   - Periodically scan products with custom images
   - Check if image files exist
   - If missing:
     - Log alert
     - Optionally: Auto-fallback to placeholder (with admin approval)
     - Update `image_storage_path`, `image_url`, `image_checksum` in DB
     - Create audit log entry

2. **Recovery Strategy**:
   ```python
   def recover_missing_product_images():
       """Background job to recover missing product images"""
       products_with_custom_images = get_products_with_custom_images()
       
       for product in products_with_custom_images:
           if not os.path.exists(product.image_storage_path):
               log_warning(f"Product {product.product_id} has missing image: {product.image_storage_path}")
               # Auto-fallback to placeholder
               fallback_to_placeholder(product.product_id)
               # Or: Send alert to admin for manual review
   ```

---

## Implementation Roadmap

### ✅ Phase 0: Current (COMPLETE)
- [x] `has_image` flag in enriched product API
- [x] Default placeholder path constant
- [x] Schema defaults for placeholder values

### 📋 Phase 1: Creation Validation (RECOMMENDED - Next)
**Priority**: HIGH  
**Effort**: 2-3 hours  
**Impact**: Prevents invalid product states

1. **Add placeholder file validation at product creation**:
   - Check if placeholder exists when no image provided
   - Auto-create placeholder if missing (from embedded asset)
   - Fail product creation if placeholder cannot be created

2. **Add explicit placeholder assignment**:
   - In `product_service.create()`, explicitly set placeholder if not provided
   - Validate placeholder file exists

3. **Error messages**:
   - Clear error if placeholder is missing and cannot be created

**Files to Modify**:
- `app/services/crud_service.py` - Product creation logic
- `app/services/product_image_service.py` - Placeholder validation/creation
- `app/services/route_factory.py` - Product creation endpoint

---

### 📋 Phase 2: Placeholder Health Monitoring (OPTIONAL)
**Priority**: MEDIUM  
**Effort**: 3-4 hours  
**Impact**: Early detection of missing placeholder

1. **Startup validation**:
   - Check placeholder file exists on app startup
   - Log warning if missing
   - Optionally: Auto-create from embedded asset

2. **Health check endpoint** (optional):
   - `/health/placeholder-image` endpoint
   - Returns placeholder availability status

3. **Alerting** (Future):
   - Integrate with monitoring system
   - Alert when placeholder is missing

**Files to Create/Modify**:
- `app/routes/main.py` or `app/routes/health.py` - Health check endpoint
- `application.py` - Startup validation
- `app/services/product_image_service.py` - Placeholder validation

---

### 📋 Phase 3: Image File Validation (OPTIONAL)
**Priority**: MEDIUM  
**Effort**: 4-5 hours  
**Impact**: Detects missing custom images

1. **File existence check**:
   - Add `image_exists: bool` to enriched product schema (optional)
   - Check file existence when retrieving products (performance consideration)

2. **Warning logs**:
   - Log warning when custom image file is missing
   - Don't block API calls, just log

**Files to Modify**:
- `app/services/entity_service.py` - Add file existence check (Python logic)
- `app/schemas/consolidated_schemas.py` - Optional `image_exists` field

**Performance Consideration**: 
- File system checks can be slow
- Consider caching results or background validation
- Or: Only validate on-demand (not in list endpoints)

---

### 📋 Phase 4: Auto-Recovery & Background Jobs (FUTURE)
**Priority**: LOW  
**Effort**: 6-8 hours  
**Impact**: Automatic recovery from missing images

1. **Background job**:
   - Cron job to scan products
   - Detect missing image files
   - Auto-fallback to placeholder (with configurable approval)

2. **Recovery logic**:
   - Update product records
   - Create audit logs
   - Send alerts to admins

**Files to Create/Modify**:
- `app/services/cron/image_validation_job.py` - New cron job
- `app/services/product_image_service.py` - Recovery methods
- `app/services/entity_service.py` - Bulk image validation

---

## Decision Points

### 1. Should we block product creation if placeholder is missing?
**Recommendation**: ✅ **YES** (Phase 1)
- Products must always have valid image references
- Better to fail fast than create broken state
- Placeholder should be part of deployment/infrastructure

### 2. Should we auto-create placeholder if missing?
**Recommendation**: ✅ **YES** (Phase 1)
- Embed placeholder asset in codebase or Docker image
- Auto-create from embedded asset if missing
- Ensures placeholder always exists

### 3. Should we auto-fallback missing custom images to placeholder?
**Recommendation**: ⚠️ **OPTIONAL** (Phase 4)
- Pros: Automatic recovery, better UX
- Cons: Data loss (user's custom image), requires admin approval
- Alternative: Alert admin, let them decide

### 4. Should we validate file existence on every API call?
**Recommendation**: ❌ **NO** (Performance concern)
- File system checks are slow
- Only validate on-demand or in background jobs
- UI can handle missing images gracefully

### 5. Should we add `image_exists` field to API responses?
**Recommendation**: ⚠️ **OPTIONAL** (Phase 3)
- Useful for UI, but adds overhead
- Consider: Only add to single-product endpoint, not list endpoint
- Or: Make it opt-in via query parameter

---

## Error States Summary

| Scenario | Current Behavior | Recommended Phase 1 | Recommended Phase 4 |
|----------|-----------------|---------------------|---------------------|
| Product created without image | Uses placeholder (DB default) | ✅ Explicit validation + placeholder check | ✅ Same |
| Placeholder file missing | Broken image link | ❌ ERROR: Cannot create product | ✅ Auto-create placeholder |
| Custom image file missing | Broken image link | ⚠️ LOG WARNING | ⚠️ LOG + Auto-fallback (optional) |
| Image upload failure | Exception raised | ✅ Cleanup partial files | ✅ Same |

---

## Implementation Checklist

### Phase 1: Creation Validation (COMPLETE ✅)
- [x] Add placeholder file existence check in `product_service.create()`
- [x] Add auto-create placeholder logic if missing
- [x] Add explicit placeholder assignment if no image provided
- [x] Add error handling for missing placeholder
- [x] Update error messages
- [x] Add validation in product creation route

**Implementation Details**:
- Added `validate_placeholder_exists()` method to `ProductImageService`
- Added `ensure_placeholder_exists()` method that auto-creates placeholder if missing
- Added `validate_product_image_at_creation()` method that:
  - Validates placeholder exists if no custom image provided
  - Validates custom image exists if provided
  - Returns validated image metadata (path, URL, checksum)
- Overrode product creation endpoint in `route_factory.py` to validate images before creation
- Error handling:
  - If placeholder missing and cannot be created → HTTPException 500
  - If custom image provided but file missing → HTTPException 400

### Phase 2: Health Monitoring (OPTIONAL)
- [ ] Add startup validation for placeholder file
- [ ] Add health check endpoint (optional)
- [ ] Add logging/alerts for missing placeholder

### Phase 3: File Validation (OPTIONAL)
- [ ] Add optional `image_exists` field to enriched schema
- [ ] Add file existence check (Python, not SQL)
- [ ] Add warning logs for missing custom images
- [ ] Consider performance impact (caching, background checks)

### Phase 4: Auto-Recovery (FUTURE)
- [ ] Create background job for image validation
- [ ] Add auto-fallback logic (with approval)
- [ ] Add audit logging for recoveries
- [ ] Add admin alerts

---

## Recommendations

### Immediate Actions (Phase 1)
1. **Validate placeholder at product creation**: This prevents the most critical error scenario
2. **Auto-create placeholder if missing**: Ensures placeholder always exists
3. **Clear error messages**: Help developers/debuggers understand issues

### Future Enhancements (Phases 2-4)
1. **Health monitoring**: Early detection of issues
2. **Background validation**: Detect and recover from missing images
3. **Admin alerts**: Notify when manual intervention is needed

### Best Practices
1. **Defensive programming**: Always validate file existence at critical points
2. **Graceful degradation**: UI should handle missing images without crashing
3. **Audit logging**: Track all image-related changes for debugging
4. **Performance**: Avoid file system checks in hot paths (list endpoints)

---

## Questions to Consider

1. **Should placeholder be embedded in Docker image?**
   - Yes: Ensures it always exists in deployed environments
   - Consider: Version control for placeholder updates

2. **Should we version placeholder images?**
   - If placeholder design changes, should old products keep old placeholder?
   - Or: All products use latest placeholder?

3. **How to handle S3 migration?**
   - When moving to S3, how do we validate placeholder exists?
   - Should we store placeholder in S3 bucket and reference it?

4. **Alerting strategy?**
   - Email alerts for missing placeholder?
   - Slack/Discord notifications?
   - Dashboard visualization?

---

## Notes

- Current implementation already handles most cases gracefully via schema defaults
- Main risk is placeholder file being deleted after product creation
- Phase 1 (creation validation) addresses the highest-priority risk
- Phases 2-4 are quality-of-life improvements and can be implemented incrementally

