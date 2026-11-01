-- =====================================================================
-- Q8. CUBE over (REGION, CATEGORY, YEAR).
--     CUBE returns all 2^3 = 8 grouping combinations in one pass:
--       (R,C,Y) (R,C) (R,Y) (C,Y) (R) (C) (Y) ()
--     GROUPING_ID() encodes which combination each row belongs to, so the
--     whole lattice lives in a single result set and can be sliced
--     afterwards without touching the fact table again.  That is exactly
--     the property a materialised cube buys you, so we materialise it
--     once here and then read three different slices off it.
-- =====================================================================

CREATE OR REPLACE TEMP TABLE cube_rcy AS
SELECT CASE WHEN GROUPING(customer_region) = 1 THEN 'ALL'
            ELSE customer_region END                                AS region,
       CASE WHEN GROUPING(category) = 1 THEN 'ALL'
            ELSE category END                                       AS category,
       CASE WHEN GROUPING(purchase_year) = 1 THEN 'ALL'
            ELSE CAST(purchase_year AS VARCHAR) END                 AS year,
       GROUPING_ID(customer_region, category, purchase_year)         AS grouping_id,
       GROUPING(customer_region)                                     AS g_region,
       GROUPING(category)                                            AS g_category,
       GROUPING(purchase_year)                                       AS g_year,
       ROUND(SUM(revenue), 2)                                        AS revenue,
       COUNT(DISTINCT order_id)                                      AS orders,
       COUNT(*)                                                      AS line_items,
       ROUND(AVG(price), 2)                                          AS avg_unit_price
FROM v_sales
GROUP BY CUBE (customer_region, category, purchase_year);

-- (a) The complete cube, one row per cell ------------------------------
SELECT grouping_id,
       CASE grouping_id
            WHEN 0 THEN '(Region, Category, Year)'
            WHEN 1 THEN '(Region, Category)'
            WHEN 2 THEN '(Region, Year)'
            WHEN 3 THEN '(Region)'
            WHEN 4 THEN '(Category, Year)'
            WHEN 5 THEN '(Category)'
            WHEN 6 THEN '(Year)'
            ELSE        '()  grand total' END AS grouping_set,
       region, category, year,
       revenue, orders, line_items, avg_unit_price
FROM cube_rcy
ORDER BY grouping_id, revenue DESC;

-- (b) How many cells does each of the 8 grouping sets contribute? -------
SELECT grouping_id,
       CASE grouping_id
            WHEN 0 THEN '(Region, Category, Year)'
            WHEN 1 THEN '(Region, Category)'
            WHEN 2 THEN '(Region, Year)'
            WHEN 3 THEN '(Region)'
            WHEN 4 THEN '(Category, Year)'
            WHEN 5 THEN '(Category)'
            WHEN 6 THEN '(Year)'
            ELSE        '()  grand total' END AS grouping_set,
       COUNT(*)                              AS cells,
       ROUND(SUM(revenue), 2)                AS revenue_in_slice
FROM cube_rcy
GROUP BY grouping_id
ORDER BY grouping_id;

-- (c) Slice: the 2-D (Region x Year) face, plus its margins -------------
SELECT region, year, revenue, orders
FROM cube_rcy
WHERE grouping_id IN (2, 3, 6, 7)         -- (R,Y) (R) (Y) ()
ORDER BY CASE WHEN region = 'ALL' THEN 1 ELSE 0 END, revenue DESC, year;

-- (d) Slice: top 3 categories inside each region, all years pooled -----
WITH rc AS (
    SELECT region, category, revenue, orders
    FROM cube_rcy
    WHERE grouping_id = 1                 -- (Region, Category)
      AND region <> 'ALL'
),
r_tot AS (
    SELECT region, revenue AS region_revenue
    FROM cube_rcy
    WHERE grouping_id = 3                 -- (Region)
      AND region <> 'ALL'
)
SELECT rc.region,
       ROUND(rt.region_revenue, 2)                                  AS region_revenue,
       ROW_NUMBER() OVER (PARTITION BY rc.region ORDER BY rc.revenue DESC) AS rank_in_region,
       rc.category,
       rc.revenue,
       rc.orders,
       ROUND(100.0 * rc.revenue / rt.region_revenue, 1)             AS pct_of_region
FROM rc
JOIN r_tot rt USING (region)
QUALIFY rank_in_region <= 3
ORDER BY rt.region_revenue DESC, rank_in_region;
