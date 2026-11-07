-- Each row is one check: name, expected value, actual value. The ETL fails if any pair differs.
SELECT 'order_items rows kept' AS check_name, (SELECT count(*) FROM stg.order_items)::VARCHAR AS expected, (SELECT count(*) FROM fact_order_item)::VARCHAR AS actual
UNION ALL SELECT 'payment rows kept', (SELECT count(*) FROM stg.order_payments)::VARCHAR, (SELECT count(*) FROM fact_order_payment)::VARCHAR
UNION ALL SELECT 'orders kept', (SELECT count(*) FROM stg.orders)::VARCHAR, (SELECT count(*) FROM dim_order)::VARCHAR
UNION ALL SELECT 'review rows kept', (SELECT count(*) FROM stg.order_reviews)::VARCHAR, (SELECT count(*) FROM dim_review)::VARCHAR
UNION ALL SELECT 'customers kept', (SELECT count(*) FROM stg.customers)::VARCHAR, (SELECT count(*) FROM dim_customer)::VARCHAR
UNION ALL SELECT 'sellers kept', (SELECT count(*) FROM stg.sellers)::VARCHAR, (SELECT count(*) FROM dim_seller)::VARCHAR
UNION ALL SELECT 'products kept', (SELECT count(*) FROM stg.products)::VARCHAR, (SELECT count(*) FROM dim_product)::VARCHAR
UNION ALL SELECT 'closed deals kept', (SELECT count(*) FROM stg.closed_deals)::VARCHAR, (SELECT count(*) - 1 FROM dim_seller_acquisition)::VARCHAR
UNION ALL SELECT 'revenue total is 15843553.24', '15843553.24', (SELECT sum(revenue)::VARCHAR FROM fact_order_item)
UNION ALL SELECT 'payment total is 16008872.12', '16008872.12', (SELECT sum(payment_value)::VARCHAR FROM fact_order_payment)
UNION ALL SELECT 'revenue total matches source',
    (SELECT sum(CAST(price AS DECIMAL(12,2)) + CAST(freight_value AS DECIMAL(12,2)))::VARCHAR FROM stg.order_items),
    (SELECT sum(revenue)::VARCHAR FROM fact_order_item)
UNION ALL SELECT 'revenue = price + freight on every row', '0', (SELECT count(*)::VARCHAR FROM fact_order_item WHERE revenue <> price + freight_value)
UNION ALL SELECT 'orders with no delivery date kept',
    (SELECT count(*)::VARCHAR FROM stg.orders WHERE order_delivered_customer_date IS NULL),
    (SELECT count(*)::VARCHAR FROM dim_order WHERE delivered_date_key = -1)
UNION ALL SELECT 'orders with no review kept (768)', '768',
    (SELECT count(*)::VARCHAR FROM dim_order o WHERE NOT EXISTS (SELECT 1 FROM dim_review r WHERE r.order_key = o.order_key))
UNION ALL SELECT 'orders with no items kept (775)', '775',
    (SELECT count(*)::VARCHAR FROM dim_order o WHERE NOT EXISTS (SELECT 1 FROM fact_order_item f WHERE f.order_key = o.order_key))
UNION ALL SELECT 'customers reach a known region', '0', (SELECT count(*)::VARCHAR FROM dim_customer c JOIN v_geo g USING (zip_key) WHERE g.region_key = -1)
UNION ALL SELECT 'sellers reach a known region', '0', (SELECT count(*)::VARCHAR FROM dim_seller s JOIN v_geo g USING (zip_key) WHERE g.region_key = -1)
UNION ALL SELECT 'customer state agrees with zip hierarchy', '0',
    (SELECT count(*)::VARCHAR FROM stg.customers c JOIN dim_customer d USING (customer_id) JOIN v_geo g USING (zip_key) WHERE g.state_code <> upper(trim(c.customer_state)))
-- 35 sellers typed a state that contradicts their own zip and city (e.g. Curitiba marked SP).
-- The zip hierarchy corrects them; this check pins that count so a change is noticed.
UNION ALL SELECT 'sellers corrected by the zip hierarchy (35)', '35',
    (SELECT count(*)::VARCHAR FROM stg.sellers s JOIN dim_seller d USING (seller_id) JOIN v_geo g USING (zip_key) WHERE g.state_code <> upper(trim(s.seller_state)))
UNION ALL SELECT 'every category name resolved', '0',
    (SELECT count(*)::VARCHAR FROM stg.products p JOIN dim_product d USING (product_id) WHERE p.product_category_name IS NOT NULL AND d.category_key = -1)
UNION ALL SELECT 'products with no category go to Unknown',
    (SELECT count(*)::VARCHAR FROM stg.products WHERE product_category_name IS NULL),
    (SELECT count(*)::VARCHAR FROM dim_product WHERE category_key = -1)
UNION ALL SELECT 'purchase date always known', '0', (SELECT count(*)::VARCHAR FROM fact_order_item WHERE purchase_date_key = -1)
UNION ALL SELECT 'sellers linked to a closed deal (380)', '380',
    (SELECT count(*)::VARCHAR FROM dim_seller WHERE acquisition_key <> -1)
UNION ALL SELECT 'no city name has a separator or starts with a digit', '0',
    (SELECT count(*)::VARCHAR FROM dim_city WHERE regexp_matches(city_name, '[/\\,@]|^[0-9]'));
