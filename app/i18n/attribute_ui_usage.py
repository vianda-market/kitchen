"""UI-usage inventory: columns rendered in at least one frontend today.

Denominator for the Phase 2 coverage lint. Maintained per schema PR.

Key format: <schema>.<table>.<column>
Optional tag: surfaces — list of frontend names that render this column.
  Valid surface names: "platform", "app", "home"

Columns omitted from this inventory either:
  (a) never ship in any API response, or
  (b) ship in responses but no frontend references them — these are over-exposure
      candidates surfaced by the Phase 2 enriched-endpoint-vs-inventory lint.
"""

from typing import TypedDict


class InventoryEntry(TypedDict, total=False):
    surfaces: list[str]  # optional — which frontends render this column


INVENTORY: dict[str, InventoryEntry] = {
    # --- external.iso4217_currency ---
    #
    # .code surfaces as "currency_code" in enriched responses (renamed at the JOIN layer).
    # vianda-platform: types/api.ts (CreditCurrencyResponseSchema, MarketEnrichedSchema, etc.),
    #   utils/columnConfigs.ts, utils/formConfigs.ts — rendered in currency dropdowns and bills.
    # vianda-app: api/types.ts (expected_payout_local_currency context), SyncUserMarketToSelector.tsx.
    "external.iso4217_currency.code": {"surfaces": ["platform", "app"]},
    #
    # .name surfaces as "currency_name" in enriched responses (renamed at the JOIN layer).
    # vianda-platform: types/api.ts (CreditCurrencyResponseSchema, EnrichedPlanResponseSchema),
    #   utils/formConfigs.ts — rendered in credit currency form dropdowns and plan forms.
    "external.iso4217_currency.name": {"surfaces": ["platform"]},
}
