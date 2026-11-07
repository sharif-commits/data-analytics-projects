-- Snowflake schema for the marketplace warehouse (DuckDB).
--
-- Grain of the main fact table:
--   fact_order_item has one row per item line of an order (order_id + order_item_id).
-- fact_order_payment is a second fact at a different grain: one row per payment of an order.
-- Payments are kept apart because joining them to items would multiply revenue.
--
-- Every hierarchy is split into one table per level and linked by foreign keys.
-- Key -1 is the "Unknown" member of a dimension, so a missing value never drops a row.

-- Geography: zip -> city -> state -> region. Customers and sellers share this hierarchy.
CREATE TABLE dim_region (
    region_key   INTEGER PRIMARY KEY,
    region_name  VARCHAR NOT NULL UNIQUE
);
CREATE TABLE dim_state (
    state_key    INTEGER PRIMARY KEY,
    state_code   VARCHAR NOT NULL UNIQUE,
    state_name   VARCHAR NOT NULL,
    region_key   INTEGER NOT NULL REFERENCES dim_region (region_key)
);
CREATE TABLE dim_city (
    city_key     INTEGER PRIMARY KEY,
    city_name    VARCHAR NOT NULL,
    state_key    INTEGER NOT NULL REFERENCES dim_state (state_key),
    UNIQUE (city_name, state_key)
);
CREATE TABLE dim_zip (
    zip_key      INTEGER PRIMARY KEY,
    zip_prefix   VARCHAR NOT NULL UNIQUE,
    city_key     INTEGER NOT NULL REFERENCES dim_city (city_key),
    latitude     DOUBLE,
    longitude    DOUBLE
);

-- Calendar: date -> month -> quarter -> year.
CREATE TABLE dim_year (
    year_key     INTEGER PRIMARY KEY,
    year_number  INTEGER
);
CREATE TABLE dim_quarter (
    quarter_key    INTEGER PRIMARY KEY,
    quarter_number INTEGER,
    year_key       INTEGER NOT NULL REFERENCES dim_year (year_key)
);
CREATE TABLE dim_month (
    month_key    INTEGER PRIMARY KEY,
    month_number INTEGER,
    month_name   VARCHAR,
    quarter_key  INTEGER NOT NULL REFERENCES dim_quarter (quarter_key)
);
CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,
    full_date    DATE,
    day_of_month INTEGER,
    day_name     VARCHAR,
    is_weekend   BOOLEAN,
    month_key    INTEGER NOT NULL REFERENCES dim_month (month_key)
);

-- Product: product -> category.
CREATE TABLE dim_category (
    category_key     INTEGER PRIMARY KEY,
    category_name_pt VARCHAR NOT NULL UNIQUE,
    category_name_en VARCHAR NOT NULL
);
CREATE TABLE dim_product (
    product_key        INTEGER PRIMARY KEY,
    product_id         VARCHAR NOT NULL UNIQUE,
    category_key       INTEGER NOT NULL REFERENCES dim_category (category_key),
    name_length        INTEGER,
    description_length INTEGER,
    photos_qty         INTEGER,
    weight_g           INTEGER,
    length_cm          INTEGER,
    height_cm          INTEGER,
    width_cm           INTEGER
);

-- Seller: seller -> acquisition details -> lead origin.
CREATE TABLE dim_lead_origin (
    lead_origin_key INTEGER PRIMARY KEY,
    lead_origin     VARCHAR NOT NULL UNIQUE
);
CREATE TABLE dim_seller_acquisition (
    acquisition_key        INTEGER PRIMARY KEY,
    mql_id                 VARCHAR NOT NULL UNIQUE,
    lead_origin_key        INTEGER NOT NULL REFERENCES dim_lead_origin (lead_origin_key),
    business_segment       VARCHAR,
    lead_type              VARCHAR,
    business_type          VARCHAR,
    first_contact_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    won_date_key           INTEGER NOT NULL REFERENCES dim_date (date_key)
);
CREATE TABLE dim_seller (
    seller_key      INTEGER PRIMARY KEY,
    seller_id       VARCHAR NOT NULL UNIQUE,
    zip_key         INTEGER NOT NULL REFERENCES dim_zip (zip_key),
    acquisition_key INTEGER NOT NULL REFERENCES dim_seller_acquisition (acquisition_key)
);

-- Customer. customer_id is issued per order; customer_unique_id identifies the person.
CREATE TABLE dim_customer (
    customer_key       INTEGER PRIMARY KEY,
    customer_id        VARCHAR NOT NULL UNIQUE,
    customer_unique_id VARCHAR NOT NULL,
    zip_key            INTEGER NOT NULL REFERENCES dim_zip (zip_key)
);

-- Order. Every order lives here, including orders with no items, no delivery date or no review.
CREATE TABLE dim_order_status (
    order_status_key INTEGER PRIMARY KEY,
    order_status     VARCHAR NOT NULL UNIQUE
);
CREATE TABLE dim_order (
    order_key          INTEGER PRIMARY KEY,
    order_id           VARCHAR NOT NULL UNIQUE,
    customer_key       INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    order_status_key   INTEGER NOT NULL REFERENCES dim_order_status (order_status_key),
    purchase_date_key  INTEGER NOT NULL REFERENCES dim_date (date_key),
    delivered_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    estimated_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    purchase_ts        TIMESTAMP,
    approved_ts        TIMESTAMP,
    carrier_ts         TIMESTAMP,
    delivered_ts       TIMESTAMP,
    estimated_ts       TIMESTAMP,
    days_vs_estimate   INTEGER      -- delivered date minus estimated date; NULL if not delivered
);
-- One order can have several reviews, and one review_id can cover several orders.
CREATE TABLE dim_review (
    review_key        INTEGER PRIMARY KEY,
    review_id         VARCHAR NOT NULL,
    order_key         INTEGER NOT NULL REFERENCES dim_order (order_key),
    review_score      INTEGER NOT NULL,
    has_comment       BOOLEAN,
    creation_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    answer_ts         TIMESTAMP,
    UNIQUE (review_id, order_key)
);
CREATE TABLE dim_payment_type (
    payment_type_key INTEGER PRIMARY KEY,
    payment_type     VARCHAR NOT NULL UNIQUE
);

-- Facts.
CREATE TABLE fact_order_item (
    order_key               INTEGER NOT NULL REFERENCES dim_order (order_key),
    order_item_id           INTEGER NOT NULL,
    product_key             INTEGER NOT NULL REFERENCES dim_product (product_key),
    seller_key              INTEGER NOT NULL REFERENCES dim_seller (seller_key),
    customer_key            INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    purchase_date_key       INTEGER NOT NULL REFERENCES dim_date (date_key),
    shipping_limit_date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    price                   DECIMAL(12, 2) NOT NULL,
    freight_value           DECIMAL(12, 2) NOT NULL,
    revenue                 DECIMAL(12, 2) NOT NULL,   -- price + freight_value
    PRIMARY KEY (order_key, order_item_id)
);
CREATE TABLE fact_order_payment (
    order_key          INTEGER NOT NULL REFERENCES dim_order (order_key),
    payment_sequential INTEGER NOT NULL,
    payment_type_key   INTEGER NOT NULL REFERENCES dim_payment_type (payment_type_key),
    purchase_date_key  INTEGER NOT NULL REFERENCES dim_date (date_key),
    installments       INTEGER,
    payment_value      DECIMAL(12, 2) NOT NULL,
    PRIMARY KEY (order_key, payment_sequential)
);
