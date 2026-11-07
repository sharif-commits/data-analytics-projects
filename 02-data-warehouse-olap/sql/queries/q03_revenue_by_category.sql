-- Q3. Which product categories generate the most revenue?
-- @result q03_category_revenue
WITH by_category AS (
    SELECT p.category, sum(f.revenue) AS revenue, count(*) AS units
    FROM fact_order_item f
    JOIN v_product p USING (product_key)
    GROUP BY 1
)
SELECT rank() OVER (ORDER BY revenue DESC) AS rank, category, units, revenue,
       round(100.0 * revenue / sum(revenue) OVER (), 2) AS pct_of_total,
       round(100.0 * sum(revenue) OVER (ORDER BY revenue DESC) / sum(revenue) OVER (), 2) AS cumulative_pct
FROM by_category
ORDER BY revenue DESC;
