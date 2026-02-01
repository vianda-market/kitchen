# Performance Monitoring Strategy

This document outlines the log-based performance monitoring approach used in the Kitchen API.

## Overview

Instead of complex middleware-based query counting, we use **structured logging** and **log analysis** to monitor performance. This approach is:
- ✅ **More reliable** - No complex middleware to debug
- ✅ **Easier to maintain** - Standard logging practices
- ✅ **Better performance** - No overhead from query counting
- ✅ **Richer insights** - Actual execution times, not just counts

## What We Monitor

### 1. Database Operations
- **Query execution time** - All database queries are timed
- **Slow query detection** - Queries taking >1 second are flagged
- **Operation types** - INSERT, UPDATE, DELETE, archival operations
- **Table performance** - Which tables are slowest

### 2. API Endpoints
- **Response times** - How long each endpoint takes
- **Slow endpoint detection** - Endpoints taking >2 seconds are flagged
- **Error tracking** - Failed requests and their timing
- **Usage patterns** - Most/least used endpoints

### 3. System Resources
- **Database connections** - Connection pool usage
- **Memory consumption** - Process memory usage
- **Error rates** - 4xx/5xx response distribution

## How It Works

### Database Timing
```python
# In app/utils/db.py
def db_read(query: str, values: tuple = None, connection=None, fetch_one: bool = False):
    start_time = time.time()
    try:
        # ... execute query ...
        execution_time = time.time() - start_time
        
        log_info(f"📊 Query executed in {execution_time:.3f}s: {query[:100]}...")
        
        if execution_time > 1.0:  # Log slow queries
            log_warning(f"🐌 Slow query detected: {execution_time:.3f}s - {query}")
```

### Endpoint Monitoring
```python
# In route files
from app.utils.performance import monitor_endpoint

@monitor_endpoint(threshold=1.0)
async def my_endpoint():
    # ... endpoint logic ...
    return result
```

### Database Operation Monitoring
```python
from app.utils.performance import monitor_database_operation

async def my_function():
    with monitor_database_operation("User Lookup"):
        # ... database operations ...
```

## Log Analysis

### Performance Analysis Script
```bash
# Analyze application logs
python scripts/analyze_performance.py app.log

# With custom slow threshold
python scripts/analyze_performance.py app.log --slow-threshold 0.5
```

### What the Script Shows
- **Slow queries** - Queries taking >1 second
- **Slow operations** - INSERT/UPDATE/DELETE operations
- **Query performance** - Average, min, max execution times
- **Endpoint performance** - Response times per endpoint
- **Error analysis** - Common error patterns

## Log Patterns

### Database Operations
```
📊 Query executed in 0.045s: SELECT role_id, role_type, name...
🐌 Slow query detected: 1.234s - SELECT * FROM large_table WHERE...
📊 INSERT executed in 0.023s
🐌 Slow INSERT detected: 1.567s - user_info
```

### Endpoint Performance
```
🌐 /auth/token completed in 0.156s
🐌 Slow endpoint detected: /large-report took 2.345s
❌ /api/endpoint failed after 0.234s: Database connection error
```

## Configuration

### PostgreSQL Slow Query Logging
```sql
-- Enable in postgresql.conf
log_min_duration_statement = 1000  -- Log queries taking >1 second
log_statement = 'all'              -- Log all statements
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

### Application Logging
```python
# Logging configuration in application.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Best Practices

### 1. Use Decorators for Endpoints
```python
@monitor_endpoint(threshold=1.0)
async def important_endpoint():
    # ... logic ...
```

### 2. Monitor Database Operations
```python
with monitor_database_operation("Complex Join"):
    # ... database operations ...
```

### 3. Regular Log Analysis
- Run performance analysis weekly
- Monitor slow query trends
- Track endpoint performance over time
- Set up alerts for performance degradation

### 4. Database Optimization
- Use the slow query logs to identify bottlenecks
- Add indexes for slow queries
- Optimize table structures
- Monitor connection pool usage

## Benefits Over Query Counting

| Aspect | Query Counting | Log-Based Monitoring |
|--------|----------------|---------------------|
| **Reliability** | ❌ Complex middleware | ✅ Standard logging |
| **Performance** | ❌ Overhead from counting | ✅ Minimal overhead |
| **Insights** | ❌ Just query counts | ✅ Actual execution times |
| **Debugging** | ❌ Hard to troubleshoot | ✅ Clear, structured logs |
| **Maintenance** | ❌ Complex code to maintain | ✅ Simple logging calls |
| **Production** | ❌ May break in production | ✅ Works everywhere |

## Future Enhancements

### 1. Real-Time Monitoring
- Log aggregation with ELK stack
- Real-time performance dashboards
- Automated alerting for slow operations

### 2. Advanced Analytics
- Performance trend analysis
- Predictive performance modeling
- Resource usage forecasting

### 3. Integration
- Prometheus metrics export
- Grafana dashboards
- Slack/Teams notifications

## Conclusion

This log-based approach provides **better insights** with **less complexity** than the previous query counting middleware. It's more reliable, easier to maintain, and gives you actual performance data instead of just counts.

The key is to **use the decorators consistently** and **analyze logs regularly** to identify and fix performance bottlenecks. 