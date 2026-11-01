-- =====================================================================
--  Assignment 2 / Part 1 / Task 2  --  STEP 5: LOAD VALIDATION
--  Returns one row per assertion.  run_etl.py fails the build if any
--  row comes back with status <> 'PASS'.
-- =====================================================================
WITH checks AS (

    -- ---------- completeness: nothing was dropped ----------
    SELECT 1 AS id,
           'fact_order_item row count == order_items.csv row count' AS check_name,
           (SELECT COUNT(*) FROM stg_order_items)::DOUBLE  AS expected,
           (SELECT COUNT(*) FROM fact_order_item)::DOUBLE  AS actual

    UNION ALL SELECT 2,
           'fact_order_payment row count == order_payments.csv row count',
           (SELECT COUNT(*) FROM stg_order_payments)::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_payment)::DOUBLE

    UNION ALL SELECT 3,
           'distinct orders in fact == distinct orders in order_items.csv',
           (SELECT COUNT(DISTINCT trim(order_id)) FROM stg_order_items)::DOUBLE,
           (SELECT COUNT(DISTINCT order_id) FROM fact_order_item)::DOUBLE

    -- ---------- grain integrity ----------
    UNION ALL SELECT 4,
           'fact grain is unique on (order_id, order_item_id)',
           (SELECT COUNT(*) FROM fact_order_item)::DOUBLE,
           (SELECT COUNT(*) FROM (SELECT DISTINCT order_id, order_item_id
                                  FROM fact_order_item))::DOUBLE

    -- ---------- measure reconciliation ----------
    UNION ALL SELECT 5,
           'SUM(revenue) in fact == SUM(price + freight) in staging (2dp)',
           (SELECT ROUND(SUM(TRY_CAST(price AS DOUBLE)
                           + TRY_CAST(freight_value AS DOUBLE)), 2)
            FROM stg_order_items)::DOUBLE,
           (SELECT ROUND(SUM(revenue), 2) FROM fact_order_item)::DOUBLE

    UNION ALL SELECT 6,
           'SUM(payment_value) in fact == SUM in staging (2dp)',
           (SELECT ROUND(SUM(TRY_CAST(payment_value AS DOUBLE)), 2)
            FROM stg_order_payments)::DOUBLE,
           (SELECT ROUND(SUM(payment_value), 2) FROM fact_order_payment)::DOUBLE

    -- ---------- "not dropped" requirements, stated explicitly ----------
    UNION ALL SELECT 7,
           'items whose order has NO delivery date are kept (delivered_date_key = -1)',
           (SELECT COUNT(*) FROM stg_items_typed i
              JOIN stg_orders_typed o ON o.order_id = i.order_id
             WHERE o.delivered_ts IS NULL)::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_item WHERE delivered_date_key = -1)::DOUBLE

    UNION ALL SELECT 8,
           'orders with NO review are kept (review_key = -1)',
           (SELECT COUNT(DISTINCT i.order_id)
              FROM stg_items_typed i
             WHERE NOT EXISTS (SELECT 1 FROM dim_review r
                                WHERE r.order_id = i.order_id))::DOUBLE,
           (SELECT COUNT(DISTINCT order_id) FROM fact_order_item
             WHERE review_key = -1)::DOUBLE

    -- ---------- referential integrity of the snowflake hierarchies ----------
    UNION ALL SELECT 9,
           'geography: every dim_zip.city_key resolves (orphans)',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_zip z
             WHERE NOT EXISTS (SELECT 1 FROM dim_city c WHERE c.city_key = z.city_key))::DOUBLE

    UNION ALL SELECT 10,
           'geography: every dim_city.state_key resolves (orphans)',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_city c
             WHERE NOT EXISTS (SELECT 1 FROM dim_state s WHERE s.state_key = c.state_key))::DOUBLE

    UNION ALL SELECT 11,
           'geography: every dim_state.region_key resolves (orphans)',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_state s
             WHERE NOT EXISTS (SELECT 1 FROM dim_region r WHERE r.region_key = s.region_key))::DOUBLE

    UNION ALL SELECT 12,
           'geography: no zip fell back to the Unknown city member',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_zip WHERE zip_key <> -1 AND city_key = -1)::DOUBLE

    UNION ALL SELECT 13,
           'geography: no city fell back to the Unknown state member',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_city WHERE city_key <> -1 AND state_key = -1)::DOUBLE

    UNION ALL SELECT 14,
           'product: every dim_product.category_key resolves (orphans)',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_product p
             WHERE NOT EXISTS (SELECT 1 FROM dim_category c WHERE c.category_key = p.category_key))::DOUBLE

    UNION ALL SELECT 15,
           'seller: every dim_seller.acquisition_key resolves (orphans)',
           0::DOUBLE,
           (SELECT COUNT(*) FROM dim_seller s
             WHERE NOT EXISTS (SELECT 1 FROM dim_seller_acquisition a
                                WHERE a.acquisition_key = s.acquisition_key))::DOUBLE

    -- ---------- no unexpected fallback to Unknown on the fact table ----------
    UNION ALL SELECT 16,
           'fact: no line item lost its customer',
           0::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_item WHERE customer_key = -1)::DOUBLE

    UNION ALL SELECT 17,
           'fact: no line item lost its seller',
           0::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_item WHERE seller_key = -1)::DOUBLE

    UNION ALL SELECT 18,
           'fact: no line item lost its product',
           0::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_item WHERE product_key = -1)::DOUBLE

    UNION ALL SELECT 19,
           'fact: every purchase date resolved in dim_date',
           0::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_item WHERE purchase_date_key = -1)::DOUBLE

    UNION ALL SELECT 20,
           'dim_date covers the full range of dates present in the data',
           0::DOUBLE,
           (SELECT COUNT(*) FROM fact_order_item f
             WHERE NOT EXISTS (SELECT 1 FROM dim_date d WHERE d.date_key = f.estimated_date_key))::DOUBLE

    UNION ALL SELECT 21,
           'customer dimension is unique on customer_id',
           (SELECT COUNT(*) FROM dim_customer)::DOUBLE,
           (SELECT COUNT(DISTINCT customer_id) FROM dim_customer)::DOUBLE

    UNION ALL SELECT 22,
           'review dimension is unique on order_id (one review per order)',
           (SELECT COUNT(*) FROM dim_review WHERE review_key <> -1)::DOUBLE,
           (SELECT COUNT(DISTINCT order_id) FROM dim_review WHERE review_key <> -1)::DOUBLE
)
SELECT id,
       check_name,
       expected,
       actual,
       CASE WHEN COALESCE(expected, -999999) = COALESCE(actual, -999999)
            THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks
ORDER BY id;
