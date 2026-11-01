-- =====================================================================
-- Q7. Which SELLERS generate the highest revenue IN THEIR STATE?
--     Uses the *seller* leg of the shared geography hierarchy, showing
--     that dim_customer and dim_seller really do roll up through the
--     same dim_zip -> dim_city -> dim_state -> dim_region chain.
-- =====================================================================

-- (a) The #1 seller in every state -------------------------------------
WITH seller_state AS (
    SELECT seller_state                      AS state,
           ANY_VALUE(seller_state_name)      AS state_name,
           ANY_VALUE(seller_region)          AS region,
           seller_id,
           ANY_VALUE(seller_city)            AS seller_city,
           ANY_VALUE(lead_origin)            AS lead_origin,
           SUM(revenue)                      AS revenue,
           COUNT(DISTINCT order_id)          AS orders,
           COUNT(*)                          AS items
    FROM v_sales
    GROUP BY seller_state, seller_id
)
SELECT state,
       state_name,
       region,
       seller_id,
       seller_city,
       lead_origin,
       ROUND(revenue, 2)                                                        AS revenue,
       orders,
       items,
       ROUND(100.0 * revenue / SUM(revenue) OVER (PARTITION BY state), 1)       AS pct_of_state_revenue,
       COUNT(*) OVER (PARTITION BY state)                                       AS sellers_in_state
FROM seller_state
QUALIFY RANK() OVER (PARTITION BY state ORDER BY revenue DESC) = 1
ORDER BY revenue DESC;

-- (b) Top 3 per state for the five largest seller states ---------------
WITH seller_state AS (
    SELECT seller_state AS state, seller_id,
           ANY_VALUE(seller_city) AS seller_city,
           SUM(revenue) AS revenue,
           COUNT(DISTINCT order_id) AS orders
    FROM v_sales
    GROUP BY seller_state, seller_id
),
state_tot AS (
    SELECT state, SUM(revenue) AS state_revenue,
           ROW_NUMBER() OVER (ORDER BY SUM(revenue) DESC) AS state_rank
    FROM seller_state GROUP BY state
)
SELECT t.state_rank,
       s.state,
       ROUND(t.state_revenue, 2)                    AS state_revenue,
       RANK() OVER (PARTITION BY s.state ORDER BY s.revenue DESC) AS rank_in_state,
       s.seller_id,
       s.seller_city,
       ROUND(s.revenue, 2)                          AS seller_revenue,
       s.orders
FROM seller_state s
JOIN state_tot t USING (state)
WHERE t.state_rank <= 5
QUALIFY rank_in_state <= 3
ORDER BY t.state_rank, rank_in_state;
