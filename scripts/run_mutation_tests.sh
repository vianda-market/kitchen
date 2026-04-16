#!/usr/bin/env bash
# Run mutation testing on critical business logic (Tier 1).
#
# Scoped to: credit validation, credit loading, discretionary credits,
# institution billing. These are the modules where a surviving mutant
# means potential financial loss.
#
# Usage:
#   ./scripts/run_mutation_tests.sh             # full run
#   ./scripts/run_mutation_tests.sh --quick     # time-estimate only
#
# Requires: mutmut (pip install mutmut)
# Runtime: expect 10-30 minutes depending on test suite speed.

set -euo pipefail

if ! command -v mutmut &>/dev/null; then
    echo "ERROR: mutmut not found. Install with: pip install mutmut" >&2
    exit 1
fi

if [ "${1:-}" = "--quick" ]; then
    echo "Estimating mutation test time..."
    mutmut print-time-estimates
    exit 0
fi

echo "=== Mutation Testing — Tier 1 Critical Business Logic ==="
echo ""
echo "Targets:"
echo "  - app/services/credit_validation_service.py"
echo "  - app/services/credit_loading_service.py"
echo "  - app/services/discretionary_service.py"
echo "  - app/services/billing/institution_billing.py"
echo ""
echo "This will take a while. Each mutant runs the relevant test suite."
echo "---"
echo ""

mutmut run

echo ""
echo "=== Results ==="
mutmut results

# Check for survivors
survivors=$(mutmut results 2>&1 | grep -c "survived" || true)
if [ "$survivors" -gt 0 ]; then
    echo ""
    echo "WARNING: $survivors mutant(s) survived — tests did not catch these mutations."
    echo ""
    echo "To inspect survivors:"
    echo "  mutmut show <mutant_name>    # see the mutation diff"
    echo "  mutmut browse               # interactive TUI browser"
    echo ""
    echo "Common fixes:"
    echo "  - Add a test that asserts the specific behavior the mutant changed"
    echo "  - Check boundary conditions (off-by-one, wrong comparison operator)"
    echo "  - Verify return values are actually asserted, not just called"
fi
