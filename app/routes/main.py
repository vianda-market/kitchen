from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.utils.db_pool import get_db_pool
from app.utils.log import log_info
from app.utils.performance import monitor_endpoint
from app.services.error_handling import handle_business_operation
import psycopg2.extensions

router = APIRouter()

# Note: This router contains NON-VERSIONED infrastructure/monitoring endpoints only.
# All business API routes (including admin/super-admin discretionary) are versioned
# in application.py with the /api/v1/ prefix.
#
# Non-versioned endpoints (infrastructure/monitoring only):
# - / (root) - handled at app level
# - /health (health check) - handled at app level
# - /pool-stats (database pool statistics) - included below
#
# Versioned business endpoints in application.py:
# - /api/v1/admin/discretionary/ (admin discretionary management)
# - /api/v1/super-admin/discretionary/ (super-admin discretionary approval)
# - All other business APIs

@router.get("/pool-stats", include_in_schema=False)
async def get_pool_stats(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get connection pool statistics (admin only)"""
    def _get_pool_stats():
        pool = get_db_pool()
        stats = pool.get_pool_stats()
        
        if stats:
            return {
                "status": "success",
                "pool_stats": stats,
                "message": "Connection pool statistics retrieved successfully"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to retrieve pool statistics"
            }
    
    result = handle_business_operation(
        _get_pool_stats,
        "pool statistics retrieval"
    )
    
    if not result:
        return {
            "status": "error",
            "message": "Error retrieving pool statistics"
        }
    
    return result
