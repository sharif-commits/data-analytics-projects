-- =====================================================================
--  Assignment 2 / Part 1 / Task 2  --  STEP 2: LOAD DIMENSIONS
--  Loaded strictly TOP-DOWN so that every foreign key resolves at the
--  moment it is inserted (DuckDB enforces FK constraints on INSERT):
--
--      dim_date
--      dim_region  ->  dim_state  ->  dim_city  ->  dim_zip
--                                                    -> dim_customer
--      dim_lead_origin -> dim_seller_acquisition  --> dim_seller
--      dim_category    -> dim_product
--      dim_delivery_status -> dim_delivery_bucket
--      dim_order_status, dim_payment_type, dim_review
--
--  Every dimension receives an explicit "Unknown" member with key -1 so
--  that facts with missing attributes (no delivery date, no review, a zip
--  code absent from geolocation, a seller never seen in the marketing
--  funnel) can still be loaded instead of being dropped.
-- =====================================================================

-- =====================================================================
-- 1. dim_date  (conformed, role-playing).  Range deliberately wider than
--    the data so that estimated-delivery and won_date values also land.
-- =====================================================================
INSERT INTO dim_date VALUES
    (-1, NULL, NULL, NULL, NULL, 'Unknown', NULL, NULL, 'Unknown', NULL,
     'Unknown', 'Unknown', NULL);

INSERT INTO dim_date
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER)                         AS date_key,
       d                                                              AS full_date,
       year(d)                                                        AS year,
       quarter(d)                                                     AS quarter,
       month(d)                                                       AS month,
       monthname(d)                                                   AS month_name,
       day(d)                                                         AS day_of_month,
       dayofweek(d)                                                   AS day_of_week,
       dayname(d)                                                     AS day_name,
       weekofyear(d)                                                  AS week_of_year,
       strftime(d, '%Y-%m')                                           AS year_month,
       CAST(year(d) AS VARCHAR) || '-Q' || CAST(quarter(d) AS VARCHAR) AS year_quarter,
       dayofweek(d) IN (0, 6)                                         AS is_weekend
FROM (
    SELECT CAST(UNNEST(generate_series(TIMESTAMP '2015-01-01',
                                       TIMESTAMP '2020-12-31',
                                       INTERVAL 1 DAY)) AS DATE) AS d
) AS cal;

-- =====================================================================
-- 2. GEOGRAPHY level 1 : dim_region   (derived from the state seed file)
-- =====================================================================
INSERT INTO dim_region VALUES (-1, 'UN', 'Unknown');

INSERT INTO dim_region
SELECT ROW_NUMBER() OVER (ORDER BY region_code) AS region_key,
       region_code,
       region_name
FROM (SELECT DISTINCT trim(region_code) AS region_code,
                      trim(region_name) AS region_name
      FROM stg_state_region) r;

-- =====================================================================
-- 3. GEOGRAPHY level 2 : dim_state
-- =====================================================================
INSERT INTO dim_state VALUES (-1, 'UN', 'Unknown', -1);

INSERT INTO dim_state
SELECT ROW_NUMBER() OVER (ORDER BY s.state_code) AS state_key,
       s.state_code,
       s.state_name,
       r.region_key
FROM (SELECT DISTINCT upper(trim(state_code)) AS state_code,
                      trim(state_name)       AS state_name,
                      trim(region_code)      AS region_code
      FROM stg_state_region) s
JOIN dim_region r ON r.region_code = s.region_code;

-- =====================================================================
-- 4. Canonical zip -> (city, state) resolution  [helper table]
--    A zip code prefix appears many times in geolocation.csv and can be
--    spelled with different city names, and customers/sellers sometimes
--    disagree with geolocation.  A strict hierarchy needs exactly ONE
--    parent per zip, so we take the modal (most frequently observed)
--    (city, state) pair across all three sources and average the
--    coordinates to get a zip centroid.
-- =====================================================================
CREATE OR REPLACE TABLE stg_geo_obs AS
SELECT lpad(trim(geolocation_zip_code_prefix), 5, '0') AS zip_code_prefix,
       lower(trim(geolocation_city))                   AS city_name,
       upper(trim(geolocation_state))                  AS state_code
FROM stg_geolocation
WHERE geolocation_zip_code_prefix IS NOT NULL
UNION ALL
SELECT lpad(trim(customer_zip_code_prefix), 5, '0'),
       lower(trim(customer_city)),
       upper(trim(customer_state))
FROM stg_customers
WHERE customer_zip_code_prefix IS NOT NULL
UNION ALL
SELECT lpad(trim(seller_zip_code_prefix), 5, '0'),
       lower(trim(seller_city)),
       upper(trim(seller_state))
FROM stg_sellers
WHERE seller_zip_code_prefix IS NOT NULL;

CREATE OR REPLACE TABLE stg_zip_canonical AS
WITH obs AS (
    SELECT zip_code_prefix, city_name, state_code, COUNT(*) AS n
    FROM stg_geo_obs
    WHERE city_name IS NOT NULL AND city_name <> ''
      AND state_code IS NOT NULL AND state_code <> ''
    GROUP BY 1, 2, 3
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY zip_code_prefix
                              ORDER BY n DESC, state_code, city_name) AS rn
    FROM obs
),
centroid AS (
    SELECT lpad(trim(geolocation_zip_code_prefix), 5, '0')  AS zip_code_prefix,
           AVG(TRY_CAST(geolocation_lat AS DOUBLE))         AS latitude,
           AVG(TRY_CAST(geolocation_lng AS DOUBLE))         AS longitude
    FROM stg_geolocation
    GROUP BY 1
)
SELECT r.zip_code_prefix,
       r.city_name,
       r.state_code,
       c.latitude,
       c.longitude
FROM ranked r
LEFT JOIN centroid c USING (zip_code_prefix)
WHERE r.rn = 1;

-- =====================================================================
-- 5. GEOGRAPHY level 3 : dim_city
--    Natural key is (city_name, state_key) because city names repeat
--    across states (e.g. 'bom jesus' exists in 8 different states).
-- =====================================================================
INSERT INTO dim_city VALUES (-1, 'unknown', -1);

INSERT INTO dim_city
SELECT ROW_NUMBER() OVER (ORDER BY c.state_code, c.city_name) AS city_key,
       c.city_name,
       COALESCE(s.state_key, -1)                             AS state_key
FROM (SELECT DISTINCT city_name, state_code FROM stg_zip_canonical) c
LEFT JOIN dim_state s ON s.state_code = c.state_code;

-- =====================================================================
-- 6. GEOGRAPHY level 4 : dim_zip
-- =====================================================================
INSERT INTO dim_zip VALUES (-1, 'UNKNOWN', -1, NULL, NULL);

INSERT INTO dim_zip
SELECT ROW_NUMBER() OVER (ORDER BY z.zip_code_prefix) AS zip_key,
       z.zip_code_prefix,
       COALESCE(ci.city_key, -1)                     AS city_key,
       z.latitude,
       z.longitude
FROM stg_zip_canonical z
LEFT JOIN dim_state s  ON s.state_code = z.state_code
LEFT JOIN dim_city  ci ON ci.city_name = z.city_name
                      AND ci.state_key = COALESCE(s.state_key, -1);

-- =====================================================================
-- 7. dim_customer   (hangs off the shared geography hierarchy)
-- =====================================================================
INSERT INTO dim_customer VALUES (-1, 'UNKNOWN', 'UNKNOWN', -1);

INSERT INTO dim_customer
SELECT ROW_NUMBER() OVER (ORDER BY c.customer_id) AS customer_key,
       c.customer_id,
       c.customer_unique_id,
       COALESCE(z.zip_key, -1)                    AS zip_key
FROM (SELECT trim(customer_id)                              AS customer_id,
             trim(customer_unique_id)                       AS customer_unique_id,
             lpad(trim(customer_zip_code_prefix), 5, '0')   AS zip_code_prefix
      FROM stg_customers) c
LEFT JOIN dim_zip z ON z.zip_code_prefix = c.zip_code_prefix;

-- =====================================================================
-- 8. SELLER hierarchy level 1 : dim_lead_origin (marketing channel)
-- =====================================================================
INSERT INTO dim_lead_origin VALUES (-1, 'not_via_funnel', 'Not Acquired Via Funnel');

INSERT INTO dim_lead_origin
SELECT ROW_NUMBER() OVER (ORDER BY origin) AS lead_origin_key,
       origin,
       CASE origin
            WHEN 'paid_search'       THEN 'Paid Media'
            WHEN 'display'           THEN 'Paid Media'
            WHEN 'organic_search'    THEN 'Organic'
            WHEN 'direct_traffic'    THEN 'Organic'
            WHEN 'social'            THEN 'Owned/Social'
            WHEN 'email'             THEN 'Owned/Social'
            WHEN 'referral'          THEN 'Referral'
            ELSE 'Other/Unknown'
       END                                 AS lead_origin_group
FROM (
    SELECT DISTINCT COALESCE(NULLIF(lower(trim(origin)), ''), 'unknown') AS origin
    FROM stg_leads
) o;

-- =====================================================================
-- 9. SELLER hierarchy level 2 : dim_seller_acquisition
--    One row per won marketing deal (closed_deals x leads).
-- =====================================================================
INSERT INTO dim_seller_acquisition
    (acquisition_key, mql_id, lead_origin_key, business_segment, lead_type,
     lead_behaviour_profile, business_type, landing_page_id,
     first_contact_date_key, won_date_key, won_date, days_to_close,
     has_company, has_gtin, average_stock,
     declared_product_catalog_size, declared_monthly_revenue)
VALUES
    (-1, NULL, -1, 'Unknown', 'Unknown', 'Unknown', 'Unknown', NULL,
     -1, -1, NULL, NULL, NULL, NULL, 'Unknown', NULL, NULL);

INSERT INTO dim_seller_acquisition
SELECT ROW_NUMBER() OVER (ORDER BY d.mql_id)                             AS acquisition_key,
       d.mql_id,
       COALESCE(lo.lead_origin_key, -1)                                  AS lead_origin_key,
       COALESCE(NULLIF(lower(trim(d.business_segment)), ''), 'unknown')   AS business_segment,
       COALESCE(NULLIF(lower(trim(d.lead_type)), ''), 'unknown')          AS lead_type,
       COALESCE(NULLIF(lower(trim(d.lead_behaviour_profile)), ''), 'unknown') AS lead_behaviour_profile,
       COALESCE(NULLIF(lower(trim(d.business_type)), ''), 'unknown')      AS business_type,
       l.landing_page_id,
       COALESCE(CAST(strftime(TRY_CAST(l.first_contact_date AS DATE), '%Y%m%d') AS INTEGER), -1) AS first_contact_date_key,
       COALESCE(CAST(strftime(TRY_CAST(d.won_date AS TIMESTAMP), '%Y%m%d') AS INTEGER), -1)      AS won_date_key,
       TRY_CAST(d.won_date AS TIMESTAMP)                                  AS won_date,
       date_diff('day', TRY_CAST(l.first_contact_date AS DATE),
                        CAST(TRY_CAST(d.won_date AS TIMESTAMP) AS DATE))  AS days_to_close,
       CASE WHEN lower(trim(COALESCE(d.has_company, ''))) IN ('true','1','1.0','t','yes')  THEN TRUE
            WHEN lower(trim(COALESCE(d.has_company, ''))) IN ('false','0','0.0','f','no') THEN FALSE
            ELSE NULL END                                                AS has_company,
       CASE WHEN lower(trim(COALESCE(d.has_gtin, ''))) IN ('true','1','1.0','t','yes')  THEN TRUE
            WHEN lower(trim(COALESCE(d.has_gtin, ''))) IN ('false','0','0.0','f','no') THEN FALSE
            ELSE NULL END                                                AS has_gtin,
       COALESCE(NULLIF(lower(trim(d.average_stock)), ''), 'unknown')      AS average_stock,
       TRY_CAST(d.declared_product_catalog_size AS DOUBLE)                AS declared_product_catalog_size,
       TRY_CAST(d.declared_monthly_revenue AS DOUBLE)                     AS declared_monthly_revenue
FROM stg_closed_deals d
LEFT JOIN stg_leads l
       ON trim(l.mql_id) = trim(d.mql_id)
LEFT JOIN dim_lead_origin lo
       ON lo.lead_origin = COALESCE(NULLIF(lower(trim(l.origin)), ''), 'unknown');

-- =====================================================================
-- 10. dim_seller  (geography hierarchy + acquisition hierarchy)
--     A handful of sellers appear more than once in closed_deals; keep
--     the earliest won deal so that seller_id stays unique.
-- =====================================================================
INSERT INTO dim_seller VALUES (-1, 'UNKNOWN', -1, -1);

INSERT INTO dim_seller
WITH deal_per_seller AS (
    SELECT trim(seller_id) AS seller_id,
           trim(mql_id)    AS mql_id,
           ROW_NUMBER() OVER (PARTITION BY trim(seller_id)
                              ORDER BY TRY_CAST(won_date AS TIMESTAMP), trim(mql_id)) AS rn
    FROM stg_closed_deals
    WHERE seller_id IS NOT NULL AND trim(seller_id) <> ''
)
SELECT ROW_NUMBER() OVER (ORDER BY s.seller_id) AS seller_key,
       s.seller_id,
       COALESCE(z.zip_key, -1)                  AS zip_key,
       COALESCE(a.acquisition_key, -1)          AS acquisition_key
FROM (SELECT trim(seller_id)                            AS seller_id,
             lpad(trim(seller_zip_code_prefix), 5, '0') AS zip_code_prefix
      FROM stg_sellers) s
LEFT JOIN dim_zip z         ON z.zip_code_prefix = s.zip_code_prefix
LEFT JOIN deal_per_seller ds ON ds.seller_id = s.seller_id AND ds.rn = 1
LEFT JOIN dim_seller_acquisition a ON a.mql_id = ds.mql_id;

-- =====================================================================
-- 11. PRODUCT hierarchy level 1 : dim_category
--     Two categories present in products.csv are missing from the
--     translation file; they fall back to the Portuguese name.
-- =====================================================================
INSERT INTO dim_category VALUES (-1, 'unknown', 'unknown');

INSERT INTO dim_category
WITH cats AS (
    SELECT DISTINCT lower(trim(product_category_name)) AS category_name_pt
    FROM stg_categories
    WHERE product_category_name IS NOT NULL AND trim(product_category_name) <> ''
    UNION
    SELECT DISTINCT lower(trim(product_category_name))
    FROM stg_products
    WHERE product_category_name IS NOT NULL AND trim(product_category_name) <> ''
),
trans AS (
    SELECT lower(trim(product_category_name))         AS category_name_pt,
           lower(trim(product_category_name_english)) AS category_name_english
    FROM stg_categories
    WHERE product_category_name IS NOT NULL
)
SELECT ROW_NUMBER() OVER (ORDER BY c.category_name_pt)        AS category_key,
       c.category_name_pt,
       COALESCE(t.category_name_english, c.category_name_pt)  AS category_name_english
FROM cats c
LEFT JOIN trans t USING (category_name_pt);

-- =====================================================================
-- 12. PRODUCT hierarchy level 2 : dim_product
-- =====================================================================
INSERT INTO dim_product VALUES
    (-1, 'UNKNOWN', -1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);

INSERT INTO dim_product
SELECT ROW_NUMBER() OVER (ORDER BY p.product_id) AS product_key,
       p.product_id,
       COALESCE(c.category_key, -1)              AS category_key,
       TRY_CAST(p.product_name_lenght        AS INTEGER),
       TRY_CAST(p.product_description_lenght AS INTEGER),
       TRY_CAST(p.product_photos_qty         AS INTEGER),
       TRY_CAST(p.product_weight_g           AS INTEGER),
       TRY_CAST(p.product_length_cm          AS INTEGER),
       TRY_CAST(p.product_height_cm          AS INTEGER),
       TRY_CAST(p.product_width_cm           AS INTEGER),
       CAST(TRY_CAST(p.product_length_cm AS INTEGER)
          * TRY_CAST(p.product_height_cm AS INTEGER)
          * TRY_CAST(p.product_width_cm  AS INTEGER) AS BIGINT) AS product_volume_cm3
FROM (SELECT trim(product_id) AS product_id,
             NULLIF(lower(trim(product_category_name)), '') AS category_name_pt,
             * EXCLUDE (product_id, product_category_name)
      FROM stg_products) p
LEFT JOIN dim_category c ON c.category_name_pt = p.category_name_pt;

-- =====================================================================
-- 13. dim_order_status
-- =====================================================================
INSERT INTO dim_order_status VALUES (-1, 'unknown');

INSERT INTO dim_order_status
SELECT ROW_NUMBER() OVER (ORDER BY order_status) AS order_status_key,
       order_status
FROM (SELECT DISTINCT COALESCE(NULLIF(lower(trim(order_status)), ''), 'unknown') AS order_status
      FROM stg_orders) s;

-- =====================================================================
-- 14. DELIVERY hierarchy: dim_delivery_status <- dim_delivery_bucket
--     Compares the actual delivery date against the date promised to the
--     customer at checkout (order_estimated_delivery_date).
-- =====================================================================
INSERT INTO dim_delivery_status VALUES
    (1, 'Early',         1),
    (2, 'On Time',       2),
    (3, 'Late',          3),
    (4, 'Not Delivered', 4);

INSERT INTO dim_delivery_bucket VALUES
    ( 1, 'Early (> 7 days)',   1, 1),
    ( 2, 'Early (1-7 days)',   1, 2),
    ( 3, 'On Time (same day)', 2, 3),
    ( 4, 'Late (1-7 days)',    3, 4),
    ( 5, 'Late (> 7 days)',    3, 5),
    (-1, 'Not Delivered',      4, 6);

-- =====================================================================
-- 15. dim_payment_type
-- =====================================================================
INSERT INTO dim_payment_type VALUES (-1, 'unknown');

INSERT INTO dim_payment_type
SELECT ROW_NUMBER() OVER (ORDER BY payment_type) AS payment_type_key,
       payment_type
FROM (SELECT DISTINCT COALESCE(NULLIF(lower(trim(payment_type)), ''), 'unknown') AS payment_type
      FROM stg_order_payments) p;

-- =====================================================================
-- 16. dim_review
--     A few orders carry more than one review row.  The fact table needs
--     a single-valued foreign key, so we keep the most recent review per
--     order (deterministic tie-break on review_id).  Orders with no
--     review at all point at review_key = -1 -- they are NOT dropped.
-- =====================================================================
INSERT INTO dim_review
    (review_key, review_id, order_id, review_score, review_score_band,
     has_comment, review_creation_date_key, review_answer_date_key, response_hours)
VALUES (-1, NULL, NULL, NULL, 'No Review', FALSE, -1, -1, NULL);

INSERT INTO dim_review
WITH dedup AS (
    SELECT trim(review_id)                               AS review_id,
           trim(order_id)                                AS order_id,
           TRY_CAST(review_score AS INTEGER)             AS review_score,
           review_comment_message,
           TRY_CAST(review_creation_date  AS TIMESTAMP)  AS review_creation_ts,
           TRY_CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_ts,
           ROW_NUMBER() OVER (PARTITION BY trim(order_id)
                              ORDER BY TRY_CAST(review_creation_date AS TIMESTAMP) DESC,
                                       TRY_CAST(review_answer_timestamp AS TIMESTAMP) DESC,
                                       trim(review_id)) AS rn
    FROM stg_order_reviews
    WHERE order_id IS NOT NULL AND trim(order_id) <> ''
)
SELECT ROW_NUMBER() OVER (ORDER BY order_id)                        AS review_key,
       review_id,
       order_id,
       review_score,
       CASE WHEN review_score <= 2 THEN 'Negative'
            WHEN review_score  = 3 THEN 'Neutral'
            WHEN review_score >= 4 THEN 'Positive'
            ELSE 'Unknown' END                                      AS review_score_band,
       (review_comment_message IS NOT NULL
        AND trim(review_comment_message) <> '')                     AS has_comment,
       COALESCE(CAST(strftime(review_creation_ts, '%Y%m%d') AS INTEGER), -1) AS review_creation_date_key,
       COALESCE(CAST(strftime(review_answer_ts,  '%Y%m%d') AS INTEGER), -1)  AS review_answer_date_key,
       date_diff('minute', review_creation_ts, review_answer_ts) / 60.0      AS response_hours
FROM dedup
WHERE rn = 1;
