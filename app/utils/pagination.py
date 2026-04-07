# app/utils/pagination.py
"""
Generic server-side pagination primitives.

Provides opt-in pagination for list endpoints via query params (page, page_size)
and response headers (X-Total-Count). Internal/cron callers never use these —
pagination only activates when explicit page/page_size are passed from routes.
"""

from dataclasses import dataclass
from typing import Optional
from fastapi import Query, Response


@dataclass(frozen=True)
class PaginationParams:
    """Validated, clamped pagination parameters."""
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedList(list):
    """A list that carries pagination metadata.

    Behaves exactly like a normal list so existing callers (services, crons)
    are unaffected. Routes that are pagination-aware read .total_count to
    set the X-Total-Count response header.
    """

    def __init__(self, items, *, total_count: int):
        super().__init__(items)
        self.total_count = total_count


def get_pagination_params(
    page: Optional[int] = Query(None, ge=1, description="1-based page number"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Rows per page (max 100)"),
) -> Optional[PaginationParams]:
    """FastAPI dependency that returns PaginationParams when both params are
    provided, or None when neither is (backward-compatible no-pagination mode).
    """
    if page is not None and page_size is not None:
        return PaginationParams(page=page, page_size=min(page_size, 100))
    return None


def set_pagination_headers(response: Response, result) -> None:
    """Set X-Total-Count header if the result carries pagination metadata."""
    if isinstance(result, PaginatedList):
        response.headers["X-Total-Count"] = str(result.total_count)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
