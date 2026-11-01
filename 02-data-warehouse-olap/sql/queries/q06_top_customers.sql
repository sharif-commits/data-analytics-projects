-- =====================================================================
-- Q6. Top 5 CUSTOMERS by total purchase amount.
--
--     Note on the grain of "customer": in this dataset customer_id is
--     issued per ORDER, while customer_unique_id identifies the actual
--     person.  (a) answers the question at the person level, which is
--     what "customer" normally means; (b) repeats it at customer_id
--     level so the two readings can be compared.
-- =====================================================================

-- (a) Top 5 people (customer_unique_id) --------------------------------
SELECT customer_unique_id,
       ANY_VALUE(customer_city)                     AS city,
       ANY_VALUE(customer_state)                    AS state,
       ANY_VALUE(customer_region)                   AS region,
       COUNT(DISTINCT order_id)                     AS orders,
       COUNT(*)                                     AS items,
       ROUND(SUM(price), 2)                         AS product_spend,
       ROUND(SUM(freight_value), 2)                 AS freight_spend,
       ROUND(SUM(revenue), 2)                       AS total_purchase_amount
FROM v_sales
GROUP BY customer_unique_id
ORDER BY total_purchase_amount DESC
LIMIT 5;

-- (b) Top 5 single orders' customers (customer_id) ---------------------
SELECT customer_id,
       ANY_VALUE(customer_unique_id)                AS customer_unique_id,
       ANY_VALUE(customer_city)                     AS city,
       ANY_VALUE(customer_state)                    AS state,
       COUNT(*)                                     AS items,
       ROUND(SUM(revenue), 2)                       AS total_purchase_amount
FROM v_sales
GROUP BY customer_id
ORDER BY total_purchase_amount DESC
LIMIT 5;

-- (c) How repeat-buying behaves overall (context for the top 5) --------
SELECT CASE WHEN orders = 1 THEN '1 order'
            WHEN orders = 2 THEN '2 orders'
            WHEN orders BETWEEN 3 AND 5 THEN '3-5 orders'
            ELSE '6+ orders' END                    AS orders_placed,
       COUNT(*)                                     AS customers,
       ROUND(SUM(spend), 2)                         AS revenue,
       ROUND(100.0 * SUM(spend) / SUM(SUM(spend)) OVER (), 2) AS pct_of_revenue,
       ROUND(AVG(spend), 2)                         AS avg_spend_per_customer
FROM (SELECT customer_unique_id,
             COUNT(DISTINCT order_id) AS orders,
             SUM(revenue)             AS spend
      FROM v_sales
      GROUP BY customer_unique_id)
GROUP BY 1
ORDER BY customers DESC;
