# Data Dictionary — Inspected Nassau Candy Distributor Dataset

| Field | Type in source | Meaning / dashboard use |
|---|---|---|
| Row ID | integer | Unique row identifier; validated for duplicates |
| Order ID | text | Order-level identifier; repeated across line items is expected |
| Order Date | text → datetime | Order date; primary time field |
| Ship Date | text → datetime | Ship date; retained for validation only because observed lags are anomalous |
| Ship Mode | text | Shipping method; descriptive only |
| Customer ID | integer | Customer identifier |
| Country/Region | text | Customer/order country |
| City | text | Customer/order city |
| State/Province | text | Customer/order state/province |
| Postal Code | text | Postal code retained as source text |
| Division | text | Product division/category |
| Region | text | Business/geographic region |
| Product ID | text | Product identifier |
| Product Name | text | Product name; primary product analysis dimension |
| Sales | numeric | Revenue input |
| Units | integer | Units sold |
| Gross Profit | numeric | Gross profit input |
| Cost | numeric | Cost input |

## Source quality results

- 10,194 rows, 18 columns.
- Missing values: none.
- Duplicate full rows: 0.
- Duplicate Row IDs: 0.
- Invalid Order Dates: 0.
- Sales/Units/Gross Profit/Cost zero values: 0.
- Sales/Units/Gross Profit/Cost negative values: 0.
- Sales − Cost − Gross Profit mismatch above $0.01: 0.
- Duplicate Order IDs: 1,645 repeated rows; treated as line-item repetition, not duplicate records.
- Ship-before-order rows: 0, but ship dates are 904–1,642 days after order dates and therefore require source-system confirmation.
