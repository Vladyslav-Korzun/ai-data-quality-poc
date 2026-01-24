# Dataset: Accounting Transactions (sample)

## Columns (high-level)
- Authorization Group: group id / authorization category.
- Bus. Transac. Type: business transaction type (e.g., RFBU, RFAD).
- Calculate Tax: boolean flag.
- Cash Flow-Relevant Doc.: selection-like field (Selected / Not Selected).
- Cleared Item: date/time when item was cleared (can be missing).
- Clearing Date: date/time when clearing happened (can be missing).
- Clearing Entry Date: date/time of clearing entry (can be missing).
- Clearing Fiscal Year: fiscal year of clearing (can be missing).
- Country Key: country code (e.g., US).
- Currency: currency code (e.g., USD, CAD).
- Debit/Credit ind: indicator, typically:
  - H = negative values (credit)
  - S = positive values (debit)
- Transaction Value: numeric amount (mixed locales in source, normalized in PoC).
- Document Is Back-Posted: boolean flag.
- Exchange rate: numeric exchange rate (mostly missing in the sample).
- Fiscal Year.1 / Fiscal Year.2: fiscal year fields.
- Posting period.1: posting period.
- Ref. Doc. Line Item: reference document line item.
