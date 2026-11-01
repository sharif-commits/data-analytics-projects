-- =====================================================================
-- Q9. Average REVIEW SCORE for orders delivered EARLY / ON TIME / LATE.
--
--     Computed at ORDER grain (v_orders), not line-item grain: a 1-star
--     order containing six items must count once, not six times.
--     GROUPING SETS gives the coarse 3-way answer and the finer bucket
--     breakdown (including "more than a week late") in a single pass.
-- =====================================================================

-- (a) Delivery timeliness vs review score ------------------------------
SELECT CASE WHEN GROUPING(delivery_status) = 1 THEN 'ALL ORDERS'
            ELSE delivery_status END                                     AS delivery_status,
       CASE WHEN GROUPING(delivery_bucket) = 1 THEN 'All buckets'
            ELSE delivery_bucket END                                     AS delivery_bucket,
       COUNT(*)                                                          AS orders,
       COUNT(review_score)                                               AS reviewed_orders,
       ROUND(100.0 * COUNT(review_score) / COUNT(*), 1)                   AS pct_reviewed,
       ROUND(AVG(review_score), 3)                                       AS avg_review_score,
       ROUND(100.0 * COUNT(*) FILTER (WHERE review_score <= 2)
             / NULLIF(COUNT(review_score), 0), 1)                        AS pct_negative_1_2,
       ROUND(100.0 * COUNT(*) FILTER (WHERE review_score >= 4)
             / NULLIF(COUNT(review_score), 0), 1)                        AS pct_positive_4_5,
       ROUND(AVG(delivery_delay_days), 2)                                AS avg_delay_days,
       ROUND(AVG(delivery_days), 2)                                      AS avg_days_to_deliver
FROM v_orders
GROUP BY GROUPING SETS ((delivery_status, delivery_bucket), (delivery_status), ())
ORDER BY GROUPING(delivery_status) DESC,
         MIN(delivery_status_order),
         GROUPING(delivery_bucket) DESC,
         MIN(delivery_delay_days);

-- (b) Just the headline three-way comparison the question asks for -----
SELECT delivery_status,
       COUNT(*)                                     AS orders,
       COUNT(review_score)                          AS reviewed_orders,
       ROUND(AVG(review_score), 3)                  AS avg_review_score,
       ROUND(AVG(delivery_delay_days), 2)           AS avg_delay_days
FROM v_orders
WHERE delivery_status IN ('Early', 'On Time', 'Late')
GROUP BY delivery_status
ORDER BY MIN(delivery_status_order);

-- (c) The dose-response curve: lateness in days vs average score -------
SELECT CASE WHEN delivery_delay_days IS NULL           THEN 'not delivered'
            WHEN delivery_delay_days <= -30            THEN '30+ days early'
            WHEN delivery_delay_days <= -15            THEN '15-29 days early'
            WHEN delivery_delay_days <=  -8            THEN '8-14 days early'
            WHEN delivery_delay_days <=  -1            THEN '1-7 days early'
            WHEN delivery_delay_days  =   0            THEN 'on time'
            WHEN delivery_delay_days <=   7            THEN '1-7 days late'
            WHEN delivery_delay_days <=  14            THEN '8-14 days late'
            WHEN delivery_delay_days <=  30            THEN '15-30 days late'
            ELSE                                            'more than 30 days late'
       END                                                  AS lateness_band,
       COUNT(*)                                             AS orders,
       ROUND(AVG(review_score), 3)                          AS avg_review_score,
       ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 1)
             / NULLIF(COUNT(review_score), 0), 1)           AS pct_one_star
FROM v_orders
GROUP BY 1
ORDER BY MIN(COALESCE(delivery_delay_days, 99999));
