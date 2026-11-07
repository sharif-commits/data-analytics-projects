-- Raw CSVs land 1:1 in stg.* tables as text, so the load is traceable and nothing is coerced early.
CREATE SCHEMA stg;
CREATE TABLE stg.categories     AS SELECT * FROM read_csv('{{DATA_DIR}}/categories.csv',     header = true, all_varchar = true);
CREATE TABLE stg.closed_deals   AS SELECT * FROM read_csv('{{DATA_DIR}}/closed_deals.csv',   header = true, all_varchar = true);
CREATE TABLE stg.customers      AS SELECT * FROM read_csv('{{DATA_DIR}}/customers.csv',      header = true, all_varchar = true);
CREATE TABLE stg.geolocation    AS SELECT * FROM read_csv('{{DATA_DIR}}/geolocation.csv',    header = true, all_varchar = true);
CREATE TABLE stg.leads          AS SELECT * FROM read_csv('{{DATA_DIR}}/leads.csv',          header = true, all_varchar = true);
CREATE TABLE stg.order_items    AS SELECT * FROM read_csv('{{DATA_DIR}}/order_items.csv',    header = true, all_varchar = true);
CREATE TABLE stg.order_payments AS SELECT * FROM read_csv('{{DATA_DIR}}/order_payments.csv', header = true, all_varchar = true);
CREATE TABLE stg.order_reviews  AS SELECT * FROM read_csv('{{DATA_DIR}}/order_reviews.csv',  header = true, all_varchar = true);
CREATE TABLE stg.orders         AS SELECT * FROM read_csv('{{DATA_DIR}}/orders.csv',         header = true, all_varchar = true);
CREATE TABLE stg.products       AS SELECT * FROM read_csv('{{DATA_DIR}}/products.csv',       header = true, all_varchar = true);
CREATE TABLE stg.sellers        AS SELECT * FROM read_csv('{{DATA_DIR}}/sellers.csv',        header = true, all_varchar = true);
CREATE TABLE stg.state_region   AS SELECT * FROM read_csv('{{SEED_DIR}}/br_state_region.csv', header = true, all_varchar = true);
CREATE TABLE stg.category_extra AS SELECT * FROM read_csv('{{SEED_DIR}}/category_translation_extra.csv', header = true, all_varchar = true);
