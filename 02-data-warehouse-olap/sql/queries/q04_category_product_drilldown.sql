-- Q4. Drill down from category to product to find the best-selling products.
-- ROLLUP supplies the category subtotal and the product rows together.

-- @result q04_top_products_overall
SELECT p.product_id, p.category, count(*) AS units, sum(f.revenue) AS revenue
FROM fact_order_item f
JOIN v_product p USING (product_key)
GROUP BY 1, 2
ORDER BY units DESC, revenue DESC
LIMIT 10;

-- @result q04_drilldown_top5_categories
WITH rolled AS (
    SELECT p.category, p.product_id, GROUPING(p.product_id) AS is_subtotal,
           count(*) AS units, sum(f.revenue) AS revenue
    FROM fact_order_item f
    JOIN v_product p USING (product_key)
    GROUP BY ROLLUP (p.category, p.product_id)
    HAVING GROUPING(p.category) = 0
),
ranked AS (
    SELECT *,
           max(CASE WHEN is_subtotal = 1 THEN revenue END) OVER (PARTITION BY category) AS category_revenue,
           row_number() OVER (PARTITION BY category, is_subtotal ORDER BY units DESC, revenue DESC) AS rank_in_category
    FROM rolled
)
SELECT category, CASE WHEN is_subtotal = 1 THEN 'ALL PRODUCTS' ELSE product_id END AS product,
       CASE WHEN is_subtotal = 1 THEN NULL ELSE rank_in_category END AS rank_in_category,
       units, revenue, round(100.0 * revenue / category_revenue, 2) AS pct_of_category
FROM ranked
WHERE category_revenue IN (SELECT DISTINCT category_revenue FROM ranked ORDER BY 1 DESC LIMIT 5)
  AND (is_subtotal = 1 OR rank_in_category <= 3)
ORDER BY category_revenue DESC, is_subtotal DESC, rank_in_category;
