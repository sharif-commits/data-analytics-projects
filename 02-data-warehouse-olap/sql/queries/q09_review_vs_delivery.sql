-- Q9. Average review score for orders delivered early, on time and late.
-- This runs at order grain, from v_order_delivery, so an order with 5 items counts once.
-- "Late" compares the delivered date with the estimated date promised to the customer.

-- @result q09_delivery_class
SELECT delivery_class,
       count(*) AS orders,
       count(review_score) AS orders_with_review,
       round(avg(review_score), 3) AS avg_review,
       round(100.0 * avg(CASE WHEN review_score <= 2 THEN 1.0 WHEN review_score IS NOT NULL THEN 0.0 END), 1) AS pct_low_scores,
       round(avg(days_vs_estimate), 1) AS avg_days_vs_estimate
FROM v_order_delivery
GROUP BY 1
ORDER BY CASE delivery_class WHEN 'early' THEN 1 WHEN 'on_time' THEN 2 WHEN 'late' THEN 3 ELSE 4 END;

-- @result q09_late_split
SELECT CASE WHEN delivery_class <> 'late' THEN delivery_class
            WHEN days_vs_estimate <= 7 THEN 'late_1_to_7_days'
            ELSE 'late_over_7_days' END AS bucket,
       count(*) AS orders,
       count(review_score) AS orders_with_review,
       round(avg(review_score), 3) AS avg_review,
       round(100.0 * avg(CASE WHEN review_score <= 2 THEN 1.0 WHEN review_score IS NOT NULL THEN 0.0 END), 1) AS pct_low_scores
FROM v_order_delivery
GROUP BY 1
ORDER BY CASE bucket WHEN 'early' THEN 1 WHEN 'on_time' THEN 2 WHEN 'late_1_to_7_days' THEN 3
                     WHEN 'late_over_7_days' THEN 4 ELSE 5 END;

-- The wrong way, kept as a check: joining reviews to item rows weights each order by its item count.
-- @result q09_grain_check
SELECT d.delivery_class,
       round(avg(d.review_score), 3) AS order_grain_avg,
       round(avg(d.review_score) FILTER (WHERE f.order_key IS NOT NULL), 3) AS order_grain_with_items,
       (SELECT round(avg(x.review_score), 3)
        FROM fact_order_item i JOIN v_order_delivery x USING (order_key)
        WHERE x.delivery_class = d.delivery_class) AS item_grain_avg
FROM v_order_delivery d
LEFT JOIN (SELECT DISTINCT order_key FROM fact_order_item) f USING (order_key)
GROUP BY 1
ORDER BY 1;
