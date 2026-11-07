-- Q7. Which sellers generate the highest revenue in their state?
-- A seller's state comes from the seller's own zip, through the shared geography hierarchy.
-- @result q07_top_seller_per_state
WITH by_seller AS (
    SELECT g.state_code AS state, g.region_name AS region, s.seller_id, g.city_name AS city,
           sum(f.revenue) AS revenue, count(*) AS items
    FROM fact_order_item f
    JOIN dim_seller s USING (seller_key)
    JOIN v_geo g USING (zip_key)
    GROUP BY 1, 2, 3, 4
)
SELECT state, region, seller_id, city, items, revenue,
       round(100.0 * revenue / sum(revenue) OVER (PARTITION BY state), 2) AS pct_of_state,
       count(*) OVER (PARTITION BY state) AS sellers_in_state,
       sum(revenue) OVER (PARTITION BY state) AS state_revenue
FROM by_seller
QUALIFY rank() OVER (PARTITION BY state ORDER BY revenue DESC) = 1
ORDER BY revenue DESC;
