-- Q2. The month with the highest revenue in each year.
-- @result q02_peak_month
WITH monthly AS (
    SELECT c.year_number AS year, c.month_number AS month, c.month_name, sum(f.revenue) AS revenue
    FROM fact_order_item f
    JOIN v_calendar c ON c.date_key = f.purchase_date_key
    GROUP BY 1, 2, 3
)
SELECT year, month, month_name, revenue,
       round(100.0 * revenue / sum(revenue) OVER (PARTITION BY year), 1) AS pct_of_year
FROM monthly
QUALIFY rank() OVER (PARTITION BY year ORDER BY revenue DESC) = 1
ORDER BY year;
