-- =====================================================================
-- Q1. Total revenue per YEAR, then drilled down to QUARTER and MONTH.
--     OLAP operation: ROLLUP over the time hierarchy year > quarter >
--     month.  A single pass returns all four aggregation levels
--     (grand total, year, quarter, month); GROUPING() tells them apart.
--     revenue = price + freight_value
-- =====================================================================

-- (a) Full time roll-up -----------------------------------------------
SELECT CASE WHEN GROUPING(purchase_year)    = 1 THEN 'ALL YEARS'
            ELSE CAST(purchase_year AS VARCHAR) END                     AS year,
       CASE WHEN GROUPING(purchase_quarter) = 1 THEN 'All quarters'
            ELSE 'Q' || CAST(purchase_quarter AS VARCHAR) END           AS quarter,
       CASE WHEN GROUPING(purchase_month)   = 1 THEN 'All months'
            ELSE printf('%02d', purchase_month) END                     AS month,
       CASE GROUPING(purchase_year) * 4
          + GROUPING(purchase_quarter) * 2
          + GROUPING(purchase_month)
            WHEN 7 THEN 'GRAND TOTAL'
            WHEN 3 THEN 'YEAR'
            WHEN 1 THEN 'QUARTER'
            ELSE        'MONTH' END                                     AS agg_level,
       ROUND(SUM(revenue), 2)                                           AS revenue,
       ROUND(SUM(price), 2)                                             AS product_revenue,
       ROUND(SUM(freight_value), 2)                                     AS freight_revenue,
       COUNT(DISTINCT order_id)                                         AS orders,
       COUNT(*)                                                         AS line_items
FROM v_sales
GROUP BY ROLLUP (purchase_year, purchase_quarter, purchase_month)
ORDER BY GROUPING(purchase_year) DESC,
         purchase_year,
         GROUPING(purchase_quarter) DESC,
         purchase_quarter,
         GROUPING(purchase_month) DESC,
         purchase_month;

-- (b) Year level only, with year-on-year growth ------------------------
SELECT purchase_year                                        AS year,
       ROUND(SUM(revenue), 2)                               AS revenue,
       COUNT(DISTINCT order_id)                             AS orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)    AS avg_order_value,
       ROUND(100.0 * (SUM(revenue) - LAG(SUM(revenue)) OVER (ORDER BY purchase_year))
             / NULLIF(LAG(SUM(revenue)) OVER (ORDER BY purchase_year), 0), 1) AS yoy_growth_pct
FROM v_sales
GROUP BY purchase_year
ORDER BY purchase_year;
