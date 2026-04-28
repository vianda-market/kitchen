#!/usr/bin/env bash
# scripts/test_parallel_newman.sh — smoke test for parallel Newman execution.
#
# PURPOSE
#   Validates that two kitchen API instances can run simultaneously on different
#   ports against different databases, each serving Newman collection 000 without
#   interfering with each other.
#
# PREREQUISITES
#   - Postgres running locally with CREATEDB privilege for $DB_USER
#     (one-time: ALTER USER <db_user> CREATEDB;)
#   - newman installed globally (npm install -g newman)
#   - Python venv at venv/ or .venv/ with kitchen deps installed
#   - scripts/worktree_env.sh present (part of this PR)
#
# USAGE (from repository root)
#   bash scripts/test_parallel_newman.sh
#
# What it does:
#   1. Forks two background subshells, each operating from a tmp dir whose path
#      causes worktree_env.sh to derive a distinct port + DB name.
#   2. Each subshell: builds its DB, starts the API on the unique port, runs
#      Newman collection 000 against it.
#   3. Both must exit 0 for the smoke test to pass.
#   4. Cleans up (drops DBs, kills API processes) in the EXIT trap.
#
# NOTE: This script is intentionally run by hand to demonstrate the parallel
# contract. It is NOT wired into CI (each CI job already gets an isolated
# runner with its own Postgres). Wire it as a local pre-push hook if desired.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DB_USER="${DB_USER:-${USER:-cdeachaval}}"
LOG_DIR="$(mktemp -d)"

echo "=== Parallel Newman smoke test ==="
echo "    repo:     ${REPO_ROOT}"
echo "    log dir:  ${LOG_DIR}"
echo ""

# ── Cleanup trap ─────────────────────────────────────────────────────────────
PIDS=()
DBS_TO_DROP=()

cleanup() {
    echo ""
    echo "=== Cleanup ==="
    for pid in "${PIDS[@]:-}"; do
        kill "$pid" 2>/dev/null || true
    done
    for db in "${DBS_TO_DROP[@]:-}"; do
        echo "    dropping DB: $db"
        psql -h localhost -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${db};" 2>/dev/null || true
    done
    echo "    removing log dir: ${LOG_DIR}"
    rm -rf "${LOG_DIR}"
    echo "Done."
}
trap cleanup EXIT

# ── Helper: run one agent slot ────────────────────────────────────────────────
# Arguments: <slot_index> <fake_worktree_path>
run_slot() {
    local slot="$1"
    local fake_pwd="$2"
    local log="${LOG_DIR}/slot${slot}.log"

    (
        # Derive env the same way worktree_env.sh does but without sourcing it
        # (subshell has its own $PWD that we want to be fake_pwd)
        local WORKTREE_HASH
        WORKTREE_HASH=$(printf '%s' "${fake_pwd}" | shasum | cut -c1-6)
        local PORT_OFFSET=$(( 16#${WORKTREE_HASH:0:4} % 1000 ))
        local API_PORT=$(( 8000 + PORT_OFFSET ))
        local DB_NAME="kitchen_${WORKTREE_HASH}"
        local BASE_URL="http://localhost:${API_PORT}"

        echo "[slot${slot}] port=${API_PORT}  db=${DB_NAME}  base_url=${BASE_URL}" | tee -a "${log}"

        # Export for the scripts we call
        export KITCHEN_API_PORT="${API_PORT}"
        export KITCHEN_DB_NAME="${DB_NAME}"
        export NEWMAN_BASE_URL="${BASE_URL}"
        export DB_NAME="${DB_NAME}"

        # Build DB (fresh)
        echo "[slot${slot}] Building DB ${DB_NAME}..." | tee -a "${log}"
        # create DB if it does not exist
        psql -h localhost -U "${DB_USER}" -d postgres \
            -c "CREATE DATABASE ${DB_NAME};" 2>>"${log}" || true
        DB_NAME="${DB_NAME}" SKIP_PYTEST=1 SKIP_POST_REBUILD_SYNC=1 \
            bash "${REPO_ROOT}/app/db/build_kitchen_db.sh" >>"${log}" 2>&1

        # Start API
        echo "[slot${slot}] Starting API on port ${API_PORT}..." | tee -a "${log}"
        DB_NAME="${DB_NAME}" \
            bash "${REPO_ROOT}/run_dev_trusted_only_error.sh" >>"${log}" 2>&1 &
        local API_PID=$!
        echo "[slot${slot}] API PID=${API_PID}" | tee -a "${log}"

        # Wait up to 20s for API to become ready
        local retries=0
        until curl -sf "${BASE_URL}/docs" > /dev/null 2>&1; do
            sleep 1
            retries=$(( retries + 1 ))
            if (( retries >= 20 )); then
                echo "[slot${slot}] ERROR: API did not start in time" | tee -a "${log}"
                kill "${API_PID}" 2>/dev/null || true
                exit 1
            fi
        done
        echo "[slot${slot}] API ready after ${retries}s" | tee -a "${log}"

        # Run Newman collection 000
        echo "[slot${slot}] Running Newman 000..." | tee -a "${log}"
        NEWMAN_BASE_URL="${BASE_URL}" \
            bash "${REPO_ROOT}/scripts/run_newman.sh" 000 >>"${log}" 2>&1
        local newman_exit=$?

        kill "${API_PID}" 2>/dev/null || true

        if [[ "${newman_exit}" -eq 0 ]]; then
            echo "[slot${slot}] PASS" | tee -a "${log}"
        else
            echo "[slot${slot}] FAIL (newman exit ${newman_exit})" | tee -a "${log}"
        fi
        exit "${newman_exit}"
    ) &
    PIDS+=($!)
}

# ── Two fake worktree paths that are guaranteed to differ ─────────────────────
FAKE_WT_A="/tmp/kitchen-test-parallel-worktree-agent-aaaaaaaa"
FAKE_WT_B="/tmp/kitchen-test-parallel-worktree-agent-bbbbbbbb"

# Pre-compute DB names so the cleanup trap can drop them
WT_A_HASH=$(printf '%s' "${FAKE_WT_A}" | shasum | cut -c1-6)
WT_B_HASH=$(printf '%s' "${FAKE_WT_B}" | shasum | cut -c1-6)
DBS_TO_DROP=("kitchen_${WT_A_HASH}" "kitchen_${WT_B_HASH}")

echo "Forking two parallel agents..."
echo "  Slot A fake path: ${FAKE_WT_A} → hash=${WT_A_HASH}"
echo "  Slot B fake path: ${FAKE_WT_B} → hash=${WT_B_HASH}"
echo ""

run_slot "A" "${FAKE_WT_A}"
run_slot "B" "${FAKE_WT_B}"

# ── Wait for both and collect exit codes ─────────────────────────────────────
OVERALL=0
for i in "${!PIDS[@]}"; do
    pid="${PIDS[$i]}"
    slot_label="$( [[ $i -eq 0 ]] && echo A || echo B )"
    if wait "${pid}"; then
        echo "[slot${slot_label}] exited 0 — PASS"
    else
        echo "[slot${slot_label}] exited non-zero — FAIL"
        OVERALL=1
    fi
done

echo ""
if [[ "${OVERALL}" -eq 0 ]]; then
    echo "=== PARALLEL NEWMAN SMOKE TEST: PASS ==="
else
    echo "=== PARALLEL NEWMAN SMOKE TEST: FAIL ==="
    echo "    Logs: ${LOG_DIR}/slotA.log  ${LOG_DIR}/slotB.log"
fi

exit "${OVERALL}"
