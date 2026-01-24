# Data Quality Rules (PoC)

## Missing values
- A value is considered missing if it is NULL after parsing / cleaning.

## Outliers
- Outliers are detected using the IQR rule:
  - Q1 = 25th percentile
  - Q3 = 75th percentile
  - IQR = Q3 - Q1
  - lower = Q1 - 1.5 * IQR
  - upper = Q3 + 1.5 * IQR

## SQL safety
- Only SELECT queries are allowed.
- Queries without LIMIT may be limited to 50 rows for CLI readability.
