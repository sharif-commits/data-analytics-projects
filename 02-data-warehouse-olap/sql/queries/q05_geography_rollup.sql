-- Q5. Roll up geography from city to state to region, on where the customer lives.

-- @result q05_geography_rollup
SELECT CASE GROUPING(g.region_name, g.state_code, g.city_name)
            WHEN 7 THEN 'grand total' WHEN 3 THEN 'region' WHEN 1 THEN 'state' ELSE 'city' END AS level,
       g.region_name AS region, g.state_code AS state, g.city_name AS city,
       count(DISTINCT f.order_key) AS orders,
       sum(f.revenue) AS revenue,
       round(100.0 * sum(f.revenue) / (SELECT sum(revenue) FROM fact_order_item), 2) AS pct_of_total
FROM fact_order_item f
JOIN dim_customer c USING (customer_key)
JOIN v_geo g USING (zip_key)
GROUP BY ROLLUP (g.region_name, g.state_code, g.city_name)
ORDER BY revenue DESC;

-- @result q05_regions
SELECT g.region_name AS region, count(DISTINCT g.state_code) AS states,
       count(DISTINCT f.order_key) AS orders, sum(f.revenue) AS revenue,
       round(100.0 * sum(f.revenue) / (SELECT sum(revenue) FROM fact_order_item), 2) AS pct_of_total,
       round(sum(f.revenue) / count(DISTINCT f.order_key), 2) AS revenue_per_order
FROM fact_order_item f
JOIN dim_customer c USING (customer_key)
JOIN v_geo g USING (zip_key)
GROUP BY 1
ORDER BY revenue DESC;
