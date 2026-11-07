-- Q10. Which lead origin recruited the sellers that generate the most revenue?
-- Only sellers with a closed deal have an origin. The rest are reported apart as not_in_funnel,
-- so the ranking is not mistaken for a view of all revenue.

-- @result q10_lead_origin
WITH by_origin AS (
    SELECT o.lead_origin,
           count(DISTINCT f.seller_key) AS active_sellers,
           sum(f.revenue) AS revenue
    FROM fact_order_item f
    JOIN dim_seller s USING (seller_key)
    JOIN dim_seller_acquisition a USING (acquisition_key)
    JOIN dim_lead_origin o USING (lead_origin_key)
    GROUP BY 1
),
recruited AS (
    SELECT o.lead_origin, count(*) AS deals_won
    FROM dim_seller_acquisition a
    JOIN dim_lead_origin o USING (lead_origin_key)
    WHERE a.acquisition_key <> -1
    GROUP BY 1
)
SELECT b.lead_origin, r.deals_won, b.active_sellers, b.revenue,
       round(b.revenue / b.active_sellers, 2) AS revenue_per_active_seller,
       CASE WHEN b.lead_origin = 'not_in_funnel' THEN NULL
            ELSE round(100.0 * b.revenue / sum(b.revenue) FILTER (WHERE b.lead_origin <> 'not_in_funnel') OVER (), 2)
       END AS pct_of_funnel_revenue,
       round(100.0 * b.revenue / sum(b.revenue) OVER (), 2) AS pct_of_all_revenue
FROM by_origin b
LEFT JOIN recruited r USING (lead_origin)
ORDER BY b.lead_origin = 'not_in_funnel', b.revenue DESC;

-- @result q10_coverage
SELECT (SELECT count(*) - 1 FROM dim_seller_acquisition) AS deals_won,
       (SELECT count(*) FROM dim_seller WHERE acquisition_key <> -1) AS deals_matching_a_seller,
       (SELECT count(*) FROM dim_seller) AS all_sellers,
       round(100.0 * (SELECT sum(f.revenue) FROM fact_order_item f JOIN dim_seller s USING (seller_key) WHERE s.acquisition_key <> -1)
             / (SELECT sum(revenue) FROM fact_order_item), 2) AS pct_of_revenue_with_origin;
