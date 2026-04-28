"""
Regression tests for get_enriched_restaurants — institution_id UUID cast (#183).

Bug: institution_id was passed as a raw Python UUID object into a hand-written SQL
condition, which causes psycopg2 to raise a TypeError/500 because psycopg2 does not
accept UUID objects in parameterised queries (kitchen "Never Do These" rule).

Fix: cast to str(institution_id) before appending to the SQL param list.

These tests patch db_read to capture the SQL params tuple that would be sent to
psycopg2 and assert:
  - When institution_id is passed as a UUID, the param reaching psycopg2 is a str.
  - When institution_market_id is passed as a UUID, the param reaching psycopg2 is a str.
  - When neither is given, no extra params are emitted.
"""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.services.entity_service import get_enriched_restaurants

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_mock() -> MagicMock:
    """Minimal DB mock — get_enriched_restaurants never calls it directly,
    but EnrichedService._execute_query does via db_read."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetEnrichedRestaurantsUUIDCast:
    """institution_id and institution_market_id must be str, not UUID, in SQL params."""

    @patch("app.services.enriched_service.db_read")
    def test_institution_id_uuid_is_cast_to_str(self, mock_db_read):
        """institution_id as UUID must arrive at db_read as a str, not a UUID object.

        Before the fix this produced a raw UUID in the params tuple, causing a
        psycopg2 TypeError (→ 500).  After the fix it is str(uuid).
        """
        mock_db_read.return_value = []
        db = _make_db_mock()
        institution_id = uuid4()

        get_enriched_restaurants(db, institution_id=institution_id)

        assert mock_db_read.called, "db_read should have been called"
        # db_read is called as db_read(query, params_tuple, connection=db)
        call_args = mock_db_read.call_args
        params_tuple = call_args[0][1]  # positional arg 1

        # Every param must be a str (or None/bool/int/float — never a bare UUID).
        uuid_params = [p for p in params_tuple if isinstance(p, UUID)]
        assert uuid_params == [], (
            f"Raw UUID objects found in db_read params: {uuid_params}. "
            "Cast institution_id to str() before appending to SQL params."
        )

        # The institution_id value must appear as a str.
        assert str(institution_id) in params_tuple, (
            f"Expected str(institution_id)={str(institution_id)!r} in params, got {params_tuple}"
        )

    @patch("app.services.enriched_service.db_read")
    def test_institution_market_id_uuid_is_cast_to_str(self, mock_db_read):
        """institution_market_id as UUID must arrive at db_read as a str, not a UUID object."""
        mock_db_read.return_value = []
        db = _make_db_mock()
        market_id = uuid4()

        get_enriched_restaurants(db, institution_market_id=market_id)

        assert mock_db_read.called
        call_args = mock_db_read.call_args
        params_tuple = call_args[0][1]

        uuid_params = [p for p in params_tuple if isinstance(p, UUID)]
        assert uuid_params == [], (
            f"Raw UUID objects found in db_read params: {uuid_params}. "
            "Cast institution_market_id to str() before appending to SQL params."
        )

        assert str(market_id) in params_tuple, (
            f"Expected str(market_id)={str(market_id)!r} in params, got {params_tuple}"
        )

    @patch("app.services.enriched_service.db_read")
    def test_both_ids_as_uuid_are_cast_to_str(self, mock_db_read):
        """When both institution_id and institution_market_id are given, both must be str."""
        mock_db_read.return_value = []
        db = _make_db_mock()
        institution_id = uuid4()
        market_id = uuid4()

        get_enriched_restaurants(db, institution_id=institution_id, institution_market_id=market_id)

        assert mock_db_read.called
        params_tuple = mock_db_read.call_args[0][1]

        uuid_params = [p for p in params_tuple if isinstance(p, UUID)]
        assert uuid_params == [], f"Raw UUID objects found in db_read params: {uuid_params}."
        assert str(institution_id) in params_tuple
        assert str(market_id) in params_tuple

    @patch("app.services.enriched_service.db_read")
    def test_no_ids_emits_no_extra_params(self, mock_db_read):
        """When neither institution_id nor institution_market_id is given, no extra params."""
        mock_db_read.return_value = []
        db = _make_db_mock()

        get_enriched_restaurants(db)

        assert mock_db_read.called
        params_tuple = mock_db_read.call_args[0][1]

        # With no filters the WHERE clause has no %s placeholders, so params is None or empty.
        # Confirm no UUID objects slipped in.
        if params_tuple is not None:
            uuid_params = [p for p in params_tuple if isinstance(p, UUID)]
            assert uuid_params == []
