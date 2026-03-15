# Kitchen day SLA

## Order cutoff

No new orders are accepted after **1:30 PM local time** (market timezone) for that kitchen day. Source: `MarketConfiguration.kitchen_day_config[day].kitchen_close` (13:30) in [app/config/market_config.py](../../app/config/market_config.py).

## Restaurant price and credit

Restaurants can update plate **price** and **credit** at any time; changes are live. Clients should refresh (e.g. on entering explore or pull-to-refresh) so users see current values.

## Billing and data window

Billing runs and "day close" logic use the same timezone and `kitchen_close`. Reservation opens at a configurable delay after kitchen close (e.g. 2.5h). See [KITCHEN_DAY_BILLING_EXPLANATION.md](../../billing/KITCHEN_DAY_BILLING_EXPLANATION.md) for billing timing.
