"""
Unit tests for app/services/credit_spread.py

Tests the spread floor check logic, not the DB layer. All DB calls are mocked.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_rows(
    floor_pct: str,
    supplier_value: str,
    plans: list[tuple[str, str, int]] | None = None,
) -> list[dict]:
    """
    Build the row list that check_spread_floor's db_read would return.

    plans: list of (plan_id_str, price_str, credit_int)
    If None, returns one row with plan_id=None (no active plans).
    """
    if plans:
        return [
            {
                "min_credit_spread_pct": floor_pct,
                "credit_value_supplier_local": supplier_value,
                "plan_id": plan_id,
                "price": price,
                "credit": credit,
            }
            for plan_id, price, credit in plans
        ]
    return [
        {
            "min_credit_spread_pct": floor_pct,
            "credit_value_supplier_local": supplier_value,
            "plan_id": None,
            "price": None,
            "credit": None,
        }
    ]


class TestCheckSpreadFloor:
    """check_spread_floor: existing plans vs. floor."""

    def test_ok_when_no_active_plans(self):
        """No active plans → ok=True (nothing to enforce)."""
        from app.services.credit_spread import check_spread_floor

        rows = _make_db_rows("0.2000", "1.0")  # no plans
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor(MagicMock(), market_id=uuid4())

        assert result.ok is True

    def test_ok_when_plan_above_floor(self):
        """Plan price/credit = 1.5, supplier=1.0, floor=20% → spread=50% ≥ 20% → ok."""
        from app.services.credit_spread import check_spread_floor

        plan_id = str(uuid4())
        rows = _make_db_rows("0.2000", "1.0", [(plan_id, "15.00", 10)])  # per-credit = 1.5
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor(MagicMock(), market_id=uuid4())

        assert result.ok is True
        assert result.observed_pct == Decimal("0.5")  # 1.5/1.0 - 1 = 0.5

    def test_violation_when_plan_below_floor(self):
        """Plan price/credit = 1.1, supplier=1.0, floor=20% → spread=10% < 20% → not ok."""
        from app.services.credit_spread import check_spread_floor

        plan_id = str(uuid4())
        rows = _make_db_rows("0.2000", "1.0", [(plan_id, "11.00", 10)])  # per-credit = 1.1
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor(MagicMock(), market_id=uuid4())

        assert result.ok is False
        assert plan_id in result.offending_plan_ids

    def test_floor_exactly_met_is_ok(self):
        """Plan price/credit = 1.2, supplier=1.0, floor=20% → spread=20% = floor → ok."""
        from app.services.credit_spread import check_spread_floor

        plan_id = str(uuid4())
        rows = _make_db_rows("0.2000", "1.0", [(plan_id, "12.00", 10)])  # per-credit = 1.2
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor(MagicMock(), market_id=uuid4())

        assert result.ok is True

    def test_multiple_plans_only_offending_flagged(self):
        """Two plans: one above floor, one below. Only the below-floor plan is in offending_plan_ids."""
        from app.services.credit_spread import check_spread_floor

        good_id = str(uuid4())
        bad_id = str(uuid4())
        rows = _make_db_rows(
            "0.2000",
            "1.0",
            [
                (good_id, "15.00", 10),  # per-credit = 1.5 → ok
                (bad_id, "11.00", 10),  # per-credit = 1.1 → violation
            ],
        )
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor(MagicMock(), market_id=uuid4())

        assert result.ok is False
        assert bad_id in result.offending_plan_ids
        assert good_id not in result.offending_plan_ids

    def test_margin_varies_by_tier(self):
        """
        Two plan tiers in one market; margin per credit is different.
        This is the expected asymmetry — high-tier plans (more credits per $) yield narrower margin.
        """
        from app.services.credit_spread import check_spread_floor

        high_tier_id = str(uuid4())  # 50 credits for $49.99 → $0.9998/credit
        low_tier_id = str(uuid4())  # 10 credits for $12.99 → $1.299/credit
        rows = _make_db_rows(
            "0.1000",  # 10% floor
            "0.80",  # supplier gets $0.80/credit
            [
                (high_tier_id, "49.99", 50),  # per-credit 0.9998 → margin 0.1998
                (low_tier_id, "12.99", 10),  # per-credit 1.299 → margin 0.499
            ],
        )
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor(MagicMock(), market_id=uuid4())

        assert result.ok is True
        # cheapest is high_tier: 49.99/50 = 0.9998
        assert result.cheapest_per_credit is not None
        assert abs(float(result.cheapest_per_credit) - 49.99 / 50) < 0.001
        # observed spread = 0.9998/0.80 - 1 = 0.24975 > 10% floor
        assert float(result.observed_pct) > 0.10


class TestCheckSpreadFloorWithPlan:
    """check_spread_floor_with_plan: includes proposed plan in evaluation."""

    def test_proposed_plan_violation_flagged(self):
        """A proposed plan that violates the floor is correctly identified."""
        from app.services.credit_spread import check_spread_floor_with_plan

        # No existing plans (LEFT JOIN returns None row)
        rows = [
            {
                "min_credit_spread_pct": "0.2000",
                "credit_value_supplier_local": "1.0",
                "plan_id": None,
                "price": None,
                "credit": None,
            }
        ]
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor_with_plan(
                MagicMock(),
                market_id=uuid4(),
                proposed_price=1.1,  # per-credit = 1.1, supplier=1.0, floor=20%
                proposed_credit=1,
            )

        assert result.ok is False
        assert "proposed_plan" in result.offending_plan_ids

    def test_proposed_plan_passes_floor(self):
        """A proposed plan above the floor returns ok=True."""
        from app.services.credit_spread import check_spread_floor_with_plan

        rows = [
            {
                "min_credit_spread_pct": "0.2000",
                "credit_value_supplier_local": "1.0",
                "plan_id": None,
                "price": None,
                "credit": None,
            }
        ]
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor_with_plan(
                MagicMock(),
                market_id=uuid4(),
                proposed_price=1.5,  # per-credit = 1.5 > 1.2 threshold
                proposed_credit=1,
            )

        assert result.ok is True


class TestCheckSpreadFloorWithNewSupplierValue:
    """check_spread_floor_with_new_supplier_value: re-checks with proposed supplier value."""

    def test_increase_that_violates_floor(self):
        """Raising supplier value can create violations against existing plans."""
        from app.services.credit_spread import check_spread_floor_with_new_supplier_value

        plan_id = str(uuid4())
        rows = [
            {
                "min_credit_spread_pct": "0.2000",
                "plan_id": plan_id,
                "price": "12.00",
                "credit": 10,
            }
        ]
        # plan per-credit = 1.2; if supplier rises to 1.1 → threshold = 1.1*1.2 = 1.32 > 1.2 → violation
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor_with_new_supplier_value(
                MagicMock(), market_id=uuid4(), proposed_supplier_value=Decimal("1.1")
            )

        assert result.ok is False
        assert plan_id in result.offending_plan_ids

    def test_decrease_that_widens_spread(self):
        """Lowering supplier value generally widens the spread (ok)."""
        from app.services.credit_spread import check_spread_floor_with_new_supplier_value

        plan_id = str(uuid4())
        rows = [
            {
                "min_credit_spread_pct": "0.2000",
                "plan_id": plan_id,
                "price": "12.00",
                "credit": 10,
            }
        ]
        # plan per-credit = 1.2; supplier drops to 0.5 → threshold = 0.5*1.2 = 0.6 < 1.2 → ok
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor_with_new_supplier_value(
                MagicMock(), market_id=uuid4(), proposed_supplier_value=Decimal("0.5")
            )

        assert result.ok is True


class TestCheckSpreadFloorWithNewFloorPct:
    """check_spread_floor_with_new_floor_pct: raises floor, may conflict with active plans."""

    def test_raised_floor_creates_violation(self):
        """Raising the floor above the observed spread causes violations."""
        from app.services.credit_spread import check_spread_floor_with_new_floor_pct

        plan_id = str(uuid4())
        rows = [
            {
                "credit_value_supplier_local": "1.0",
                "plan_id": plan_id,
                "price": "12.00",
                "credit": 10,
            }
        ]
        # plan per-credit = 1.2, spread = 20%; raising floor to 25% → violation
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor_with_new_floor_pct(
                MagicMock(), market_id=uuid4(), proposed_floor_pct=Decimal("0.2500")
            )

        assert result.ok is False
        assert plan_id in result.offending_plan_ids

    def test_lowered_floor_always_ok(self):
        """Lowering the floor below the observed spread always passes."""
        from app.services.credit_spread import check_spread_floor_with_new_floor_pct

        plan_id = str(uuid4())
        rows = [
            {
                "credit_value_supplier_local": "1.0",
                "plan_id": plan_id,
                "price": "12.00",
                "credit": 10,
            }
        ]
        # plan per-credit = 1.2, spread = 20%; lowering floor to 5% → ok
        with patch("app.services.credit_spread.db_read", return_value=rows):
            result = check_spread_floor_with_new_floor_pct(
                MagicMock(), market_id=uuid4(), proposed_floor_pct=Decimal("0.0500")
            )

        assert result.ok is True


class TestRecordAcknowledgement:
    """record_acknowledgement writes the correct row to audit.spread_acknowledgement."""

    def test_calls_cursor_execute_with_correct_params(self):
        """record_acknowledgement calls cursor.execute with all required fields."""
        from app.services.credit_spread import SpreadAckContext, SpreadCheck, record_acknowledgement

        spread = SpreadCheck(
            ok=False,
            observed_pct=Decimal("0.10"),
            floor_pct=Decimal("0.20"),
            offending_plan_ids=["plan-123"],
        )
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        actor = uuid4()
        market = uuid4()
        entity = uuid4()

        ctx = SpreadAckContext(
            actor_user_id=actor,
            market_id=market,
            write_kind="plan",
            entity_id=entity,
            justification="intentional below-floor tier",
        )
        record_acknowledgement(mock_db, ctx, spread)

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]  # second positional arg = params tuple
        assert str(actor) in params
        assert str(market) in params
        assert "plan" in params
        assert str(entity) in params
        assert float(Decimal("0.10")) in params
        assert float(Decimal("0.20")) in params
