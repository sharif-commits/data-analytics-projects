-- Q6. Top 5 customers by total purchase amount.
-- customer_id is issued per order, so grouping by it would treat a repeat buyer as several people.
-- customer_unique_id identifies the person.
-- @result q06_top_customers
SELECT c.customer_unique_id,
       count(DISTINCT f.order_key) AS orders,
       count(*) AS items,
       sum(f.revenue) AS total_purchase,
       min(g.city_name) AS city,
       min(g.state_code) AS state
FROM fact_order_item f
JOIN dim_customer c USING (customer_key)
JOIN v_geo g USING (zip_key)
GROUP BY 1
ORDER BY total_purchase DESC
LIMIT 5;

-- How much of a difference the identifier makes.
-- @result q06_identifier_check
SELECT (SELECT count(DISTINCT customer_id) FROM dim_customer) AS customer_ids,
       (SELECT count(DISTINCT customer_unique_id) FROM dim_customer) AS real_customers,
       (SELECT count(*) FROM (SELECT customer_unique_id FROM dim_customer GROUP BY 1 HAVING count(*) > 1)) AS repeat_customers;
