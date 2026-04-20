#!/usr/bin/env bash
# Build and post/update a sticky PR comment with coverage + ratchet state.
#
# Combines (a) total line coverage, (b) five lowest-covered files in testable
# layers, (c) per-layer floor vs measured, (d) diff-cover summary on changed
# lines. Single sticky comment per PR — matched by an HTML marker so pushes
# update in place instead of spamming.
#
# Pattern from infra-kitchen-gcp/scripts/build_pr_coverage_comment.sh.
#
# Requires: coverage.xml in cwd, diff-cover, gh, $GITHUB_TOKEN in env, the
# $PR_NUMBER and $GITHUB_REPOSITORY env vars (GitHub Actions sets these).
#
# Usage (CI):
#   bash scripts/build_pr_coverage_comment.sh
# Usage (local dry run — prints body, does not post):
#   DRY_RUN=1 PR_NUMBER=123 GITHUB_REPOSITORY=vianda-market/kitchen \
#     bash scripts/build_pr_coverage_comment.sh

set -euo pipefail

MARKER="<!-- coverage-pr-comment -->"
XML="${XML:-coverage.xml}"

if [[ ! -f "$XML" ]]; then
    echo "ERROR: $XML not found. Run pytest with --cov-report=xml first." >&2
    exit 1
fi

# --- Section 1: total coverage ---
total_rate=$(python3 -c "
import xml.etree.ElementTree as ET
root = ET.parse('$XML').getroot()
print(f'{float(root.get(\"line-rate\") or 0) * 100:.1f}')
")

# --- Section 2: five lowest-covered files in testable layers ---
worst_files=$(python3 - "$XML" <<'PY'
import sys
import xml.etree.ElementTree as ET

testable_prefixes = ("utils/", "auth/", "security/", "gateways/", "i18n/")
root = ET.parse(sys.argv[1]).getroot()
rows = []
for cls in root.iter("class"):
    filename = cls.get("filename") or ""
    if not filename.startswith(testable_prefixes):
        continue
    lines = len(cls.findall(".//line"))
    if lines < 10:
        continue
    rate = float(cls.get("line-rate") or 0) * 100
    rows.append((filename, rate, lines))

rows.sort(key=lambda r: r[1])
if not rows:
    print("(no testable files with ≥10 lines — unusual; investigate)")
else:
    for filename, rate, lines in rows[:5]:
        print(f"| `{filename}` | {rate:.1f}% | {lines} |")
PY
)

# --- Section 3: per-layer floor vs measured ---
layer_table=$(python3 - "$XML" <<'PY'
import sys
import xml.etree.ElementTree as ET

LAYER_FLOORS = {"utils": 40, "auth": 25, "security": 20, "gateways": 45, "i18n": 30}
EXCLUDED = {
    "gateways/ads/google/campaign_gateway.py",
    "gateways/ads/meta/campaign_gateway.py",
    "utils/gcs.py",
    "utils/db_pool.py",
}

root = ET.parse(sys.argv[1]).getroot()
per_layer = {layer: [] for layer in LAYER_FLOORS}
for cls in root.iter("class"):
    filename = cls.get("filename") or ""
    if filename in EXCLUDED:
        continue
    lines = len(cls.findall(".//line"))
    if lines < 5:
        continue
    rate = float(cls.get("line-rate") or 0) * 100
    for layer in per_layer:
        if filename.startswith(layer + "/"):
            per_layer[layer].append((rate, lines))
            break

for layer, floor in LAYER_FLOORS.items():
    rows = per_layer[layer]
    if not rows:
        continue
    total = sum(v for _, v in rows)
    weighted = sum(r * v for r, v in rows) / total
    status = "✅" if weighted >= floor else "❌"
    print(f"| `{layer}` | {weighted:.1f}% | {floor}% | {status} |")
PY
)

# --- Section 4: diff-cover summary on changed lines ---
diff_summary=""
if command -v diff-cover >/dev/null 2>&1; then
    tmp_md=$(mktemp)
    # diff-cover exits non-zero when coverage < threshold; we want the output
    # regardless. --markdown-report writes to a file (it doesn't support
    # stdout markdown as of 9.x).
    diff-cover "$XML" --compare-branch=origin/main \
        --fail-under=0 \
        --exclude "*app/routes/*" "*app/services/*" \
        --markdown-report "$tmp_md" >/dev/null 2>&1 || true
    if [[ -s "$tmp_md" ]]; then
        # Strip the top-level heading — we embed inside our own section.
        diff_summary=$(tail -n +2 "$tmp_md")
    fi
    rm -f "$tmp_md"
fi

# --- Compose comment body ---
body="$MARKER
## 📊 Coverage report

**Total line coverage:** \`${total_rate}%\`

### Per-layer floors

| Layer | Measured | Floor | |
|---|---|---|---|
${layer_table}

### Five lowest-covered files (testable layers, ≥10 lines)

| File | Coverage | Lines |
|---|---|---|
${worst_files}

> Tip: \`python scripts/coverage_ratchet.py --suggest 40 --include utils/\` finds the next ratchet target.

### Changed-lines coverage

<details><summary>diff-cover output (click to expand)</summary>

\`\`\`
${diff_summary}
\`\`\`

</details>

<sub>Thresholds: see [\`docs/testing/THRESHOLDS.md\`](../blob/main/docs/testing/THRESHOLDS.md). Comment auto-updated on every push.</sub>"

# --- Dry run: print and exit ---
if [[ "${DRY_RUN:-}" == "1" ]]; then
    echo "=== DRY RUN ==="
    echo "$body"
    exit 0
fi

# --- Post or update sticky comment ---
if [[ -z "${PR_NUMBER:-}" || -z "${GITHUB_REPOSITORY:-}" ]]; then
    echo "ERROR: PR_NUMBER and GITHUB_REPOSITORY must be set." >&2
    exit 2
fi

existing_id=$(gh api "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" \
              --paginate --jq ".[] | select(.body | contains(\"${MARKER}\")) | .id" \
              | head -1)

if [[ -n "$existing_id" ]]; then
    echo "Updating existing comment ${existing_id}"
    gh api "repos/${GITHUB_REPOSITORY}/issues/comments/${existing_id}" \
        --method PATCH -f body="$body" >/dev/null
else
    echo "Posting new coverage comment on PR ${PR_NUMBER}"
    gh pr comment "${PR_NUMBER}" --body "$body"
fi
