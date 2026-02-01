from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.utils.db_pool import get_db_pool
from app.utils.log import log_info
from app.utils.performance import monitor_endpoint
from app.services.error_handling import handle_business_operation
import psycopg2.extensions

# Import discretionary routes
from app.routes.admin.discretionary import router as admin_discretionary_router
from app.routes.super_admin.discretionary import router as super_admin_discretionary_router

router = APIRouter()

# Include discretionary routes
router.include_router(admin_discretionary_router)
router.include_router(super_admin_discretionary_router)

# Note: Root (/) and /health endpoints are handled at the app level (non-versioned)
# for infrastructure/monitoring purposes. They are available at:
# - / (root)
# - /health (health check)
# Business endpoints require versioning: /api/v1/...

@router.get("/pool-stats")
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
