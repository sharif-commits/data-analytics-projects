-- =====================================================================
--  Assignment 2 / Part 1 / Task 1  --  SNOWFLAKE SCHEMA DDL  (DuckDB)
--  M26 Data Analytics I
-- =====================================================================
--  Grain of the fact table
--  ------------------------
--  fact_order_item  : one row per line item of an order
--                     (i.e. one row per (order_id, order_item_id) pair --
--                     one physical unit of one product sold in one order).
--  fact_order_payment : one row per payment transaction of an order
--                     (one row per (order_id, payment_sequential)).
--
--  Why two fact tables?  price/freight live at item grain while payments
--  live at order grain.  Keeping them apart is the standard way to avoid
--  the classic "fan trap" double-count you get from joining a 1:N item
--  table to a 1:N payment table.  Both facts share the same conformed
--  dimensions, so they can be drilled across.
--
--  Normalised (snowflaked) hierarchies
--  -----------------------------------
--  1. GEOGRAPHY  dim_region <- dim_state <- dim_city <- dim_zip
--                                                        ^        ^
--                                              dim_customer   dim_seller
--     (one single conformed hierarchy shared by customers AND sellers)
--  2. PRODUCT    dim_category <- dim_product
--  3. SELLER     dim_lead_origin <- dim_seller_acquisition <- dim_seller
--  4. DELIVERY   dim_delivery_status <- dim_delivery_bucket
--
--  Conventions
--  -----------
--  * Every dimension has an integer surrogate key.
--  * Key value -1 is the "Unknown / Not applicable" member of every
--    dimension.  This is what guarantees the Task-2 requirement that
--    "orders with missing delivery dates or no review are not dropped":
--    those facts point at the -1 member instead of being filtered out.
--  * dim_date is a conformed role-playing dimension, referenced six times
--    from fact_order_item (purchase / approved / carrier / delivered /
--    estimated / shipping-limit).
-- =====================================================================

-- ---------------------------------------------------------------------
-- Drop in reverse dependency order so the script is re-runnable.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS fact_order_payment;
DROP TABLE IF EXISTS fact_order_item;
DROP TABLE IF EXISTS dim_review;
DROP TABLE IF EXISTS dim_payment_type;
DROP TABLE IF EXISTS dim_delivery_bucket;
DROP TABLE IF EXISTS dim_delivery_status;
DROP TABLE IF EXISTS dim_order_status;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_category;
DROP TABLE IF EXISTS dim_seller;
DROP TABLE IF EXISTS dim_seller_acquisition;
DROP TABLE IF EXISTS dim_lead_origin;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_zip;
DROP TABLE IF EXISTS dim_city;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_date;

-- =====================================================================
-- LEVEL 0 dimensions (no outgoing foreign keys) -- loaded first
-- =====================================================================

-- ---------- Conformed date dimension (role-playing) -------------------
CREATE TABLE dim_date (
    date_key      INTEGER      PRIMARY KEY,   -- yyyymmdd, -1 = Unknown
    full_date     DATE,
    year          INTEGER,
    quarter       INTEGER,
    month         INTEGER,
    month_name    VARCHAR,
    day_of_month  INTEGER,
    day_of_week   INTEGER,                    -- 0 = Sunday
    day_name      VARCHAR,
    week_of_year  INTEGER,
    year_month    VARCHAR,                    -- '2017-05'
    year_quarter  VARCHAR,                    -- '2017-Q2'
    is_weekend    BOOLEAN
);

-- ---------- GEOGRAPHY level 1 : region --------------------------------
-- The region level does NOT exist in the source data; it is derived from
-- the state code via the seed file part1/seed/br_state_region.csv.
CREATE TABLE dim_region (
    region_key   INTEGER PRIMARY KEY,         -- -1 = Unknown
    region_code  VARCHAR NOT NULL UNIQUE,
    region_name  VARCHAR NOT NULL
);

-- ---------- SELLER ACQUISITION level 1 : lead origin ------------------
CREATE TABLE dim_lead_origin (
    lead_origin_key INTEGER PRIMARY KEY,      -- -1 = Not acquired via funnel
    lead_origin     VARCHAR NOT NULL UNIQUE,
    lead_origin_group VARCHAR NOT NULL        -- paid / organic / referral / other
);

-- ---------- PRODUCT level 1 : category --------------------------------
CREATE TABLE dim_category (
    category_key          INTEGER PRIMARY KEY,   -- -1 = Unknown
    category_name_pt      VARCHAR NOT NULL UNIQUE,
    category_name_english VARCHAR NOT NULL
);

-- ---------- Small stand-alone dimensions ------------------------------
CREATE TABLE dim_order_status (
    order_status_key INTEGER PRIMARY KEY,
    order_status     VARCHAR NOT NULL UNIQUE
);

CREATE TABLE dim_delivery_status (            -- coarse level of the hierarchy
    delivery_status_key INTEGER PRIMARY KEY,
    delivery_status     VARCHAR NOT NULL UNIQUE,  -- Early / On Time / Late / Not Delivered
    sort_order          INTEGER NOT NULL
);

CREATE TABLE dim_payment_type (
    payment_type_key INTEGER PRIMARY KEY,
    payment_type     VARCHAR NOT NULL UNIQUE
);

-- =====================================================================
-- LEVEL 2 dimensions
-- =====================================================================

-- ---------- GEOGRAPHY level 2 : state ---------------------------------
CREATE TABLE dim_state (
    state_key  INTEGER PRIMARY KEY,
    state_code VARCHAR NOT NULL UNIQUE,
    state_name VARCHAR NOT NULL,
    region_key INTEGER NOT NULL REFERENCES dim_region(region_key)
);

-- ---------- DELIVERY level 2 : fine-grained bucket --------------------
CREATE TABLE dim_delivery_bucket (
    delivery_bucket_key INTEGER PRIMARY KEY,
    delivery_bucket     VARCHAR NOT NULL UNIQUE,  -- 'Late (> 7 days)' etc.
    delivery_status_key INTEGER NOT NULL REFERENCES dim_delivery_status(delivery_status_key),
    sort_order          INTEGER NOT NULL
);

-- ---------- SELLER level 2 : acquisition details ----------------------
-- One row per closed marketing deal (leads x closed_deals), plus the -1
-- member for sellers that never came through the recruitment funnel.
CREATE TABLE dim_seller_acquisition (
    acquisition_key               INTEGER PRIMARY KEY,
    mql_id                        VARCHAR,
    lead_origin_key               INTEGER NOT NULL REFERENCES dim_lead_origin(lead_origin_key),
    business_segment              VARCHAR,
    lead_type                     VARCHAR,
    lead_behaviour_profile        VARCHAR,
    business_type                 VARCHAR,
    landing_page_id               VARCHAR,
    first_contact_date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    won_date_key                  INTEGER NOT NULL REFERENCES dim_date(date_key),
    won_date                      TIMESTAMP,
    days_to_close                 INTEGER,
    has_company                   BOOLEAN,
    has_gtin                      BOOLEAN,
    average_stock                 VARCHAR,
    declared_product_catalog_size DOUBLE,
    declared_monthly_revenue      DOUBLE
);

-- ---------- PRODUCT level 2 : product ---------------------------------
CREATE TABLE dim_product (
    product_key                INTEGER PRIMARY KEY,
    product_id                 VARCHAR NOT NULL UNIQUE,
    category_key               INTEGER NOT NULL REFERENCES dim_category(category_key),
    product_name_length        INTEGER,
    product_description_length INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           INTEGER,
    product_length_cm          INTEGER,
    product_height_cm          INTEGER,
    product_width_cm           INTEGER,
    product_volume_cm3         BIGINT
);

-- ---------- REVIEW dimension ------------------------------------------
CREATE TABLE dim_review (
    review_key               INTEGER PRIMARY KEY,   -- -1 = No review
    review_id                VARCHAR,
    order_id                 VARCHAR,
    review_score             INTEGER,
    review_score_band        VARCHAR,               -- Negative / Neutral / Positive
    has_comment              BOOLEAN,
    review_creation_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    review_answer_date_key   INTEGER NOT NULL REFERENCES dim_date(date_key),
    response_hours           DOUBLE
);

-- =====================================================================
-- LEVEL 3 dimensions
-- =====================================================================

-- ---------- GEOGRAPHY level 3 : city ----------------------------------
-- City names repeat across states, so the natural key is (city, state).
CREATE TABLE dim_city (
    city_key  INTEGER PRIMARY KEY,
    city_name VARCHAR NOT NULL,
    state_key INTEGER NOT NULL REFERENCES dim_state(state_key),
    UNIQUE (city_name, state_key)
);

-- =====================================================================
-- LEVEL 4 dimensions
-- =====================================================================

-- ---------- GEOGRAPHY level 4 : zip code prefix -----------------------
-- The lowest level of the shared geography hierarchy.  Both dim_customer
-- and dim_seller hang off this table, which is what makes the geography
-- hierarchy a single conformed hierarchy rather than two parallel ones.
CREATE TABLE dim_zip (
    zip_key         INTEGER PRIMARY KEY,
    zip_code_prefix VARCHAR NOT NULL UNIQUE,
    city_key        INTEGER NOT NULL REFERENCES dim_city(city_key),
    latitude        DOUBLE,
    longitude       DOUBLE
);

-- =====================================================================
-- LEVEL 5 dimensions (leaf dimensions referenced by the facts)
-- =====================================================================

CREATE TABLE dim_customer (
    customer_key       INTEGER PRIMARY KEY,
    customer_id        VARCHAR NOT NULL UNIQUE,   -- one per order in the source
    customer_unique_id VARCHAR NOT NULL,          -- the actual person
    zip_key            INTEGER NOT NULL REFERENCES dim_zip(zip_key)
);

CREATE TABLE dim_seller (
    seller_key      INTEGER PRIMARY KEY,
    seller_id       VARCHAR NOT NULL UNIQUE,
    zip_key         INTEGER NOT NULL REFERENCES dim_zip(zip_key),
    acquisition_key INTEGER NOT NULL REFERENCES dim_seller_acquisition(acquisition_key)
);

-- =====================================================================
-- FACT TABLES
-- =====================================================================

-- GRAIN: one row per line item of an order -- (order_id, order_item_id).
CREATE TABLE fact_order_item (
    order_item_sk           BIGINT  PRIMARY KEY,
    -- degenerate dimensions --------------------------------------------
    order_id                VARCHAR NOT NULL,
    order_item_id           INTEGER NOT NULL,
    -- dimension foreign keys -------------------------------------------
    customer_key            INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    seller_key              INTEGER NOT NULL REFERENCES dim_seller(seller_key),
    product_key             INTEGER NOT NULL REFERENCES dim_product(product_key),
    order_status_key        INTEGER NOT NULL REFERENCES dim_order_status(order_status_key),
    delivery_bucket_key     INTEGER NOT NULL REFERENCES dim_delivery_bucket(delivery_bucket_key),
    review_key              INTEGER NOT NULL REFERENCES dim_review(review_key),
    purchase_date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    approved_date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    carrier_date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    delivered_date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    estimated_date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    shipping_limit_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    -- additive measures ------------------------------------------------
    price                   DOUBLE  NOT NULL,
    freight_value           DOUBLE  NOT NULL,
    revenue                 DOUBLE  NOT NULL,     -- price + freight_value
    -- semi-additive / degenerate measures ------------------------------
    items_in_order          INTEGER NOT NULL,     -- for order-grain allocation
    delivery_days           INTEGER,              -- purchase -> delivered
    delivery_delay_days     INTEGER,              -- delivered - estimated (<0 = early)
    approval_hours          DOUBLE,
    UNIQUE (order_id, order_item_id)
);

-- GRAIN: one row per payment transaction -- (order_id, payment_sequential).
CREATE TABLE fact_order_payment (
    payment_sk           BIGINT  PRIMARY KEY,
    order_id             VARCHAR NOT NULL,
    payment_sequential   INTEGER NOT NULL,
    customer_key         INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    payment_type_key     INTEGER NOT NULL REFERENCES dim_payment_type(payment_type_key),
    order_status_key     INTEGER NOT NULL REFERENCES dim_order_status(order_status_key),
    purchase_date_key    INTEGER NOT NULL REFERENCES dim_date(date_key),
    payment_installments INTEGER,
    payment_value        DOUBLE  NOT NULL,
    UNIQUE (order_id, payment_sequential)
);
