# ETL report

## Steps

```
01_schema.sql             0.07 s
02_staging.sql            3.99 s
03_dimensions.sql         3.16 s
04_facts.sql              1.35 s
05_views.sql              0.01 s
```

## Row counts

| Table | Rows |
|---|---:|
| dim_category | 74 |
| dim_city | 6,190 |
| dim_customer | 99,441 |
| dim_date | 1,828 |
| dim_lead_origin | 11 |
| dim_month | 61 |
| dim_order | 99,441 |
| dim_order_status | 8 |
| dim_payment_type | 5 |
| dim_product | 32,951 |
| dim_quarter | 21 |
| dim_region | 6 |
| dim_review | 99,224 |
| dim_seller | 3,095 |
| dim_seller_acquisition | 843 |
| dim_state | 28 |
| dim_year | 6 |
| dim_zip | 19,178 |
| fact_order_item | 112,650 |
| fact_order_payment | 103,886 |

## Validation: 24/24 passed

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| order_items rows kept | 112650 | 112650 | PASS |
| payment rows kept | 103886 | 103886 | PASS |
| orders kept | 99441 | 99441 | PASS |
| review rows kept | 99224 | 99224 | PASS |
| customers kept | 99441 | 99441 | PASS |
| sellers kept | 3095 | 3095 | PASS |
| products kept | 32951 | 32951 | PASS |
| closed deals kept | 842 | 842 | PASS |
| revenue total is 15843553.24 | 15843553.24 | 15843553.24 | PASS |
| payment total is 16008872.12 | 16008872.12 | 16008872.12 | PASS |
| revenue total matches source | 15843553.24 | 15843553.24 | PASS |
| revenue = price + freight on every row | 0 | 0 | PASS |
| orders with no delivery date kept | 2965 | 2965 | PASS |
| orders with no review kept (768) | 768 | 768 | PASS |
| orders with no items kept (775) | 775 | 775 | PASS |
| customers reach a known region | 0 | 0 | PASS |
| sellers reach a known region | 0 | 0 | PASS |
| customer state agrees with zip hierarchy | 0 | 0 | PASS |
| sellers corrected by the zip hierarchy (35) | 35 | 35 | PASS |
| every category name resolved | 0 | 0 | PASS |
| products with no category go to Unknown | 610 | 610 | PASS |
| purchase date always known | 0 | 0 | PASS |
| sellers linked to a closed deal (380) | 380 | 380 | PASS |
| no city name has a separator or starts with a digit | 0 | 0 | PASS |
