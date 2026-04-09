"""
Restaurant explorer service for B2C explore-by-city flow.

- Cities for dropdown: use get_cities_with_coverage from city_metrics_service (city_info + has restaurant).
- get_restaurants_by_city(city, country_code, db, ...): list of restaurants in that city
  with name, cuisine, lat/lng for list and map; optional market filter and plates for a kitchen day.
- resolve_kitchen_day_for_explore(country_code, timezone_str, db): next available kitchen day (or today if still open).
"""

from typing import Optional, List, Any, Tuple
from datetime import datetime, date, timedelta, time
from uuid import UUID
import psycopg2.extensions
import pytz

from app.utils.db import db_read
from app.utils.address_formatting import format_street_display
from app.utils.portion_size import bucket_portion_size
from app.utils.cursor_pagination import slice_restaurants_by_cursor
from app.services.plate_review_service import get_plate_review_aggregates
from app.services.kitchen_day_service import (
    get_effective_current_day,
    is_today_kitchen_closed,
    VALID_KITCHEN_DAYS,
    WEEKDAY_NUM_TO_NAME,
)
from app.services.plate_selection_validation import _find_next_available_kitchen_day_in_week

WEEKDAY_NAME_TO_NUM = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}


def _parse_window_to_minutes(window: str) -> Optional[int]:
    """Parse 'HH:MM-HH:MM' to start minutes since midnight. Returns None if invalid."""
    try:
        parts = window.strip().split("-")
        if len(parts) != 2:
            return None
        start_part = parts[0].strip()
        h, m = map(int, start_part.split(":"))
        return h * 60 + m
    except (ValueError, AttributeError):
        return None


def _expand_flexible_windows(original_window: str, all_windows: List[str]) -> List[str]:
    """Given original window and all valid windows, return original + adjacent within ±30 min."""
    start_min = _parse_window_to_minutes(original_window)
    if start_min is None:
        return [original_window]
    out: List[str] = []
    for w in all_windows:
        w_min = _parse_window_to_minutes(w)
        if w_min is not None and abs(w_min - start_min) <= 30:
            out.append(w)
    return sorted(set(out), key=_parse_window_to_minutes) if out else [original_window]


def get_coworker_pickup_windows(
    restaurant_id: UUID,
    kitchen_day: str,
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> List[dict]:
    """
    Return pickup windows from coworkers (same employer) with offer/request for this restaurant+kitchen_day.
    Excludes users who opted out (coworkers_can_see_my_orders=false or can_participate_in_plate_pickups=false).
    When pickup_intent=request and flexible_on_time=true: expands ±30 min; marks original with flexible_on_time.
    Returns empty list when user has no employer.
    """
    if kitchen_day not in VALID_KITCHEN_DAYS:
        return []

    user_row = db_read(
        "SELECT employer_id, employer_address_id FROM user_info WHERE user_id = %s",
        (str(user_id),),
        connection=db,
        fetch_one=True,
    )
    if not user_row or not user_row.get("employer_id"):
        return []

    employer_id = user_row["employer_id"]
    employer_address_id = user_row.get("employer_address_id")

    # Get country_code from restaurant for market windows
    addr_row = db_read(
        """
        SELECT a.country_code FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        WHERE r.restaurant_id = %s
        """,
        (str(restaurant_id),),
        connection=db,
        fetch_one=True,
    )
    country_code = ((addr_row or {}).get("country_code") or "US").strip().upper()
    target_date = resolve_weekday_to_next_occurrence(kitchen_day, "UTC")
    all_windows = get_pickup_windows_for_kitchen_day(country_code, kitchen_day, target_date)
    if not all_windows:
        return []

    if employer_address_id is not None:
        sel_query = """
            SELECT ps.pickup_time_range, ps.pickup_intent, ps.flexible_on_time
            FROM plate_selection_info ps
            INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
            INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
            WHERE ps.restaurant_id = %s AND ps.kitchen_day = %s
              AND ps.pickup_intent IN ('offer', 'request') AND ps.is_archived = FALSE
              AND ump.coworkers_can_see_my_orders = TRUE
              AND ump.can_participate_in_plate_pickups = TRUE
              AND u_ps.employer_id = %s AND u_ps.employer_address_id = %s
        """
        params = (str(restaurant_id), kitchen_day, str(employer_id), str(employer_address_id))
    else:
        sel_query = """
            SELECT ps.pickup_time_range, ps.pickup_intent, ps.flexible_on_time
            FROM plate_selection_info ps
            INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
            INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
            WHERE ps.restaurant_id = %s AND ps.kitchen_day = %s
              AND ps.pickup_intent IN ('offer', 'request') AND ps.is_archived = FALSE
              AND ump.coworkers_can_see_my_orders = TRUE
              AND ump.can_participate_in_plate_pickups = TRUE
              AND u_ps.employer_id = %s AND u_ps.employer_address_id IS NULL
        """
        params = (str(restaurant_id), kitchen_day, str(employer_id))

    rows = db_read(sel_query, params, connection=db) or []
    seen: set = set()
    result: List[dict] = []
    for r in rows:
        ptr = (r.get("pickup_time_range") or "").strip()
        intent = (r.get("pickup_intent") or "self").strip()
        flexible = r.get("flexible_on_time") is True and intent == "request"
        if not ptr or intent not in ("offer", "request"):
            continue
        if flexible:
            expanded = _expand_flexible_windows(ptr, all_windows)
            for w in expanded:
                key = (w, intent)
                if key not in seen:
                    seen.add(key)
                    result.append({
                        "pickup_time_range": w,
                        "intent": intent,
                        "flexible_on_time": True if w == ptr else None,
                    })
        else:
            key = (ptr, intent)
            if key not in seen:
                seen.add(key)
                result.append({
                    "pickup_time_range": ptr,
                    "intent": intent,
                    "flexible_on_time": None,
                })
    return result


def _compute_savings_pct(plate_price: float, plate_credit: int, credit_cost_local_currency: float) -> int:
    """
    Compute savings percentage: (plate_price - plate_credit * credit_cost_local_currency) / plate_price * 100.
    Clamped to [0, 100]. Returns 0 if plate_price <= 0.
    """
    if plate_price <= 0:
        return 0
    raw = (plate_price - plate_credit * credit_cost_local_currency) / plate_price * 100
    return int(round(max(0.0, min(100.0, raw))))


def get_allowed_kitchen_date_range(timezone_str: str) -> Tuple[date, date]:
    """
    Allowed kitchen_day window: today (in market TZ) through next week's Friday inclusive.
    Returns (start_date, end_date) for validation.
    """
    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    today = datetime.now(tz).date()
    # Monday of current week (weekday 0 = Monday in Python)
    current_week_monday = today - timedelta(days=today.weekday())
    next_week_friday = current_week_monday + timedelta(days=7 + 4)  # next week's Friday
    return today, next_week_friday


def resolve_weekday_to_next_occurrence(weekday_name: str, timezone_str: str) -> date:
    """Return the next occurrence of the given weekday (Monday–Friday) from today in the given TZ."""
    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    today = datetime.now(tz).date()
    target = WEEKDAY_NAME_TO_NUM.get(weekday_name)
    if target is None:
        raise ValueError(f"Invalid kitchen_day: {weekday_name!r}")
    days_ahead = (target - today.weekday() + 7) % 7
    return today + timedelta(days=days_ahead)


def get_allowed_kitchen_days_sorted_by_date(
    timezone_str: str,
    country_code: Optional[str] = None,
) -> List[dict]:
    """
    Return the list of allowed kitchen days for the explore window (today through next week's Friday),
    ordered by date ascending (closest first). Each item has kitchen_day (weekday name) and date (ISO).
    Use for B2C explore kitchen-day dropdown; client can default to the first item.

    When country_code is provided and the market has kitchen_day_config, today is excluded from the
    list if the kitchen has already closed (e.g. after 1:30 PM local). For unknown markets or when
    country_code is omitted, today is always included (backward compatible).
    """
    start_date, end_date = get_allowed_kitchen_date_range(timezone_str or "UTC")
    out: List[dict] = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:  # Monday=0 .. Friday=4
            # Skip today if kitchen has closed (after cutoff in market timezone)
            if d == start_date and country_code and is_today_kitchen_closed(country_code, timezone_str):
                d += timedelta(days=1)
                continue
            out.append({
                "kitchen_day": WEEKDAY_NUM_TO_NAME[d.weekday()],
                "date": d.isoformat(),
            })
        d += timedelta(days=1)
    return out


def get_pickup_windows_for_kitchen_day(
    country_code: str,
    kitchen_day: str,
    target_date: date,
) -> List[str]:
    """
    Return 15-minute pickup windows for a given kitchen day and market, in market local time.

    Uses MarketConfiguration.business_hours for open/close. Windows are non-overlapping,
    from open to close, formatted as "HH:MM-HH:MM" (e.g. "11:30-11:45").

    Args:
        country_code: ISO country code (e.g. AR, US, PE)
        kitchen_day: Weekday name (Monday–Friday)
        target_date: The date for the kitchen day (used for validation; times are day-agnostic)

    Returns:
        List of window strings, or empty list if config missing or day not in business_hours.
    """
    from app.config.market_config import MarketConfiguration

    config = MarketConfiguration.get_market_config((country_code or "").strip().upper())
    if not config or not config.business_hours:
        return []
    day_hours = config.business_hours.get(kitchen_day)
    if not day_hours:
        return []
    open_t = day_hours.get("open")
    close_t = day_hours.get("close")
    if not isinstance(open_t, time) or not isinstance(close_t, time):
        return []
    if open_t >= close_t:
        return []

    windows: List[str] = []
    current_minutes = open_t.hour * 60 + open_t.minute
    close_minutes = close_t.hour * 60 + close_t.minute
    while current_minutes + 15 <= close_minutes:
        start_h = current_minutes // 60
        start_m = current_minutes % 60
        end_minutes = current_minutes + 15
        end_h = end_minutes // 60
        end_m = end_minutes % 60
        windows.append(f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}")
        current_minutes += 15
    return windows


def validate_kitchen_day_in_window(kitchen_day: str, timezone_str: str) -> None:
    """
    Validate that the given weekday (Monday–Friday) falls within the allowed window:
    this week and next week at most, with next week ending on Friday.
    Raises ValueError if kitchen_day is invalid or its next occurrence is after next week's Friday.
    """
    if kitchen_day not in VALID_KITCHEN_DAYS:
        raise ValueError(f"kitchen_day must be one of: {', '.join(VALID_KITCHEN_DAYS)}")
    start_date, end_date = get_allowed_kitchen_date_range(timezone_str)
    occurrence = resolve_weekday_to_next_occurrence(kitchen_day, timezone_str)
    if occurrence > end_date:
        raise ValueError(
            f"kitchen_day {kitchen_day!r} (date {occurrence}) is after the allowed window. "
            f"Allowed: from today ({start_date}) through next week's Friday ({end_date})."
        )


def resolve_kitchen_day_for_explore(
    country_code: str,
    timezone_str: str,
    db: psycopg2.extensions.connection,
) -> str:
    """
    Resolve the kitchen day to use for explore when the client does not send one.
    Returns today if it's a weekday and the kitchen is still open in the market's timezone;
    otherwise the next available weekday (e.g. Saturday -> Monday).
    """
    from app.config.market_config import MarketConfiguration

    current_day = get_effective_current_day(timezone_str or "UTC")
    config = MarketConfiguration.get_market_config((country_code or "").upper()) if country_code else None

    if current_day not in VALID_KITCHEN_DAYS:
        next_day = _find_next_available_kitchen_day_in_week(
            current_day, list(VALID_KITCHEN_DAYS), country_code, db
        )
        return next_day or "monday"

    if config and config.kitchen_day_config:
        day_config = config.kitchen_day_config.get(current_day)
        if day_config and day_config.get("enabled", True):
            try:
                tz = pytz.timezone(timezone_str)
            except Exception:
                tz = pytz.UTC
            now_local = datetime.now(tz)
            close_time = day_config.get("kitchen_close")
            if close_time and now_local.time() < close_time:
                return current_day

    next_day = _find_next_available_kitchen_day_in_week(
        current_day, list(VALID_KITCHEN_DAYS), country_code, db
    )
    return next_day or "monday"


def _build_lean_plate_dict(plate: dict) -> dict:
    """Build lean plate payload for by-city cards (modal fetches via enriched)."""
    return {
        "plate_id": plate["plate_id"],
        "product_name": plate.get("product_name") or "",
        "image_url": plate.get("image_url"),
        "credit": plate["credit"],
        "savings": plate.get("savings", 0),
        "is_recommended": plate.get("is_recommended", False),
        "is_favorite": plate.get("is_favorite", False),
        "is_already_reserved": plate.get("is_already_reserved", False),
        "existing_plate_selection_id": plate.get("existing_plate_selection_id"),
    }


def get_plates_for_restaurants(
    restaurant_ids: List[Any],
    kitchen_day: str,
    db: psycopg2.extensions.connection,
    *,
    favorite_plate_ids: Optional[List[UUID]] = None,
) -> dict:
    """
    Return map restaurant_id -> list of plates (plate_id, product_name, price, credit, kitchen_day,
    image_url from product_info). Savings are NOT read from DB; caller should compute from
    price, credit, and user's credit_cost_local_currency (see get_restaurants_by_city).
    Only non-archived plates with a matching plate_kitchen_day.
    """
    if not restaurant_ids or kitchen_day not in VALID_KITCHEN_DAYS:
        return {}
    ids_placeholder = ",".join("%s" for _ in restaurant_ids)
    query = """
        SELECT
            p.restaurant_id,
            p.plate_id,
            COALESCE(pr.name, '') AS product_name,
            p.price,
            p.credit,
            pkd.kitchen_day,
            COALESCE(pr.image_thumbnail_url, pr.image_url) AS image_url,
            pr.ingredients
        FROM plate_info p
        INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.kitchen_day = %s
          AND pkd.is_archived = FALSE AND pkd.status = 'active'
        INNER JOIN product_info pr ON pr.product_id = p.product_id AND pr.is_archived = FALSE
        WHERE p.restaurant_id IN (""" + ids_placeholder + """)
          AND p.is_archived = FALSE
        ORDER BY p.restaurant_id, pr.name
    """
    params = [kitchen_day] + [str(rid) for rid in restaurant_ids]
    rows = db_read(query, tuple(params), connection=db) or []
    by_restaurant: dict = {}
    plate_ids: List[Any] = []
    for row in rows:
        rid = row["restaurant_id"]
        plate_ids.append(row["plate_id"])
        if rid not in by_restaurant:
            by_restaurant[rid] = []
        fav_ids = set(str(x) for x in (favorite_plate_ids or []))
        by_restaurant[rid].append({
            "plate_id": row["plate_id"],
            "product_name": (row.get("product_name") or "").strip(),
            "price": float(row["price"]),
            "credit": int(row["credit"]),
            "kitchen_day": row["kitchen_day"],
            "image_url": (row.get("image_url") or "").strip() or None,
            "ingredients": (row.get("ingredients") or "").strip() or None,
            "savings": 0,  # Set by get_restaurants_by_city from credit_cost_local_currency
            "average_stars": None,
            "average_portion_size": None,
            "portion_size": "insufficient_reviews",
            "review_count": 0,
            "is_favorite": str(row["plate_id"]) in fav_ids,
        })
    # Merge review aggregates; apply minimum-threshold (5 reviews) and portion_size bucketing
    aggregates = get_plate_review_aggregates(plate_ids, db)
    for rid, plates in by_restaurant.items():
        for p in plates:
            pid_str = str(p["plate_id"])
            if pid_str in aggregates:
                agg = aggregates[pid_str]
                rc = agg["review_count"]
                p["review_count"] = rc
                if rc >= 5:
                    p["average_stars"] = agg["average_stars"]
                    p["average_portion_size"] = agg["average_portion_size"]
                    p["portion_size"] = bucket_portion_size(agg["average_portion_size"], rc)
                else:
                    p["average_stars"] = None
                    p["average_portion_size"] = None
                    p["portion_size"] = "insufficient_reviews"
            # else: no aggregates, keep defaults (averages=None, portion_size=insufficient_reviews)
    return by_restaurant


def get_restaurants_by_city(
    city: str,
    country_code: str,
    db: psycopg2.extensions.connection,
    *,
    timezone_str: Optional[str] = None,
    kitchen_day: Optional[str] = None,
    credit_cost_local_currency: Optional[float] = None,
    user_id: Optional[UUID] = None,
    employer_id: Optional[UUID] = None,
    employer_address_id: Optional[UUID] = None,
    locale: str = "en",
    cursor: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """
    Return restaurants in the given city (case-insensitive match) in the given country.
    Only restaurants with status = 'Active' and is_archived = FALSE are returned
    (Pending/Inactive or archived restaurants are excluded).
    Response: requested_city, city (matched), center (optional lat/lng), optional kitchen_day,
    and restaurants list with restaurant_id, name, cuisine, lat, lng, etc.
    When timezone_str is set and kitchen_day is omitted, resolve next available kitchen day.
    When kitchen_day is set (or resolved), attach plates for that day to each restaurant.
    credit_cost_local_currency: optional plan credit cost (local currency per credit); when set, savings
    are computed per plate; otherwise savings=0.
    user_id: optional; when set, favorites are surfaced at top and is_favorite set on items.
    employer_id, employer_address_id: optional; when set (user has employer), has_coworker_offer
    and has_coworker_request are computed per restaurant for coworker-scoped pickup intents.
    No institution scope; B2C explore by market (country + city).
    """
    country = (country_code or "").strip().upper()
    requested = (city or "").strip()

    # Resolve kitchen_day when not provided but we have market timezone (explore-with-plates flow)
    resolved_kitchen_day: Optional[str] = None
    if kitchen_day and kitchen_day in VALID_KITCHEN_DAYS:
        resolved_kitchen_day = kitchen_day
    elif timezone_str and country:
        resolved_kitchen_day = resolve_kitchen_day_for_explore(country, timezone_str, db)

    # 1) Check we have this city in this country (Active + plate_kitchen_days)
    query_cities = """
        SELECT DISTINCT TRIM(a.city) AS city
        FROM address_info a
        INNER JOIN restaurant_info r ON r.address_id = a.address_id
        WHERE a.country_code = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM plate_info p
            INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )
          AND TRIM(a.city) != ''
    """
    rows = db_read(query_cities, (country,), connection=db)
    cities = [r["city"] for r in rows] if rows else []
    matched_city = requested
    if requested and cities:
        requested_lower = requested.lower()
        for c in cities:
            if (c or "").strip().lower() == requested_lower:
                matched_city = (c or "").strip()
                break

    # 2) Restaurants in matched_city (Active + plate_kitchen_days) with geolocation and address line
    query_restaurants = """
        SELECT
            r.restaurant_id,
            r.name,
            COALESCE(cu.cuisine_name_i18n->>%s, cu.cuisine_name) AS cuisine_name,
            COALESCE(r.tagline_i18n->>%s, r.tagline) AS tagline,
            r.pickup_instructions,
            a.postal_code,
            TRIM(a.city) AS city,
            a.street_type::text AS street_type,
            a.street_name,
            a.building_number,
            g.latitude AS lat,
            g.longitude AS lng
        FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        LEFT JOIN cuisine cu ON r.cuisine_id = cu.cuisine_id
        LEFT JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE
        WHERE a.country_code = %s
          AND TRIM(a.city) = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM plate_info p
            INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )
        ORDER BY r.name
    """
    rest_rows = db_read(
        query_restaurants,
        (locale, locale, country, matched_city),
        connection=db,
    ) or []
    restaurants: List[dict] = []
    for row in rest_rows:
        restaurants.append({
            "restaurant_id": row["restaurant_id"],
            "name": row["name"] or "",
            "cuisine_name": row.get("cuisine_name"),
            "tagline": row.get("tagline"),
            "pickup_instructions": (row.get("pickup_instructions") or "").strip() or None,
            "lat": float(row["lat"]) if row.get("lat") is not None else None,
            "lng": float(row["lng"]) if row.get("lng") is not None else None,
            "postal_code": (row.get("postal_code") or "").strip() or None,
            "city": (row.get("city") or "").strip() or None,
            "street_type": (row.get("street_type") or "").strip() or None,
            "street_name": (row.get("street_name") or "").strip() or None,
            "building_number": (row.get("building_number") or "").strip() or None,
            "address_display": format_street_display(
                country,
                (row.get("street_type") or "").strip() or None,
                (row.get("street_name") or "").strip() or None,
                (row.get("building_number") or "").strip() or None,
            ),
            "plates": None,
            "has_volunteer": False,
            "has_coworker_offer": False,
            "has_coworker_request": False,
        })

        # 3) Plates for resolved/requested kitchen_day; compute savings from credit_cost_local_currency
    if resolved_kitchen_day and restaurants:
        rest_ids = [r["restaurant_id"] for r in restaurants]
        plates_by_restaurant = get_plates_for_restaurants(rest_ids, resolved_kitchen_day, db)
        for r in restaurants:
            plates = plates_by_restaurant.get(r["restaurant_id"]) or []
            for plate in plates:
                plate["savings"] = (
                    _compute_savings_pct(plate["price"], plate["credit"], credit_cost_local_currency)
                    if credit_cost_local_currency is not None else 0
                )
            r["plates"] = plates

        # 3.4) has_volunteer: at least one user has pickup_intent=offer for this restaurant + kitchen_day
        # Exclude users who opted out (coworkers_can_see_my_orders=false or can_participate_in_plate_pickups=false)
        rest_ids_str = [str(rid) for rid in rest_ids]
        vol_query = """
            SELECT DISTINCT ps.restaurant_id
            FROM plate_selection_info ps
            INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
            WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
              AND ps.pickup_intent = 'offer' AND ps.is_archived = FALSE
              AND ump.coworkers_can_see_my_orders = TRUE
              AND ump.can_participate_in_plate_pickups = TRUE
        """
        vol_rows = db_read(vol_query, (rest_ids_str, resolved_kitchen_day), connection=db) or []
        volunteer_rest_ids = {r["restaurant_id"] for r in vol_rows}
        for r in restaurants:
            r["has_volunteer"] = r["restaurant_id"] in volunteer_rest_ids

        # 3.41) has_coworker_offer, has_coworker_request: coworker-scoped when user has employer
        # Exclude current user's own offer/request so pills show only when another coworker has need
        if employer_id and resolved_kitchen_day:
            exclude_self_clause = " AND ps.user_id != %s" if user_id else ""
            if employer_address_id is not None:
                coworker_offer_query = """
                    SELECT DISTINCT ps.restaurant_id
                    FROM plate_selection_info ps
                    INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
                    INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
                    WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
                      AND ps.pickup_intent = 'offer' AND ps.is_archived = FALSE
                      AND ump.coworkers_can_see_my_orders = TRUE
                      AND ump.can_participate_in_plate_pickups = TRUE
                      AND u_ps.employer_id = %s AND u_ps.employer_address_id = %s
                """ + exclude_self_clause
                coworker_request_query = """
                    SELECT DISTINCT ps.restaurant_id
                    FROM plate_selection_info ps
                    INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
                    INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
                    WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
                      AND ps.pickup_intent = 'request' AND ps.is_archived = FALSE
                      AND ump.coworkers_can_see_my_orders = TRUE
                      AND ump.can_participate_in_plate_pickups = TRUE
                      AND u_ps.employer_id = %s AND u_ps.employer_address_id = %s
                """ + exclude_self_clause
                offer_params = (rest_ids_str, resolved_kitchen_day, str(employer_id), str(employer_address_id))
                request_params = (rest_ids_str, resolved_kitchen_day, str(employer_id), str(employer_address_id))
                if user_id:
                    offer_params += (str(user_id),)
                    request_params += (str(user_id),)
            else:
                coworker_offer_query = """
                    SELECT DISTINCT ps.restaurant_id
                    FROM plate_selection_info ps
                    INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
                    INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
                    WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
                      AND ps.pickup_intent = 'offer' AND ps.is_archived = FALSE
                      AND ump.coworkers_can_see_my_orders = TRUE
                      AND ump.can_participate_in_plate_pickups = TRUE
                      AND u_ps.employer_id = %s AND u_ps.employer_address_id IS NULL
                """ + exclude_self_clause
                coworker_request_query = """
                    SELECT DISTINCT ps.restaurant_id
                    FROM plate_selection_info ps
                    INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
                    INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
                    WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
                      AND ps.pickup_intent = 'request' AND ps.is_archived = FALSE
                      AND ump.coworkers_can_see_my_orders = TRUE
                      AND ump.can_participate_in_plate_pickups = TRUE
                      AND u_ps.employer_id = %s AND u_ps.employer_address_id IS NULL
                """ + exclude_self_clause
                offer_params = (rest_ids_str, resolved_kitchen_day, str(employer_id))
                request_params = (rest_ids_str, resolved_kitchen_day, str(employer_id))
                if user_id:
                    offer_params += (str(user_id),)
                    request_params += (str(user_id),)
            offer_rows = db_read(coworker_offer_query, offer_params, connection=db) or []
            request_rows = db_read(coworker_request_query, request_params, connection=db) or []
            coworker_offer_rest_ids = {r["restaurant_id"] for r in offer_rows}
            coworker_request_rest_ids = {r["restaurant_id"] for r in request_rows}
            for r in restaurants:
                r["has_coworker_offer"] = r["restaurant_id"] in coworker_offer_rest_ids
                r["has_coworker_request"] = r["restaurant_id"] in coworker_request_rest_ids

        # 3.45) is_already_reserved: when user_id + kitchen_day present, mark plates user has reserved
        reserved_plate_to_selection: dict = {}
        if user_id and resolved_kitchen_day:
            reserved_query = """
                SELECT plate_id, plate_selection_id FROM plate_selection_info
                WHERE user_id = %s AND kitchen_day = %s AND is_archived = FALSE
            """
            reserved_rows = db_read(
                reserved_query,
                (str(user_id), resolved_kitchen_day),
                connection=db,
            ) or []
            reserved_plate_to_selection = {
                str(r["plate_id"]): str(r["plate_selection_id"]) for r in reserved_rows
            }
        for r in restaurants:
            for p in (r.get("plates") or []):
                pid_str = str(p.get("plate_id", ""))
                if pid_str in reserved_plate_to_selection:
                    p["is_already_reserved"] = True
                    p["existing_plate_selection_id"] = reserved_plate_to_selection[pid_str]
                else:
                    p["is_already_reserved"] = False
                    p["existing_plate_selection_id"] = None

    # 3.5) Favorites (is_favorite for UI) + Recommendation layer (is_recommended, sort to top)
    if user_id:
        from app.services.favorite_service import get_favorite_ids
        from app.services.recommendation_service import apply_recommendation

        fav = get_favorite_ids(user_id, db)
        for r in restaurants:
            r["is_favorite"] = str(r["restaurant_id"]) in {str(rid) for rid in fav["restaurant_ids"]}
            for p in (r.get("plates") or []):
                p["is_favorite"] = str(p["plate_id"]) in {str(pid) for pid in fav["plate_ids"]}
        apply_recommendation(restaurants, user_id, db, favorite_ids=fav)
        for r in restaurants:
            plates = r.get("plates") or []
            plates.sort(
                key=lambda x: (
                    not x.get("is_recommended", False),
                    -(x.get("_recommendation_score", 0)),
                    (x.get("product_name") or "").lower(),
                )
            )
            r["plates"] = plates
        restaurants.sort(
            key=lambda x: (
                not x.get("is_recommended", False),
                -(x.get("_recommendation_score", 0)),
                (x.get("name") or "").lower(),
            )
        )
        # Narrow plates to lean payload after favorites/recommendation applied (modal fetches via enriched)
        for r in restaurants:
            r["plates"] = [_build_lean_plate_dict(p) for p in (r.get("plates") or [])]
    else:
        for r in restaurants:
            r["is_favorite"] = False
            r["is_recommended"] = False
            for p in (r.get("plates") or []):
                p["is_favorite"] = False
                p["is_recommended"] = False
        # Narrow plates to lean payload when no user (modal fetches via enriched)
        for r in restaurants:
            r["plates"] = [_build_lean_plate_dict(p) for p in (r.get("plates") or [])]

    # 5) Cursor pagination: slice the sorted list before building the response.
    page_restaurants, next_cursor, has_more = slice_restaurants_by_cursor(
        restaurants, cursor, limit,
    )
    restaurants = page_restaurants

    # 4) Center: avg lat/lng for the city (Active + plate_kitchen_days)
    # Skip center query on page 2+ — the frontend caches it from page 1.
    is_first_page = cursor is None
    center: Optional[dict] = None
    if is_first_page and matched_city and restaurants:
        query_center = """
            SELECT AVG(g.latitude) AS lat, AVG(g.longitude) AS lng
            FROM geolocation_info g
            INNER JOIN address_info a ON g.address_id = a.address_id
            INNER JOIN restaurant_info r ON r.address_id = a.address_id
            WHERE a.country_code = %s
              AND TRIM(a.city) = %s
              AND a.is_archived = FALSE
              AND r.is_archived = FALSE
              AND r.status = 'active'
              AND EXISTS (
                SELECT 1 FROM plate_info p
                INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
                WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
              )
              AND EXISTS (
                SELECT 1 FROM qr_code qc
                WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
              )
              AND g.is_archived = FALSE
        """
        center_row = db_read(
            query_center,
            (country, matched_city),
            connection=db,
            fetch_one=True,
        )
        if center_row and center_row.get("lat") is not None and center_row.get("lng") is not None:
            center = {"lat": float(center_row["lat"]), "lng": float(center_row["lng"])}

    # Fallback: when no center from restaurants, use city default (for users without default address)
    if is_first_page and center is None and matched_city and country:
        from app.config.supported_cities_default_location import get_city_default_location_by_name
        city_default = get_city_default_location_by_name(country, matched_city)
        if city_default:
            center = city_default

    out: dict[str, Any] = {
        "requested_city": requested or "",
        "city": matched_city or requested or "",
        "center": center,
        "restaurants": restaurants,
    }
    if resolved_kitchen_day:
        out["kitchen_day"] = resolved_kitchen_day
    out["next_cursor"] = next_cursor
    out["has_more"] = has_more
    return out
