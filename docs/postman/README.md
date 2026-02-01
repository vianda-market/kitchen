# Postman Collections & Documentation

This directory contains Postman collections for API testing and their associated documentation.

## 📁 Directory Structure

### Collections (`.json` files)
- **`Permissions Testing - Employee-Only Access.postman_collection.json`** - Comprehensive permissions testing for all role combinations
- **`DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`** - End-to-end testing for discretionary credit system
- **`E2E Plate Selection.postman_collection.json`** - Complete plate selection workflow testing
- **`INSTITUTION_BANK_ACCOUNT_POSTMAN_COLLECTION.json`** - Institution bank account API testing

### Documentation

#### `guidelines/` - Active Documentation
Contains current, relevant guides for using the Postman collections:
- **`ROLE_COVERAGE_ANALYSIS.md`** - Test coverage analysis and roadmap for role-based permissions
- **`PERMISSIONS_TESTING_GUIDE.md`** - Guide for the Permissions Testing collection
- **`DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md`** - Guide for the Discretionary Credit System collection
- **`QUICK_SETUP_GUIDE.md`** - Quick setup instructions
- **`INSTITUTION_BANK_ACCOUNT_POSTMAN_SCRIPTS.md`** - Scripts and examples for institution bank account testing
- **`POSTMAN_INSTITUTION_BANK_ACCOUNT_SCRIPTS.md`** - Additional institution bank account scripts
- **`POSTMAN_INSTITUTION_ENTITY_SCRIPTS.md`** - Institution entity API scripts
- **`POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS.md`** - Payment attempt API scripts

#### `../zArchive/postman/` - Archived Documentation
Contains historical/outdated documentation that has been superseded:
- **`POSTMAN_COLLECTION_FIXES.md`** - Historical fixes (already applied)
- **`POSTMAN_E2E_API_CALLS.md`** - Incomplete template (contains "TO BE FILLED" placeholders)
- **`POSTMAN_E2E_API_CALLS_TEMPLATE.md`** - Outdated template file
- **`setup_discretionary_testing.md`** - Redundant setup guide (covered by QUICK_SETUP_GUIDE.md and DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md)

## 🚀 Quick Start

1. **Import Collections**: Import the `.json` files into Postman
2. **Set Environment Variables**: See individual collection guides in `guidelines/`
3. **Run Tests**: Execute collections in the order specified in their guides

## 📚 Documentation by Collection

### Permissions Testing Collection
- **Guide**: `guidelines/PERMISSIONS_TESTING_GUIDE.md`
- **Coverage Analysis**: `guidelines/ROLE_COVERAGE_ANALYSIS.md`
- **Purpose**: Tests role-based access control for all role combinations

### Discretionary Credit System Collection
- **Guide**: `guidelines/DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md`
- **Quick Setup**: `guidelines/QUICK_SETUP_GUIDE.md`
- **Purpose**: End-to-end testing of discretionary credit workflows

### E2E Plate Selection Collection
- **Purpose**: Complete workflow testing for plate selection process
- **Note**: See collection description for usage instructions

### Institution Bank Account Collection
- **Scripts**: `guidelines/INSTITUTION_BANK_ACCOUNT_POSTMAN_SCRIPTS.md`
- **Purpose**: Testing institution bank account management APIs

## 🔄 Recent Updates

### Phase 3 Scope Logic Implementation (Completed)
- Added Employee Operator blocking tests for:
  - `DELETE /users/{user_id}`
  - `GET /users/enriched/{user_id}`
  - `DELETE /addresses/{address_id}`
- Added address creation request for test setup
- All tests verify 403 Forbidden responses for unauthorized access

## 📝 Notes

- All collections use **collection variables** (not environment variables) for tokens and IDs
- Token management follows the pattern: `{roleType}{roleName}Token`
- Collections are self-contained and can run independently after initial setup

