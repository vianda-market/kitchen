#!/usr/bin/env bash
# scripts/verify.sh — full local gate sweep mirroring CI exactly.
#
# PURPOSE
#   One command that runs every required gate CI runs, in CI's exact commands.
#   Catches what "I ran some gates locally" misses (e.g. ruff check vs
#   ruff format --check; mypy alone vs mypy | mypy_baseline filter).
#   Motivation: PR #191 failed CI on `ruff format --check` even though the
#   agent reported "ruff: clean" — it only ran `ruff check`.
#
# USAGE
#   bash scripts/verify.sh                  # full sweep (all gates)
#   bash scripts/verify.sh --fast           # skip slow gates (pytest + newman)
#   bash scripts/verify.sh --gate ruff-fmt  # run a single named gate
#
# GATE NAMES (for --gate)
#   ruff-lint, ruff-fmt, mypy, lint-imports, complexity,
#   maintainability, complexity-strict, vulture, bandit,
#   thresholds-parity, filter-schema, sqlfluff, gitleaks,
#   pytest, diff-cover, coverage-floor, newman
#
# SLOW GATES (skipped with --fast)
#   pytest, diff-cover, coverage-floor, newman
#
# ENV VARS (must be set; these are the same vars CI sets)
#   SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
#   If not set, the script exports the same sentinel values CI uses.
#
# NEWMAN NOTE
#   The newman gate requires a running server (bash run_dev_quiet.sh in another
#   terminal) and newman installed (npm install -g newman). The script skips
#   newman automatically if no server is reachable and prints a warning rather
#   than hard-failing (CI always starts its own server; you must do so manually
#   when running locally). To force-fail on a missing server, set:
#   NEWMAN_REQUIRE_SERVER=1
#
#   In a worktree, worktree_env.sh (auto-sourced above) sets KITCHEN_API_PORT
#   to a unique port and NEWMAN_BASE_URL accordingly — multiple worktrees can
#   run Newman in parallel without port collisions.

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Worktree auto-source: if running inside a .claude/worktrees/* path, source
# worktree_env.sh to claim a unique KITCHEN_API_PORT and KITCHEN_DB_NAME.
# No-op for human dev (main working tree stays on port 8000 / DB kitchen).
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$PWD" == */.claude/worktrees/* ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "${SCRIPT_DIR}/worktree_env.sh" ]]; then
        # shellcheck source=scripts/worktree_env.sh
        source "${SCRIPT_DIR}/worktree_env.sh"
    fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# Resolve `python` — CI virtualenv exposes `python`; local machines often only
# have `python3`. Use whichever is available, preferring `python`.
# ──────────────────────────────────────────────────────────────────────────────
if command -v python &>/dev/null; then
    PY="python"
else
    PY="python3"
fi

# ──────────────────────────────────────────────────────────────────────────────
# Parse arguments
# ──────────────────────────────────────────────────────────────────────────────
FAST=0
SINGLE_GATE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fast)  FAST=1; shift ;;
        --gate)  SINGLE_GATE="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# ──────────────────────────────────────────────────────────────────────────────
# Env vars — same sentinel values CI exports
# ──────────────────────────────────────────────────────────────────────────────
export SECRET_KEY="${SECRET_KEY:-ci-test-secret-key}"
export ALGORITHM="${ALGORITHM:-HS256}"
export ACCESS_TOKEN_EXPIRE_MINUTES="${ACCESS_TOKEN_EXPIRE_MINUTES:-30}"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
FAILED_GATES=()
PASSED_GATES=()
SKIPPED_GATES=()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

run_gate() {
    local name="$1"
    shift  # remaining args are the command

    # If --gate was specified, skip all other gates
    if [[ -n "$SINGLE_GATE" && "$name" != "$SINGLE_GATE" ]]; then
        return
    fi

    echo ""
    echo -e "${BOLD}── gate: ${name} ──${RESET}"
    echo "   cmd: $*"
    echo ""

    local output
    local exit_code=0

    # Capture output but also stream it to terminal
    if output=$(eval "$@" 2>&1); then
        echo "$output"
        echo ""
        echo -e "${GREEN}PASS${RESET} ${name}"
        PASSED_GATES+=("$name")
    else
        exit_code=$?
        echo "$output"
        echo ""
        echo -e "${RED}FAIL${RESET} ${name} (exit ${exit_code})"
        FAILED_GATES+=("$name")
    fi
}

skip_gate() {
    local name="$1"
    local reason="$2"

    if [[ -n "$SINGLE_GATE" && "$name" != "$SINGLE_GATE" ]]; then
        return
    fi

    echo ""
    echo -e "${YELLOW}SKIP${RESET} ${name} — ${reason}"
    SKIPPED_GATES+=("$name")
}

# ──────────────────────────────────────────────────────────────────────────────
# GATE 1 — ruff check (lint)
# Source: ci.yml lint-job "Ruff check"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "ruff-lint" \
    "ruff check ."

# ──────────────────────────────────────────────────────────────────────────────
# GATE 2 — ruff format --check
# Source: ci.yml lint-job "Ruff format check"
# THE GATE THAT TRIGGERED THIS SCRIPT: PR #191 ran `ruff check` but not this.
# ──────────────────────────────────────────────────────────────────────────────
run_gate "ruff-fmt" \
    "ruff format --check ."

# ──────────────────────────────────────────────────────────────────────────────
# GATE 3 — mypy with bidirectional baseline filter
# Source: ci.yml types-job "Mypy (baseline-filtered)"
# NOTE: mypy_baseline is strict in BOTH directions — refactors that resolve
# baseline entries also fail the gate. See CLAUDE.md and Never Do These.
# ──────────────────────────────────────────────────────────────────────────────
run_gate "mypy" \
    "mypy app/ 2>&1 | $PY -m mypy_baseline filter --no-colors"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 4 — import layer boundaries
# Source: ci.yml structure-job "Import boundaries"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "lint-imports" \
    "lint-imports"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 5 — repo-wide complexity (CC ≤ 25)
# Source: ci.yml structure-job "Complexity (repo-wide, CC ≤ 25)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "complexity" \
    "bash scripts/check_complexity.sh"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 6 — maintainability index (>5% drop = fail)
# Source: ci.yml structure-job "Maintainability index (>5% drop = fail)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "maintainability" \
    "bash scripts/check_maintainability.sh"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 7 — strict complexity (CC ≤ 15 on changed files)
# Source: ci.yml structure-job "Complexity (strict, CC ≤ 15 on changed files)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "complexity-strict" \
    "bash scripts/check_complexity_strict.sh"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 8 — dead code (vulture, baselined)
# Source: ci.yml structure-job "Dead code (vulture, baselined)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "vulture" \
    "bash scripts/check_vulture.sh"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 9 — bandit security lint (high severity, baselined)
# Source: ci.yml security-job "Bandit (high severity, baselined)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "bandit" \
    "bandit -r app/ -lll --exclude app/tests -b .bandit-baseline.json"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 10 — threshold parity (lock ↔ source ↔ doc must agree)
# Source: ci.yml security-job "Threshold parity (lock ↔ source ↔ doc)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "thresholds-parity" \
    "$PY scripts/check_thresholds_parity.py"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 11 — filter schema sync (filters.json vs FILTER_REGISTRY)
# Source: ci.yml security-job "Filter schema sync (filters.json vs FILTER_REGISTRY)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "filter-schema" \
    "bash scripts/check_filter_schema.sh"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 12 — SQL lint (sqlfluff, baselined)
# Source: ci.yml security-job "SQL lint (sqlfluff, baselined)"
# ──────────────────────────────────────────────────────────────────────────────
run_gate "sqlfluff" \
    "bash scripts/check_sqlfluff.sh"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 13 — secret scanning (gitleaks)
# Source: ci.yml secrets job "Gitleaks"
# CI uses --redact; local uses --verbose (same as CLAUDE.md Essential Commands)
# ──────────────────────────────────────────────────────────────────────────────
run_gate "gitleaks" \
    "gitleaks detect --source . --verbose"

# ──────────────────────────────────────────────────────────────────────────────
# GATE 14 — unit tests (pytest)
# Source: ci.yml test job "Run unit tests"
# SLOW — skipped with --fast
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$FAST" -eq 1 ]]; then
    skip_gate "pytest" "--fast flag set"
else
    run_gate "pytest" \
        "pytest -m 'not integration and not database and not slow' --ignore=app/tests/database --ignore=app/tests/routes --tb=short --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=0 -q"
fi

# ──────────────────────────────────────────────────────────────────────────────
# GATE 15 — diff-coverage gate (changed lines only, ≥80%)
# Source: ci.yml test job "Diff coverage gate (changed lines only, >=80%)"
# SLOW — skipped with --fast; also skipped if pytest was skipped (no coverage.xml)
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$FAST" -eq 1 ]]; then
    skip_gate "diff-cover" "--fast flag set"
elif [[ -z "$SINGLE_GATE" || "$SINGLE_GATE" == "diff-cover" ]]; then
    if [[ ! -f coverage.xml ]]; then
        skip_gate "diff-cover" "coverage.xml not found — run pytest gate first"
    else
        run_gate "diff-cover" \
            "diff-cover coverage.xml --compare-branch=origin/main --fail-under=80 --exclude '*app/routes/*' '*app/services/*' '*app/tests/routes/*' '*app/schemas/*'"
    fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# GATE 16 — per-layer coverage floor (absolute)
# Source: ci.yml test job "Per-layer coverage floor (absolute)"
# SLOW — skipped with --fast; also skipped if no coverage.xml
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$FAST" -eq 1 ]]; then
    skip_gate "coverage-floor" "--fast flag set"
elif [[ -z "$SINGLE_GATE" || "$SINGLE_GATE" == "coverage-floor" ]]; then
    if [[ ! -f coverage.xml ]]; then
        skip_gate "coverage-floor" "coverage.xml not found — run pytest gate first"
    else
        run_gate "coverage-floor" \
            "$PY scripts/check_coverage_floor.py"
    fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# GATE 17 — Newman acceptance tests
# Source: ci.yml acceptance job "Run Postman collections"
# SLOW — skipped with --fast; also skipped if no server is reachable and
# NEWMAN_REQUIRE_SERVER is not set.
#
# Requires: server running on KITCHEN_API_PORT (default 8000), newman globally.
# Start server: bash run_dev_quiet.sh (in another terminal)
# Newman reference: Newman is one of the gates scripts/verify.sh runs; when
# only the postman collection changed, you can run
# `bash scripts/verify.sh --gate newman` instead of the full sweep.
# ──────────────────────────────────────────────────────────────────────────────
if [[ "$FAST" -eq 1 ]]; then
    skip_gate "newman" "--fast flag set"
elif [[ -z "$SINGLE_GATE" || "$SINGLE_GATE" == "newman" ]]; then
    NEWMAN_REQUIRE_SERVER="${NEWMAN_REQUIRE_SERVER:-0}"
    _NEWMAN_PORT="${KITCHEN_API_PORT:-8000}"
    _NEWMAN_BASE_URL="${NEWMAN_BASE_URL:-http://localhost:${_NEWMAN_PORT}}"
    if ! curl -sf "${_NEWMAN_BASE_URL}/docs" > /dev/null 2>&1; then
        if [[ "$NEWMAN_REQUIRE_SERVER" -eq 1 ]]; then
            echo ""
            echo -e "${RED}FAIL${RESET} newman — server not reachable on ${_NEWMAN_BASE_URL} (NEWMAN_REQUIRE_SERVER=1)"
            FAILED_GATES+=("newman")
        else
            skip_gate "newman" "server not reachable on ${_NEWMAN_BASE_URL} — start with: bash run_dev_quiet.sh"
        fi
    elif ! command -v newman &>/dev/null; then
        skip_gate "newman" "newman not installed — install with: npm install -g newman"
    else
        # Run the same collection sequence as CI (ci.yml line 495)
        run_gate "newman" \
            "NEWMAN_BASE_URL=${_NEWMAN_BASE_URL} bash scripts/run_newman.sh 000 001 002 003 004 005 006 007 008 011 013 014 015 016 017 018 010"
    fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BOLD}  VERIFY SUMMARY${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

total_run=$(( ${#PASSED_GATES[@]} + ${#FAILED_GATES[@]} ))
echo "  Run: ${total_run} | Passed: ${#PASSED_GATES[@]} | Failed: ${#FAILED_GATES[@]} | Skipped: ${#SKIPPED_GATES[@]}"
echo ""

if [[ ${#PASSED_GATES[@]} -gt 0 ]]; then
    echo "  PASSED:"
    for g in "${PASSED_GATES[@]}"; do
        echo "    + ${g}"
    done
fi

if [[ ${#SKIPPED_GATES[@]} -gt 0 ]]; then
    echo ""
    echo "  SKIPPED:"
    for g in "${SKIPPED_GATES[@]}"; do
        echo "    - ${g}"
    done
fi

if [[ ${#FAILED_GATES[@]} -gt 0 ]]; then
    echo ""
    echo -e "  ${RED}FAILED:${RESET}"
    for g in "${FAILED_GATES[@]}"; do
        echo -e "    ${RED}x ${g}${RESET}"
    done
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${RED}${BOLD}  VERIFY FAILED — fix the gates above before pushing${RESET}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}${BOLD}  VERIFY PASSED — all required gates green${RESET}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 0
fi
