-- =====================================================================
-- Q3. Which PRODUCT CATEGORIES generate the most revenue?
--     Walks the product hierarchy one level up (product -> category) and
--     adds a Pareto (cumulative share) column so the concentration of
--     revenue across categories is visible directly in the result.
-- =====================================================================

-- (a) Categories ranked by revenue, with cumulative share --------------
SELECT category,
       ROUND(SUM(revenue), 2)                                            AS revenue,
       ROUND(SUM(price), 2)                                              AS product_revenue,
       ROUND(SUM(freight_value), 2)                                      AS freight_revenue,
       COUNT(*)                                                          AS units_sold,
       COUNT(DISTINCT order_id)                                          AS orders,
       COUNT(DISTINCT product_id)                                        AS distinct_products,
       ROUND(AVG(price), 2)                                              AS avg_unit_price,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)        AS pct_of_total,
       ROUND(100.0 * SUM(SUM(revenue)) OVER (ORDER BY SUM(revenue) DESC
                                             ROWS UNBOUNDED PRECEDING)
             / SUM(SUM(revenue)) OVER (), 2)                             AS cumulative_pct
FROM v_sales
GROUP BY category
ORDER BY revenue DESC;

-- (b) Roll-up of category revenue by customer region (cross-tab feed) --
SELECT category,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'Southeast'), 2)     AS southeast,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'South'), 2)         AS south,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'Northeast'), 2)     AS northeast,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'Central-West'), 2)  AS central_west,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'North'), 2)         AS north,
       ROUND(SUM(revenue), 2)                                                  AS total
FROM v_sales
GROUP BY category
ORDER BY total DESC
LIMIT 15;
