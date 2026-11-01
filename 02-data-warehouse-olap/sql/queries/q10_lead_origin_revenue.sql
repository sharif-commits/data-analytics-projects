-- =====================================================================
-- Q10. Which LEAD ORIGIN (marketing channel) recruited the sellers that
--      generate the most revenue?
--      Walks the third snowflaked hierarchy:
--          dim_lead_origin -> dim_seller_acquisition -> dim_seller
--      Only 842 of the 3 095 sellers were recruited through the tracked
--      marketing funnel, so (a) reports funnel vs non-funnel first and
--      (b) then ranks the channels inside the funnel population.
-- =====================================================================

-- (a) Funnel-acquired vs organically-present sellers -------------------
SELECT CASE WHEN seller_from_funnel THEN 'Recruited via marketing funnel'
            ELSE 'Already on the platform / untracked' END          AS acquisition,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(DISTINCT order_id)                                     AS orders,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)    AS pct_of_revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT seller_id), 2)           AS revenue_per_seller
FROM v_sales
GROUP BY seller_from_funnel
ORDER BY revenue DESC;

-- (b) Channel roll-up inside the funnel population ---------------------
--     ROLLUP over lead_origin_group -> lead_origin (channel grouping is
--     an attribute of dim_lead_origin, i.e. one more hierarchy level).
SELECT CASE WHEN GROUPING(lead_origin_group) = 1 THEN 'ALL CHANNELS'
            ELSE lead_origin_group END                              AS channel_group,
       CASE WHEN GROUPING(lead_origin) = 1 THEN 'All origins'
            ELSE lead_origin END                                    AS lead_origin,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(DISTINCT order_id)                                     AS orders,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT seller_id), 2)           AS revenue_per_seller,
       ROUND(100.0 * SUM(revenue) / MAX(SUM(revenue)) OVER (), 2)    AS pct_of_funnel_revenue
FROM v_sales
WHERE seller_from_funnel
GROUP BY ROLLUP (lead_origin_group, lead_origin)
ORDER BY GROUPING(lead_origin_group) DESC,
         MAX(SUM(revenue)) OVER (PARTITION BY lead_origin_group) DESC,
         lead_origin_group,
         GROUPING(lead_origin) DESC,
         revenue DESC;

-- (c) Flat channel ranking -- the direct answer to the question --------
SELECT lead_origin,
       ANY_VALUE(lead_origin_group)                                 AS channel_group,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(DISTINCT order_id)                                     AS orders,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT seller_id), 2)           AS revenue_per_seller,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)    AS pct_of_funnel_revenue
FROM v_sales
WHERE seller_from_funnel
GROUP BY lead_origin
ORDER BY revenue DESC;

-- (d) Which business segments did the best channels bring in? ----------
SELECT lead_origin,
       business_segment,
       COUNT(DISTINCT seller_id)            AS sellers,
       ROUND(SUM(revenue), 2)               AS revenue
FROM v_sales
WHERE seller_from_funnel
GROUP BY lead_origin, business_segment
QUALIFY ROW_NUMBER() OVER (PARTITION BY lead_origin ORDER BY SUM(revenue) DESC) <= 3
ORDER BY MAX(SUM(revenue)) OVER (PARTITION BY lead_origin) DESC,
         lead_origin, revenue DESC;
