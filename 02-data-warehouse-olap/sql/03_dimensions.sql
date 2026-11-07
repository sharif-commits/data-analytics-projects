-- Dimensions load top-down: each level is loaded before the level that points to it.
-- The foreign keys in 01_schema.sql reject any other order.

CREATE MACRO date_key(ts) AS coalesce(CAST(strftime(CAST(ts AS TIMESTAMP), '%Y%m%d') AS INTEGER), -1);

-- Lower-case, remove accents and apostrophes, and collapse spaces.
CREATE MACRO norm_city(c) AS
    regexp_replace(regexp_replace(lower(trim(strip_accents(c))), '[´`’'']', '', 'g'), '\s+', ' ', 'g');

-- Sellers typed free text such as "sao paulo - sp" or an e-mail address. Keep the part before the
-- first separator, and reject anything that is not a plausible name.
CREATE MACRO clean_city(c) AS
    CASE WHEN c IS NULL OR c LIKE '%@%' OR NOT regexp_matches(norm_city(c), '^[a-z]') THEN NULL
         ELSE trim(regexp_split_to_array(norm_city(c), '\s*[/\\,]\s*|\s+-\s+|-[a-z]{2}$')[1])
    END;

-- Region and state come from the hand-written seed file, because region is not in the data.
INSERT INTO dim_region VALUES (-1, 'Unknown');
INSERT INTO dim_region
SELECT row_number() OVER (ORDER BY region_name), region_name
FROM (SELECT DISTINCT region_name FROM stg.state_region);

INSERT INTO dim_state VALUES (-1, '??', 'Unknown', -1);
INSERT INTO dim_state
SELECT row_number() OVER (ORDER BY s.state_code), s.state_code, s.state_name, r.region_key
FROM stg.state_region s
JOIN dim_region r USING (region_name);

-- One canonical (state, city) per zip prefix, so the hierarchy stays strict.
-- A prefix can cover several cities, so the most frequent one in geolocation.csv wins, with ties
-- broken alphabetically. Zips missing from geolocation.csv fall back to customer and seller addresses.
CREATE TEMP TABLE zip_votes AS
SELECT zip, state, city, sum(n) AS n
FROM (
    SELECT geolocation_zip_code_prefix AS zip, upper(trim(geolocation_state)) AS state,
           norm_city(geolocation_city) AS city, count(*) AS n
    FROM stg.geolocation GROUP BY 1, 2, 3
    UNION ALL
    SELECT customer_zip_code_prefix, upper(trim(customer_state)), clean_city(customer_city), count(*)
    FROM stg.customers
    WHERE customer_zip_code_prefix NOT IN (SELECT geolocation_zip_code_prefix FROM stg.geolocation)
    GROUP BY 1, 2, 3
    UNION ALL
    SELECT seller_zip_code_prefix, upper(trim(seller_state)), clean_city(seller_city), count(*)
    FROM stg.sellers
    WHERE seller_zip_code_prefix NOT IN (SELECT geolocation_zip_code_prefix FROM stg.geolocation)
    GROUP BY 1, 2, 3
)
WHERE city IS NOT NULL AND city <> ''
GROUP BY 1, 2, 3;

CREATE TEMP TABLE zip_state AS
SELECT zip, state FROM (
    SELECT zip, state, row_number() OVER (PARTITION BY zip ORDER BY sum(n) DESC, state) AS rk
    FROM zip_votes GROUP BY zip, state
) WHERE rk = 1;

CREATE TEMP TABLE zip_canon AS
SELECT zip, state, city FROM (
    SELECT v.zip, v.state, v.city,
           row_number() OVER (PARTITION BY v.zip ORDER BY v.n DESC, v.city) AS rk
    FROM zip_votes v JOIN zip_state s ON s.zip = v.zip AND s.state = v.state
) WHERE rk = 1;

INSERT INTO dim_city VALUES (-1, 'unknown', -1);
INSERT INTO dim_city
SELECT row_number() OVER (ORDER BY st.state_code, z.city), z.city, st.state_key
FROM (SELECT DISTINCT state, city FROM zip_canon) z
JOIN dim_state st ON st.state_code = z.state;

-- Median coordinates resist the handful of geolocation rows that fall outside Brazil.
INSERT INTO dim_zip VALUES (-1, 'unknown', -1, NULL, NULL);
INSERT INTO dim_zip
SELECT row_number() OVER (ORDER BY z.zip), z.zip, c.city_key, g.lat, g.lng
FROM zip_canon z
JOIN dim_state st ON st.state_code = z.state
JOIN dim_city c ON c.city_name = z.city AND c.state_key = st.state_key
LEFT JOIN (
    SELECT geolocation_zip_code_prefix AS zip, upper(trim(geolocation_state)) AS state,
           round(median(CAST(geolocation_lat AS DOUBLE)), 6) AS lat,
           round(median(CAST(geolocation_lng AS DOUBLE)), 6) AS lng
    FROM stg.geolocation GROUP BY 1, 2
) g ON g.zip = z.zip AND g.state = z.state;

-- Calendar, generated from the earliest and latest years used anywhere in the data.
CREATE TEMP TABLE calendar AS
WITH used AS (
    SELECT CAST(order_purchase_timestamp AS TIMESTAMP) AS d FROM stg.orders
    UNION ALL SELECT CAST(order_delivered_customer_date AS TIMESTAMP) FROM stg.orders
    UNION ALL SELECT CAST(order_estimated_delivery_date AS TIMESTAMP) FROM stg.orders
    UNION ALL SELECT CAST(shipping_limit_date AS TIMESTAMP) FROM stg.order_items
    UNION ALL SELECT CAST(review_creation_date AS TIMESTAMP) FROM stg.order_reviews
    UNION ALL SELECT CAST(won_date AS TIMESTAMP) FROM stg.closed_deals
    UNION ALL SELECT CAST(first_contact_date AS TIMESTAMP) FROM stg.leads
),
bounds AS (SELECT min(year(d)) AS y0, max(year(d)) AS y1 FROM used)
SELECT CAST(unnest(generate_series(make_date(y0, 1, 1), make_date(y1, 12, 31), INTERVAL 1 DAY)) AS DATE) AS d
FROM bounds;

INSERT INTO dim_year VALUES (-1, NULL);
INSERT INTO dim_year SELECT DISTINCT year(d), year(d) FROM calendar;

INSERT INTO dim_quarter VALUES (-1, NULL, -1);
INSERT INTO dim_quarter SELECT DISTINCT year(d) * 10 + quarter(d), quarter(d), year(d) FROM calendar;

INSERT INTO dim_month VALUES (-1, NULL, 'Unknown', -1);
INSERT INTO dim_month
SELECT DISTINCT year(d) * 100 + month(d), month(d), monthname(d), year(d) * 10 + quarter(d) FROM calendar;

INSERT INTO dim_date VALUES (-1, NULL, NULL, 'Unknown', NULL, -1);
INSERT INTO dim_date
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER), d, day(d), dayname(d), isodow(d) >= 6, year(d) * 100 + month(d)
FROM calendar;

-- Product hierarchy. Two categories have no translation in categories.csv; the seed file adds them.
INSERT INTO dim_category VALUES (-1, 'unknown', 'unknown');
INSERT INTO dim_category
SELECT row_number() OVER (ORDER BY product_category_name), product_category_name, product_category_name_english
FROM (SELECT product_category_name, product_category_name_english FROM stg.categories
      UNION SELECT product_category_name, product_category_name_english FROM stg.category_extra);

INSERT INTO dim_product
SELECT row_number() OVER (ORDER BY p.product_id), p.product_id, coalesce(c.category_key, -1),
       CAST(CAST(p.product_name_lenght AS DOUBLE) AS INTEGER),
       CAST(CAST(p.product_description_lenght AS DOUBLE) AS INTEGER),
       CAST(CAST(p.product_photos_qty AS DOUBLE) AS INTEGER),
       CAST(CAST(p.product_weight_g AS DOUBLE) AS INTEGER),
       CAST(CAST(p.product_length_cm AS DOUBLE) AS INTEGER),
       CAST(CAST(p.product_height_cm AS DOUBLE) AS INTEGER),
       CAST(CAST(p.product_width_cm AS DOUBLE) AS INTEGER)
FROM stg.products p
LEFT JOIN dim_category c ON c.category_name_pt = p.product_category_name;

-- Seller hierarchy. Key -1 marks sellers with no closed deal, i.e. not recruited through the funnel.
INSERT INTO dim_lead_origin VALUES (-1, 'not_in_funnel');
INSERT INTO dim_lead_origin
SELECT row_number() OVER (ORDER BY origin), origin
FROM (SELECT DISTINCT coalesce(origin, 'unknown') AS origin FROM stg.leads);

INSERT INTO dim_seller_acquisition VALUES (-1, 'none', -1, NULL, NULL, NULL, -1, -1);
INSERT INTO dim_seller_acquisition
SELECT row_number() OVER (ORDER BY d.mql_id), d.mql_id, o.lead_origin_key, d.business_segment, d.lead_type,
       d.business_type, date_key(l.first_contact_date), date_key(d.won_date)
FROM stg.closed_deals d
JOIN stg.leads l USING (mql_id)
JOIN dim_lead_origin o ON o.lead_origin = coalesce(l.origin, 'unknown');

INSERT INTO dim_seller
SELECT row_number() OVER (ORDER BY s.seller_id), s.seller_id, z.zip_key, coalesce(a.acquisition_key, -1)
FROM stg.sellers s
JOIN dim_zip z ON z.zip_prefix = s.seller_zip_code_prefix
LEFT JOIN stg.closed_deals d ON d.seller_id = s.seller_id
LEFT JOIN dim_seller_acquisition a ON a.mql_id = d.mql_id;

INSERT INTO dim_customer
SELECT row_number() OVER (ORDER BY c.customer_id), c.customer_id, c.customer_unique_id, z.zip_key
FROM stg.customers c
JOIN dim_zip z ON z.zip_prefix = c.customer_zip_code_prefix;

-- Order level.
INSERT INTO dim_order_status
SELECT row_number() OVER (ORDER BY order_status), order_status
FROM (SELECT DISTINCT order_status FROM stg.orders);

INSERT INTO dim_order
SELECT row_number() OVER (ORDER BY o.order_id), o.order_id, c.customer_key, s.order_status_key,
       date_key(o.order_purchase_timestamp), date_key(o.order_delivered_customer_date),
       date_key(o.order_estimated_delivery_date),
       CAST(o.order_purchase_timestamp AS TIMESTAMP), CAST(o.order_approved_at AS TIMESTAMP),
       CAST(o.order_delivered_carrier_date AS TIMESTAMP), CAST(o.order_delivered_customer_date AS TIMESTAMP),
       CAST(o.order_estimated_delivery_date AS TIMESTAMP),
       date_diff('day', CAST(o.order_estimated_delivery_date AS DATE), CAST(o.order_delivered_customer_date AS DATE))
FROM stg.orders o
JOIN dim_customer c USING (customer_id)
JOIN dim_order_status s USING (order_status);

INSERT INTO dim_review
SELECT row_number() OVER (ORDER BY r.review_id, o.order_key), r.review_id, o.order_key,
       CAST(r.review_score AS INTEGER),
       r.review_comment_title IS NOT NULL OR r.review_comment_message IS NOT NULL,
       date_key(r.review_creation_date), CAST(r.review_answer_timestamp AS TIMESTAMP)
FROM stg.order_reviews r
JOIN dim_order o USING (order_id);

INSERT INTO dim_payment_type
SELECT row_number() OVER (ORDER BY payment_type), payment_type
FROM (SELECT DISTINCT payment_type FROM stg.order_payments);
