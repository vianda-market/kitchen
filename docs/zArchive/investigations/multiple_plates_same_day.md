# Multiple Plates Per Restaurant Per Day – Exploratory Check

## Goal
Verify the current backend permits more than one plate for the same restaurant and kitchen day without schema or service constraints, as preparation for expanding plate registration.

## Approach
Ran a short psycopg2 script (via `python3 - <<'PY'`) against `kitchen_db_dev` that:
- grabbed an existing active restaurant and user
- inserted two new `product_info` rows for that institution (names: `Exploratory Product 1` and `Exploratory Product 2`)
- created matching `plate_info` records pointing to the same restaurant, with identical credit/no-show settings
- assigned both plates to `Tuesday` in `plate_kitchen_days`
- queried the join to confirm both entries share the same kitchen day

## Findings
- Inserts for `plate_info` and `plate_kitchen_days` succeeded without constraint violations.
- Result query shows both plates mapped to `Tuesday`, confirming the schema already allows overlapping availability:

```
('a63d24cb-3dde-4d39-abb0-db9618e6d6a1', 'Exploratory Product 1', 'Tuesday')
('4c24f802-0d84-41cd-a041-8f3ba9a13d2f', 'Exploratory Product 2', 'Tuesday')
```

## Notes / Follow Ups
- These exploratory rows remain in the dev database. We can keep them for future tests or remove them later via:
  ```
  DELETE FROM plate_kitchen_days WHERE plate_id IN (...);
  DELETE FROM plate_info WHERE plate_id IN (...);
  DELETE FROM product_info WHERE product_id IN (...);
  ```
- Next steps in the execution plan: add automated coverage and extend Postman flows to exercise multi-plate scenarios.

