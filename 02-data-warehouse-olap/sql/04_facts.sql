-- Facts load last, once every key they reference exists.
INSERT INTO fact_order_item
SELECT o.order_key, CAST(i.order_item_id AS INTEGER), p.product_key, s.seller_key, o.customer_key,
       o.purchase_date_key, date_key(i.shipping_limit_date),
       CAST(i.price AS DECIMAL(12, 2)), CAST(i.freight_value AS DECIMAL(12, 2)),
       CAST(i.price AS DECIMAL(12, 2)) + CAST(i.freight_value AS DECIMAL(12, 2))
FROM stg.order_items i
JOIN dim_order o USING (order_id)
JOIN dim_product p USING (product_id)
JOIN dim_seller s USING (seller_id);

INSERT INTO fact_order_payment
SELECT o.order_key, CAST(p.payment_sequential AS INTEGER), t.payment_type_key, o.purchase_date_key,
       CAST(p.payment_installments AS INTEGER), CAST(p.payment_value AS DECIMAL(12, 2))
FROM stg.order_payments p
JOIN dim_order o USING (order_id)
JOIN dim_payment_type t USING (payment_type);
