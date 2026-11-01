-- =====================================================================
-- Q2. The month with the HIGHEST revenue in each year.
--     OLAP operation: drill down the time hierarchy to month level, then
--     rank within each year (QUALIFY = HAVING for window functions).
-- =====================================================================

-- (a) Peak month per year ---------------------------------------------
WITH monthly AS (
    SELECT purchase_year               AS year,
           purchase_month              AS month,
           ANY_VALUE(purchase_month_name) AS month_name,
           SUM(revenue)                AS revenue,
           COUNT(DISTINCT order_id)    AS orders
    FROM v_sales
    GROUP BY purchase_year, purchase_month
)
SELECT year,
       month,
       month_name,
       ROUND(revenue, 2)                                                AS revenue,
       orders,
       ROUND(revenue / orders, 2)                                       AS avg_order_value,
       ROUND(100.0 * revenue / SUM(revenue) OVER (PARTITION BY year), 1) AS pct_of_year_revenue
FROM monthly
QUALIFY ROW_NUMBER() OVER (PARTITION BY year ORDER BY revenue DESC) = 1
ORDER BY year;

-- (b) Supporting detail: every month ranked inside its year ------------
WITH monthly AS (
    SELECT purchase_year AS year,
           purchase_month AS month,
           ANY_VALUE(purchase_month_name) AS month_name,
           SUM(revenue) AS revenue
    FROM v_sales
    GROUP BY purchase_year, purchase_month
)
SELECT year,
       printf('%04d-%02d', year, month)                                  AS year_month,
       month_name,
       ROUND(revenue, 2)                                                 AS revenue,
       RANK() OVER (PARTITION BY year ORDER BY revenue DESC)             AS rank_in_year
FROM monthly
ORDER BY year, month;
