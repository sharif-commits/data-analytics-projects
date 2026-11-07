-- Q1. Total revenue per year, then drill down to quarter and month.
-- ROLLUP gives every level in one pass; GROUPING() labels which level a row belongs to.
-- @result q01_revenue_rollup
SELECT CASE GROUPING(c.year_number, c.quarter_number, c.month_number)
            WHEN 7 THEN 'grand total' WHEN 3 THEN 'year' WHEN 1 THEN 'quarter' ELSE 'month' END AS level,
       c.year_number AS year, c.quarter_number AS quarter, c.month_number AS month,
       count(DISTINCT f.order_key) AS orders,
       sum(f.revenue) AS revenue
FROM fact_order_item f
JOIN v_calendar c ON c.date_key = f.purchase_date_key
GROUP BY ROLLUP (c.year_number, c.quarter_number, c.month_number)
ORDER BY c.year_number NULLS LAST, c.quarter_number NULLS FIRST, c.month_number NULLS FIRST;
