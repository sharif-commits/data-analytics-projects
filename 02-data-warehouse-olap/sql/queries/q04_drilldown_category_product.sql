-- =====================================================================
-- Q4. DRILL DOWN from CATEGORY -> PRODUCT to find the best-selling
--     products.
--     OLAP operation: GROUPING SETS ((category), (category, product)) so
--     that one pass returns the category subtotal *and* the product
--     detail underneath it -- exactly what a drill-down does in a UI.
-- =====================================================================

-- (a) Top 10 categories, each followed by its top 3 products -----------
WITH lvl AS (
    SELECT category,
           product_id,
           GROUPING(product_id)  AS g_product,
           SUM(revenue)          AS revenue,
           SUM(price)            AS product_revenue,
           COUNT(*)              AS units_sold,
           COUNT(DISTINCT order_id) AS orders
    FROM v_sales
    GROUP BY GROUPING SETS ((category), (category, product_id))
),
cat_rank AS (                       -- rank the categories by their subtotal
    SELECT category, revenue,
           ROW_NUMBER() OVER (ORDER BY revenue DESC) AS cat_rank
    FROM lvl
    WHERE g_product = 1
),
labelled AS (
    SELECT l.category,
           CASE WHEN l.g_product = 1 THEN '-- category subtotal --'
                ELSE l.product_id END                     AS product_id,
           CASE WHEN l.g_product = 1 THEN 'CATEGORY' ELSE 'PRODUCT' END AS agg_level,
           l.revenue, l.product_revenue, l.units_sold, l.orders,
           l.g_product,
           cr.cat_rank,
           cr.revenue                                     AS category_revenue,
           CASE WHEN l.g_product = 1 THEN 0
                ELSE ROW_NUMBER() OVER (PARTITION BY l.category, l.g_product
                                        ORDER BY l.revenue DESC) END AS rank_in_category
    FROM lvl l
    JOIN cat_rank cr USING (category)
)
SELECT cat_rank,
       category,
       agg_level,
       product_id,
       rank_in_category,
       ROUND(revenue, 2)                                        AS revenue,
       units_sold,
       orders,
       ROUND(100.0 * revenue / category_revenue, 1)             AS pct_of_category
FROM labelled
WHERE cat_rank <= 10
  AND (g_product = 1 OR rank_in_category <= 3)
ORDER BY cat_rank, g_product DESC, revenue DESC;

-- (b) Overall best-selling products (leaf level of the hierarchy) ------
SELECT product_id,
       ANY_VALUE(category)                       AS category,
       ROUND(SUM(revenue), 2)                    AS revenue,
       COUNT(*)                                  AS units_sold,
       COUNT(DISTINCT order_id)                  AS orders,
       ROUND(AVG(price), 2)                      AS avg_unit_price
FROM v_sales
GROUP BY product_id
ORDER BY revenue DESC
LIMIT 15;
