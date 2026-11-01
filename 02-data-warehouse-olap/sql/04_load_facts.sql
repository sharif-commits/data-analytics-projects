-- =====================================================================
--  Assignment 2 / Part 1 / Task 2  --  STEP 3: LOAD FACT TABLES
--  Dimensions are already in place, so every surrogate key resolves.
--
--  NO-DROP GUARANTEE
--  -----------------
--  Every dimension lookup is a LEFT JOIN wrapped in COALESCE(..., -1).
--  An order that was never delivered, an order that was never reviewed,
--  a seller with an unmapped zip code -- none of these are filtered out;
--  they are routed to the "Unknown" member of the relevant dimension.
--  06_validate.sql asserts that
--      count(fact_order_item) == count(order_items.csv)
--      count(fact_order_payment) == count(order_payments.csv)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Typed projections of the two order-level staging tables
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_orders_typed AS
SELECT trim(order_id)                                            AS order_id,
       trim(customer_id)                                         AS customer_id,
       COALESCE(NULLIF(lower(trim(order_status)), ''), 'unknown') AS order_status,
       TRY_CAST(order_purchase_timestamp      AS TIMESTAMP)       AS purchase_ts,
       TRY_CAST(order_approved_at             AS TIMESTAMP)       AS approved_ts,
       TRY_CAST(order_delivered_carrier_date  AS TIMESTAMP)       AS carrier_ts,
       TRY_CAST(order_delivered_customer_date AS TIMESTAMP)       AS delivered_ts,
       TRY_CAST(order_estimated_delivery_date AS TIMESTAMP)       AS estimated_ts
FROM stg_orders;

CREATE OR REPLACE TABLE stg_items_typed AS
SELECT trim(order_id)                          AS order_id,
       TRY_CAST(order_item_id AS INTEGER)      AS order_item_id,
       trim(product_id)                        AS product_id,
       trim(seller_id)                         AS seller_id,
       TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_ts,
       TRY_CAST(price         AS DOUBLE)       AS price,
       TRY_CAST(freight_value AS DOUBLE)       AS freight_value
FROM stg_order_items;

-- =====================================================================
--  fact_order_item
--  GRAIN: one row per line item of an order -- (order_id, order_item_id)
-- =====================================================================
INSERT INTO fact_order_item
WITH item_counts AS (
    SELECT order_id, COUNT(*) AS items_in_order
    FROM stg_items_typed
    GROUP BY 1
),
joined AS (
    SELECT i.order_id,
           i.order_item_id,
           i.product_id,
           i.seller_id,
           i.price,
           i.freight_value,
           i.shipping_limit_ts,
           ic.items_in_order,
           o.customer_id,
           o.order_status,
           o.purchase_ts,
           o.approved_ts,
           o.carrier_ts,
           o.delivered_ts,
           o.estimated_ts,
           -- signed lateness in whole days: negative = early, 0 = on time
           date_diff('day', CAST(o.estimated_ts AS DATE),
                            CAST(o.delivered_ts AS DATE)) AS delay_days
    FROM stg_items_typed i
    LEFT JOIN stg_orders_typed o ON o.order_id = i.order_id
    LEFT JOIN item_counts     ic ON ic.order_id = i.order_id
)
SELECT ROW_NUMBER() OVER (ORDER BY j.order_id, j.order_item_id)  AS order_item_sk,
       j.order_id,
       j.order_item_id,
       COALESCE(c.customer_key,  -1)                             AS customer_key,
       COALESCE(s.seller_key,    -1)                             AS seller_key,
       COALESCE(p.product_key,   -1)                             AS product_key,
       COALESCE(os.order_status_key, -1)                         AS order_status_key,
       CASE WHEN j.delivered_ts IS NULL OR j.estimated_ts IS NULL THEN -1
            WHEN j.delay_days < -7 THEN 1        -- Early  (> 7 days)
            WHEN j.delay_days <  0 THEN 2        -- Early  (1-7 days)
            WHEN j.delay_days =  0 THEN 3        -- On Time (same day)
            WHEN j.delay_days <= 7 THEN 4        -- Late   (1-7 days)
            ELSE                        5        -- Late   (> 7 days)
       END                                                       AS delivery_bucket_key,
       COALESCE(r.review_key, -1)                                AS review_key,
       COALESCE(CAST(strftime(j.purchase_ts,       '%Y%m%d') AS INTEGER), -1) AS purchase_date_key,
       COALESCE(CAST(strftime(j.approved_ts,       '%Y%m%d') AS INTEGER), -1) AS approved_date_key,
       COALESCE(CAST(strftime(j.carrier_ts,        '%Y%m%d') AS INTEGER), -1) AS carrier_date_key,
       COALESCE(CAST(strftime(j.delivered_ts,      '%Y%m%d') AS INTEGER), -1) AS delivered_date_key,
       COALESCE(CAST(strftime(j.estimated_ts,      '%Y%m%d') AS INTEGER), -1) AS estimated_date_key,
       COALESCE(CAST(strftime(j.shipping_limit_ts, '%Y%m%d') AS INTEGER), -1) AS shipping_limit_date_key,
       COALESCE(j.price, 0.0)                                    AS price,
       COALESCE(j.freight_value, 0.0)                            AS freight_value,
       COALESCE(j.price, 0.0) + COALESCE(j.freight_value, 0.0)   AS revenue,
       COALESCE(j.items_in_order, 1)                             AS items_in_order,
       date_diff('day', CAST(j.purchase_ts AS DATE),
                        CAST(j.delivered_ts AS DATE))            AS delivery_days,
       j.delay_days                                              AS delivery_delay_days,
       date_diff('minute', j.purchase_ts, j.approved_ts) / 60.0   AS approval_hours
FROM joined j
LEFT JOIN dim_customer     c  ON c.customer_id  = j.customer_id
LEFT JOIN dim_seller       s  ON s.seller_id    = j.seller_id
LEFT JOIN dim_product      p  ON p.product_id   = j.product_id
LEFT JOIN dim_order_status os ON os.order_status = j.order_status
LEFT JOIN dim_review       r  ON r.order_id     = j.order_id;

-- =====================================================================
--  fact_order_payment
--  GRAIN: one row per payment transaction -- (order_id, payment_sequential)
-- =====================================================================
INSERT INTO fact_order_payment
WITH pay AS (
    SELECT trim(order_id)                            AS order_id,
           TRY_CAST(payment_sequential AS INTEGER)   AS payment_sequential,
           COALESCE(NULLIF(lower(trim(payment_type)), ''), 'unknown') AS payment_type,
           TRY_CAST(payment_installments AS INTEGER) AS payment_installments,
           TRY_CAST(payment_value AS DOUBLE)         AS payment_value
    FROM stg_order_payments
)
SELECT ROW_NUMBER() OVER (ORDER BY pay.order_id, pay.payment_sequential) AS payment_sk,
       pay.order_id,
       pay.payment_sequential,
       COALESCE(c.customer_key, -1)      AS customer_key,
       COALESCE(pt.payment_type_key, -1) AS payment_type_key,
       COALESCE(os.order_status_key, -1) AS order_status_key,
       COALESCE(CAST(strftime(o.purchase_ts, '%Y%m%d') AS INTEGER), -1) AS purchase_date_key,
       pay.payment_installments,
       COALESCE(pay.payment_value, 0.0)  AS payment_value
FROM pay
LEFT JOIN stg_orders_typed o  ON o.order_id     = pay.order_id
LEFT JOIN dim_customer     c  ON c.customer_id  = o.customer_id
LEFT JOIN dim_payment_type pt ON pt.payment_type = pay.payment_type
LEFT JOIN dim_order_status os ON os.order_status = o.order_status;