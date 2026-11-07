-- Extra: why total payments exceed total item revenue. Not one of the 10 questions, but the two
-- totals differ and a reader should know why. Each order falls in exactly one class.

-- @result recon_payment_vs_revenue
WITH items AS (SELECT order_key, sum(revenue) AS revenue FROM fact_order_item GROUP BY 1),
pay AS (SELECT order_key, sum(payment_value) AS paid, max(installments) AS max_installments
        FROM fact_order_payment GROUP BY 1),
o AS (
    SELECT order_key, coalesce(i.revenue, 0) AS revenue, coalesce(p.paid, 0) AS paid,
           p.max_installments, i.order_key IS NOT NULL AS has_items, p.order_key IS NOT NULL AS has_payment
    FROM items i FULL JOIN pay p USING (order_key)
),
classed AS (
    SELECT *, paid - revenue AS gap,
           CASE WHEN NOT has_items THEN 'payment but no items'
                WHEN NOT has_payment THEN 'items but no payment'
                WHEN paid - revenue > 0.05 THEN 'paid more than item revenue'
                WHEN paid - revenue < -0.05 THEN 'paid less than item revenue'
                ELSE 'matches within 5 centavos' END AS class
    FROM o
)
SELECT class, count(*) AS orders, sum(gap) AS gap,
       count(*) FILTER (WHERE max_installments > 1) AS orders_with_installments
FROM classed
GROUP BY ROLLUP (class)
ORDER BY class NULLS LAST;

-- @result recon_totals
SELECT (SELECT sum(payment_value) FROM fact_order_payment) AS total_payments,
       (SELECT sum(revenue) FROM fact_order_item) AS total_item_revenue,
       (SELECT sum(payment_value) FROM fact_order_payment) - (SELECT sum(revenue) FROM fact_order_item) AS gap;

-- How much of revenue comes from orders that were never delivered (revenue here counts every item).
-- @result recon_revenue_by_status
SELECT s.order_status, count(DISTINCT f.order_key) AS orders, sum(f.revenue) AS revenue,
       round(100.0 * sum(f.revenue) / (SELECT sum(revenue) FROM fact_order_item), 2) AS pct_of_total
FROM fact_order_item f
JOIN dim_order o USING (order_key)
JOIN dim_order_status s USING (order_status_key)
GROUP BY 1
ORDER BY revenue DESC;

-- How often a customer's typed city differs from the canonical city of the zip.
-- @result recon_city_agreement
SELECT count(*) AS customers,
       count(*) FILTER (WHERE g.city_name <> regexp_replace(lower(trim(strip_accents(c.customer_city))), '[´`’'']', '', 'g')) AS city_differs,
       round(100.0 * count(*) FILTER (WHERE g.city_name <> regexp_replace(lower(trim(strip_accents(c.customer_city))), '[´`’'']', '', 'g')) / count(*), 2) AS pct_differs
FROM stg.customers c
JOIN dim_customer d USING (customer_id)
JOIN v_geo g USING (zip_key);
