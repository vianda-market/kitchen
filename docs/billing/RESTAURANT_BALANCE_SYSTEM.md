# Restaurant Balance Tracking System

## 📊 Overview

The Restaurant Balance Tracking System automatically calculates and maintains restaurant earnings and transaction counts whenever orders are placed or completed. It integrates seamlessly with the existing transaction flow to provide real-time financial tracking.

## 🏗️ System Architecture

### Core Components

1. **RestaurantBalance Model** (`app/models/restaurant_balance.py`)
   - Manages restaurant balance records in `restaurant_balance_info` table
   - Tracks monetary balance and transaction count per restaurant
   - Handles automatic balance updates and calculations

2. **Enhanced RestaurantTransaction Model** (`app/models/restaurant_transaction.py`)
   - Added `create_with_balance_update()` method for order placement
   - Added `mark_collected_with_balance_update()` method for order completion
   - Automatic balance adjustments for discounts and final amounts

3. **Database Integration**
   - `restaurant_balance_info` table schema
   - Primary key mapping in database utilities
   - Archival system integration for balance records

## 💰 Financial Calculation Logic

### Balance Formula
```
Monetary Amount = Credits × Credit Value
```

**Example:**
- Order: 8 credits
- Credit Value: $2.50 per credit
- **Calculated Amount: 8 × $2.50 = $20.00**

### Transaction Flow

#### 1. Order Placement (via `plate_selection.py`)
```python
RestaurantTransaction.create(transaction_data)
```

**What happens:**
1. Creates restaurant transaction record with status "Pending"
2. **NO restaurant balance update yet** - restaurant doesn't get paid until customer shows up
3. Transaction waits for customer arrival (QR scan)

#### 2. Customer Arrival - QR Scan (via `plate_pickup.py`)
```python
RestaurantTransaction.update_balance_on_arrival(transaction_id, arrival_time, user_id)
```

**What happens:**
1. Customer scans QR code at restaurant
2. Transaction status updated to "Arrived"
3. **Restaurant balance updated with FULL amount**: `credits × credit_value_local_currency`
4. Restaurant gets paid because customer actually showed up

#### 3. Order Completion (via `plate_pickup.py`)
```python
RestaurantTransaction.mark_collected_with_balance_update(
    transaction_id, completion_time, user_id, update_balance=True
)
```

**What happens:**
1. Marks transaction as collected and completed
2. Handles any final amount adjustments if needed
3. Balance already updated on arrival, so minimal changes here

#### 4. No-Show Processing (end of kitchen_day)
```python
RestaurantTransaction.process_no_show_balance_update(transaction_id, system_user_id)
```

**What happens:**
1. For orders still "Pending" at end of day (customer never arrived)
2. Restaurant gets **discounted amount** based on `no_show_discount` (configured at institution level, applied per transaction)
3. Transaction marked as "No-Show"
4. Example: 20% discount → restaurant gets 80% of original amount

## 🗄️ Database Schema

### restaurant_balance_info Table
```sql
CREATE TABLE restaurant_balance_info (
    restaurant_id UUID PRIMARY KEY,           -- Links to restaurant_info
    credit_currency_id UUID NOT NULL,         -- Currency used
    transaction_count INTEGER NOT NULL,       -- Total order count
    balance NUMERIC NOT NULL,                  -- Total earnings ($)
    currency_code VARCHAR(10) NOT NULL,       -- e.g., 'USD', 'EUR'
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 API Usage

### Create Transaction (No Balance Update)
```python
from app.models.restaurant_transaction import RestaurantTransaction

# Data structure (from plate selection)
transaction_data = {
    "transaction_id": pickup_id,
    "restaurant_id": restaurant_id,
    "credit": 8,                    # Credits ordered
    "currency_code": "USD",
    "credit_currency_id": currency_id,
    "final_amount": 20.00,          # Will be calculated
    "modified_by": user_id
}

# Creates transaction WITHOUT updating balance (waits for customer arrival)
transaction = RestaurantTransaction.create(transaction_data)
```

### Update Balance on Customer Arrival (QR Scan)
```python
# Customer arrives and scans QR - restaurant gets paid NOW
success = RestaurantTransaction.update_balance_on_arrival(
    transaction_id=transaction_id,
    arrival_time=datetime.now(),
    modified_by=user_id
)
```

### Process No-Show Orders
```python
# For orders where customer never arrived (end of kitchen_day)
success = RestaurantTransaction.process_no_show_balance_update(
    transaction_id=transaction_id,
    modified_by=system_user_id  # Automated process
)
```

### Complete Order
```python
# Mark as collected (balance already updated on arrival)
success = RestaurantTransaction.mark_collected_with_balance_update(
    transaction_id=transaction_id,
    collected_timestamp=completion_time,
    modified_by=user_id,
    update_balance=False  # Balance already correct from arrival
)
```

### Query Restaurant Earnings
```python
from app.models.restaurant_balance import RestaurantBalance

# Get total earnings
total_earnings = RestaurantBalance.get_total_earnings(restaurant_id)

# Get transaction count
order_count = RestaurantBalance.get_transaction_count(restaurant_id)

# Get full balance record
balance_record = RestaurantBalance.get_by_restaurant(restaurant_id)
```

## 🎯 Key Features

### ✅ Automatic Financial Tracking
- **Real-time balance updates** when orders are placed
- **Transaction count tracking** for order volume analytics
- **Monetary calculations** using credits × credit_value_local_currency formula

### ✅ Discount & Adjustment Handling
- **Final amount adjustments** for no-show discounts
- **Price difference reconciliation** between original and final amounts
- **Balance corrections** to maintain accurate financial records

### ✅ Multi-Currency Support
- **Currency-specific calculations** based on credit_currency_id
- **Proper decimal precision** using Python Decimal for financial accuracy
- **Currency code tracking** (USD, EUR, etc.)

### ✅ Integration & Consistency
- **Seamless integration** with existing transaction flow
- **Archival system support** for balance record lifecycle management
- **Database utilities integration** with proper primary key mapping

## 📈 Business Impact

### For Restaurants
- **Real-time earnings tracking** without manual calculations
- **Order volume analytics** via transaction counts
- **Accurate financial records** for business planning

### For Platform
- **Automated financial reconciliation** reduces manual processing
- **Scalable balance tracking** as more restaurants join
- **Audit trail preservation** through transaction history

## 🔄 Workflow Integration

### Current Integration Points

1. **Order Placement** (`app/routes/plate_selection.py`)
   - Line ~147: Now uses `create_with_balance_update()`
   - Automatically calculates and updates restaurant balance

2. **Order Completion** (`app/routes/plate_pickup.py`)
   - Line ~239: Now uses `mark_collected_with_balance_update()`
   - Handles final amount adjustments for accurate balances

3. **Archival System** (`app/services/archival.py`)
   - Restaurant balance records included in automated archival
   - Proper retention policy for financial data compliance

## 🧪 Testing & Validation

The system has been tested for:
- ✅ **Balance calculation accuracy** (credits × credit_value_local_currency)
- ✅ **Method existence and signatures**
- ✅ **Transaction flow simulation**
- ✅ **Archival system integration**
- ✅ **Database utility compatibility**

## 🚀 Production Readiness

### Deployment Checklist
- [x] Database schema includes `restaurant_balance_info` table
- [x] Primary key mapping updated in `app/utils/db.py`
- [x] RestaurantBalance model implements BaseModelCRUD
- [x] Enhanced RestaurantTransaction methods available
- [x] Integration points updated (plate_selection.py, plate_pickup.py)
- [x] Archival system includes restaurant balance records
- [x] Comprehensive testing completed

### Performance Considerations
- **Efficient queries**: Balance lookups use restaurant_id primary key
- **Minimal overhead**: Balance updates happen only during transaction events
- **Decimal precision**: Financial calculations use proper decimal types
- **Database optimization**: Leverages existing transaction processing flow

---

## 📞 Usage Examples

### Example 1: Restaurant with 5 orders
```
Orders: 5 × 8 credits each = 40 total credits
Credit Value: $2.50 per credit
Expected Balance: 40 × $2.50 = $100.00
Transaction Count: 5
```

### Example 2: Order with discount
```
Original: 10 credits × $3.00 = $30.00
Discount Applied: 20% no-show discount
Final Amount: $24.00
Balance Adjustment: $24.00 - $30.00 = -$6.00 (corrected automatically)
```

The Restaurant Balance Tracking System provides a robust, automated solution for financial tracking that scales with your platform's growth while maintaining accuracy and audit compliance. 