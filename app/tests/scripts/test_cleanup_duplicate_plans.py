"""
Unit tests for scripts/cleanup_duplicate_plans.py

Verifies:
- find_duplicate_groups returns correct groups from mocked DB results.
- archive_plans issues the correct UPDATE in live mode.
- archive_plans performs no writes in dry-run mode.
- run() is a no-op when no duplicates exist.
- run() archives exactly the non-canonical duplicates.
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers to import the script module without needing a live DB at import time
# ---------------------------------------------------------------------------


def _import_cleanup():
    """Import cleanup_duplicate_plans lazily (avoids DB calls at module load)."""
    import importlib.util
    import os

    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "cleanup_duplicate_plans.py")
    script_path = os.path.normpath(script_path)
    spec = importlib.util.spec_from_file_location("cleanup_duplicate_plans", script_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


cleanup = _import_cleanup()


# ---------------------------------------------------------------------------
# Tests for find_duplicate_groups
# ---------------------------------------------------------------------------


class TestFindDuplicateGroups:
    def _cursor_returning(self, rows):
        """Build a mock cursor whose fetchall() returns the given rows."""
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        return cursor

    def test_empty_when_no_duplicates(self):
        cursor = self._cursor_returning([])
        groups = cleanup.find_duplicate_groups(cursor)
        assert groups == []

    def test_single_duplicate_group(self):
        """Two rows for the same market+name → one group, oldest kept, newest archived."""
        plan_a = "aaaaaaaa-0000-0000-0000-000000000001"
        plan_b = "aaaaaaaa-0000-0000-0000-000000000002"
        market = "00000000-0000-0000-0000-000000000002"
        cursor = self._cursor_returning([(market, "Argentina Plan A", [plan_a, plan_b])])
        groups = cleanup.find_duplicate_groups(cursor)
        assert len(groups) == 1
        g = groups[0]
        assert g["keep_plan_id"] == plan_a
        assert g["archive_plan_ids"] == [plan_b]

    def test_multiple_groups(self):
        """Two separate duplicate groups → two entries returned."""
        market_ar = "00000000-0000-0000-0000-000000000002"
        market_us = "00000000-0000-0000-0000-000000000004"
        rows = [
            (market_ar, "Plan A", ["p1", "p2", "p3"]),
            (market_us, "Plan B", ["p4", "p5"]),
        ]
        cursor = self._cursor_returning(rows)
        groups = cleanup.find_duplicate_groups(cursor)
        assert len(groups) == 2
        # AR group: keep p1, archive p2 and p3
        assert groups[0]["keep_plan_id"] == "p1"
        assert groups[0]["archive_plan_ids"] == ["p2", "p3"]
        # US group: keep p4, archive p5
        assert groups[1]["keep_plan_id"] == "p4"
        assert groups[1]["archive_plan_ids"] == ["p5"]


# ---------------------------------------------------------------------------
# Tests for archive_plans
# ---------------------------------------------------------------------------


class TestArchivePlans:
    def test_dry_run_does_not_execute(self):
        """In dry-run mode, no SQL is executed; the count of would-be archives is returned."""
        cursor = MagicMock()
        result = cleanup.archive_plans(cursor, ["p1", "p2", "p3"], dry_run=True)
        cursor.execute.assert_not_called()
        assert result == 3

    def test_dry_run_empty_list_returns_zero(self):
        cursor = MagicMock()
        result = cleanup.archive_plans(cursor, [], dry_run=True)
        assert result == 0

    def test_live_mode_executes_update(self):
        """In live mode, an UPDATE is issued and rowcount is returned."""
        cursor = MagicMock()
        cursor.rowcount = 2
        result = cleanup.archive_plans(cursor, ["p1", "p2"], dry_run=False)
        cursor.execute.assert_called_once()
        # Verify the SQL is an UPDATE touching is_archived
        sql_called = cursor.execute.call_args[0][0]
        assert "UPDATE" in sql_called.upper()
        assert "is_archived" in sql_called
        assert result == 2

    def test_live_mode_empty_list_is_noop(self):
        cursor = MagicMock()
        result = cleanup.archive_plans(cursor, [], dry_run=False)
        cursor.execute.assert_not_called()
        assert result == 0


# ---------------------------------------------------------------------------
# Tests for run() integration
# ---------------------------------------------------------------------------


class TestRun:
    def _mock_connection(self, groups):
        """
        Build a mock psycopg2 connection whose cursor.fetchall() yields the
        given duplicate group rows.
        """
        cursor = MagicMock()
        # find_duplicate_groups calls fetchall once
        cursor.fetchall.return_value = [
            (g["market_id"], g["name"], [g["keep_plan_id"]] + g["archive_plan_ids"]) for g in groups
        ]
        cursor.rowcount = sum(len(g["archive_plan_ids"]) for g in groups)
        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=cursor)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn

    def test_no_duplicates_is_noop(self, capsys):
        """run() with no duplicates prints clean message and commits nothing."""
        with patch.object(cleanup, "get_connection") as mock_gc:
            conn = MagicMock()
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = conn
            cleanup.run(dry_run=False)
            conn.commit.assert_not_called()
        captured = capsys.readouterr()
        assert "clean" in captured.out.lower()

    def test_dry_run_does_not_commit(self, capsys):
        """run(dry_run=True) calls rollback, not commit."""
        groups = [
            {
                "market_id": "00000000-0000-0000-0000-000000000002",
                "name": "Dup Plan",
                "keep_plan_id": "p1",
                "archive_plan_ids": ["p2"],
            }
        ]
        with patch.object(cleanup, "get_connection") as mock_gc:
            conn = MagicMock()
            cursor = MagicMock()
            cursor.fetchall.return_value = [
                (g["market_id"], g["name"], [g["keep_plan_id"], *g["archive_plan_ids"]]) for g in groups
            ]
            conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = conn
            cleanup.run(dry_run=True)
            conn.commit.assert_not_called()
            conn.rollback.assert_called_once()
