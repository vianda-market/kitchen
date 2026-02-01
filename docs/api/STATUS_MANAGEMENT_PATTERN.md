# Status Management Pattern

## Overview
All tables with a `status` field now follow a consistent pattern for managing record lifecycle:

1. **On Creation**: Status automatically set to `'Pending'`
2. **On Completion**: Status updated to `'Complete'` after downstream processing
3. **API Control**: Status field is removed from API input - controlled by system only

## Complete Flow Example: Plate Selection

### **🔄 Full Transaction Lifecycle:**

1. **Customer selects plate** → Creates `plate_selection` ✅
2. **System creates** `plate_pickup_live` with status 'Pending' ✅  
3. **System creates** `client_transaction` with status 'Pending' ✅
4. **🆕 System updates** subscription balance (deducts credits) ✅
5. **System marks** transaction as 'Complete' ✅

### **💰 Credit Flow:**

```python
# 1. Create transaction (Pending)
transaction_data = {
    "user_id": user_id,
    "source": "plate_selection",
    "credit": -8,  # Negative = deduction
    # ... other fields (status omitted)
}
# ✅ Status automatically set to 'Pending'

# 2. Update subscription balance
Subscription.update_balance(subscription_id, -8, user_id)
# ✅ Credits deducted from user's balance

# 3. Mark transaction complete
ClientTransaction.mark_complete(transaction_id, user_id)
# ✅ Status changes: Pending → Complete
```

## Implementation

### Base Model Changes
- Added `before_create()` hook that automatically sets `status = 'Pending'` for new records
- Status field is automatically managed, not controlled by API input

### New Methods Added

#### **Subscription Model**
- `get_by_user_id(user_id)` - Get user's active subscription
- `update_balance(subscription_id, credit_change, modified_by)` - Update balance

#### **Client Transaction Model**
- `mark_complete(transaction_id, modified_by)` - Mark transaction complete
- `get_pending_by_user(user_id)` - Get pending transactions

### Usage Example

#### Creating Records (Status Auto-Set)
```python
# Before (status field required in API)
transaction_data = {
    "user_id": user_id,
    "source": "plate_selection",
    "status": "Pending",  # ❌ No longer needed
    # ... other fields
}

# After (status automatically set)
transaction_data = {
    "user_id": user_id,
    "source": "plate_selection",
    # ... other fields (status omitted)
}
# ✅ Status automatically set to 'Pending'
```

#### Marking Records Complete
```python
# After downstream processing (e.g., subscription credits updated)
ClientTransaction.mark_complete(transaction_id, modified_by_user_id)
# Status changes from 'Pending' → 'Complete'
```

#### Finding Pending Records
```python
# Get all pending transactions for a user
pending_transactions = ClientTransaction.get_pending_by_user(user_id)
```

## Benefits

1. **Consistency**: All tables follow the same status lifecycle
2. **Data Integrity**: Status cannot be manipulated by API input
3. **Audit Trail**: Clear progression from Pending → Complete
4. **Error Prevention**: No risk of setting wrong status on creation
5. **🆕 Automatic Processing**: Subscription balance updates happen automatically
6. **🆕 Transaction Completeness**: Clear indication when credits are actually deducted

## Tables Using This Pattern

### **🆕 Enhanced Tracking with modified_date**

The `client_transaction` table now includes a `modified_date` field that automatically tracks when the status changes from 'Pending' to 'Complete'. This provides:

- **Latency Tracking**: Measure time between transaction creation and completion
- **Performance Monitoring**: Identify bottlenecks in credit processing
- **Audit Trail**: Clear record of when transactions were finalized
- **No History Table Needed**: For simple Pending→Complete workflows, `created_date` and `modified_date` provide sufficient tracking

### **When to Use History Tables vs. modified_date**

| Use Case | Approach | Example |
|----------|----------|---------|
| **Simple Status Changes** | `modified_date` only | `client_transaction` (Pending→Complete) |
| **Complex State Machines** | History table | `subscription_info` (multiple statuses, balance changes) |
| **Audit Requirements** | History table | `user_info` (regulatory compliance) |
| **Performance Monitoring** | `modified_date` + metrics | `plate_pickup_live` (timing analysis) |

### **Note for Development**

Since this is a local development environment, the `modified_date` column is included in the main schema file and will be automatically created when building the database from scratch.

- `client_transaction` - Credit transactions (Pending → Complete)
- `plate_pickup_live` - Plate pickup tracking (Pending → Complete)
- `plate_selection` - Customer plate selections (Pending → Complete)
- Any other table with a `status` field

## Migration Notes

- Existing code that manually sets `status: "Pending"` should remove this field
- Status will be automatically set by the base model
- Use `mark_complete()` method to update status after processing
- **🆕 Subscription balance updates are now automatic** after transaction creation 