-- =====================================================================
-- Q5. ROLL UP geography CITY -> STATE -> REGION and find the
--     best-selling regions.
--     This is the query the snowflaked geography hierarchy exists for:
--     dim_zip -> dim_city -> dim_state -> dim_region.  The region level
--     is not in the source data at all; it comes from the seed file.
-- =====================================================================

-- (a) Full geography roll-up (all region + state rows, top 3 cities per state)
WITH rolled AS (
    SELECT customer_region                AS region,
           customer_state                 AS state,
           customer_city                  AS city,
           GROUPING(customer_region)      AS g_region,
           GROUPING(customer_state)       AS g_state,
           GROUPING(customer_city)        AS g_city,
           SUM(revenue)                   AS revenue,
           COUNT(DISTINCT order_id)       AS orders,
           COUNT(DISTINCT customer_unique_id) AS customers,
           COUNT(*)                       AS line_items
    FROM v_sales
    GROUP BY ROLLUP (customer_region, customer_state, customer_city)
),
with_totals AS (
    SELECT *,
           MAX(CASE WHEN g_region = 0 AND g_state = 1 THEN revenue END)
               OVER (PARTITION BY region)                AS region_revenue,
           MAX(CASE WHEN g_state = 0 AND g_city = 1 THEN revenue END)
               OVER (PARTITION BY region, state)         AS state_revenue,
           MAX(CASE WHEN g_region = 1 THEN revenue END) OVER ()  AS grand_revenue
    FROM rolled
)
SELECT CASE WHEN g_region = 1 THEN 'ALL REGIONS' ELSE region END          AS region,
       CASE WHEN g_state  = 1 THEN 'All states'  ELSE state  END          AS state,
       CASE WHEN g_city   = 1 THEN 'All cities'  ELSE city   END          AS city,
       CASE g_region * 4 + g_state * 2 + g_city
            WHEN 7 THEN 'GRAND TOTAL'
            WHEN 3 THEN 'REGION'
            WHEN 1 THEN 'STATE'
            ELSE        'CITY' END                                        AS agg_level,
       ROUND(revenue, 2)                                                  AS revenue,
       orders,
       customers,
       ROUND(revenue / NULLIF(orders, 0), 2)                              AS avg_order_value,
       ROUND(100.0 * revenue / grand_revenue, 2)                          AS pct_of_total
FROM with_totals
QUALIFY g_city = 1
     OR ROW_NUMBER() OVER (PARTITION BY region, state ORDER BY revenue DESC) <= 3
ORDER BY g_region DESC,
         region_revenue DESC NULLS LAST, region,
         g_state DESC,
         state_revenue DESC NULLS LAST, state,
         g_city DESC,
         revenue DESC;

-- (b) Best-selling regions, compact ------------------------------------
SELECT customer_region                                                  AS region,
       ROUND(SUM(revenue), 2)                                           AS revenue,
       COUNT(DISTINCT order_id)                                         AS orders,
       COUNT(DISTINCT customer_unique_id)                               AS customers,
       COUNT(DISTINCT customer_state)                                   AS states,
       COUNT(DISTINCT customer_city)                                    AS cities,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)                AS avg_order_value,
       ROUND(SUM(freight_value) / SUM(revenue) * 100, 2)                AS freight_pct_of_revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)       AS pct_of_total
FROM v_sales
GROUP BY customer_region
ORDER BY revenue DESC;

-- (c) Best-selling states ---------------------------------------------
SELECT customer_region                                                  AS region,
       customer_state                                                   AS state,
       ANY_VALUE(customer_state_name)                                   AS state_name,
       ROUND(SUM(revenue), 2)                                           AS revenue,
       COUNT(DISTINCT order_id)                                         AS orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)                AS avg_order_value,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)       AS pct_of_total
FROM v_sales
GROUP BY customer_region, customer_state
ORDER BY revenue DESC
LIMIT 15;
