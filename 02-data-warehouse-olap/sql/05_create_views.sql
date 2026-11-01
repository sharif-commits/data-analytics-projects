-- =====================================================================
--  Assignment 2 / Part 1  --  STEP 4: ANALYTIC VIEWS
--  A snowflake schema is deliberately normalised, which means every
--  analytical query has to re-walk the same 4-level geography chain and
--  2-level product chain.  These two views encapsulate that navigation
--  once so the Task-3 queries stay readable.  They are plain views (no
--  materialisation), so all aggregation still happens on the base tables.
-- =====================================================================

-- ---------------------------------------------------------------------
-- v_sales : fact_order_item flattened through the whole snowflake.
--           One row per (order_id, order_item_id) -- the fact grain.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_sales AS
SELECT f.order_item_sk,
       f.order_id,
       f.order_item_id,

       -- ---- calendar (purchase date role) ----
       dp.full_date        AS purchase_date,
       dp.year             AS purchase_year,
       dp.quarter          AS purchase_quarter,
       dp.month            AS purchase_month,
       dp.month_name       AS purchase_month_name,
       dp.year_quarter     AS purchase_year_quarter,
       dp.year_month       AS purchase_year_month,

       -- ---- customer geography (zip -> city -> state -> region) ----
       cu.customer_key,
       cu.customer_id,
       cu.customer_unique_id,
       cz.zip_code_prefix  AS customer_zip,
       cc.city_name        AS customer_city,
       cs.state_code       AS customer_state,
       cs.state_name       AS customer_state_name,
       cr.region_name      AS customer_region,

       -- ---- seller geography (same conformed hierarchy) ----
       se.seller_key,
       se.seller_id,
       sz.zip_code_prefix  AS seller_zip,
       sc.city_name        AS seller_city,
       ss.state_code       AS seller_state,
       ss.state_name       AS seller_state_name,
       sr.region_name      AS seller_region,

       -- ---- seller acquisition (lead origin -> acquisition -> seller) ----
       lo.lead_origin,
       lo.lead_origin_group,
       sa.business_segment,
       sa.lead_type,
       sa.business_type,
       sa.won_date,
       (sa.acquisition_key <> -1) AS seller_from_funnel,

       -- ---- product (category -> product) ----
       pr.product_key,
       pr.product_id,
       ca.category_name_english AS category,
       ca.category_name_pt      AS category_pt,

       -- ---- order status / delivery performance ----
       os.order_status,
       db.delivery_bucket,
       ds.delivery_status,
       ds.sort_order       AS delivery_status_order,
       f.delivery_days,
       f.delivery_delay_days,
       f.approval_hours,

       -- ---- review ----
       rv.review_score,
       rv.review_score_band,
       rv.has_comment,
       (rv.review_key <> -1) AS has_review,

       -- ---- measures ----
       f.price,
       f.freight_value,
       f.revenue,
       f.items_in_order
FROM fact_order_item f
JOIN dim_date               dp ON dp.date_key       = f.purchase_date_key
JOIN dim_customer           cu ON cu.customer_key   = f.customer_key
JOIN dim_zip                cz ON cz.zip_key        = cu.zip_key
JOIN dim_city               cc ON cc.city_key       = cz.city_key
JOIN dim_state              cs ON cs.state_key      = cc.state_key
JOIN dim_region             cr ON cr.region_key     = cs.region_key
JOIN dim_seller             se ON se.seller_key     = f.seller_key
JOIN dim_zip                sz ON sz.zip_key        = se.zip_key
JOIN dim_city               sc ON sc.city_key       = sz.city_key
JOIN dim_state              ss ON ss.state_key      = sc.state_key
JOIN dim_region             sr ON sr.region_key     = ss.region_key
JOIN dim_seller_acquisition sa ON sa.acquisition_key = se.acquisition_key
JOIN dim_lead_origin        lo ON lo.lead_origin_key = sa.lead_origin_key
JOIN dim_product            pr ON pr.product_key    = f.product_key
JOIN dim_category           ca ON ca.category_key   = pr.category_key
JOIN dim_order_status       os ON os.order_status_key = f.order_status_key
JOIN dim_delivery_bucket    db ON db.delivery_bucket_key = f.delivery_bucket_key
JOIN dim_delivery_status    ds ON ds.delivery_status_key = db.delivery_status_key
JOIN dim_review             rv ON rv.review_key     = f.review_key;

-- ---------------------------------------------------------------------
-- v_orders : one row per ORDER.  Needed for any question about orders
--            rather than line items -- e.g. average review score by
--            delivery timeliness (Q9), where using item grain would
--            weight a 1-star order with 6 items six times over.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_orders AS
SELECT order_id,
       ANY_VALUE(customer_key)         AS customer_key,
       ANY_VALUE(customer_unique_id)   AS customer_unique_id,
       ANY_VALUE(customer_city)        AS customer_city,
       ANY_VALUE(customer_state)       AS customer_state,
       ANY_VALUE(customer_region)      AS customer_region,
       ANY_VALUE(purchase_date)        AS purchase_date,
       ANY_VALUE(purchase_year)        AS purchase_year,
       ANY_VALUE(purchase_quarter)     AS purchase_quarter,
       ANY_VALUE(purchase_month)       AS purchase_month,
       ANY_VALUE(order_status)         AS order_status,
       ANY_VALUE(delivery_status)      AS delivery_status,
       ANY_VALUE(delivery_bucket)      AS delivery_bucket,
       ANY_VALUE(delivery_status_order) AS delivery_status_order,
       ANY_VALUE(delivery_days)        AS delivery_days,
       ANY_VALUE(delivery_delay_days)  AS delivery_delay_days,
       ANY_VALUE(review_score)         AS review_score,
       ANY_VALUE(has_review)           AS has_review,
       COUNT(*)                        AS n_items,
       COUNT(DISTINCT seller_id)       AS n_sellers,
       SUM(price)                      AS order_price,
       SUM(freight_value)              AS order_freight,
       SUM(revenue)                    AS order_revenue
FROM v_sales
GROUP BY order_id;
