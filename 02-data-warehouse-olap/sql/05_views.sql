-- Views flatten each snowflake hierarchy once, so the analytical queries stay readable.
CREATE VIEW v_geo AS
SELECT z.zip_key, z.zip_prefix, c.city_key, c.city_name, s.state_key, s.state_code, s.state_name,
       r.region_key, r.region_name
FROM dim_zip z
JOIN dim_city c USING (city_key)
JOIN dim_state s USING (state_key)
JOIN dim_region r USING (region_key);

CREATE VIEW v_calendar AS
SELECT d.date_key, d.full_date, m.month_key, m.month_number, m.month_name,
       q.quarter_key, q.quarter_number, y.year_key, y.year_number
FROM dim_date d
JOIN dim_month m USING (month_key)
JOIN dim_quarter q USING (quarter_key)
JOIN dim_year y USING (year_key);

CREATE VIEW v_product AS
SELECT p.product_key, p.product_id, c.category_key, c.category_name_en AS category
FROM dim_product p
JOIN dim_category c USING (category_key);

-- One row per order, so review averages are not weighted by the number of items in the order.
-- Orders with several reviews use their mean score; orders with no review keep a NULL score.
CREATE VIEW v_order_delivery AS
SELECT o.order_key, o.days_vs_estimate, s.order_status, r.review_score,
       CASE WHEN s.order_status <> 'delivered' OR o.delivered_ts IS NULL THEN 'not_delivered'
            WHEN o.days_vs_estimate < 0 THEN 'early'
            WHEN o.days_vs_estimate = 0 THEN 'on_time'
            ELSE 'late' END AS delivery_class
FROM dim_order o
JOIN dim_order_status s USING (order_status_key)
LEFT JOIN (SELECT order_key, avg(review_score) AS review_score FROM dim_review GROUP BY 1) r USING (order_key);
