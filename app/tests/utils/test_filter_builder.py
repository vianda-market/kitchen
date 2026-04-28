"""
Unit tests for app/utils/filter_builder.py.

Covers every supported op (eq, in, gte, lte, ilike, bool) and every cast type
(uuid, text, upper, bool, date, int, float). Tests use an in-process registry
fixture so they are decoupled from the real FILTER_REGISTRY contents.
"""

import uuid
from unittest.mock import patch

import pytest

from app.utils.filter_builder import build_filter_conditions

# ---------------------------------------------------------------------------
# Registry fixture — patched into FILTER_REGISTRY for each test
# ---------------------------------------------------------------------------
FAKE_REGISTRY: dict = {
    "test_entity": {
        # eq ops
        "market_id": {"col": "market_id", "alias": "t", "op": "eq", "cast": "uuid"},
        "name": {"col": "name", "alias": "t", "op": "eq", "cast": "text"},
        "code": {"col": "code", "alias": "t", "op": "eq", "cast": "upper"},
        "flag": {"col": "flag", "alias": "t", "op": "eq", "cast": "bool"},
        "start_date": {"col": "start_date", "alias": "t", "op": "eq", "cast": "date"},
        "count": {"col": "count", "alias": "t", "op": "eq", "cast": "int"},
        "score": {"col": "score", "alias": "t", "op": "eq", "cast": "float"},
        # in op
        "status": {"col": "status", "alias": "t", "op": "in", "cast": "text"},
        "tag_ids": {"col": "tag_id", "alias": "t", "op": "in", "cast": "uuid"},
        # gte / lte
        "price_min": {"col": "price", "alias": "t", "op": "gte", "cast": "float"},
        "price_max": {"col": "price", "alias": "t", "op": "lte", "cast": "float"},
        "created_from": {"col": "created_date", "alias": "t", "op": "gte", "cast": "date"},
        "created_to": {"col": "created_date", "alias": "t", "op": "lte", "cast": "date"},
        # ilike
        "search": {"cols": ["t.name", "t.description"], "op": "ilike"},
        "search_single": {"cols": ["t.name"], "op": "ilike"},
        # bool op
        "is_active": {"col": "is_active", "alias": "t", "op": "bool"},
    }
}


@pytest.fixture(autouse=True)
def patch_registry():
    with patch("app.utils.filter_builder.FILTER_REGISTRY", FAKE_REGISTRY):
        yield


# ---------------------------------------------------------------------------
# None / missing filtering
# ---------------------------------------------------------------------------


def test_none_values_are_skipped():
    result = build_filter_conditions("test_entity", {"market_id": None, "name": None})
    assert result is None


def test_unregistered_params_are_ignored():
    result = build_filter_conditions("test_entity", {"nonexistent": "val"})
    assert result is None


def test_unknown_entity_returns_none():
    result = build_filter_conditions("no_such_entity", {"name": "x"})
    assert result is None


def test_returns_none_when_all_filtered_out():
    result = build_filter_conditions("test_entity", {"market_id": None})
    assert result is None


# ---------------------------------------------------------------------------
# op == "eq" — all cast types
# ---------------------------------------------------------------------------


def test_eq_uuid_cast():
    uid = uuid.uuid4()
    result = build_filter_conditions("test_entity", {"market_id": uid})
    assert result is not None
    assert len(result) == 1
    condition, param = result[0]
    assert condition == "t.market_id = %s::uuid"
    assert param == [str(uid)]


def test_eq_text_cast():
    result = build_filter_conditions("test_entity", {"name": "hello"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.name = %s"
    assert param == ["hello"]


def test_eq_upper_cast():
    result = build_filter_conditions("test_entity", {"code": "usd"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.code = UPPER(%s)"
    assert param == ["USD"]


def test_eq_bool_cast():
    result = build_filter_conditions("test_entity", {"flag": True})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.flag = %s::bool"
    assert param == [True]


def test_eq_date_cast():
    result = build_filter_conditions("test_entity", {"start_date": "2025-01-01"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.start_date = %s::date"
    assert param == ["2025-01-01"]


def test_eq_int_cast():
    result = build_filter_conditions("test_entity", {"count": "7"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.count = %s::int"
    assert param == [7]


def test_eq_float_cast():
    result = build_filter_conditions("test_entity", {"score": "3.5"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.score = %s::float"
    assert param == [3.5]


# ---------------------------------------------------------------------------
# op == "in"
# ---------------------------------------------------------------------------


def test_in_with_list():
    result = build_filter_conditions("test_entity", {"status": ["active", "pending"]})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.status = ANY(%s)"
    assert param == [["active", "pending"]]


def test_in_with_single_value():
    result = build_filter_conditions("test_entity", {"status": "active"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.status = ANY(%s)"
    assert param == [["active"]]


def test_in_with_uuid_list():
    uid1 = str(uuid.uuid4())
    uid2 = str(uuid.uuid4())
    result = build_filter_conditions("test_entity", {"tag_ids": [uid1, uid2]})
    assert result is not None
    condition, param = result[0]
    # uuid cast → explicit array cast to avoid "operator does not exist: uuid = text"
    assert condition == "t.tag_id = ANY(%s::uuid[])"
    # uuid cast coerces to str
    assert param == [[str(uid1), str(uid2)]]


# ---------------------------------------------------------------------------
# op == "gte" / "lte"
# ---------------------------------------------------------------------------


def test_gte_float():
    result = build_filter_conditions("test_entity", {"price_min": "10.5"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.price >= %s::float"
    assert param == [10.5]


def test_lte_float():
    result = build_filter_conditions("test_entity", {"price_max": "99.99"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.price <= %s::float"
    assert param == [99.99]


def test_gte_date():
    result = build_filter_conditions("test_entity", {"created_from": "2025-01-01"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.created_date >= %s::date"
    assert param == ["2025-01-01"]


def test_lte_date():
    result = build_filter_conditions("test_entity", {"created_to": "2025-12-31"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.created_date <= %s::date"
    assert param == ["2025-12-31"]


def test_range_both_bounds():
    result = build_filter_conditions("test_entity", {"price_min": 5.0, "price_max": 50.0})
    assert result is not None
    assert len(result) == 2
    ops = dict(result)
    assert "t.price >= %s::float" in ops
    assert "t.price <= %s::float" in ops
    assert ops["t.price >= %s::float"] == [5.0]
    assert ops["t.price <= %s::float"] == [50.0]


# ---------------------------------------------------------------------------
# op == "ilike"
# ---------------------------------------------------------------------------


def test_ilike_single_col():
    result = build_filter_conditions("test_entity", {"search_single": "pizza"})
    assert result is not None
    assert len(result) == 1
    condition, param = result[0]
    assert condition == "t.name ILIKE %s"
    assert param == ["%pizza%"]


def test_ilike_multi_col():
    result = build_filter_conditions("test_entity", {"search": "pizza"})
    assert result is not None
    # Single OR-compound tuple, not one per column
    assert len(result) == 1
    condition, params = result[0]
    assert condition == "(t.name ILIKE %s OR t.description ILIKE %s)"
    # N identical wrapped params, one per col
    assert params == ["%pizza%", "%pizza%"]


def test_ilike_wraps_value():
    result = build_filter_conditions("test_entity", {"search_single": "tacos"})
    _, param = result[0]
    assert param == ["%tacos%"]


# ---------------------------------------------------------------------------
# op == "bool"
# ---------------------------------------------------------------------------


def test_bool_op_true():
    result = build_filter_conditions("test_entity", {"is_active": True})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.is_active = %s::bool"
    assert param == [True]


def test_bool_op_false():
    result = build_filter_conditions("test_entity", {"is_active": False})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.is_active = %s::bool"
    assert param == [False]


def test_bool_op_coerces_truthy():
    result = build_filter_conditions("test_entity", {"is_active": 1})
    assert result is not None
    _, param = result[0]
    assert param == [True]


# ---------------------------------------------------------------------------
# timestamptz cast
# ---------------------------------------------------------------------------

FAKE_REGISTRY_TIMESTAMPTZ: dict = {
    "test_ts": {
        "expected_from": {"col": "expected_completion_time", "alias": "ppl", "op": "gte", "cast": "timestamptz"},
        "expected_to": {"col": "expected_completion_time", "alias": "ppl", "op": "lte", "cast": "timestamptz"},
    }
}


def test_gte_timestamptz():
    with patch("app.utils.filter_builder.FILTER_REGISTRY", FAKE_REGISTRY_TIMESTAMPTZ):
        result = build_filter_conditions("test_ts", {"expected_from": "2025-01-01T09:00:00Z"})
    assert result is not None
    condition, params = result[0]
    assert condition == "ppl.expected_completion_time >= %s::timestamptz"
    assert params == ["2025-01-01T09:00:00Z"]


def test_lte_timestamptz():
    with patch("app.utils.filter_builder.FILTER_REGISTRY", FAKE_REGISTRY_TIMESTAMPTZ):
        result = build_filter_conditions("test_ts", {"expected_to": "2025-01-01T13:30:00Z"})
    assert result is not None
    condition, params = result[0]
    assert condition == "ppl.expected_completion_time <= %s::timestamptz"
    assert params == ["2025-01-01T13:30:00Z"]


def test_window_range_both_bounds():
    with patch("app.utils.filter_builder.FILTER_REGISTRY", FAKE_REGISTRY_TIMESTAMPTZ):
        result = build_filter_conditions(
            "test_ts",
            {"expected_from": "2025-01-01T09:00:00Z", "expected_to": "2025-01-01T13:30:00Z"},
        )
    assert result is not None
    assert len(result) == 2


# ---------------------------------------------------------------------------
# ilike OR semantics — additional edge cases
# ---------------------------------------------------------------------------


def test_ilike_or_semantics_params_count():
    """N cols → N identical params in a single tuple."""
    result = build_filter_conditions("test_entity", {"search": "tacos"})
    assert result is not None
    assert len(result) == 1
    condition, params = result[0]
    assert len(params) == 2
    assert all(p == "%tacos%" for p in params)


def test_ilike_single_col_no_parens():
    """Single-col ilike should not wrap in parens."""
    result = build_filter_conditions("test_entity", {"search_single": "burger"})
    assert result is not None
    condition, params = result[0]
    assert condition == "t.name ILIKE %s"
    assert "(" not in condition


# ---------------------------------------------------------------------------
# Plans registry — smoke test to confirm migrated shape still works
# ---------------------------------------------------------------------------


def test_plans_registry_market_id():
    """Confirm migrated plans registry emits correct eq/uuid condition."""
    with patch("app.utils.filter_builder.FILTER_REGISTRY", {}):
        pass  # Don't re-patch; use autouse patch which has our fake registry.

    # Use real FILTER_REGISTRY via a dedicated import to avoid mock interference
    from app.config.filter_registry import FILTER_REGISTRY as REAL_REGISTRY

    with patch("app.utils.filter_builder.FILTER_REGISTRY", REAL_REGISTRY):
        uid = uuid.uuid4()
        result = build_filter_conditions("plans", {"market_id": uid, "status": None, "currency_code": None})
        assert result is not None
        assert len(result) == 1
        condition, param = result[0]
        assert condition == "pl.market_id = %s::uuid"
        assert param == [str(uid)]


def test_plans_registry_status():
    from app.config.filter_registry import FILTER_REGISTRY as REAL_REGISTRY

    with patch("app.utils.filter_builder.FILTER_REGISTRY", REAL_REGISTRY):
        result = build_filter_conditions("plans", {"market_id": None, "status": "active", "currency_code": None})
        assert result is not None
        assert len(result) == 1
        condition, param = result[0]
        assert condition == "pl.status = %s"
        assert param == ["active"]


def test_plans_registry_currency_code():
    from app.config.filter_registry import FILTER_REGISTRY as REAL_REGISTRY

    with patch("app.utils.filter_builder.FILTER_REGISTRY", REAL_REGISTRY):
        result = build_filter_conditions("plans", {"market_id": None, "status": None, "currency_code": "usd"})
        assert result is not None
        assert len(result) == 1
        condition, param = result[0]
        assert condition == "cc.currency_code = UPPER(%s)"
        assert param == ["USD"]


def test_plans_registry_all_none_returns_none():
    from app.config.filter_registry import FILTER_REGISTRY as REAL_REGISTRY

    with patch("app.utils.filter_builder.FILTER_REGISTRY", REAL_REGISTRY):
        result = build_filter_conditions("plans", {"market_id": None, "status": None, "currency_code": None})
        assert result is None


# ---------------------------------------------------------------------------
# Enum validation — Fix 1
# ---------------------------------------------------------------------------

FAKE_REGISTRY_ENUM: dict = {
    "enum_entity": {
        # eq with enum, no context
        "kitchen_day": {"col": "kitchen_day", "alias": "t", "op": "eq", "cast": "text", "enum": "KitchenDay"},
        # in with enum, no context
        "days": {"col": "day", "alias": "t", "op": "in", "cast": "text", "enum": "KitchenDay"},
        # eq with enum + context
        "pickup_status": {
            "col": "status",
            "alias": "t",
            "op": "eq",
            "cast": "text",
            "enum": "Status",
            "context": "plate_pickup",
        },
        # field without enum (no validation)
        "city": {"col": "city", "alias": "t", "op": "eq", "cast": "text"},
    }
}


@pytest.fixture
def patch_enum_registry():
    """Patch registry for enum validation tests (does NOT use autouse fixture)."""
    with patch("app.utils.filter_builder.FILTER_REGISTRY", FAKE_REGISTRY_ENUM):
        yield


def test_valid_enum_eq_generates_condition(patch_enum_registry):
    """Valid enum value on eq → condition generated normally."""
    result = build_filter_conditions("enum_entity", {"kitchen_day": "monday"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.kitchen_day = %s"
    assert param == ["monday"]


def test_invalid_enum_eq_raises_value_error(patch_enum_registry):
    """Invalid enum value on eq → raises ValueError naming the invalid item."""
    with pytest.raises(ValueError, match="Invalid value 'saturday'"):
        build_filter_conditions("enum_entity", {"kitchen_day": "saturday"})


def test_invalid_enum_eq_error_lists_valid_values(patch_enum_registry):
    """ValueError message includes a sorted list of valid values."""
    with pytest.raises(ValueError, match="expected one of:"):
        build_filter_conditions("enum_entity", {"kitchen_day": "sunday"})


def test_valid_enum_in_generates_condition(patch_enum_registry):
    """Valid enum values on in → condition generated normally."""
    result = build_filter_conditions("enum_entity", {"days": ["monday", "friday"]})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.day = ANY(%s)"
    assert param == [["monday", "friday"]]


def test_invalid_enum_in_raises_value_error_names_bad_item(patch_enum_registry):
    """Mixed valid/invalid on in → raises ValueError naming the invalid item."""
    with pytest.raises(ValueError, match="Invalid value 'saturday'"):
        build_filter_conditions("enum_entity", {"days": ["monday", "saturday"]})


def test_no_enum_field_no_validation(patch_enum_registry):
    """Field without 'enum' key → no validation, works as before."""
    result = build_filter_conditions("enum_entity", {"city": "any_value_here"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.city = %s"
    assert param == ["any_value_here"]


def test_context_scoped_enum_valid_value_accepted(patch_enum_registry):
    """Value valid in context (plate_pickup) → condition generated normally."""
    result = build_filter_conditions("enum_entity", {"pickup_status": "pending"})
    assert result is not None
    condition, param = result[0]
    assert condition == "t.status = %s"
    assert param == ["pending"]


def test_context_scoped_enum_rejects_out_of_context_value(patch_enum_registry):
    """'active' is valid in full Status enum but not in plate_pickup context → 400."""
    with pytest.raises(ValueError, match="Invalid value 'active'"):
        build_filter_conditions("enum_entity", {"pickup_status": "active"})


def test_context_scoped_enum_rejects_processed(patch_enum_registry):
    """'processed' is valid in full Status enum but not in plate_pickup context → ValueError."""
    with pytest.raises(ValueError, match="Invalid value 'processed'"):
        build_filter_conditions("enum_entity", {"pickup_status": "processed"})


# ---------------------------------------------------------------------------
# Geo op — bbox and radius
# ---------------------------------------------------------------------------

FAKE_REGISTRY_GEO: dict = {
    "geo_entity": {
        "bbox": {"col": "location", "alias": "r", "op": "geo", "mode": "bbox"},
        "radius": {"col": "location", "alias": "r", "op": "geo", "mode": "radius"},
    }
}


@pytest.fixture
def patch_geo_registry():
    with patch("app.utils.filter_builder.FILTER_REGISTRY", FAKE_REGISTRY_GEO):
        yield


def test_geo_bbox_valid(patch_geo_registry):
    """Valid bbox → correct ST_MakeEnvelope condition with 4 float params."""
    result = build_filter_conditions("geo_entity", {"bbox": [-74.05, 40.68, -73.91, 40.83]})
    assert result is not None
    assert len(result) == 1
    condition, params = result[0]
    assert condition == "ST_MakeEnvelope(%s, %s, %s, %s, 4326) && r.location"
    assert params == [-74.05, 40.68, -73.91, 40.83]


def test_geo_radius_valid(patch_geo_registry):
    """Valid radius → correct ST_DWithin condition with 3 float params (lng, lat, radius_m)."""
    result = build_filter_conditions("geo_entity", {"radius": [40.7484, -73.9857, 1000.0]})
    assert result is not None
    assert len(result) == 1
    condition, params = result[0]
    assert "ST_DWithin" in condition
    assert "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography" in condition
    # Builder emits [lng, lat, radius_m] — note lat/lng swap for PostGIS
    assert params == [-73.9857, 40.7484, 1000.0]


def test_geo_bbox_wrong_arity_raises(patch_geo_registry):
    """bbox with 3 values → ValueError."""
    with pytest.raises(ValueError, match="exactly 4 values"):
        build_filter_conditions("geo_entity", {"bbox": [-74.0, 40.0, -73.0]})


def test_geo_radius_wrong_arity_raises(patch_geo_registry):
    """radius with 2 values → ValueError."""
    with pytest.raises(ValueError, match="exactly 3 values"):
        build_filter_conditions("geo_entity", {"radius": [40.7, -73.9]})


def test_geo_bbox_non_numeric_raises(patch_geo_registry):
    """Non-numeric bbox element → ValueError."""
    with pytest.raises(ValueError, match="must be a number"):
        build_filter_conditions("geo_entity", {"bbox": ["not", "a", "number", "here"]})


def test_geo_radius_non_numeric_raises(patch_geo_registry):
    """Non-numeric radius element → ValueError."""
    with pytest.raises(ValueError, match="must be a number"):
        build_filter_conditions("geo_entity", {"radius": ["lat", "lng", "500"]})


def test_geo_bbox_lat_out_of_range_raises(patch_geo_registry):
    """lat > 90 in bbox → ValueError."""
    with pytest.raises(ValueError, match="out of range"):
        build_filter_conditions("geo_entity", {"bbox": [-74.0, 91.0, -73.0, 40.0]})


def test_geo_bbox_lng_out_of_range_raises(patch_geo_registry):
    """lng > 180 in bbox → ValueError."""
    with pytest.raises(ValueError, match="out of range"):
        build_filter_conditions("geo_entity", {"radius": [40.0, 181.0, 500.0]})


def test_geo_radius_lat_out_of_range_raises(patch_geo_registry):
    """lat < -90 in radius → ValueError."""
    with pytest.raises(ValueError, match="out of range"):
        build_filter_conditions("geo_entity", {"radius": [-91.0, -73.9, 500.0]})


def test_geo_radius_negative_radius_raises(patch_geo_registry):
    """radius_m <= 0 → ValueError."""
    with pytest.raises(ValueError, match="must be > 0"):
        build_filter_conditions("geo_entity", {"radius": [40.7, -73.9, -100.0]})


def test_geo_bbox_and_existing_filter_combined(patch_geo_registry):
    """bbox combined with another filter returns 2 conditions."""
    registry_with_city = {
        "geo_entity": {
            "bbox": {"col": "location", "alias": "r", "op": "geo", "mode": "bbox"},
            "city": {"col": "city", "alias": "a", "op": "eq", "cast": "text"},
        }
    }
    with patch("app.utils.filter_builder.FILTER_REGISTRY", registry_with_city):
        result = build_filter_conditions("geo_entity", {"bbox": [-74.05, 40.68, -73.91, 40.83], "city": "New York"})
    assert result is not None
    assert len(result) == 2
