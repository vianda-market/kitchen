"""
Market Service

Handles business logic for market (country-based subscription regions) operations.
Markets define the countries where the platform operates, each with its own
currency, timezone, and subscription plans.
"""

from datetime import time
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from app.utils.db_pool import get_db_pool
from app.utils.log import logger
from app.config import Status

# Sentinel market for global scope (Internal Admin, Super Admin, Supplier Admin). Seeded in seed.sql; editable only by Super Admin.
GLOBAL_MARKET_ID = UUID("00000000-0000-0000-0000-000000000001")


def is_global_market(market_id: Optional[UUID]) -> bool:
    """Return True if market_id is the Global Marketplace sentinel."""
    return market_id is not None and market_id == GLOBAL_MARKET_ID


def default_language_for_country_code(country_code: str) -> str:
    """
    Default UI language for a market from ISO 3166-1 alpha-2 country code.
    AR/PE/CL/MX -> es; US/CA -> en; BR -> pt; else en.
    """
    cc = (country_code or "").strip().upper()
    if cc in ("AR", "PE", "CL", "MX"):
        return "es"
    if cc in ("US", "CA"):
        return "en"
    if cc == "BR":
        return "pt"
    return "en"


def reject_global_market_for_entity(market_id: Optional[UUID], entity_name: str) -> None:
    """
    Raise HTTP 400 if market_id is the Global Marketplace sentinel.
    Global Marketplace is only valid for user assignment (unrestricted query scope);
    it must not be assigned to plans, subscriptions, or other entities.
    """
    if market_id is not None and market_id == GLOBAL_MARKET_ID:
        raise HTTPException(
            status_code=400,
            detail=f"Global Marketplace cannot be assigned to {entity_name}. Use a market from GET /api/v1/leads/markets.",
        )


def _serialize_market(market: dict) -> dict:
    """Convert kitchen_close_time (time) to HH:MM string for API responses."""
    if not market:
        return market
    m = dict(market)
    kct = m.get("kitchen_close_time")
    if kct is not None and hasattr(kct, "strftime"):
        m["kitchen_close_time"] = kct.strftime("%H:%M")
    return m


class MarketService:
    """Service for managing markets (country-based subscription regions)"""

    def get_all(
        self,
        include_archived: bool = False,
        status: Optional[Status] = None
    ) -> List[dict]:
        """
        Retrieve all markets with optional filtering.
        
        Args:
            include_archived: Whether to include archived markets
            status: Optional status filter (Active/Inactive)
            
        Returns:
            List of market dictionaries
        """
        pool = get_db_pool()
        conn = pool.get_connection()
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT
                        m.market_id,
                        m.country_name,
                        m.country_code,
                        m.credit_currency_id,
                        c.currency_code,
                        c.currency_name,
                        m.timezone,
                        m.kitchen_close_time,
                        m.language,
                        m.phone_dial_code,
                        m.phone_local_digits,
                        m.is_archived,
                        m.status,
                        m.created_date,
                        m.modified_date
                    FROM market_info m
                    LEFT JOIN credit_currency_info c ON m.credit_currency_id = c.credit_currency_id
                    WHERE 1=1
                """
                params = []
                
                if not include_archived:
                    query += " AND m.is_archived = FALSE"
                
                if status:
                    query += " AND m.status = %s"
                    params.append(status.value)
                
                query += " ORDER BY country_name ASC"
                
                cur.execute(query, params)
                markets = cur.fetchall()
                
                logger.info(f"Retrieved {len(markets)} markets (include_archived={include_archived}, status={status})")
                return [_serialize_market(dict(market)) for market in markets]
                
        except Exception as e:
            logger.error(f"Error retrieving markets: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving markets: {str(e)}")
        finally:
            pool.return_connection(conn)

    def get_by_id(self, market_id: UUID) -> Optional[dict]:
        """
        Retrieve a specific market by ID.
        
        Args:
            market_id: UUID of the market
            
        Returns:
            Market dictionary or None if not found
        """
        pool = get_db_pool()
        conn = pool.get_connection()
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        m.market_id,
                        m.country_name,
                        m.country_code,
                        m.credit_currency_id,
                        c.currency_code,
                        c.currency_name,
                        m.timezone,
                        m.kitchen_close_time,
                        m.language,
                        m.phone_dial_code,
                        m.phone_local_digits,
                        m.is_archived,
                        m.status,
                        m.created_date,
                        m.modified_date
                    FROM market_info m
                    LEFT JOIN credit_currency_info c ON m.credit_currency_id = c.credit_currency_id
                    WHERE m.market_id = %s
                """, (str(market_id),))
                
                market = cur.fetchone()
                
                if market:
                    logger.info(f"Retrieved market: {market['country_name']} ({market_id})")
                    return _serialize_market(dict(market))
                else:
                    logger.warning(f"Market not found: {market_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving market {market_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving market: {str(e)}")
        finally:
            pool.return_connection(conn)

    def get_by_country_code(self, country_code: str) -> Optional[dict]:
        """
        Retrieve a market by country code.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code (e.g., 'AR', 'PE')
            
        Returns:
            Market dictionary or None if not found
        """
        pool = get_db_pool()
        conn = pool.get_connection()
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        m.market_id,
                        m.country_name,
                        m.country_code,
                        m.credit_currency_id,
                        c.currency_code,
                        c.currency_name,
                        m.timezone,
                        m.kitchen_close_time,
                        m.language,
                        m.phone_dial_code,
                        m.phone_local_digits,
                        m.is_archived,
                        m.status,
                        m.created_date,
                        m.modified_date
                    FROM market_info m
                    LEFT JOIN credit_currency_info c ON m.credit_currency_id = c.credit_currency_id
                    WHERE m.country_code = %s
                """, (country_code.upper(),))
                
                market = cur.fetchone()
                
                if market:
                    logger.info(f"Retrieved market by country code: {market['country_name']} ({country_code})")
                    return _serialize_market(dict(market))
                else:
                    logger.warning(f"Market not found for country code: {country_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving market by country code {country_code}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving market: {str(e)}")
        finally:
            pool.return_connection(conn)

    def create(
        self,
        country_name: str,
        country_code: str,
        credit_currency_id: UUID,
        timezone: str,
        modified_by: UUID,
        status: Status = Status.ACTIVE,
        kitchen_close_time: Optional[time] = None,
        language: Optional[str] = None,
    ) -> dict:
        """
        Create a new market.
        
        Args:
            country_name: Full country name
            country_code: ISO 3166-1 alpha-2 country code
            credit_currency_id: FK to credit_currency_info
            timezone: Timezone for this market
            modified_by: User ID creating the market
            status: Market status (default: Active)
            kitchen_close_time: Order cutoff time (default: 13:30)
            
        Returns:
            Created market dictionary with enriched currency info
        """
        pool = get_db_pool()
        conn = pool.get_connection()
        
        try:
            kct = kitchen_close_time if kitchen_close_time is not None else time(13, 30)
            lang = language if language is not None else default_language_for_country_code(country_code)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO market_info (
                        country_name,
                        country_code,
                        credit_currency_id,
                        timezone,
                        kitchen_close_time,
                        language,
                        status,
                        modified_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING 
                        market_id,
                        country_name,
                        country_code,
                        credit_currency_id,
                        timezone,
                        kitchen_close_time,
                        language,
                        is_archived,
                        status,
                        created_date,
                        modified_date
                """, (
                    country_name,
                    country_code.upper(),
                    str(credit_currency_id),
                    timezone,
                    kct,
                    lang,
                    status.value,
                    str(modified_by)
                ))
                
                market = cur.fetchone()
                conn.commit()
                
                # Fetch enriched market with currency info
                cur.execute("""
                    SELECT
                        m.market_id,
                        m.country_name,
                        m.country_code,
                        m.credit_currency_id,
                        c.currency_code,
                        c.currency_name,
                        m.timezone,
                        m.kitchen_close_time,
                        m.language,
                        m.phone_dial_code,
                        m.phone_local_digits,
                        m.is_archived,
                        m.status,
                        m.created_date,
                        m.modified_date
                    FROM market_info m
                    LEFT JOIN credit_currency_info c ON m.credit_currency_id = c.credit_currency_id
                    WHERE m.market_id = %s
                """, (market['market_id'],))
                
                enriched_market = cur.fetchone()
                
                logger.info(f"Created market: {country_name} ({country_code}) - {market['market_id']}")
                return _serialize_market(dict(enriched_market))
                
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            from app.utils.error_messages import handle_database_exception
            raise handle_database_exception(e, "create market")
        finally:
            pool.return_connection(conn)

    def update(
        self,
        market_id: UUID,
        modified_by: UUID,
        country_name: Optional[str] = None,
        country_code: Optional[str] = None,
        credit_currency_id: Optional[UUID] = None,
        timezone: Optional[str] = None,
        kitchen_close_time: Optional[time] = None,
        status: Optional[Status] = None,
        is_archived: Optional[bool] = None,
        language: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Update an existing market.
        
        Args:
            market_id: UUID of the market to update
            modified_by: User ID performing the update
            country_name: Optional new country name
            country_code: Optional new country code
            credit_currency_id: Optional new FK to credit_currency_info
            timezone: Optional new timezone
            kitchen_close_time: Optional new order cutoff time
            status: Optional new status
            is_archived: Optional archive status
            
        Returns:
            Updated market dictionary with enriched currency info or None if not found
        """
        pool = get_db_pool()
        conn = pool.get_connection()
        
        try:
            # Build dynamic UPDATE query
            updates = []
            params = []
            
            if country_name is not None:
                updates.append("country_name = %s")
                params.append(country_name)
            
            if country_code is not None:
                updates.append("country_code = %s")
                params.append(country_code.upper())
            
            if credit_currency_id is not None:
                updates.append("credit_currency_id = %s")
                params.append(str(credit_currency_id))
            
            if timezone is not None:
                updates.append("timezone = %s")
                params.append(timezone)
            
            if kitchen_close_time is not None:
                updates.append("kitchen_close_time = %s")
                params.append(kitchen_close_time)
            
            if status is not None:
                updates.append("status = %s")
                params.append(status.value)
            
            if is_archived is not None:
                updates.append("is_archived = %s")
                params.append(is_archived)

            if language is not None:
                updates.append("language = %s")
                params.append(language)
            
            if not updates:
                # No updates provided
                return self.get_by_id(market_id)
            
            updates.append("modified_by = %s")
            params.append(str(modified_by))
            
            updates.append("modified_date = CURRENT_TIMESTAMP")
            
            params.append(str(market_id))
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = f"""
                    UPDATE market_info
                    SET {', '.join(updates)}
                    WHERE market_id = %s
                    RETURNING market_id
                """
                
                cur.execute(query, params)
                market = cur.fetchone()
                
                if market:
                    conn.commit()
                    
                    # Fetch enriched market with currency info
                    enriched_market = self.get_by_id(market['market_id'])
                    logger.info(f"Updated market: {enriched_market['country_name']} ({market_id})")
                    return enriched_market
                else:
                    conn.rollback()
                    logger.warning(f"Market not found for update: {market_id}")
                    return None
                    
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating market {market_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating market: {str(e)}")
        finally:
            pool.return_connection(conn)


# Singleton instance
market_service = MarketService()
