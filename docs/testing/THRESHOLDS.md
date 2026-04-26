# Quality thresholds

Single source of truth for every numeric gate enforced in CI. Every row is bound to:

- The **source file** that actually runs the gate (column "Configured in").
- [`thresholds.lock.yaml`](thresholds.lock.yaml) — machine-readable mirror.
- [`scripts/check_thresholds_parity.py`](../../scripts/check_thresholds_parity.py) — CI step that fails if any of the three disagree.

When you bump a threshold, all three get updated in the same PR. CI tells you which one is out of step.

**No "Suggested next" column.** Use `scripts/coverage_ratchet.py` (or the layer report in `scripts/check_coverage_floor.py`) to find the next ratchet — grounded in current measurements, not vibes.

## Gates

| Gate | Current value | Last raised | Reason | Configured in |
|---|---|---|---|---|
| `diff-coverage` | 80 | 2026-04-25 | Restored from 50 to 80; K6..KN HTTPException envelope sweep complete (kitchen#66 closed, kitchen#87 closed). | `.github/workflows/ci.yml` (`diff-cover --fail-under=80`) |
| `max-cc-repo-wide` | 25 | 2026-04-10 | Baselined at current worst-case; new code above this must be refactored, not accepted into the baseline. | `scripts/check_complexity.sh` (`MAX_CC`) |
| `max-cc-strict-changed` | 15 | 2026-04-10 | Tighter gate on changed files so new/edited code is held to a stricter bar than pre-existing debt. | `scripts/check_complexity_strict.sh` (`STRICT_CC`) |
| `maintainability-max-drop` | 8 | 2026-04-26 | Percentage-point drop in radon MI that fails the gate — caught restructures that made files materially harder to maintain. Loosened from 5 in fix/issue-128 (live.py +50 lines of validation code). Restore to 5 once concerns are split. | `scripts/check_maintainability.sh` (`MAX_DROP`) |
| `layer-coverage-utils` | 40 | 2026-04-19 | Baselined ~5pt below measured weighted coverage (49.5%). Catches test deletion without source change. | `scripts/check_coverage_floor.py` (`LAYER_FLOORS["utils"]`) |
| `layer-coverage-auth` | 25 | 2026-04-19 | Baselined ~5pt below measured weighted coverage (34.5%). | `scripts/check_coverage_floor.py` |
| `layer-coverage-security` | 20 | 2026-04-19 | Baselined ~5pt below measured weighted coverage (27.2%). | `scripts/check_coverage_floor.py` |
| `layer-coverage-gateways` | 45 | 2026-04-19 | Baselined ~5pt below measured weighted coverage (55.9%). | `scripts/check_coverage_floor.py` |
| `layer-coverage-i18n` | 30 | 2026-04-19 | Baselined ~5pt below measured weighted coverage (40.2%). | `scripts/check_coverage_floor.py` |
| `mutation-kill-rate` | 65 | 2026-04-20 | Baselined ~5pt below cleaned-up Tier-1 rate (70.6% after excluding 103 equivalent mutants — log/error-text mutations). See `MUTATION_TRIAGE.md`. | `.github/workflows/mutation.yml` (`KILL_RATE_MIN`) |

## Ratcheting

Do not raise a floor unless local measurements show headroom. Steps:

1. Regenerate `coverage.xml`: `pytest -m "not integration and not database and not slow" --ignore=app/tests/database --ignore=app/tests/routes --cov=app --cov-report=xml --cov-fail-under=0`
2. Inspect candidates: `python scripts/coverage_ratchet.py --floor 40 --headroom 10` (adjust per layer).
3. Pick a bump size ≤ (current − floor) ÷ 2 so one bad PR can't put the layer below.
4. Update the source file, `thresholds.lock.yaml`, and this doc in the same PR.

## Non-numeric gates (not tracked here)

`ruff check`, `ruff format`, `lint-imports`, `bandit`, `sqlfluff`, `vulture`, `pip-audit`, `gitleaks`, the route auth-allowlist policy test, and every pytest invariant are pass/fail with no knob to ratchet — they belong in `docs/testing/README.md`, not here.

## Advisory (non-blocking) signals

`analyze_crap.py` currently runs as a non-blocking step in `ci.yml`. When it flips to blocking, its threshold moves into the table above and the lock.
