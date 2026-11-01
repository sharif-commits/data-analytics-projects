# Part 1 -- ETL run report

## Row counts after load

| table | kind | rows |
|---|---|---|
| dim_date | dimension | 2,193 |
| dim_region | dimension | 6 |
| dim_state | dimension | 28 |
| dim_city | dimension | 6,246 |
| dim_zip | dimension | 19,178 |
| dim_customer | dimension | 99,442 |
| dim_lead_origin | dimension | 11 |
| dim_seller_acquisition | dimension | 843 |
| dim_seller | dimension | 3,096 |
| dim_category | dimension | 74 |
| dim_product | dimension | 32,952 |
| dim_order_status | dimension | 9 |
| dim_delivery_status | dimension | 4 |
| dim_delivery_bucket | dimension | 6 |
| dim_payment_type | dimension | 6 |
| dim_review | dimension | 98,674 |
| fact_order_item | FACT | 112,650 |
| fact_order_payment | FACT | 103,886 |

## Load validation

| id | check_name | expected | actual | status |
|---|---|---|---|---|
| 1 | fact_order_item row count == order_items.csv row count | 112,650.00 | 112,650.00 | PASS |
| 2 | fact_order_payment row count == order_payments.csv row count | 103,886.00 | 103,886.00 | PASS |
| 3 | distinct orders in fact == distinct orders in order_items.csv | 98,666.00 | 98,666.00 | PASS |
| 4 | fact grain is unique on (order_id, order_item_id) | 112,650.00 | 112,650.00 | PASS |
| 5 | SUM(revenue) in fact == SUM(price + freight) in staging (2dp) | 15,843,553.24 | 15,843,553.24 | PASS |
| 6 | SUM(payment_value) in fact == SUM in staging (2dp) | 16,008,872.12 | 16,008,872.12 | PASS |
| 7 | items whose order has NO delivery date are kept (delivered_date_key = -1) | 2,454.00 | 2,454.00 | PASS |
| 8 | orders with NO review are kept (review_key = -1) | 749.00 | 749.00 | PASS |
| 9 | geography: every dim_zip.city_key resolves (orphans) | 0.00 | 0.00 | PASS |
| 10 | geography: every dim_city.state_key resolves (orphans) | 0.00 | 0.00 | PASS |
| 11 | geography: every dim_state.region_key resolves (orphans) | 0.00 | 0.00 | PASS |
| 12 | geography: no zip fell back to the Unknown city member | 0.00 | 0.00 | PASS |
| 13 | geography: no city fell back to the Unknown state member | 0.00 | 0.00 | PASS |
| 14 | product: every dim_product.category_key resolves (orphans) | 0.00 | 0.00 | PASS |
| 15 | seller: every dim_seller.acquisition_key resolves (orphans) | 0.00 | 0.00 | PASS |
| 16 | fact: no line item lost its customer | 0.00 | 0.00 | PASS |
| 17 | fact: no line item lost its seller | 0.00 | 0.00 | PASS |
| 18 | fact: no line item lost its product | 0.00 | 0.00 | PASS |
| 19 | fact: every purchase date resolved in dim_date | 0.00 | 0.00 | PASS |
| 20 | dim_date covers the full range of dates present in the data | 0.00 | 0.00 | PASS |
| 21 | customer dimension is unique on customer_id | 99,442.00 | 99,442.00 | PASS |
| 22 | review dimension is unique on order_id (one review per order) | 98,673.00 | 98,673.00 | PASS |
