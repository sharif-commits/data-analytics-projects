-- Q8. CUBE of revenue over (Region, Category, Year).
-- GROUPING_ID is a 3-bit mask: 0 = all three grouped, 7 = grand total.

-- @result q08_cube
SELECT GROUPING_ID(g.region_name, p.category, c.year_number) AS grouping_id,
       g.region_name AS region, p.category, c.year_number AS year,
       sum(f.revenue) AS revenue
FROM fact_order_item f
JOIN dim_customer d USING (customer_key)
JOIN v_geo g USING (zip_key)
JOIN v_product p USING (product_key)
JOIN v_calendar c ON c.date_key = f.purchase_date_key
GROUP BY CUBE (g.region_name, p.category, c.year_number)
ORDER BY grouping_id DESC, revenue DESC;

-- Revenue is fully additive, so each of the 8 slices must re-sum to the same grand total.
-- @result q08_slice_totals
WITH cube AS (
    SELECT GROUPING_ID(g.region_name, p.category, c.year_number) AS grouping_id, sum(f.revenue) AS revenue
    FROM fact_order_item f
    JOIN dim_customer d USING (customer_key)
    JOIN v_geo g USING (zip_key)
    JOIN v_product p USING (product_key)
    JOIN v_calendar c ON c.date_key = f.purchase_date_key
    GROUP BY CUBE (g.region_name, p.category, c.year_number)
)
SELECT grouping_id,
       CASE grouping_id WHEN 0 THEN 'region, category, year' WHEN 1 THEN 'region, category'
            WHEN 2 THEN 'region, year' WHEN 3 THEN 'region' WHEN 4 THEN 'category, year'
            WHEN 5 THEN 'category' WHEN 6 THEN 'year' ELSE 'grand total' END AS grouped_by,
       count(*) AS cells, sum(revenue) AS slice_total,
       sum(revenue) = (SELECT sum(revenue) FROM fact_order_item) AS matches_grand_total
FROM cube
GROUP BY 1
ORDER BY 1;

-- Example read of the cube: each region's leading category over the whole period.
-- @result q08_top_category_per_region
WITH cell AS (
    SELECT g.region_name AS region, p.category, sum(f.revenue) AS revenue
    FROM fact_order_item f
    JOIN dim_customer d USING (customer_key)
    JOIN v_geo g USING (zip_key)
    JOIN v_product p USING (product_key)
    GROUP BY 1, 2
)
SELECT region, category, revenue, round(100.0 * revenue / sum(revenue) OVER (PARTITION BY region), 2) AS pct_of_region
FROM cell
QUALIFY rank() OVER (PARTITION BY region ORDER BY revenue DESC) = 1
ORDER BY revenue DESC;
