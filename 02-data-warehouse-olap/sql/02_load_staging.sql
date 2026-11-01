-- =====================================================================
--  Assignment 2 / Part 1 / Task 2  --  STEP 1: RAW -> STAGING  (DuckDB)
-- =====================================================================
--  Everything is landed as VARCHAR (all_varchar=true) on purpose:
--    * zip code prefixes such as '01037' keep their leading zero,
--    * no silent type-coercion failures at read time -- every cast is
--      made explicit (and TRY_CAST'ed) in the transform layer, so a bad
--      value becomes NULL instead of aborting the whole load.
--  {RAW} is substituted by part1/etl/run_etl.py with the dataset folder.
-- =====================================================================

CREATE OR REPLACE TABLE stg_customers AS
SELECT * FROM read_csv('{RAW}/customers.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_sellers AS
SELECT * FROM read_csv('{RAW}/sellers.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_geolocation AS
SELECT * FROM read_csv('{RAW}/geolocation.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_orders AS
SELECT * FROM read_csv('{RAW}/orders.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_order_items AS
SELECT * FROM read_csv('{RAW}/order_items.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_order_payments AS
SELECT * FROM read_csv('{RAW}/order_payments.csv',
                       header = true, all_varchar = true, sample_size = -1);

-- review comments contain embedded newlines and doubled quotes
CREATE OR REPLACE TABLE stg_order_reviews AS
SELECT * FROM read_csv('{RAW}/order_reviews.csv',
                       header = true, all_varchar = true, sample_size = -1,
                       quote = '"', escape = '"');

CREATE OR REPLACE TABLE stg_products AS
SELECT * FROM read_csv('{RAW}/products.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_categories AS
SELECT * FROM read_csv('{RAW}/categories.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_leads AS
SELECT * FROM read_csv('{RAW}/leads.csv',
                       header = true, all_varchar = true, sample_size = -1);

CREATE OR REPLACE TABLE stg_closed_deals AS
SELECT * FROM read_csv('{RAW}/closed_deals.csv',
                       header = true, all_varchar = true, sample_size = -1);

-- ---------------------------------------------------------------------
-- Seed table: state -> region.  The region level is absent from the
-- source data, so it is supplied as *data* (a seed CSV), not hard-coded
-- in the SQL, which keeps the mapping auditable and easy to correct.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_state_region AS
SELECT * FROM read_csv('{SEED}/br_state_region.csv',
                       header = true, all_varchar = true, sample_size = -1);
