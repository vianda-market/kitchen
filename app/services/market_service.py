"""
Market Service

Handles business logic for market (country-based subscription regions) operations.
Markets define the countries where the platform operates, each with its own
currency and subscription plans. Operational timezone now lives on address_info
per-restaurant (see docs/plans/country_city_data_structure.md — PR2 migration).

Country name is derived via JOIN to external.geonames_country; currency name via
JOIN to external.iso4217_currency. The deprecated market_info.country_name /
timezone and currency_metadata.currency_name compatibility columns are no longer
read by this module.
"""

from uuid import UUID

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from app.config import Status
from app.utils.db import db_read
from app.utils.db_pool import get_db_pool
from app.utils.log import logger

# Sentinel market for global scope (Internal Admin, Super Admin, Supplier Admin). Seeded in seed.sql; editable only by Super Admin.
GLOBAL_MARKET_ID = UUID("00000000-0000-0000-0000-000000000001")

# Shared SELECT column list used by get_all / get_by_id / get_by_country_code / create-enrich / update-enrich.
# Joins:
#   m  core.market_info (primary)
#   c  core.currency_metadata (Vianda pricing policy, FK via currency_metadata_id)
#   gc external.geonames_country (authoritative country name, JOIN by country_code = iso_alpha2)
#   ic external.iso4217_currency (authoritative currency name, JOIN by currency_code)
_MARKET_ENRICHED_COLUMNS = """
            m.market_id,
            gc.name AS country_name,
            m.country_code,
            m.currency_metadata_id,
            c.currency_code,
            ic.name AS currency_name,
            c.credit_value_local_currency,
            c.currency_conversion_usd,
            m.language,
            m.phone_dial_code,
            m.phone_local_digits,
            m.is_archived,
            m.status,
            m.created_date,
            m.modified_date
"""

_MARKET_ENRICHED_FROM = """
        FROM core.market_info m
        LEFT JOIN core.currency_metadata c ON m.currency_metadata_id = c.currency_metadata_id
        LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
        LEFT JOIN external.iso4217_currency ic ON ic.code = c.currency_code
"""


def is_global_market(market_id: UUID | None) -> bool:
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


def reject_global_market_for_entity(market_id: UUID | None, entity_name: str) -> None:
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
    """Serialize market dict for API responses. Enriches with tax_id hints from config."""
    if not market:
        return market
    result = dict(market)
    from app.config.tax_id_config import get_tax_id_config

    tax_cfg = get_tax_id_config(result.get("country_code", ""))
    result["tax_id_label"] = tax_cfg["label"] if tax_cfg else None
    result["tax_id_mask"] = tax_cfg["mask"] if tax_cfg else None
    result["tax_id_regex"] = tax_cfg["regex"] if tax_cfg else None
    result["tax_id_example"] = tax_cfg["example"] if tax_cfg else None
    return result


def market_has_active_plate_coverage(market_id: UUID, db) -> bool:
    """
    True when the market has at least one institution → restaurant → plate → plate_kitchen_days
    chain, all active and non-archived. Mirrors the EXISTS subquery in get_markets_with_coverage
    and is the shared "operational coverage" predicate used by both the /leads/countries filter
    and admin status override validation.

    Weekly recurring coverage (plate_kitchen_days is day-of-week) means a single active row
    implies continuous forward coverage. A calendar-date refinement (e.g. "active in the next
    30 days") is tracked in docs/plans/market-status-cron.md.
    """
    row = db_read(
        """
        SELECT EXISTS (
            SELECT 1
            FROM core.institution_market im_sub
            JOIN core.institution_info i ON i.institution_id = im_sub.institution_id
            JOIN ops.restaurant_info r ON r.institution_id = i.institution_id
            JOIN ops.plate_info p ON p.restaurant_id = r.restaurant_id
            JOIN ops.plate_kitchen_days pkd ON pkd.plate_id = p.plate_id
            WHERE im_sub.market_id = %s
              AND i.status = 'active' AND i.is_archived = FALSE
              AND r.status = 'active' AND r.is_archived = FALSE
              AND p.is_archived = FALSE
              AND pkd.status = 'active' AND pkd.is_archived = FALSE
        ) AS has_coverage
        """,
        (str(market_id),),
        connection=db,
        fetch_one=True,
    )
    return bool(row and row["has_coverage"])


def get_markets_with_coverage(db) -> list[dict]:
    """
    Return active non-global markets that have at least one
    institution -> restaurant -> plate -> plate_kitchen_days chain, all active.
    Used by GET /leads/markets (default, no audience param).
    """
    query = """
        SELECT m.country_code, gc.name AS country_name, m.language,
               m.phone_dial_code, m.phone_local_digits
        FROM core.market_info m
        LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
        WHERE m.status = 'active'
          AND m.is_archived = FALSE
          AND m.market_id != %s
          AND EXISTS (
              SELECT 1
              FROM core.institution_market im_sub
              JOIN core.institution_info i ON i.institution_id = im_sub.institution_id
              JOIN ops.restaurant_info r ON r.institution_id = i.institution_id
              JOIN ops.plate_info p ON p.restaurant_id = r.restaurant_id
              JOIN ops.plate_kitchen_days pkd ON pkd.plate_id = p.plate_id
              WHERE im_sub.market_id = m.market_id
                AND i.status = 'active' AND i.is_archived = FALSE
                AND r.status = 'active' AND r.is_archived = FALSE
                AND p.is_archived = FALSE
                AND pkd.status = 'active' AND pkd.is_archived = FALSE
          )
        ORDER BY gc.name
    """
    rows = db_read(query, (str(GLOBAL_MARKET_ID),), connection=db)
    return [dict(r) for r in rows] if rows else []


class MarketService:
    """Service for managing markets (country-based subscription regions)"""

    def get_all(self, include_archived: bool = False, status: Status | None = None) -> list[dict]:
        """
        Retrieve all markets with optional filtering.

        Args:
            include_archived: Whether to include archived markets
            status: Optional status filter (Active/Inactive)

        Returns:
            List of market dictionaries (country_name enriched from external.geonames_country)
        """
        pool = get_db_pool()
        conn = pool.get_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = f"""
                    SELECT
                        {_MARKET_ENRICHED_COLUMNS}
                    {_MARKET_ENRICHED_FROM}
                    WHERE 1=1
                """
                params = []

                if not include_archived:
                    query += " AND m.is_archived = FALSE"

                if status:
                    query += " AND m.status = %s"
                    params.append(status.value)

                query += " ORDER BY gc.name ASC"

                cur.execute(query, params)
                markets = cur.fetchall()

                logger.info(f"Retrieved {len(markets)} markets (include_archived={include_archived}, status={status})")
                return [_serialize_market(dict(market)) for market in markets]

        except Exception as e:
            logger.error(f"Error retrieving markets: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving markets: {str(e)}") from None
        finally:
            pool.return_connection(conn)

    def get_by_id(self, market_id: UUID) -> dict | None:
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
                cur.execute(
                    f"""
                    SELECT
                        {_MARKET_ENRICHED_COLUMNS}
                    {_MARKET_ENRICHED_FROM}
                    WHERE m.market_id = %s
                """,
                    (str(market_id),),
                )

                market = cur.fetchone()

                if market:
                    logger.info(f"Retrieved market: {market['country_name']} ({market_id})")
                    return _serialize_market(dict(market))
                logger.warning(f"Market not found: {market_id}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving market {market_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving market: {str(e)}") from None
        finally:
            pool.return_connection(conn)

    def get_by_country_code(self, country_code: str) -> dict | None:
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
                cur.execute(
                    f"""
                    SELECT
                        {_MARKET_ENRICHED_COLUMNS}
                    {_MARKET_ENRICHED_FROM}
                    WHERE m.country_code = %s
                """,
                    (country_code.upper(),),
                )

                market = cur.fetchone()

                if market:
                    logger.info(f"Retrieved market by country code: {market['country_name']} ({country_code})")
                    return _serialize_market(dict(market))
                logger.warning(f"Market not found for country code: {country_code}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving market by country code {country_code}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving market: {str(e)}") from None
        finally:
            pool.return_connection(conn)

    def create(
        self,
        country_code: str,
        currency_metadata_id: UUID,
        modified_by: UUID,
        status: Status = Status.ACTIVE,
        language: str | None = None,
        billing_config: dict | None = None,
        # --- Accepted-and-ignored for backward compat during PR2 migration (country_name/timezone columns retired) ---
        country_name: str | None = None,
        timezone: str | None = None,
    ) -> dict:
        """
        Create a new market.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (name derived via external.geonames_country)
            currency_metadata_id: FK to currency_metadata
            modified_by: User ID creating the market
            status: Market status (default: Active)
            language: Default UI locale (default: derived from country_code)
            billing_config: Optional market_payout_aggregator config (includes kitchen hours defaults)

        Deprecated kwargs (accepted but ignored — the market_info.country_name and
        timezone columns are retired. country_name resolves via the external.geonames_country
        FK join; timezone is per-restaurant on address_info):
            country_name: ignored
            timezone: ignored

        Returns:
            Created market dictionary with enriched currency info
        """
        del country_name, timezone  # explicit: compat kwargs intentionally unused
        pool = get_db_pool()
        conn = pool.get_connection()

        try:
            lang = language if language is not None else default_language_for_country_code(country_code)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO core.market_info (
                        country_code,
                        currency_metadata_id,
                        language,
                        status,
                        modified_by
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING market_id
                """,
                    (country_code.upper(), str(currency_metadata_id), lang, status.value, str(modified_by)),
                )

                new_row = cur.fetchone()
                new_market_id = new_row["market_id"]

                # Auto-create billing config for non-global markets
                if not is_global_market(new_market_id):
                    bc = billing_config or {}
                    cur.execute(
                        """
                        INSERT INTO billing.market_payout_aggregator (
                            market_id, aggregator, is_active, require_invoice,
                            max_unmatched_bill_days, kitchen_open_time, kitchen_close_time,
                            notes, modified_by
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            str(new_market_id),
                            bc.get("aggregator", "stripe"),
                            bc.get("is_active", True),
                            bc.get("require_invoice", False),
                            bc.get("max_unmatched_bill_days", 30),
                            bc.get("kitchen_open_time", "09:00"),
                            bc.get("kitchen_close_time", "13:30"),
                            bc.get("notes"),
                            str(modified_by),
                        ),
                    )

                conn.commit()

                # Fetch enriched market with currency info + joined country name
                cur.execute(
                    f"""
                    SELECT
                        {_MARKET_ENRICHED_COLUMNS}
                    {_MARKET_ENRICHED_FROM}
                    WHERE m.market_id = %s
                """,
                    (new_market_id,),
                )

                enriched_market = cur.fetchone()

                logger.info(
                    f"Created market: {enriched_market['country_name']} ({country_code}) - {enriched_market['market_id']}"
                )
                return _serialize_market(dict(enriched_market))

        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            from app.utils.error_messages import handle_database_exception

            raise handle_database_exception(e, "create market") from e
        finally:
            pool.return_connection(conn)

    def update(
        self,
        market_id: UUID,
        modified_by: UUID,
        country_code: str | None = None,
        currency_metadata_id: UUID | None = None,
        status: Status | None = None,
        is_archived: bool | None = None,
        language: str | None = None,
        # --- Accepted-and-ignored for backward compat during PR2 migration ---
        country_name: str | None = None,
        timezone: str | None = None,
    ) -> dict | None:
        """
        Update an existing market.

        Args:
            market_id: UUID of the market to update
            modified_by: User ID performing the update
            country_code: Optional new country code
            currency_metadata_id: Optional new FK to currency_metadata
            status: Optional new status
            is_archived: Optional archive status
            language: Optional new default locale

        Deprecated kwargs (accepted but ignored — see create() docstring):
            country_name: ignored
            timezone: ignored

        Returns:
            Updated market dictionary with enriched currency info or None if not found
        """
        del country_name, timezone  # explicit: compat kwargs intentionally unused
        pool = get_db_pool()
        conn = pool.get_connection()

        try:
            # Build dynamic UPDATE query
            updates = []
            params = []

            if country_code is not None:
                updates.append("country_code = %s")
                params.append(country_code.upper())

            if currency_metadata_id is not None:
                updates.append("currency_metadata_id = %s")
                params.append(str(currency_metadata_id))

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
                    UPDATE core.market_info
                    SET {", ".join(updates)}
                    WHERE market_id = %s
                    RETURNING market_id
                """

                cur.execute(query, params)
                market = cur.fetchone()

                if market:
                    conn.commit()

                    # Fetch enriched market with currency info
                    enriched_market = self.get_by_id(market["market_id"])
                    logger.info(f"Updated market: {enriched_market['country_name']} ({market_id})")
                    return enriched_market
                conn.rollback()
                logger.warning(f"Market not found for update: {market_id}")
                return None

        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating market {market_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating market: {str(e)}") from None
        finally:
            pool.return_connection(conn)

    def get_billing_config(self, market_id: UUID, db) -> dict | None:
        """Get billing configuration for a market."""
        row = db_read(
            """SELECT market_id, aggregator, is_active, require_invoice,
                      max_unmatched_bill_days, kitchen_open_time, kitchen_close_time,
                      notes, is_archived, status,
                      created_date, modified_by, modified_date
               FROM billing.market_payout_aggregator
               WHERE market_id = %s AND is_archived = FALSE""",
            (str(market_id),),
            connection=db,
            fetch_one=True,
        )
        if not row:
            return None
        result = dict(row)
        # Serialize time objects to HH:MM for API responses
        for field in ("kitchen_open_time", "kitchen_close_time"):
            v = result.get(field)
            if v is not None and hasattr(v, "strftime"):
                result[field] = v.strftime("%H:%M")
        return result

    def update_billing_config(self, market_id: UUID, data: dict, modified_by: UUID, db) -> dict | None:
        """Update billing configuration for a market. Returns updated row or None."""
        # Verify market and billing config exist
        existing = self.get_billing_config(market_id, db)
        if not existing:
            return None

        updates = []
        params = []
        for field in (
            "aggregator",
            "is_active",
            "require_invoice",
            "max_unmatched_bill_days",
            "kitchen_open_time",
            "kitchen_close_time",
            "notes",
        ):
            if field in data and data[field] is not None:
                updates.append(f"{field} = %s")
                params.append(data[field])

        if not updates:
            return existing

        updates.append("modified_by = %s")
        params.append(str(modified_by))
        updates.append("modified_date = CURRENT_TIMESTAMP")
        params.append(str(market_id))

        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""UPDATE billing.market_payout_aggregator
                    SET {", ".join(updates)}
                    WHERE market_id = %s
                    RETURNING market_id""",
                params,
            )
            row = cur.fetchone()
            if not row:
                db.rollback()
                return None
            db.commit()

        return self.get_billing_config(market_id, db)

    def get_billing_propagation_preview(self, market_id: UUID, db) -> dict:
        """Preview which suppliers inherit billing config from this market.
        Read-only — returns affected suppliers with their effective values."""
        config = self.get_billing_config(market_id, db)
        if not config:
            raise HTTPException(status_code=404, detail=f"No billing config for market {market_id}")

        rows = db_read(
            """SELECT i.institution_id, i.name AS institution_name,
                      st.require_invoice AS supplier_require_invoice,
                      st.invoice_hold_days AS supplier_invoice_hold_days,
                      st.kitchen_open_time AS supplier_kitchen_open_time,
                      st.kitchen_close_time AS supplier_kitchen_close_time
               FROM core.institution_info i
               JOIN core.institution_market im_prop ON i.institution_id = im_prop.institution_id
               LEFT JOIN billing.supplier_terms st ON st.institution_id = i.institution_id AND st.institution_entity_id IS NULL
               WHERE im_prop.market_id = %s
                 AND i.is_archived = FALSE
                 AND i.institution_type = 'supplier'
                 AND (st.require_invoice IS NULL OR st.invoice_hold_days IS NULL
                      OR st.kitchen_open_time IS NULL OR st.kitchen_close_time IS NULL)
               ORDER BY i.name""",
            (str(market_id),),
            connection=db,
        )

        affected = []
        for r in rows or []:
            affected.append(
                {
                    "institution_id": r["institution_id"],
                    "institution_name": r["institution_name"],
                    "supplier_require_invoice": r["supplier_require_invoice"],
                    "supplier_invoice_hold_days": r["supplier_invoice_hold_days"],
                    "effective_require_invoice": r["supplier_require_invoice"]
                    if r["supplier_require_invoice"] is not None
                    else config["require_invoice"],
                    "effective_invoice_hold_days": r["supplier_invoice_hold_days"]
                    if r["supplier_invoice_hold_days"] is not None
                    else config["max_unmatched_bill_days"],
                    "effective_kitchen_open_time": r["supplier_kitchen_open_time"]
                    if r["supplier_kitchen_open_time"] is not None
                    else config.get("kitchen_open_time", "09:00"),
                    "effective_kitchen_close_time": r["supplier_kitchen_close_time"]
                    if r["supplier_kitchen_close_time"] is not None
                    else config.get("kitchen_close_time", "13:30"),
                }
            )

        return {
            "market_id": str(market_id),
            "market_config": config,
            "affected_suppliers": affected,
            "total_affected": len(affected),
        }


# Singleton instance
market_service = MarketService()
