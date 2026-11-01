## Contents

- [Q01 -- revenue by time rollup](#q01-revenue-by-time-rollup)
- [Q02 -- peak month per year](#q02-peak-month-per-year)
- [Q03 -- revenue by category](#q03-revenue-by-category)
- [Q04 -- drilldown category product](#q04-drilldown-category-product)
- [Q05 -- geography rollup](#q05-geography-rollup)
- [Q06 -- top customers](#q06-top-customers)
- [Q07 -- top seller per state](#q07-top-seller-per-state)
- [Q08 -- cube region category year](#q08-cube-region-category-year)
- [Q09 -- review vs delivery](#q09-review-vs-delivery)
- [Q10 -- lead origin revenue](#q10-lead-origin-revenue)

# Part 1 / Task 3 -- Analytical query outputs

Revenue is defined throughout as `price + freight_value`.
Every query runs against the snowflake warehouse through the
`v_sales` / `v_orders` navigation views (see `sql/05_create_views.sql`).
Complete result sets are in `outputs/csv/`; the tables below are
truncated where a result is long.

## Q01 -- revenue by time rollup

> Q1. Total revenue per YEAR, then drilled down to QUARTER and MONTH.
> OLAP operation: ROLLUP over the time hierarchy year > quarter >
> month.  A single pass returns all four aggregation levels
> (grand total, year, quarter, month); GROUPING() tells them apart.
> revenue = price + freight_value

### Q1. Total revenue per YEAR, then drilled down to QUARTER and MONTH.

`q01_revenue_by_time_rollup_a.csv` -- 37 row(s), 587 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q1. Total revenue per YEAR, then drilled down to QUARTER and MONTH.
--     OLAP operation: ROLLUP over the time hierarchy year > quarter >
--     month.  A single pass returns all four aggregation levels
--     (grand total, year, quarter, month); GROUPING() tells them apart.
--     revenue = price + freight_value
-- =====================================================================

-- (a) Full time roll-up -----------------------------------------------
SELECT CASE WHEN GROUPING(purchase_year)    = 1 THEN 'ALL YEARS'
            ELSE CAST(purchase_year AS VARCHAR) END                     AS year,
       CASE WHEN GROUPING(purchase_quarter) = 1 THEN 'All quarters'
            ELSE 'Q' || CAST(purchase_quarter AS VARCHAR) END           AS quarter,
       CASE WHEN GROUPING(purchase_month)   = 1 THEN 'All months'
            ELSE printf('%02d', purchase_month) END                     AS month,
       CASE GROUPING(purchase_year) * 4
          + GROUPING(purchase_quarter) * 2
          + GROUPING(purchase_month)
            WHEN 7 THEN 'GRAND TOTAL'
            WHEN 3 THEN 'YEAR'
            WHEN 1 THEN 'QUARTER'
            ELSE        'MONTH' END                                     AS agg_level,
       ROUND(SUM(revenue), 2)                                           AS revenue,
       ROUND(SUM(price), 2)                                             AS product_revenue,
       ROUND(SUM(freight_value), 2)                                     AS freight_revenue,
       COUNT(DISTINCT order_id)                                         AS orders,
       COUNT(*)                                                         AS line_items
FROM v_sales
GROUP BY ROLLUP (purchase_year, purchase_quarter, purchase_month)
ORDER BY GROUPING(purchase_year) DESC,
         purchase_year,
         GROUPING(purchase_quarter) DESC,
         purchase_quarter,
         GROUPING(purchase_month) DESC,
         purchase_month
```

</details>

| year | quarter | month | agg_level | revenue | product_revenue | freight_revenue | orders | line_items |
|---|---|---|---|---|---|---|---|---|
| ALL YEARS | All quarters | All months | GRAND TOTAL | 15,843,553.24 | 13,591,643.70 | 2,251,909.54 | 98,666 | 112,650 |
| 2016 | All quarters | All months | YEAR | 57,183.21 | 49,785.92 | 7,397.29 | 312 | 370 |
| 2016 | Q3 | All months | QUARTER | 354.75 | 267.36 | 87.39 | 3 | 6 |
| 2016 | Q3 | 09 | MONTH | 354.75 | 267.36 | 87.39 | 3 | 6 |
| 2016 | Q4 | All months | QUARTER | 56,828.46 | 49,518.56 | 7,309.90 | 309 | 364 |
| 2016 | Q4 | 10 | MONTH | 56,808.84 | 49,507.66 | 7,301.18 | 308 | 363 |
| 2016 | Q4 | 12 | MONTH | 19.62 | 10.90 | 8.72 | 1 | 1 |
| 2017 | All quarters | All months | YEAR | 7,142,672.43 | 6,155,806.98 | 986,865.45 | 44,579 | 50,864 |
| 2017 | Q1 | All months | QUARTER | 855,517.70 | 741,960.19 | 113,557.51 | 5,163 | 5,906 |
| 2017 | Q1 | 01 | MONTH | 137,188.49 | 120,312.87 | 16,875.62 | 789 | 955 |
| 2017 | Q1 | 02 | MONTH | 286,280.62 | 247,303.02 | 38,977.60 | 1,733 | 1,951 |
| 2017 | Q1 | 03 | MONTH | 432,048.59 | 374,344.30 | 57,704.29 | 2,641 | 3,000 |
| 2017 | Q2 | All months | QUARTER | 1,501,576.23 | 1,299,036.97 | 202,539.26 | 9,268 | 10,403 |
| 2017 | Q2 | 04 | MONTH | 412,422.24 | 359,927.23 | 52,495.01 | 2,391 | 2,684 |
| 2017 | Q2 | 05 | MONTH | 586,190.95 | 506,071.14 | 80,119.81 | 3,660 | 4,136 |
| 2017 | Q2 | 06 | MONTH | 502,963.04 | 433,038.60 | 69,924.44 | 3,217 | 3,583 |
| 2017 | Q3 | All months | QUARTER | 1,973,575.13 | 1,696,404.85 | 277,170.28 | 12,505 | 14,260 |
| 2017 | Q3 | 07 | MONTH | 584,971.62 | 498,031.48 | 86,940.14 | 3,969 | 4,519 |
| 2017 | Q3 | 08 | MONTH | 668,204.60 | 573,971.68 | 94,232.92 | 4,293 | 4,910 |
| 2017 | Q3 | 09 | MONTH | 720,398.91 | 624,401.69 | 95,997.22 | 4,243 | 4,831 |
| 2017 | Q4 | All months | QUARTER | 2,812,003.37 | 2,418,404.97 | 393,598.40 | 17,643 | 20,295 |
| 2017 | Q4 | 10 | MONTH | 769,312.37 | 664,219.43 | 105,092.94 | 4,568 | 5,322 |
| 2017 | Q4 | 11 | MONTH | 1,179,143.77 | 1,010,271.37 | 168,872.40 | 7,451 | 8,665 |
| 2017 | Q4 | 12 | MONTH | 863,547.23 | 743,914.17 | 119,633.06 | 5,624 | 6,308 |
| 2018 | All quarters | All months | YEAR | 8,643,697.60 | 7,386,050.80 | 1,257,646.80 | 53,775 | 61,416 |
| 2018 | Q1 | All months | QUARTER | 3,249,337.67 | 2,777,422.51 | 471,915.16 | 21,102 | 24,097 |
| 2018 | Q1 | 01 | MONTH | 1,107,301.89 | 950,030.36 | 157,271.53 | 7,220 | 8,208 |
| 2018 | Q1 | 02 | MONTH | 986,908.96 | 844,178.71 | 142,730.25 | 6,694 | 7,672 |
| 2018 | Q1 | 03 | MONTH | 1,155,126.82 | 983,213.44 | 171,913.38 | 7,188 | 8,217 |
| 2018 | Q2 | All months | QUARTER | 3,332,156.97 | 2,858,289.74 | 473,867.23 | 19,947 | 22,978 |
| 2018 | Q2 | 04 | MONTH | 1,159,698.04 | 996,647.75 | 163,050.29 | 6,934 | 7,975 |
| 2018 | Q2 | 05 | MONTH | 1,149,781.82 | 996,517.68 | 153,264.14 | 6,853 | 7,925 |
| 2018 | Q2 | 06 | MONTH | 1,022,677.11 | 865,124.31 | 157,552.80 | 6,160 | 7,078 |
| 2018 | Q3 | All months | QUARTER | 2,062,202.96 | 1,750,338.55 | 311,864.41 | 12,726 | 14,341 |
| 2018 | Q3 | 07 | MONTH | 1,058,728.03 | 895,507.22 | 163,220.81 | 6,273 | 7,092 |
| 2018 | Q3 | 08 | MONTH | 1,003,308.47 | 854,686.33 | 148,622.14 | 6,452 | 7,248 |
| 2018 | Q3 | 09 | MONTH | 166.46 | 145.00 | 21.46 | 1 | 1 |

### (b) Year level only, with year-on-year growth

`q01_revenue_by_time_rollup_b.csv` -- 3 row(s), 219 ms

<details><summary>SQL</summary>

```sql
-- (b) Year level only, with year-on-year growth ------------------------
SELECT purchase_year                                        AS year,
       ROUND(SUM(revenue), 2)                               AS revenue,
       COUNT(DISTINCT order_id)                             AS orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)    AS avg_order_value,
       ROUND(100.0 * (SUM(revenue) - LAG(SUM(revenue)) OVER (ORDER BY purchase_year))
             / NULLIF(LAG(SUM(revenue)) OVER (ORDER BY purchase_year), 0), 1) AS yoy_growth_pct
FROM v_sales
GROUP BY purchase_year
ORDER BY purchase_year
```

</details>

| year | revenue | orders | avg_order_value | yoy_growth_pct |
|---|---|---|---|---|
| 2,016 | 57,183.21 | 312 | 183.28 | *(ALL)* |
| 2,017 | 7,142,672.43 | 44,579 | 160.23 | 12,390.90 |
| 2,018 | 8,643,697.60 | 53,775 | 160.74 | 21.00 |

## Q02 -- peak month per year

> Q2. The month with the HIGHEST revenue in each year.
> OLAP operation: drill down the time hierarchy to month level, then
> rank within each year (QUALIFY = HAVING for window functions).

### Q2. The month with the HIGHEST revenue in each year.

`q02_peak_month_per_year_a.csv` -- 3 row(s), 306 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q2. The month with the HIGHEST revenue in each year.
--     OLAP operation: drill down the time hierarchy to month level, then
--     rank within each year (QUALIFY = HAVING for window functions).
-- =====================================================================

-- (a) Peak month per year ---------------------------------------------
WITH monthly AS (
    SELECT purchase_year               AS year,
           purchase_month              AS month,
           ANY_VALUE(purchase_month_name) AS month_name,
           SUM(revenue)                AS revenue,
           COUNT(DISTINCT order_id)    AS orders
    FROM v_sales
    GROUP BY purchase_year, purchase_month
)
SELECT year,
       month,
       month_name,
       ROUND(revenue, 2)                                                AS revenue,
       orders,
       ROUND(revenue / orders, 2)                                       AS avg_order_value,
       ROUND(100.0 * revenue / SUM(revenue) OVER (PARTITION BY year), 1) AS pct_of_year_revenue
FROM monthly
QUALIFY ROW_NUMBER() OVER (PARTITION BY year ORDER BY revenue DESC) = 1
ORDER BY year
```

</details>

| year | month | month_name | revenue | orders | avg_order_value | pct_of_year_revenue |
|---|---|---|---|---|---|---|
| 2,016 | 10 | October | 56,808.84 | 308 | 184.44 | 99.30 |
| 2,017 | 11 | November | 1,179,143.77 | 7,451 | 158.25 | 16.50 |
| 2,018 | 4 | April | 1,159,698.04 | 6,934 | 167.25 | 13.40 |

### (b) Supporting detail: every month ranked inside its year

`q02_peak_month_per_year_b.csv` -- 24 row(s), 193 ms

<details><summary>SQL</summary>

```sql
-- (b) Supporting detail: every month ranked inside its year ------------
WITH monthly AS (
    SELECT purchase_year AS year,
           purchase_month AS month,
           ANY_VALUE(purchase_month_name) AS month_name,
           SUM(revenue) AS revenue
    FROM v_sales
    GROUP BY purchase_year, purchase_month
)
SELECT year,
       printf('%04d-%02d', year, month)                                  AS year_month,
       month_name,
       ROUND(revenue, 2)                                                 AS revenue,
       RANK() OVER (PARTITION BY year ORDER BY revenue DESC)             AS rank_in_year
FROM monthly
ORDER BY year, month
```

</details>

| year | year_month | month_name | revenue | rank_in_year |
|---|---|---|---|---|
| 2,016 | 2016-09 | September | 354.75 | 2 |
| 2,016 | 2016-10 | October | 56,808.84 | 1 |
| 2,016 | 2016-12 | December | 19.62 | 3 |
| 2,017 | 2017-01 | January | 137,188.49 | 12 |
| 2,017 | 2017-02 | February | 286,280.62 | 11 |
| 2,017 | 2017-03 | March | 432,048.59 | 9 |
| 2,017 | 2017-04 | April | 412,422.24 | 10 |
| 2,017 | 2017-05 | May | 586,190.95 | 6 |
| 2,017 | 2017-06 | June | 502,963.04 | 8 |
| 2,017 | 2017-07 | July | 584,971.62 | 7 |
| 2,017 | 2017-08 | August | 668,204.60 | 5 |
| 2,017 | 2017-09 | September | 720,398.91 | 4 |
| 2,017 | 2017-10 | October | 769,312.37 | 3 |
| 2,017 | 2017-11 | November | 1,179,143.77 | 1 |
| 2,017 | 2017-12 | December | 863,547.23 | 2 |
| 2,018 | 2018-01 | January | 1,107,301.89 | 4 |
| 2,018 | 2018-02 | February | 986,908.96 | 8 |
| 2,018 | 2018-03 | March | 1,155,126.82 | 2 |
| 2,018 | 2018-04 | April | 1,159,698.04 | 1 |
| 2,018 | 2018-05 | May | 1,149,781.82 | 3 |
| 2,018 | 2018-06 | June | 1,022,677.11 | 6 |
| 2,018 | 2018-07 | July | 1,058,728.03 | 5 |
| 2,018 | 2018-08 | August | 1,003,308.47 | 7 |
| 2,018 | 2018-09 | September | 166.46 | 9 |

## Q03 -- revenue by category

> Q3. Which PRODUCT CATEGORIES generate the most revenue?
> Walks the product hierarchy one level up (product -> category) and
> adds a Pareto (cumulative share) column so the concentration of
> revenue across categories is visible directly in the result.

### Q3. Which PRODUCT CATEGORIES generate the most revenue?

`q03_revenue_by_category_a.csv` -- 74 row(s), 363 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q3. Which PRODUCT CATEGORIES generate the most revenue?
--     Walks the product hierarchy one level up (product -> category) and
--     adds a Pareto (cumulative share) column so the concentration of
--     revenue across categories is visible directly in the result.
-- =====================================================================

-- (a) Categories ranked by revenue, with cumulative share --------------
SELECT category,
       ROUND(SUM(revenue), 2)                                            AS revenue,
       ROUND(SUM(price), 2)                                              AS product_revenue,
       ROUND(SUM(freight_value), 2)                                      AS freight_revenue,
       COUNT(*)                                                          AS units_sold,
       COUNT(DISTINCT order_id)                                          AS orders,
       COUNT(DISTINCT product_id)                                        AS distinct_products,
       ROUND(AVG(price), 2)                                              AS avg_unit_price,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)        AS pct_of_total,
       ROUND(100.0 * SUM(SUM(revenue)) OVER (ORDER BY SUM(revenue) DESC
                                             ROWS UNBOUNDED PRECEDING)
             / SUM(SUM(revenue)) OVER (), 2)                             AS cumulative_pct
FROM v_sales
GROUP BY category
ORDER BY revenue DESC
```

</details>

| category | revenue | product_revenue | freight_revenue | units_sold | orders | distinct_products | avg_unit_price | pct_of_total | cumulative_pct |
|---|---|---|---|---|---|---|---|---|---|
| health_beauty | 1,441,248.07 | 1,258,681.34 | 182,566.73 | 9,670 | 8,836 | 2,444 | 130.16 | 9.10 | 9.10 |
| watches_gifts | 1,305,541.61 | 1,205,005.68 | 100,535.93 | 5,991 | 5,624 | 1,329 | 201.14 | 8.24 | 17.34 |
| bed_bath_table | 1,241,681.72 | 1,036,988.68 | 204,693.04 | 11,115 | 9,417 | 3,029 | 93.30 | 7.84 | 25.17 |
| sports_leisure | 1,156,656.48 | 988,048.97 | 168,607.51 | 8,641 | 7,720 | 2,867 | 114.34 | 7.30 | 32.47 |
| computers_accessories | 1,059,272.40 | 911,954.32 | 147,318.08 | 7,827 | 6,689 | 1,639 | 116.51 | 6.69 | 39.16 |
| furniture_decor | 902,511.79 | 729,762.49 | 172,749.30 | 8,334 | 6,449 | 2,657 | 87.56 | 5.70 | 44.86 |
| housewares | 778,397.77 | 632,248.66 | 146,149.11 | 6,964 | 5,884 | 2,335 | 90.79 | 4.91 | 49.77 |
| cool_stuff | 719,329.95 | 635,290.85 | 84,039.10 | 3,796 | 3,632 | 789 | 167.36 | 4.54 | 54.31 |
| auto | 685,384.32 | 592,720.11 | 92,664.21 | 4,235 | 3,897 | 1,900 | 139.96 | 4.33 | 58.64 |
| garden_tools | 584,219.21 | 485,256.46 | 98,962.75 | 4,347 | 3,518 | 753 | 111.63 | 3.69 | 62.32 |
| toys | 561,372.55 | 483,946.60 | 77,425.95 | 4,117 | 3,886 | 1,411 | 117.55 | 3.54 | 65.87 |
| baby | 480,118.00 | 411,764.89 | 68,353.11 | 3,065 | 2,885 | 919 | 134.34 | 3.03 | 68.90 |
| perfumery | 453,338.71 | 399,124.87 | 54,213.84 | 3,419 | 3,162 | 868 | 116.74 | 2.86 | 71.76 |
| telephony | 394,883.32 | 323,667.53 | 71,215.79 | 4,545 | 4,199 | 1,134 | 71.21 | 2.49 | 74.25 |
| office_furniture | 342,532.65 | 273,960.70 | 68,571.95 | 1,691 | 1,273 | 309 | 162.01 | 2.16 | 76.41 |
| stationery | 277,741.71 | 230,943.23 | 46,798.48 | 2,517 | 2,311 | 849 | 91.75 | 1.75 | 78.17 |
| pet_shop | 253,876.65 | 214,315.41 | 39,561.24 | 1,947 | 1,710 | 719 | 110.07 | 1.60 | 79.77 |
| computers | 232,799.43 | 222,963.13 | 9,836.30 | 203 | 181 | 30 | 1,098.34 | 1.47 | 81.24 |
| musical_instruments | 210,137.37 | 191,498.88 | 18,638.49 | 680 | 628 | 289 | 281.62 | 1.33 | 82.56 |
| unknown | 207,705.09 | 179,535.28 | 28,169.81 | 1,603 | 1,451 | 610 | 112.00 | 1.31 | 83.87 |
| electronics | 206,825.06 | 160,246.74 | 46,578.32 | 2,767 | 2,550 | 517 | 57.91 | 1.31 | 85.18 |
| small_appliances | 206,668.83 | 190,648.58 | 16,020.25 | 679 | 630 | 231 | 280.78 | 1.30 | 86.48 |
| fashion_bags_accessories | 184,273.54 | 152,823.54 | 31,450.00 | 2,031 | 1,864 | 849 | 75.25 | 1.16 | 87.65 |
| consoles_games | 177,293.24 | 157,465.22 | 19,828.02 | 1,137 | 1,062 | 317 | 138.49 | 1.12 | 88.77 |
| luggage_accessories | 170,875.21 | 140,429.98 | 30,445.23 | 1,092 | 1,034 | 349 | 128.60 | 1.08 | 89.85 |
| construction_tools_construction | 165,328.00 | 144,677.59 | 20,650.41 | 929 | 748 | 400 | 155.73 | 1.04 | 90.89 |
| home_appliances_2 | 123,917.92 | 113,317.74 | 10,600.18 | 238 | 234 | 90 | 476.12 | 0.78 | 91.67 |
| home_construction | 96,920.36 | 83,088.12 | 13,832.24 | 604 | 490 | 225 | 137.56 | 0.61 | 92.28 |
| home_appliances | 94,990.43 | 80,171.53 | 14,818.90 | 771 | 764 | 370 | 103.98 | 0.60 | 92.88 |
| furniture_living_room | 86,884.73 | 68,916.56 | 17,968.17 | 503 | 422 | 156 | 137.01 | 0.55 | 93.43 |
| agro_industry_and_commerce | 78,374.07 | 72,530.47 | 5,843.60 | 212 | 182 | 74 | 342.12 | 0.49 | 93.93 |
| home_confort | 67,073.27 | 58,572.04 | 8,501.23 | 434 | 397 | 111 | 134.96 | 0.42 | 94.35 |
| fixed_telephony | 64,220.81 | 59,583.00 | 4,637.81 | 264 | 217 | 116 | 225.69 | 0.41 | 94.75 |
| air_conditioning | 61,774.19 | 55,024.96 | 6,749.23 | 297 | 253 | 124 | 185.27 | 0.39 | 95.14 |
| kitchen_dining_laundry_garden_furniture | 58,327.80 | 46,328.37 | 11,999.43 | 281 | 248 | 94 | 164.87 | 0.37 | 95.51 |
| audio | 56,398.94 | 50,688.50 | 5,710.44 | 364 | 350 | 58 | 139.25 | 0.36 | 95.87 |
| books_general_interest | 56,052.40 | 46,856.88 | 9,195.52 | 553 | 512 | 216 | 84.73 | 0.35 | 96.22 |
| small_appliances_home_oven_and_coffee | 50,193.57 | 47,445.71 | 2,747.86 | 76 | 75 | 31 | 624.29 | 0.32 | 96.54 |
| construction_tools_lights | 48,663.80 | 41,080.00 | 7,583.80 | 304 | 244 | 78 | 135.13 | 0.31 | 96.85 |
| industry_commerce_and_business | 47,554.29 | 39,669.61 | 7,884.68 | 268 | 235 | 68 | 148.02 | 0.30 | 97.15 |

*(34 further rows omitted)*

### (b) Roll-up of category revenue by customer region (cross-tab feed)

`q03_revenue_by_category_b.csv` -- 15 row(s), 132 ms

<details><summary>SQL</summary>

```sql
-- (b) Roll-up of category revenue by customer region (cross-tab feed) --
SELECT category,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'Southeast'), 2)     AS southeast,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'South'), 2)         AS south,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'Northeast'), 2)     AS northeast,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'Central-West'), 2)  AS central_west,
       ROUND(SUM(revenue) FILTER (WHERE customer_region = 'North'), 2)         AS north,
       ROUND(SUM(revenue), 2)                                                  AS total
FROM v_sales
GROUP BY category
ORDER BY total DESC
LIMIT 15
```

</details>

| category | southeast | south | northeast | central_west | north | total |
|---|---|---|---|---|---|---|
| health_beauty | 886,750.28 | 169,174.89 | 236,942.00 | 98,513.81 | 49,867.09 | 1,441,248.07 |
| watches_gifts | 828,720.08 | 153,753.51 | 186,013.11 | 94,914.18 | 42,140.73 | 1,305,541.61 |
| bed_bath_table | 921,076.09 | 165,541.23 | 79,530.42 | 63,782.93 | 11,751.05 | 1,241,681.72 |
| sports_leisure | 744,402.56 | 182,769.64 | 123,735.56 | 72,812.13 | 32,936.59 | 1,156,656.48 |
| computers_accessories | 685,973.34 | 157,359.26 | 119,030.17 | 66,992.59 | 29,917.04 | 1,059,272.40 |
| furniture_decor | 581,355.69 | 169,076.81 | 85,204.22 | 46,684.69 | 20,190.38 | 902,511.79 |
| housewares | 539,452.69 | 120,812.89 | 55,356.97 | 52,130.30 | 10,644.92 | 778,397.77 |
| cool_stuff | 426,574.58 | 126,541.13 | 93,254.24 | 55,265.81 | 17,694.19 | 719,329.95 |
| auto | 414,863.50 | 96,821.79 | 101,850.59 | 53,845.81 | 18,002.63 | 685,384.32 |
| garden_tools | 357,041.87 | 97,162.74 | 71,512.35 | 44,923.03 | 13,579.22 | 584,219.21 |
| toys | 376,576.99 | 79,945.51 | 57,250.51 | 35,409.49 | 12,190.05 | 561,372.55 |
| baby | 294,931.80 | 80,952.11 | 50,131.80 | 34,717.45 | 19,384.84 | 480,118.00 |
| perfumery | 309,349.75 | 57,614.17 | 47,508.70 | 28,951.49 | 9,914.60 | 453,338.71 |
| telephony | 221,131.63 | 56,469.12 | 78,372.85 | 22,601.53 | 16,308.19 | 394,883.32 |
| office_furniture | 228,612.44 | 46,801.44 | 43,353.86 | 13,925.71 | 9,839.20 | 342,532.65 |

## Q04 -- drilldown category product

> Q4. DRILL DOWN from CATEGORY -> PRODUCT to find the best-selling
> products.
> OLAP operation: GROUPING SETS ((category), (category, product)) so
> that one pass returns the category subtotal *and* the product
> detail underneath it -- exactly what a drill-down does in a UI.

### Q4. DRILL DOWN from CATEGORY -> PRODUCT to find the best-selling

`q04_drilldown_category_product_a.csv` -- 40 row(s), 565 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q4. DRILL DOWN from CATEGORY -> PRODUCT to find the best-selling
--     products.
--     OLAP operation: GROUPING SETS ((category), (category, product)) so
--     that one pass returns the category subtotal *and* the product
--     detail underneath it -- exactly what a drill-down does in a UI.
-- =====================================================================

-- (a) Top 10 categories, each followed by its top 3 products -----------
WITH lvl AS (
    SELECT category,
           product_id,
           GROUPING(product_id)  AS g_product,
           SUM(revenue)          AS revenue,
           SUM(price)            AS product_revenue,
           COUNT(*)              AS units_sold,
           COUNT(DISTINCT order_id) AS orders
    FROM v_sales
    GROUP BY GROUPING SETS ((category), (category, product_id))
),
cat_rank AS (                       -- rank the categories by their subtotal
    SELECT category, revenue,
           ROW_NUMBER() OVER (ORDER BY revenue DESC) AS cat_rank
    FROM lvl
    WHERE g_product = 1
),
labelled AS (
    SELECT l.category,
           CASE WHEN l.g_product = 1 THEN '-- category subtotal --'
                ELSE l.product_id END                     AS product_id,
           CASE WHEN l.g_product = 1 THEN 'CATEGORY' ELSE 'PRODUCT' END AS agg_level,
           l.revenue, l.product_revenue, l.units_sold, l.orders,
           l.g_product,
           cr.cat_rank,
           cr.revenue                                     AS category_revenue,
           CASE WHEN l.g_product = 1 THEN 0
                ELSE ROW_NUMBER() OVER (PARTITION BY l.category, l.g_product
                                        ORDER BY l.revenue DESC) END AS rank_in_category
    FROM lvl l
    JOIN cat_rank cr USING (category)
)
SELECT cat_rank,
       category,
       agg_level,
       product_id,
       rank_in_category,
       ROUND(revenue, 2)                                        AS revenue,
       units_sold,
       orders,
       ROUND(100.0 * revenue / category_revenue, 1)             AS pct_of_category
FROM labelled
WHERE cat_rank <= 10
  AND (g_product = 1 OR rank_in_category <= 3)
ORDER BY cat_rank, g_product DESC, revenue DESC
```

</details>

| cat_rank | category | agg_level | product_id | rank_in_category | revenue | units_sold | orders | pct_of_category |
|---|---|---|---|---|---|---|---|---|
| 1 | health_beauty | CATEGORY | -- category subtotal -- | 0 | 1,441,248.07 | 9,670 | 8,836 | 100.00 |
| 1 | health_beauty | PRODUCT | bb50f2e236e5eea0100680137654686c | 1 | 67,606.10 | 195 | 187 | 4.70 |
| 1 | health_beauty | PRODUCT | 6cdd53843498f92890544667809f1595 | 2 | 59,093.99 | 156 | 151 | 4.10 |
| 1 | health_beauty | PRODUCT | 2b4609f8948be18874494203496bc318 | 3 | 26,659.74 | 260 | 259 | 1.80 |
| 2 | watches_gifts | CATEGORY | -- category subtotal -- | 0 | 1,305,541.61 | 5,991 | 5,624 | 100.00 |
| 2 | watches_gifts | PRODUCT | 53b36df67ebb7c41585e8d54d6772e08 | 1 | 39,957.93 | 323 | 306 | 3.10 |
| 2 | watches_gifts | PRODUCT | e0d64dcfaa3b6db5c54ca298ae101d05 | 2 | 35,344.09 | 194 | 194 | 2.70 |
| 2 | watches_gifts | PRODUCT | d285360f29ac7fd97640bf0baef03de0 | 3 | 33,607.57 | 123 | 122 | 2.60 |
| 3 | bed_bath_table | CATEGORY | -- category subtotal -- | 0 | 1,241,681.72 | 11,115 | 9,417 | 100.00 |
| 3 | bed_bath_table | PRODUCT | 99a4788cb24856965c36a24e339b6058 | 1 | 51,071.60 | 488 | 467 | 4.10 |
| 3 | bed_bath_table | PRODUCT | f1c7f353075ce59d8a6f3cf58f419c9c | 2 | 33,316.76 | 154 | 150 | 2.70 |
| 3 | bed_bath_table | PRODUCT | 84f456958365164420cfc80fbe4c7fab | 3 | 12,160.45 | 111 | 106 | 1.00 |
| 4 | sports_leisure | CATEGORY | -- category subtotal -- | 0 | 1,156,656.48 | 8,641 | 7,720 | 100.00 |
| 4 | sports_leisure | PRODUCT | e44f675b60b3a3a2453ec36421e06f0f | 1 | 10,263.75 | 84 | 77 | 0.90 |
| 4 | sports_leisure | PRODUCT | b4436da747c3a53ab07ac0e71de17dcd | 2 | 10,052.68 | 6 | 6 | 0.90 |
| 4 | sports_leisure | PRODUCT | 0bbdc963004d9b2fd3427ee3c5ae3608 | 3 | 9,595.77 | 30 | 26 | 0.80 |
| 5 | computers_accessories | CATEGORY | -- category subtotal -- | 0 | 1,059,272.40 | 7,827 | 6,689 | 100.00 |
| 5 | computers_accessories | PRODUCT | d1c427060a0f73f6b889a5c7c61f2ac4 | 1 | 60,976.03 | 343 | 323 | 5.80 |
| 5 | computers_accessories | PRODUCT | 3dd2a17168ec895c781a9191c1e95ad7 | 2 | 48,212.22 | 274 | 255 | 4.60 |
| 5 | computers_accessories | PRODUCT | e53e557d5a159f5aa2c5e995dfdf244b | 3 | 18,409.72 | 183 | 156 | 1.70 |
| 6 | furniture_decor | CATEGORY | -- category subtotal -- | 0 | 902,511.79 | 8,334 | 6,449 | 100.00 |
| 6 | furniture_decor | PRODUCT | aca2eb7d00ea1a7b8ebd4e68314663af | 1 | 44,820.76 | 527 | 431 | 5.00 |
| 6 | furniture_decor | PRODUCT | 7814c273ab16783d73a9863ebfa8b141 | 2 | 18,273.08 | 62 | 58 | 2.00 |
| 6 | furniture_decor | PRODUCT | 78efe838c04bbc568be034082200ac20 | 3 | 12,027.12 | 101 | 100 | 1.30 |
| 7 | housewares | CATEGORY | -- category subtotal -- | 0 | 778,397.77 | 6,964 | 5,884 | 100.00 |
| 7 | housewares | PRODUCT | 4aa6014eceb682077f9dc4bffebc05b0 | 1 | 15,621.16 | 47 | 45 | 2.00 |
| 7 | housewares | PRODUCT | 42a2c92a0979a949ca4ea89ec5c7b934 | 2 | 14,258.97 | 183 | 160 | 1.80 |
| 7 | housewares | PRODUCT | e9a69340883a438c3f91739d14d3a56d | 3 | 11,425.17 | 58 | 55 | 1.50 |
| 8 | cool_stuff | CATEGORY | -- category subtotal -- | 0 | 719,329.95 | 3,796 | 3,632 | 100.00 |
| 8 | cool_stuff | PRODUCT | 5f504b3a1c75b73d6151be81eb05bdc9 | 1 | 41,725.81 | 63 | 63 | 5.80 |
| 8 | cool_stuff | PRODUCT | 165f86fe8b799a708a20ee4ba125c289 | 2 | 20,291.35 | 109 | 109 | 2.80 |
| 8 | cool_stuff | PRODUCT | 601a360bd2a916ecef0e88de72a6531a | 3 | 17,402.18 | 119 | 119 | 2.40 |
| 9 | auto | CATEGORY | -- category subtotal -- | 0 | 685,384.32 | 4,235 | 3,897 | 100.00 |
| 9 | auto | PRODUCT | fd0065af7f09af4b82a0ca8f3eed1852 | 1 | 22,367.88 | 11 | 11 | 3.30 |
| 9 | auto | PRODUCT | 1dec4c88c685d5a07bf01dcb0f8bf9f8 | 2 | 22,228.51 | 35 | 35 | 3.20 |
| 9 | auto | PRODUCT | f4f67ccaece962d013a4e1d7dc3a61f7 | 3 | 14,747.13 | 56 | 56 | 2.20 |
| 10 | garden_tools | CATEGORY | -- category subtotal -- | 0 | 584,219.21 | 4,347 | 3,518 | 100.00 |
| 10 | garden_tools | PRODUCT | 422879e10f46682990de24d770e7f83d | 1 | 34,201.26 | 484 | 352 | 5.90 |
| 10 | garden_tools | PRODUCT | 389d119b48cf3043d311335e499d9c6b | 2 | 28,682.68 | 392 | 311 | 4.90 |
| 10 | garden_tools | PRODUCT | 368c6c730842d78016ad823897a372db | 3 | 27,984.40 | 388 | 291 | 4.80 |

### (b) Overall best-selling products (leaf level of the hierarchy)

`q04_drilldown_category_product_b.csv` -- 15 row(s), 261 ms

<details><summary>SQL</summary>

```sql
-- (b) Overall best-selling products (leaf level of the hierarchy) ------
SELECT product_id,
       ANY_VALUE(category)                       AS category,
       ROUND(SUM(revenue), 2)                    AS revenue,
       COUNT(*)                                  AS units_sold,
       COUNT(DISTINCT order_id)                  AS orders,
       ROUND(AVG(price), 2)                      AS avg_unit_price
FROM v_sales
GROUP BY product_id
ORDER BY revenue DESC
LIMIT 15
```

</details>

| product_id | category | revenue | units_sold | orders | avg_unit_price |
|---|---|---|---|---|---|
| bb50f2e236e5eea0100680137654686c | health_beauty | 67,606.10 | 195 | 187 | 327.62 |
| d1c427060a0f73f6b889a5c7c61f2ac4 | computers_accessories | 60,976.03 | 343 | 323 | 137.65 |
| 6cdd53843498f92890544667809f1595 | health_beauty | 59,093.99 | 156 | 151 | 350.83 |
| 99a4788cb24856965c36a24e339b6058 | bed_bath_table | 51,071.60 | 488 | 467 | 88.17 |
| d6160fb7873f184099d9bc95e30376af | computers | 50,326.18 | 35 | 35 | 1,397.12 |
| 3dd2a17168ec895c781a9191c1e95ad7 | computers_accessories | 48,212.22 | 274 | 255 | 149.94 |
| aca2eb7d00ea1a7b8ebd4e68314663af | furniture_decor | 44,820.76 | 527 | 431 | 71.36 |
| 5f504b3a1c75b73d6151be81eb05bdc9 | cool_stuff | 41,725.81 | 63 | 63 | 598.95 |
| 25c38557cf793876c5abdd5931f922db | baby | 40,311.95 | 38 | 38 | 1,023.88 |
| 53b36df67ebb7c41585e8d54d6772e08 | watches_gifts | 39,957.93 | 323 | 306 | 116.67 |
| e0d64dcfaa3b6db5c54ca298ae101d05 | watches_gifts | 35,344.09 | 194 | 194 | 163.85 |
| 422879e10f46682990de24d770e7f83d | garden_tools | 34,201.26 | 484 | 352 | 54.91 |
| d285360f29ac7fd97640bf0baef03de0 | watches_gifts | 33,607.57 | 123 | 122 | 257.10 |
| f1c7f353075ce59d8a6f3cf58f419c9c | bed_bath_table | 33,316.76 | 154 | 150 | 194.79 |
| 7a10781637204d8d10485c71a6108a2e | watches_gifts | 32,790.74 | 143 | 142 | 213.06 |

## Q05 -- geography rollup

> Q5. ROLL UP geography CITY -> STATE -> REGION and find the
> best-selling regions.
> This is the query the snowflaked geography hierarchy exists for:
> dim_zip -> dim_city -> dim_state -> dim_region.  The region level
> is not in the source data at all; it comes from the seed file.

### Q5. ROLL UP geography CITY -> STATE -> REGION and find the

`q05_geography_rollup_a.csv` -- 87 row(s), 654 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q5. ROLL UP geography CITY -> STATE -> REGION and find the
--     best-selling regions.
--     This is the query the snowflaked geography hierarchy exists for:
--     dim_zip -> dim_city -> dim_state -> dim_region.  The region level
--     is not in the source data at all; it comes from the seed file.
-- =====================================================================

-- (a) Full geography roll-up (all region + state rows, top 3 cities per state)
WITH rolled AS (
    SELECT customer_region                AS region,
           customer_state                 AS state,
           customer_city                  AS city,
           GROUPING(customer_region)      AS g_region,
           GROUPING(customer_state)       AS g_state,
           GROUPING(customer_city)        AS g_city,
           SUM(revenue)                   AS revenue,
           COUNT(DISTINCT order_id)       AS orders,
           COUNT(DISTINCT customer_unique_id) AS customers,
           COUNT(*)                       AS line_items
    FROM v_sales
    GROUP BY ROLLUP (customer_region, customer_state, customer_city)
),
with_totals AS (
    SELECT *,
           MAX(CASE WHEN g_region = 0 AND g_state = 1 THEN revenue END)
               OVER (PARTITION BY region)                AS region_revenue,
           MAX(CASE WHEN g_state = 0 AND g_city = 1 THEN revenue END)
               OVER (PARTITION BY region, state)         AS state_revenue,
           MAX(CASE WHEN g_region = 1 THEN revenue END) OVER ()  AS grand_revenue
    FROM rolled
)
SELECT CASE WHEN g_region = 1 THEN 'ALL REGIONS' ELSE region END          AS region,
       CASE WHEN g_state  = 1 THEN 'All states'  ELSE state  END          AS state,
       CASE WHEN g_city   = 1 THEN 'All cities'  ELSE city   END          AS city,
       CASE g_region * 4 + g_state * 2 + g_city
            WHEN 7 THEN 'GRAND TOTAL'
            WHEN 3 THEN 'REGION'
            WHEN 1 THEN 'STATE'
            ELSE        'CITY' END                                        AS agg_level,
       ROUND(revenue, 2)                                                  AS revenue,
       orders,
       customers,
       ROUND(revenue / NULLIF(orders, 0), 2)                              AS avg_order_value,
       ROUND(100.0 * revenue / grand_revenue, 2)                          AS pct_of_total
FROM with_totals
QUALIFY g_city = 1
     OR ROW_NUMBER() OVER (PARTITION BY region, state ORDER BY revenue DESC) <= 3
ORDER BY g_region DESC,
         region_revenue DESC NULLS LAST, region,
         g_state DESC,
         state_revenue DESC NULLS LAST, state,
         g_city DESC,
         revenue DESC
```

</details>

| region | state | city | agg_level | revenue | orders | customers | avg_order_value | pct_of_total |
|---|---|---|---|---|---|---|---|---|
| ALL REGIONS | All states | All cities | GRAND TOTAL | 15,843,553.24 | 98,666 | 95,420 | 160.58 | 100.00 |
| Southeast | All states | All cities | REGION | 10,232,323.50 | 67,706 | 65,410 | 151.13 | 64.58 |
| Southeast | SP | All cities | STATE | 5,921,678.12 | 41,375 | 39,981 | 143.12 | 37.38 |
| Southeast | SP | sao paulo | CITY | 2,170,010.94 | 15,399 | 14,862 | 140.92 | 13.70 |
| Southeast | SP | campinas | CITY | 212,541.70 | 1,429 | 1,386 | 148.73 | 1.34 |
| Southeast | RJ | All cities | STATE | 2,129,681.98 | 12,762 | 12,303 | 166.88 | 13.44 |
| Southeast | RJ | rio de janeiro | CITY | 1,154,234.02 | 6,834 | 6,576 | 168.90 | 7.29 |
| Southeast | RJ | niteroi | CITY | 137,919.38 | 845 | 807 | 163.22 | 0.87 |
| Southeast | MG | All cities | STATE | 1,856,161.49 | 11,544 | 11,178 | 160.79 | 11.72 |
| Southeast | MG | belo horizonte | CITY | 416,733.39 | 2,750 | 2,654 | 151.54 | 2.63 |
| Southeast | MG | juiz de fora | CITY | 75,595.07 | 426 | 414 | 177.45 | 0.48 |
| Southeast | ES | All cities | STATE | 324,801.91 | 2,025 | 1,956 | 160.40 | 2.05 |
| Southeast | ES | vitoria | CITY | 62,678.33 | 377 | 364 | 166.26 | 0.40 |
| Southeast | ES | vila velha | CITY | 56,182.64 | 333 | 324 | 168.72 | 0.35 |
| South | All states | All cities | REGION | 2,296,975.80 | 14,042 | 13,599 | 163.58 | 14.50 |
| South | RS | All cities | STATE | 885,826.76 | 5,432 | 5,249 | 163.08 | 5.59 |
| South | RS | porto alegre | CITY | 224,064.09 | 1,372 | 1,320 | 163.31 | 1.41 |
| South | RS | caxias do sul | CITY | 44,321.36 | 224 | 213 | 197.86 | 0.28 |
| South | PR | All cities | STATE | 800,935.44 | 4,998 | 4,840 | 160.25 | 5.06 |
| South | PR | curitiba | CITY | 244,739.87 | 1,510 | 1,455 | 162.08 | 1.54 |
| South | PR | londrina | CITY | 53,105.01 | 303 | 295 | 175.26 | 0.34 |
| South | SC | All cities | STATE | 610,213.60 | 3,612 | 3,513 | 168.94 | 3.85 |
| South | SC | florianopolis | CITY | 99,925.37 | 565 | 543 | 176.86 | 0.63 |
| South | SC | joinville | CITY | 40,972.07 | 263 | 260 | 155.79 | 0.26 |
| Northeast | All states | All cities | REGION | 1,880,799.54 | 9,336 | 9,089 | 201.46 | 11.87 |
| Northeast | BA | All cities | STATE | 611,506.67 | 3,358 | 3,257 | 182.10 | 3.86 |
| Northeast | BA | salvador | CITY | 216,772.40 | 1,238 | 1,202 | 175.10 | 1.37 |
| Northeast | BA | feira de santana | CITY | 32,466.80 | 185 | 176 | 175.50 | 0.20 |
| Northeast | PE | All cities | STATE | 322,237.69 | 1,648 | 1,605 | 195.53 | 2.03 |
| Northeast | PE | recife | CITY | 110,023.52 | 612 | 589 | 179.78 | 0.69 |
| Northeast | PE | jaboatao dos guararapes | CITY | 25,672.86 | 135 | 134 | 190.17 | 0.16 |
| Northeast | CE | All cities | STATE | 275,606.30 | 1,327 | 1,305 | 207.69 | 1.74 |
| Northeast | CE | fortaleza | CITY | 118,646.07 | 650 | 640 | 182.53 | 0.75 |
| Northeast | CE | sobral | CITY | 13,295.73 | 35 | 35 | 379.88 | 0.08 |
| Northeast | MA | All cities | STATE | 151,171.99 | 740 | 719 | 204.29 | 0.95 |
| Northeast | MA | sao luis | CITY | 63,411.79 | 348 | 336 | 182.22 | 0.40 |
| Northeast | MA | imperatriz | CITY | 9,144.78 | 40 | 39 | 228.62 | 0.06 |
| Northeast | PB | All cities | STATE | 140,987.81 | 532 | 516 | 265.01 | 0.89 |
| Northeast | PB | joao pessoa | CITY | 63,070.91 | 254 | 240 | 248.31 | 0.40 |
| Northeast | PB | campina grande | CITY | 22,783.29 | 68 | 68 | 335.05 | 0.14 |
| Northeast | PI | All cities | STATE | 108,132.28 | 493 | 481 | 219.34 | 0.68 |
| Northeast | PI | teresina | CITY | 60,504.35 | 280 | 270 | 216.09 | 0.38 |
| Northeast | PI | parnaiba | CITY | 5,261.51 | 23 | 23 | 228.76 | 0.03 |
| Northeast | RN | All cities | STATE | 101,895.08 | 482 | 471 | 211.40 | 0.64 |
| Northeast | RN | natal | CITY | 42,851.00 | 205 | 201 | 209.03 | 0.27 |
| Northeast | RN | parnamirim | CITY | 9,400.97 | 59 | 57 | 159.34 | 0.06 |
| Northeast | AL | All cities | STATE | 96,229.40 | 411 | 399 | 234.13 | 0.61 |
| Northeast | AL | maceio | CITY | 53,078.08 | 246 | 242 | 215.76 | 0.34 |
| Northeast | AL | arapiraca | CITY | 10,150.03 | 29 | 28 | 350.00 | 0.06 |
| Northeast | SE | All cities | STATE | 73,032.32 | 345 | 338 | 211.69 | 0.46 |
| Northeast | SE | aracaju | CITY | 44,598.80 | 220 | 216 | 202.72 | 0.28 |
| Northeast | SE | itabaiana | CITY | 3,929.66 | 16 | 14 | 245.60 | 0.02 |
| Central-West | All states | All cities | REGION | 1,023,062.00 | 5,744 | 5,563 | 178.11 | 6.46 |
| Central-West | DF | All cities | STATE | 353,229.44 | 2,125 | 2,062 | 166.23 | 2.23 |
| Central-West | DF | brasilia | CITY | 353,135.34 | 2,124 | 2,061 | 166.26 | 2.23 |
| Central-West | DF | brasília | CITY | 94.10 | 1 | 1 | 94.10 | 0.00 |
| Central-West | GO | All cities | STATE | 347,706.93 | 2,007 | 1,942 | 173.25 | 2.19 |
| Central-West | GO | goiania | CITY | 124,060.53 | 687 | 667 | 180.58 | 0.78 |
| Central-West | GO | anapolis | CITY | 20,097.51 | 112 | 109 | 179.44 | 0.13 |
| Central-West | MT | All cities | STATE | 186,168.96 | 903 | 873 | 206.17 | 1.18 |
| Central-West | MT | cuiaba | CITY | 47,104.68 | 248 | 242 | 189.94 | 0.30 |
| Central-West | MT | rondonopolis | CITY | 14,105.63 | 65 | 60 | 217.01 | 0.09 |
| Central-West | MS | All cities | STATE | 135,956.67 | 709 | 688 | 191.76 | 0.86 |
| Central-West | MS | campo grande | CITY | 65,485.25 | 315 | 310 | 207.89 | 0.41 |
| Central-West | MS | dourados | CITY | 10,596.64 | 64 | 59 | 165.57 | 0.07 |
| North | All states | All cities | REGION | 410,392.40 | 1,838 | 1,782 | 223.28 | 2.59 |
| North | PA | All cities | STATE | 217,647.11 | 970 | 944 | 224.38 | 1.37 |
| North | PA | belem | CITY | 95,622.12 | 441 | 430 | 216.83 | 0.60 |
| North | PA | ananindeua | CITY | 21,236.85 | 88 | 85 | 241.33 | 0.13 |
| North | TO | All cities | STATE | 61,354.42 | 279 | 272 | 219.91 | 0.39 |
| North | TO | palmas | CITY | 21,790.37 | 90 | 89 | 242.12 | 0.14 |
| North | TO | araguaina | CITY | 9,848.63 | 41 | 40 | 240.21 | 0.06 |
| North | RO | All cities | STATE | 57,558.02 | 247 | 235 | 233.03 | 0.36 |
| North | RO | porto velho | CITY | 26,121.92 | 109 | 101 | 239.65 | 0.16 |
| North | RO | ariquemes | CITY | 4,969.64 | 13 | 12 | 382.28 | 0.03 |
| North | AM | All cities | STATE | 27,835.73 | 147 | 142 | 189.36 | 0.18 |
| North | AM | manaus | CITY | 25,793.06 | 139 | 134 | 185.56 | 0.16 |
| North | AM | coari | CITY | 1,259.04 | 1 | 1 | 1,259.04 | 0.01 |
| North | AC | All cities | STATE | 19,669.70 | 81 | 77 | 242.84 | 0.12 |
| North | AC | rio branco | CITY | 16,917.55 | 70 | 66 | 241.68 | 0.11 |
| North | AC | cruzeiro do sul | CITY | 1,127.06 | 3 | 3 | 375.69 | 0.01 |
| North | AP | All cities | STATE | 16,262.80 | 68 | 67 | 239.16 | 0.10 |
| North | AP | macapa | CITY | 13,666.03 | 54 | 53 | 253.07 | 0.09 |
| North | AP | santana | CITY | 1,543.94 | 9 | 9 | 171.55 | 0.01 |
| North | RR | All cities | STATE | 10,064.62 | 46 | 45 | 218.80 | 0.06 |
| North | RR | boa vista | CITY | 9,892.93 | 45 | 44 | 219.84 | 0.06 |
| North | RR | bonfim | CITY | 171.69 | 1 | 1 | 171.69 | 0.00 |

### (b) Best-selling regions, compact

`q05_geography_rollup_b.csv` -- 5 row(s), 274 ms

<details><summary>SQL</summary>

```sql
-- (b) Best-selling regions, compact ------------------------------------
SELECT customer_region                                                  AS region,
       ROUND(SUM(revenue), 2)                                           AS revenue,
       COUNT(DISTINCT order_id)                                         AS orders,
       COUNT(DISTINCT customer_unique_id)                               AS customers,
       COUNT(DISTINCT customer_state)                                   AS states,
       COUNT(DISTINCT customer_city)                                    AS cities,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)                AS avg_order_value,
       ROUND(SUM(freight_value) / SUM(revenue) * 100, 2)                AS freight_pct_of_revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)       AS pct_of_total
FROM v_sales
GROUP BY customer_region
ORDER BY revenue DESC
```

</details>

| region | revenue | orders | customers | states | cities | avg_order_value | freight_pct_of_revenue | pct_of_total |
|---|---|---|---|---|---|---|---|---|
| Southeast | 10,232,323.50 | 67,706 | 65,410 | 4 | 1,589 | 151.13 | 13.14 | 64.58 |
| South | 2,296,975.80 | 14,042 | 13,599 | 3 | 966 | 163.58 | 14.93 | 14.50 |
| Northeast | 1,880,799.54 | 9,336 | 9,089 | 9 | 1,117 | 201.46 | 17.83 | 11.87 |
| Central-West | 1,023,062.00 | 5,744 | 5,563 | 4 | 345 | 178.11 | 14.92 | 6.46 |
| North | 410,392.40 | 1,838 | 1,782 | 7 | 201 | 223.28 | 18.53 | 2.59 |

### (c) Best-selling states

`q05_geography_rollup_c.csv` -- 15 row(s), 159 ms

<details><summary>SQL</summary>

```sql
-- (c) Best-selling states ---------------------------------------------
SELECT customer_region                                                  AS region,
       customer_state                                                   AS state,
       ANY_VALUE(customer_state_name)                                   AS state_name,
       ROUND(SUM(revenue), 2)                                           AS revenue,
       COUNT(DISTINCT order_id)                                         AS orders,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id), 2)                AS avg_order_value,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)       AS pct_of_total
FROM v_sales
GROUP BY customer_region, customer_state
ORDER BY revenue DESC
LIMIT 15
```

</details>

| region | state | state_name | revenue | orders | avg_order_value | pct_of_total |
|---|---|---|---|---|---|---|
| Southeast | SP | Sao Paulo | 5,921,678.12 | 41,375 | 143.12 | 37.38 |
| Southeast | RJ | Rio de Janeiro | 2,129,681.98 | 12,762 | 166.88 | 13.44 |
| Southeast | MG | Minas Gerais | 1,856,161.49 | 11,544 | 160.79 | 11.72 |
| South | RS | Rio Grande do Sul | 885,826.76 | 5,432 | 163.08 | 5.59 |
| South | PR | Parana | 800,935.44 | 4,998 | 160.25 | 5.06 |
| Northeast | BA | Bahia | 611,506.67 | 3,358 | 182.10 | 3.86 |
| South | SC | Santa Catarina | 610,213.60 | 3,612 | 168.94 | 3.85 |
| Central-West | DF | Distrito Federal | 353,229.44 | 2,125 | 166.23 | 2.23 |
| Central-West | GO | Goias | 347,706.93 | 2,007 | 173.25 | 2.19 |
| Southeast | ES | Espirito Santo | 324,801.91 | 2,025 | 160.40 | 2.05 |
| Northeast | PE | Pernambuco | 322,237.69 | 1,648 | 195.53 | 2.03 |
| Northeast | CE | Ceara | 275,606.30 | 1,327 | 207.69 | 1.74 |
| North | PA | Para | 217,647.11 | 970 | 224.38 | 1.37 |
| Central-West | MT | Mato Grosso | 186,168.96 | 903 | 206.17 | 1.18 |
| Northeast | MA | Maranhao | 151,171.99 | 740 | 204.29 | 0.95 |

## Q06 -- top customers

> Q6. Top 5 CUSTOMERS by total purchase amount.
> Note on the grain of "customer": in this dataset customer_id is
> issued per ORDER, while customer_unique_id identifies the actual
> person.  (a) answers the question at the person level, which is
> what "customer" normally means; (b) repeats it at customer_id
> level so the two readings can be compared.

### Q6. Top 5 CUSTOMERS by total purchase amount.

`q06_top_customers_a.csv` -- 5 row(s), 379 ms

<details><summary>SQL</summary>

```sql
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
LIMIT 5
```

</details>

| customer_unique_id | city | state | region | orders | items | product_spend | freight_spend | total_purchase_amount |
|---|---|---|---|---|---|---|---|---|
| 0a0a92112bd4c708ca5fde585afaa872 | rio de janeiro | RJ | Southeast | 1 | 8 | 13,440.00 | 224.08 | 13,664.08 |
| da122df9eeddfedc1dc1f5349a1a690c | araruama | RJ | Southeast | 2 | 2 | 7,388.00 | 183.63 | 7,571.63 |
| 763c8b1c9c68a0229c42c9fc6f662b93 | vila velha | ES | Southeast | 1 | 4 | 7,160.00 | 114.88 | 7,274.88 |
| dc4802a71eae9be1dd28f5d788ceb526 | campo grande | MS | Central-West | 1 | 1 | 6,735.00 | 194.31 | 6,929.31 |
| 459bef486812aa25204be022145caa62 | vitoria | ES | Southeast | 1 | 1 | 6,729.00 | 193.21 | 6,922.21 |

### (b) Top 5 single orders' customers (customer_id)

`q06_top_customers_b.csv` -- 5 row(s), 168 ms

<details><summary>SQL</summary>

```sql
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
LIMIT 5
```

</details>

| customer_id | customer_unique_id | city | state | items | total_purchase_amount |
|---|---|---|---|---|---|
| 1617b1357756262bfa56ab541c47bc16 | 0a0a92112bd4c708ca5fde585afaa872 | rio de janeiro | RJ | 8 | 13,664.08 |
| ec5b2ba62e574342386871631fafd3fc | 763c8b1c9c68a0229c42c9fc6f662b93 | vila velha | ES | 4 | 7,274.88 |
| c6e2731c5b391845f6800c97401a43a9 | dc4802a71eae9be1dd28f5d788ceb526 | campo grande | MS | 1 | 6,929.31 |
| f48d464a0baaea338cb25f816991ab1f | 459bef486812aa25204be022145caa62 | vitoria | ES | 1 | 6,922.21 |
| 3fd6777bbce08a352fddd04e4a7cc8f6 | ff4159b92c40ebe40454e3e6a7c35ed6 | marilia | SP | 1 | 6,726.66 |

### (c) How repeat-buying behaves overall (context for the top 5)

`q06_top_customers_c.csv` -- 4 row(s), 174 ms

<details><summary>SQL</summary>

```sql
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
ORDER BY customers DESC
```

</details>

| orders_placed | customers | revenue | pct_of_revenue | avg_spend_per_customer |
|---|---|---|---|---|
| 1 order | 92,507 | 14,939,106.99 | 94.29 | 161.49 |
| 2 orders | 2,673 | 784,037.99 | 4.95 | 293.32 |
| 3-5 orders | 230 | 112,037.43 | 0.71 | 487.12 |
| 6+ orders | 10 | 8,370.83 | 0.05 | 837.08 |

## Q07 -- top seller per state

> Q7. Which SELLERS generate the highest revenue IN THEIR STATE?
> Uses the *seller* leg of the shared geography hierarchy, showing
> that dim_customer and dim_seller really do roll up through the
> same dim_zip -> dim_city -> dim_state -> dim_region chain.

### Q7. Which SELLERS generate the highest revenue IN THEIR STATE?

`q07_top_seller_per_state_a.csv` -- 22 row(s), 126 ms

<details><summary>SQL</summary>

```sql
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
ORDER BY revenue DESC
```

</details>

| state | state_name | region | seller_id | seller_city | lead_origin | revenue | orders | items | pct_of_state_revenue | sellers_in_state |
|---|---|---|---|---|---|---|---|---|---|---|
| SP | Sao Paulo | Southeast | 4869f7a5dfa277a7dca6462dcf3b52b2 | guariba | not_via_funnel | 249,640.70 | 1,132 | 1,156 | 2.50 | 1,816 |
| BA | Bahia | Northeast | 53243585a1d6dc2643021fd1853d8905 | lauro de freitas | not_via_funnel | 235,856.68 | 358 | 410 | 76.90 | 20 |
| RJ | Rio de Janeiro | Southeast | 46dc3b2cc0980fb8ec44634e21d2718e | rio de janeiro | not_via_funnel | 139,909.69 | 521 | 542 | 14.70 | 176 |
| MG | Minas Gerais | Southeast | a1043bafd471dff536d0c462352beb48 | ilicinea | not_via_funnel | 133,745.25 | 718 | 770 | 10.70 | 250 |
| PR | Parana | South | ccc4bbb5f32a6ab2b7066a4130f114e3 | curitiba | not_via_funnel | 79,261.60 | 187 | 192 | 5.40 | 360 |
| PE | Pernambuco | Northeast | de722cd6dad950a92b7d4f82673f8833 | recife | not_via_funnel | 65,112.75 | 339 | 379 | 62.70 | 9 |
| SC | Santa Catarina | South | 04308b1ee57b6625f47df1d56f00eedf | bombinhas | not_via_funnel | 63,184.99 | 94 | 94 | 8.40 | 197 |
| MA | Maranhao | Northeast | 06a2c3af7b3aee5d69171b0e14f0ee87 | sao luis | not_via_funnel | 48,550.24 | 392 | 405 | 100.00 | 1 |
| RS | Rio Grande do Sul | South | 87142160b41353c4e5fca2360caf6f92 | porto alegre | not_via_funnel | 38,314.31 | 305 | 339 | 8.80 | 132 |
| ES | Espirito Santo | Southeast | 001cca7ae9ae17fb1caed9dfb1094831 | cariacica | not_via_funnel | 33,934.17 | 200 | 239 | 56.60 | 24 |
| DF | Distrito Federal | Central-West | 44073f8b7e41514de3b7815dd0237f4f | brasilia | not_via_funnel | 21,901.93 | 144 | 153 | 18.80 | 31 |
| PB | Paraiba | Northeast | a6bd7d1ccdac48c6b33b28596b7eb122 | mamanguape | not_via_funnel | 15,046.63 | 16 | 16 | 81.00 | 6 |
| GO | Goias | Central-West | 9d5a9018aee56acb367ba9c3f05d1d6a | aparecida de goiania | not_via_funnel | 11,982.21 | 67 | 79 | 15.20 | 40 |
| MT | Mato Grosso | Central-West | 2dee2ce60de9709b1a24083217181a1f | sinop | not_via_funnel | 9,844.56 | 54 | 55 | 45.40 | 4 |
| CE | Ceara | Northeast | bbf9ad41dca6603e614efcdad7aab8c4 | fortaleza | not_via_funnel | 8,622.26 | 14 | 14 | 35.00 | 13 |
| RN | Rio Grande do Norte | Northeast | 02d35243ea2e497335cd0f076b45675d | natal | not_via_funnel | 6,399.95 | 14 | 16 | 57.10 | 4 |
| MS | Mato Grosso do Sul | Central-West | b1fecf4da1fa2689bccffa0121953643 | campo grande | not_via_funnel | 4,066.72 | 19 | 20 | 41.70 | 5 |
| RO | Rondonia | North | 3364a91ec4d56c98e44174de954b94f6 | porto velho | not_via_funnel | 3,853.85 | 6 | 6 | 70.40 | 2 |
| PI | Piaui | Northeast | 47efca563408aae19bb7206c2d969ea9 | teresina | not_via_funnel | 2,965.32 | 12 | 12 | 100.00 | 1 |
| AM | Amazonas | North | 327b89b872c14d1c0be7235ef4871685 | manaus | not_via_funnel | 1,258.80 | 3 | 3 | 100.00 | 1 |
| SE | Sergipe | Northeast | 4b39558c138930b9e5489c93b6df5fe3 | aracaju | not_via_funnel | 1,229.10 | 4 | 5 | 63.90 | 2 |
| AC | Acre | North | 4be2e7f96b4fd749d52dff41f80e39dd | rio branco | not_via_funnel | 299.84 | 1 | 1 | 100.00 | 1 |

### (b) Top 3 per state for the five largest seller states

`q07_top_seller_per_state_b.csv` -- 15 row(s), 158 ms

<details><summary>SQL</summary>

```sql
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
ORDER BY t.state_rank, rank_in_state
```

</details>

| state_rank | state | state_revenue | rank_in_state | seller_id | seller_city | seller_revenue | orders |
|---|---|---|---|---|---|---|---|
| 1 | SP | 10,165,126.21 | 1 | 4869f7a5dfa277a7dca6462dcf3b52b2 | guariba | 249,640.70 | 1,132 |
| 1 | SP | 10,165,126.21 | 2 | 7c67e1448b00f6e969d365cea6b010ab | itaquaquecetuba | 239,536.44 | 982 |
| 1 | SP | 10,165,126.21 | 3 | 4a3ca9315b744ce9f8e9374361493884 | ibitinga | 235,539.96 | 1,806 |
| 2 | PR | 1,473,612.42 | 1 | ccc4bbb5f32a6ab2b7066a4130f114e3 | curitiba | 79,261.60 | 187 |
| 2 | PR | 1,473,612.42 | 2 | 522620dcb18a6b31cd7bdf73665113a9 | cascavel | 61,829.81 | 174 |
| 2 | PR | 1,473,612.42 | 3 | 77530e9772f57a62c906e1c21538ab82 | curitiba | 55,063.99 | 320 |
| 3 | MG | 1,250,040.78 | 1 | a1043bafd471dff536d0c462352beb48 | ilicinea | 133,745.25 | 718 |
| 3 | MG | 1,250,040.78 | 2 | 25c5c91f63607446a97b143d2d535d31 | itauna | 61,679.33 | 158 |
| 3 | MG | 1,250,040.78 | 3 | dbc22125167c298ef99da25668e1011f | borda da mata | 41,789.16 | 406 |
| 4 | RJ | 953,657.89 | 1 | 46dc3b2cc0980fb8ec44634e21d2718e | rio de janeiro | 139,909.69 | 521 |
| 4 | RJ | 953,657.89 | 2 | 620c87c171fb2a6dd6e8bb4dec959fc6 | petropolis | 128,909.71 | 740 |
| 4 | RJ | 953,657.89 | 3 | edb1ef5e36e0c8cd84eb3c9b003e486d | teresopolis | 83,189.65 | 166 |
| 5 | SC | 751,687.64 | 1 | 04308b1ee57b6625f47df1d56f00eedf | bombinhas | 63,184.99 | 94 |
| 5 | SC | 751,687.64 | 2 | eeb6de78f79159600292e314a77cbd18 | lages | 46,795.28 | 83 |
| 5 | SC | 751,687.64 | 3 | 712e6ed8aa4aa1fa65dab41fed5737e4 | videira | 46,704.13 | 79 |

## Q08 -- cube region category year

> Q8. CUBE over (REGION, CATEGORY, YEAR).
> CUBE returns all 2^3 = 8 grouping combinations in one pass:
> (R,C,Y) (R,C) (R,Y) (C,Y) (R) (C) (Y) ()
> GROUPING_ID() encodes which combination each row belongs to, so the
> whole lattice lives in a single result set and can be sliced
> afterwards without touching the fact table again.  That is exactly
> the property a materialised cube buys you, so we materialise it
> once here and then read three different slices off it.

### Q8. CUBE over (REGION, CATEGORY, YEAR).

`q08_cube_region_category_year_a.csv` -- 1 row(s), 636 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q8. CUBE over (REGION, CATEGORY, YEAR).
--     CUBE returns all 2^3 = 8 grouping combinations in one pass:
--       (R,C,Y) (R,C) (R,Y) (C,Y) (R) (C) (Y) ()
--     GROUPING_ID() encodes which combination each row belongs to, so the
--     whole lattice lives in a single result set and can be sliced
--     afterwards without touching the fact table again.  That is exactly
--     the property a materialised cube buys you, so we materialise it
--     once here and then read three different slices off it.
-- =====================================================================

CREATE OR REPLACE TEMP TABLE cube_rcy AS
SELECT CASE WHEN GROUPING(customer_region) = 1 THEN 'ALL'
            ELSE customer_region END                                AS region,
       CASE WHEN GROUPING(category) = 1 THEN 'ALL'
            ELSE category END                                       AS category,
       CASE WHEN GROUPING(purchase_year) = 1 THEN 'ALL'
            ELSE CAST(purchase_year AS VARCHAR) END                 AS year,
       GROUPING_ID(customer_region, category, purchase_year)         AS grouping_id,
       GROUPING(customer_region)                                     AS g_region,
       GROUPING(category)                                            AS g_category,
       GROUPING(purchase_year)                                       AS g_year,
       ROUND(SUM(revenue), 2)                                        AS revenue,
       COUNT(DISTINCT order_id)                                      AS orders,
       COUNT(*)                                                      AS line_items,
       ROUND(AVG(price), 2)                                          AS avg_unit_price
FROM v_sales
GROUP BY CUBE (customer_region, category, purchase_year)
```

</details>

| Count |
|---|
| 1,342 |

### (a) The complete cube, one row per cell

`q08_cube_region_category_year_b.csv` -- 1,342 row(s), 6 ms

<details><summary>SQL</summary>

```sql
-- (a) The complete cube, one row per cell ------------------------------
SELECT grouping_id,
       CASE grouping_id
            WHEN 0 THEN '(Region, Category, Year)'
            WHEN 1 THEN '(Region, Category)'
            WHEN 2 THEN '(Region, Year)'
            WHEN 3 THEN '(Region)'
            WHEN 4 THEN '(Category, Year)'
            WHEN 5 THEN '(Category)'
            WHEN 6 THEN '(Year)'
            ELSE        '()  grand total' END AS grouping_set,
       region, category, year,
       revenue, orders, line_items, avg_unit_price
FROM cube_rcy
ORDER BY grouping_id, revenue DESC
```

</details>

| grouping_id | grouping_set | region | category | year | revenue | orders | line_items | avg_unit_price |
|---|---|---|---|---|---|---|---|---|
| 0 | (Region, Category, Year) | Southeast | health_beauty | 2018 | 562,843.75 | 3,752 | 4,165 | 119.46 |
| 0 | (Region, Category, Year) | Southeast | bed_bath_table | 2018 | 494,305.41 | 3,807 | 4,568 | 90.62 |
| 0 | (Region, Category, Year) | Southeast | watches_gifts | 2018 | 485,125.95 | 2,304 | 2,433 | 185.55 |
| 0 | (Region, Category, Year) | Southeast | bed_bath_table | 2017 | 426,466.21 | 3,327 | 3,864 | 94.31 |
| 0 | (Region, Category, Year) | Southeast | computers_accessories | 2018 | 403,449.95 | 2,837 | 3,307 | 104.98 |
| 0 | (Region, Category, Year) | Southeast | sports_leisure | 2018 | 402,516.44 | 2,829 | 3,123 | 111.88 |
| 0 | (Region, Category, Year) | Southeast | watches_gifts | 2017 | 341,471.73 | 1,401 | 1,508 | 212.27 |
| 0 | (Region, Category, Year) | Southeast | housewares | 2018 | 340,842.73 | 2,523 | 2,957 | 95.04 |
| 0 | (Region, Category, Year) | Southeast | sports_leisure | 2017 | 339,435.79 | 2,407 | 2,716 | 107.78 |
| 0 | (Region, Category, Year) | Southeast | health_beauty | 2017 | 320,092.55 | 2,148 | 2,323 | 122.52 |
| 0 | (Region, Category, Year) | Southeast | furniture_decor | 2018 | 301,693.20 | 2,144 | 2,777 | 89.55 |
| 0 | (Region, Category, Year) | Southeast | computers_accessories | 2017 | 281,493.37 | 1,707 | 2,004 | 124.23 |
| 0 | (Region, Category, Year) | Southeast | furniture_decor | 2017 | 276,389.80 | 2,249 | 2,899 | 77.85 |
| 0 | (Region, Category, Year) | Southeast | cool_stuff | 2017 | 264,162.68 | 1,390 | 1,451 | 162.99 |
| 0 | (Region, Category, Year) | Southeast | auto | 2018 | 241,426.86 | 1,638 | 1,740 | 121.29 |
| 0 | (Region, Category, Year) | Southeast | toys | 2017 | 236,381.36 | 1,695 | 1,809 | 114.54 |
| 0 | (Region, Category, Year) | Southeast | housewares | 2017 | 197,783.74 | 1,803 | 2,126 | 75.96 |
| 0 | (Region, Category, Year) | Southeast | garden_tools | 2017 | 191,218.47 | 1,318 | 1,609 | 98.85 |
| 0 | (Region, Category, Year) | Southeast | baby | 2018 | 185,962.97 | 1,125 | 1,202 | 134.42 |
| 0 | (Region, Category, Year) | Southeast | auto | 2017 | 172,905.32 | 937 | 1,043 | 147.29 |
| 0 | (Region, Category, Year) | Southeast | perfumery | 2017 | 164,576.28 | 1,123 | 1,197 | 123.64 |
| 0 | (Region, Category, Year) | Southeast | garden_tools | 2018 | 164,514.43 | 1,068 | 1,314 | 104.87 |
| 0 | (Region, Category, Year) | Southeast | cool_stuff | 2018 | 161,660.81 | 918 | 955 | 150.43 |
| 0 | (Region, Category, Year) | Southeast | perfumery | 2018 | 140,464.00 | 1,074 | 1,182 | 105.12 |
| 0 | (Region, Category, Year) | Southeast | toys | 2018 | 136,593.27 | 1,002 | 1,059 | 112.14 |
| 0 | (Region, Category, Year) | Northeast | health_beauty | 2018 | 133,825.41 | 612 | 647 | 175.26 |
| 0 | (Region, Category, Year) | Southeast | telephony | 2018 | 122,328.40 | 1,296 | 1,395 | 75.21 |
| 0 | (Region, Category, Year) | Southeast | office_furniture | 2018 | 121,690.07 | 463 | 611 | 162.94 |
| 0 | (Region, Category, Year) | Northeast | watches_gifts | 2018 | 118,713.79 | 478 | 507 | 206.03 |
| 0 | (Region, Category, Year) | Southeast | pet_shop | 2018 | 113,817.75 | 762 | 873 | 111.30 |
| 0 | (Region, Category, Year) | Southeast | stationery | 2018 | 108,968.49 | 969 | 1,060 | 86.86 |
| 0 | (Region, Category, Year) | Southeast | baby | 2017 | 107,258.59 | 801 | 855 | 107.81 |
| 0 | (Region, Category, Year) | Southeast | office_furniture | 2017 | 105,598.90 | 417 | 549 | 159.52 |
| 0 | (Region, Category, Year) | Northeast | health_beauty | 2017 | 102,586.52 | 466 | 488 | 177.17 |
| 0 | (Region, Category, Year) | Southeast | construction_tools_construction | 2018 | 101,758.57 | 479 | 593 | 152.56 |
| 0 | (Region, Category, Year) | Southeast | telephony | 2017 | 98,462.23 | 1,189 | 1,280 | 63.89 |
| 0 | (Region, Category, Year) | South | sports_leisure | 2018 | 95,877.31 | 588 | 682 | 119.82 |
| 0 | (Region, Category, Year) | South | health_beauty | 2018 | 95,493.26 | 600 | 665 | 122.21 |
| 0 | (Region, Category, Year) | South | furniture_decor | 2018 | 93,619.13 | 592 | 748 | 101.74 |
| 0 | (Region, Category, Year) | South | watches_gifts | 2018 | 89,738.79 | 398 | 439 | 187.24 |
| 0 | (Region, Category, Year) | South | sports_leisure | 2017 | 86,541.48 | 570 | 636 | 117.23 |
| 0 | (Region, Category, Year) | South | bed_bath_table | 2018 | 86,106.06 | 605 | 715 | 98.54 |
| 0 | (Region, Category, Year) | South | computers_accessories | 2018 | 85,430.97 | 571 | 681 | 105.70 |
| 0 | (Region, Category, Year) | Southeast | electronics | 2018 | 83,803.16 | 1,137 | 1,225 | 53.71 |
| 0 | (Region, Category, Year) | Southeast | computers | 2017 | 80,013.53 | 60 | 62 | 1,244.92 |
| 0 | (Region, Category, Year) | South | bed_bath_table | 2017 | 79,133.06 | 607 | 692 | 95.87 |
| 0 | (Region, Category, Year) | South | housewares | 2018 | 77,878.62 | 495 | 594 | 106.38 |
| 0 | (Region, Category, Year) | Southeast | unknown | 2017 | 77,733.26 | 587 | 647 | 105.02 |
| 0 | (Region, Category, Year) | South | cool_stuff | 2017 | 77,344.52 | 379 | 396 | 174.22 |
| 0 | (Region, Category, Year) | Southeast | stationery | 2017 | 73,300.43 | 608 | 658 | 94.94 |
| 0 | (Region, Category, Year) | South | furniture_decor | 2017 | 72,988.32 | 513 | 672 | 86.85 |
| 0 | (Region, Category, Year) | South | health_beauty | 2017 | 72,681.78 | 453 | 493 | 129.70 |
| 0 | (Region, Category, Year) | South | computers_accessories | 2017 | 71,636.18 | 421 | 510 | 122.39 |
| 0 | (Region, Category, Year) | Southeast | musical_instruments | 2018 | 70,872.85 | 247 | 264 | 244.75 |
| 0 | (Region, Category, Year) | Southeast | small_appliances | 2017 | 68,585.43 | 206 | 216 | 296.00 |
| 0 | (Region, Category, Year) | Southeast | consoles_games | 2017 | 67,689.40 | 468 | 504 | 119.96 |
| 0 | (Region, Category, Year) | Northeast | watches_gifts | 2017 | 66,624.99 | 260 | 276 | 216.96 |
| 0 | (Region, Category, Year) | Central-West | health_beauty | 2018 | 64,021.50 | 336 | 357 | 155.70 |
| 0 | (Region, Category, Year) | South | watches_gifts | 2017 | 64,014.72 | 267 | 286 | 207.48 |
| 0 | (Region, Category, Year) | Northeast | auto | 2018 | 63,455.31 | 263 | 276 | 192.23 |

*(1,282 further rows omitted)*

### (b) How many cells does each of the 8 grouping sets contribute?

`q08_cube_region_category_year_c.csv` -- 8 row(s), 4 ms

<details><summary>SQL</summary>

```sql
-- (b) How many cells does each of the 8 grouping sets contribute? -------
SELECT grouping_id,
       CASE grouping_id
            WHEN 0 THEN '(Region, Category, Year)'
            WHEN 1 THEN '(Region, Category)'
            WHEN 2 THEN '(Region, Year)'
            WHEN 3 THEN '(Region)'
            WHEN 4 THEN '(Category, Year)'
            WHEN 5 THEN '(Category)'
            WHEN 6 THEN '(Year)'
            ELSE        '()  grand total' END AS grouping_set,
       COUNT(*)                              AS cells,
       ROUND(SUM(revenue), 2)                AS revenue_in_slice
FROM cube_rcy
GROUP BY grouping_id
ORDER BY grouping_id
```

</details>

| grouping_id | grouping_set | cells | revenue_in_slice |
|---|---|---|---|
| 0 | (Region, Category, Year) | 718 | 15,843,553.24 |
| 1 | (Region, Category) | 348 | 15,843,553.24 |
| 2 | (Region, Year) | 15 | 15,843,553.24 |
| 3 | (Region) | 5 | 15,843,553.24 |
| 4 | (Category, Year) | 178 | 15,843,553.24 |
| 5 | (Category) | 74 | 15,843,553.24 |
| 6 | (Year) | 3 | 15,843,553.24 |
| 7 | ()  grand total | 1 | 15,843,553.24 |

### (c) Slice: the 2-D (Region x Year) face, plus its margins

`q08_cube_region_category_year_d.csv` -- 24 row(s), 6 ms

<details><summary>SQL</summary>

```sql
-- (c) Slice: the 2-D (Region x Year) face, plus its margins -------------
SELECT region, year, revenue, orders
FROM cube_rcy
WHERE grouping_id IN (2, 3, 6, 7)         -- (R,Y) (R) (Y) ()
ORDER BY CASE WHEN region = 'ALL' THEN 1 ELSE 0 END, revenue DESC, year
```

</details>

| region | year | revenue | orders |
|---|---|---|---|
| Southeast | ALL | 10,232,323.50 | 67,706 |
| Southeast | 2018 | 5,651,146.99 | 37,504 |
| Southeast | 2017 | 4,545,511.42 | 29,999 |
| South | ALL | 2,296,975.80 | 14,042 |
| Northeast | ALL | 1,880,799.54 | 9,336 |
| South | 2018 | 1,249,241.25 | 7,414 |
| South | 2017 | 1,037,872.63 | 6,574 |
| Central-West | ALL | 1,023,062.00 | 5,744 |
| Northeast | 2018 | 988,901.04 | 4,813 |
| Northeast | 2017 | 884,588.05 | 4,490 |
| Central-West | 2018 | 549,986.88 | 3,158 |
| Central-West | 2017 | 470,217.71 | 2,570 |
| North | ALL | 410,392.40 | 1,838 |
| North | 2017 | 204,482.62 | 946 |
| North | 2018 | 204,421.44 | 886 |
| Southeast | 2016 | 35,665.09 | 203 |
| South | 2016 | 9,861.92 | 54 |
| Northeast | 2016 | 7,310.45 | 33 |
| Central-West | 2016 | 2,857.41 | 16 |
| North | 2016 | 1,488.34 | 6 |
| ALL | ALL | 15,843,553.24 | 98,666 |
| ALL | 2018 | 8,643,697.60 | 53,775 |
| ALL | 2017 | 7,142,672.43 | 44,579 |
| ALL | 2016 | 57,183.21 | 312 |

### (d) Slice: top 3 categories inside each region, all years pooled

`q08_cube_region_category_year_e.csv` -- 15 row(s), 15 ms

<details><summary>SQL</summary>

```sql
-- (d) Slice: top 3 categories inside each region, all years pooled -----
WITH rc AS (
    SELECT region, category, revenue, orders
    FROM cube_rcy
    WHERE grouping_id = 1                 -- (Region, Category)
      AND region <> 'ALL'
),
r_tot AS (
    SELECT region, revenue AS region_revenue
    FROM cube_rcy
    WHERE grouping_id = 3                 -- (Region)
      AND region <> 'ALL'
)
SELECT rc.region,
       ROUND(rt.region_revenue, 2)                                  AS region_revenue,
       ROW_NUMBER() OVER (PARTITION BY rc.region ORDER BY rc.revenue DESC) AS rank_in_region,
       rc.category,
       rc.revenue,
       rc.orders,
       ROUND(100.0 * rc.revenue / rt.region_revenue, 1)             AS pct_of_region
FROM rc
JOIN r_tot rt USING (region)
QUALIFY rank_in_region <= 3
ORDER BY rt.region_revenue DESC, rank_in_region
```

</details>

| region | region_revenue | rank_in_region | category | revenue | orders | pct_of_region |
|---|---|---|---|---|---|---|
| Southeast | 10,232,323.50 | 1 | bed_bath_table | 921,076.09 | 7,137 | 9.00 |
| Southeast | 10,232,323.50 | 2 | health_beauty | 886,750.28 | 5,927 | 8.70 |
| Southeast | 10,232,323.50 | 3 | watches_gifts | 828,720.08 | 3,708 | 8.10 |
| South | 2,296,975.80 | 1 | sports_leisure | 182,769.64 | 1,164 | 8.00 |
| South | 2,296,975.80 | 2 | health_beauty | 169,174.89 | 1,064 | 7.40 |
| South | 2,296,975.80 | 3 | furniture_decor | 169,076.81 | 1,117 | 7.40 |
| Northeast | 1,880,799.54 | 1 | health_beauty | 236,942.00 | 1,082 | 12.60 |
| Northeast | 1,880,799.54 | 2 | watches_gifts | 186,013.11 | 739 | 9.90 |
| Northeast | 1,880,799.54 | 3 | sports_leisure | 123,735.56 | 686 | 6.60 |
| Central-West | 1,023,062.00 | 1 | health_beauty | 98,513.81 | 573 | 9.60 |
| Central-West | 1,023,062.00 | 2 | watches_gifts | 94,914.18 | 374 | 9.30 |
| Central-West | 1,023,062.00 | 3 | sports_leisure | 72,812.13 | 476 | 7.10 |
| North | 410,392.40 | 1 | health_beauty | 49,867.09 | 190 | 12.20 |
| North | 410,392.40 | 2 | watches_gifts | 42,140.73 | 138 | 10.30 |
| North | 410,392.40 | 3 | sports_leisure | 32,936.59 | 149 | 8.00 |

## Q09 -- review vs delivery

> Q9. Average REVIEW SCORE for orders delivered EARLY / ON TIME / LATE.
> Computed at ORDER grain (v_orders), not line-item grain: a 1-star
> order containing six items must count once, not six times.
> GROUPING SETS gives the coarse 3-way answer and the finer bucket
> breakdown (including "more than a week late") in a single pass.

### Q9. Average REVIEW SCORE for orders delivered EARLY / ON TIME / LATE.

`q09_review_vs_delivery_a.csv` -- 11 row(s), 161 ms

<details><summary>SQL</summary>

```sql
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
         MIN(delivery_delay_days)
```

</details>

| delivery_status | delivery_bucket | orders | reviewed_orders | pct_reviewed | avg_review_score | pct_negative_1_2 | pct_positive_4_5 | avg_delay_days | avg_days_to_deliver |
|---|---|---|---|---|---|---|---|---|---|
| ALL ORDERS | All buckets | 98,666 | 97,917 | 99.20 | 4.11 | 14.20 | 77.60 | -11.88 | 12.50 |
| Early | All buckets | 88,649 | 88,168 | 99.50 | 4.29 | 9.20 | 82.80 | -13.71 | 10.82 |
| Early | Early (> 7 days) | 71,308 | 70,934 | 99.50 | 4.32 | 9.00 | 83.50 | -15.86 | 10.16 |
| Early | Early (1-7 days) | 17,341 | 17,234 | 99.40 | 4.20 | 10.20 | 79.90 | -4.85 | 13.55 |
| On Time | All buckets | 1,292 | 1,280 | 99.10 | 4.03 | 12.40 | 73.70 | 0.00 | 19.17 |
| On Time | On Time (same day) | 1,292 | 1,280 | 99.10 | 4.03 | 12.40 | 73.70 | 0.00 | 19.17 |
| Late | All buckets | 6,535 | 6,382 | 97.70 | 2.27 | 62.40 | 26.70 | 10.62 | 33.91 |
| Late | Late (1-7 days) | 3,672 | 3,600 | 98.00 | 2.71 | 49.40 | 38.30 | 3.64 | 25.69 |
| Late | Late (> 7 days) | 2,863 | 2,782 | 97.20 | 1.70 | 79.30 | 11.70 | 19.58 | 44.46 |
| Not Delivered | All buckets | 2,190 | 2,087 | 95.30 | 1.76 | 77.50 | 14.70 | *(ALL)* | *(ALL)* |
| Not Delivered | Not Delivered | 2,190 | 2,087 | 95.30 | 1.76 | 77.50 | 14.70 | *(ALL)* | *(ALL)* |

### (b) Just the headline three-way comparison the question asks for

`q09_review_vs_delivery_b.csv` -- 3 row(s), 129 ms

<details><summary>SQL</summary>

```sql
-- (b) Just the headline three-way comparison the question asks for -----
SELECT delivery_status,
       COUNT(*)                                     AS orders,
       COUNT(review_score)                          AS reviewed_orders,
       ROUND(AVG(review_score), 3)                  AS avg_review_score,
       ROUND(AVG(delivery_delay_days), 2)           AS avg_delay_days
FROM v_orders
WHERE delivery_status IN ('Early', 'On Time', 'Late')
GROUP BY delivery_status
ORDER BY MIN(delivery_status_order)
```

</details>

| delivery_status | orders | reviewed_orders | avg_review_score | avg_delay_days |
|---|---|---|---|---|
| Early | 88,649 | 88,168 | 4.29 | -13.71 |
| On Time | 1,292 | 1,280 | 4.03 | 0.00 |
| Late | 6,535 | 6,382 | 2.27 | 10.62 |

### (c) The dose-response curve: lateness in days vs average score

`q09_review_vs_delivery_c.csv` -- 10 row(s), 111 ms

<details><summary>SQL</summary>

```sql
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
ORDER BY MIN(COALESCE(delivery_delay_days, 99999))
```

</details>

| lateness_band | orders | avg_review_score | pct_one_star |
|---|---|---|---|
| 30+ days early | 2,732 | 4.26 | 8.10 |
| 15-29 days early | 32,212 | 4.33 | 6.40 |
| 8-14 days early | 36,364 | 4.31 | 6.40 |
| 1-7 days early | 17,341 | 4.20 | 7.10 |
| on time | 1,292 | 4.03 | 8.50 |
| 1-7 days late | 3,672 | 2.71 | 41.40 |
| 8-14 days late | 1,479 | 1.67 | 70.60 |
| 15-30 days late | 1,039 | 1.61 | 71.00 |
| more than 30 days late | 345 | 2.06 | 63.20 |
| not delivered | 2,190 | 1.76 | 70.40 |

## Q10 -- lead origin revenue

> Q10. Which LEAD ORIGIN (marketing channel) recruited the sellers that
> generate the most revenue?
> Walks the third snowflaked hierarchy:
> dim_lead_origin -> dim_seller_acquisition -> dim_seller
> Only 842 of the 3 095 sellers were recruited through the tracked
> marketing funnel, so (a) reports funnel vs non-funnel first and
> (b) then ranks the channels inside the funnel population.
> ROLLUP over lead_origin_group -> lead_origin (channel grouping is
> an attribute of dim_lead_origin, i.e. one more hierarchy level).

### Q10. Which LEAD ORIGIN (marketing channel) recruited the sellers that

`q10_lead_origin_revenue_a.csv` -- 2 row(s), 151 ms

<details><summary>SQL</summary>

```sql
-- =====================================================================
-- Q10. Which LEAD ORIGIN (marketing channel) recruited the sellers that
--      generate the most revenue?
--      Walks the third snowflaked hierarchy:
--          dim_lead_origin -> dim_seller_acquisition -> dim_seller
--      Only 842 of the 3 095 sellers were recruited through the tracked
--      marketing funnel, so (a) reports funnel vs non-funnel first and
--      (b) then ranks the channels inside the funnel population.
-- =====================================================================

-- (a) Funnel-acquired vs organically-present sellers -------------------
SELECT CASE WHEN seller_from_funnel THEN 'Recruited via marketing funnel'
            ELSE 'Already on the platform / untracked' END          AS acquisition,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(DISTINCT order_id)                                     AS orders,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)    AS pct_of_revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT seller_id), 2)           AS revenue_per_seller
FROM v_sales
GROUP BY seller_from_funnel
ORDER BY revenue DESC
```

</details>

| acquisition | sellers | orders | revenue | pct_of_revenue | revenue_per_seller |
|---|---|---|---|---|---|
| Already on the platform / untracked | 2,715 | 94,264 | 15,067,737.61 | 95.10 | 5,549.81 |
| Recruited via marketing funnel | 380 | 4,512 | 775,815.63 | 4.90 | 2,041.62 |

### (b) Channel roll-up inside the funnel population

`q10_lead_origin_revenue_b.csv` -- 15 row(s), 101 ms

<details><summary>SQL</summary>

```sql
-- (b) Channel roll-up inside the funnel population ---------------------
--     ROLLUP over lead_origin_group -> lead_origin (channel grouping is
--     an attribute of dim_lead_origin, i.e. one more hierarchy level).
SELECT CASE WHEN GROUPING(lead_origin_group) = 1 THEN 'ALL CHANNELS'
            ELSE lead_origin_group END                              AS channel_group,
       CASE WHEN GROUPING(lead_origin) = 1 THEN 'All origins'
            ELSE lead_origin END                                    AS lead_origin,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(DISTINCT order_id)                                     AS orders,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT seller_id), 2)           AS revenue_per_seller,
       ROUND(100.0 * SUM(revenue) / MAX(SUM(revenue)) OVER (), 2)    AS pct_of_funnel_revenue
FROM v_sales
WHERE seller_from_funnel
GROUP BY ROLLUP (lead_origin_group, lead_origin)
ORDER BY GROUPING(lead_origin_group) DESC,
         MAX(SUM(revenue)) OVER (PARTITION BY lead_origin_group) DESC,
         lead_origin_group,
         GROUPING(lead_origin) DESC,
         revenue DESC
```

</details>

| channel_group | lead_origin | sellers | orders | revenue | revenue_per_seller | pct_of_funnel_revenue |
|---|---|---|---|---|---|---|
| ALL CHANNELS | All origins | 380 | 4,512 | 775,815.63 | 2,041.62 | 100.00 |
| Organic | All origins | 144 | 1,401 | 263,506.38 | 1,829.91 | 33.97 |
| Organic | organic_search | 113 | 1,208 | 235,956.58 | 2,088.11 | 30.41 |
| Organic | direct_traffic | 31 | 193 | 27,549.80 | 888.70 | 3.55 |
| Other/Unknown | All origins | 87 | 1,380 | 248,927.52 | 2,861.24 | 32.09 |
| Other/Unknown | unknown | 85 | 1,291 | 240,160.89 | 2,825.42 | 30.96 |
| Other/Unknown | other | 2 | 89 | 8,766.63 | 4,383.32 | 1.13 |
| Paid Media | All origins | 103 | 1,254 | 183,208.01 | 1,778.72 | 23.61 |
| Paid Media | paid_search | 101 | 1,247 | 182,000.06 | 1,801.98 | 23.46 |
| Paid Media | display | 2 | 7 | 1,207.95 | 603.98 | 0.16 |
| Owned/Social | All origins | 37 | 414 | 60,485.88 | 1,634.75 | 7.80 |
| Owned/Social | social | 31 | 392 | 51,363.47 | 1,656.89 | 6.62 |
| Owned/Social | email | 6 | 22 | 9,122.41 | 1,520.40 | 1.18 |
| Referral | All origins | 9 | 69 | 19,687.84 | 2,187.54 | 2.54 |
| Referral | referral | 9 | 69 | 19,687.84 | 2,187.54 | 2.54 |

### (c) Flat channel ranking -- the direct answer to the question

`q10_lead_origin_revenue_c.csv` -- 9 row(s), 131 ms

<details><summary>SQL</summary>

```sql
-- (c) Flat channel ranking -- the direct answer to the question --------
SELECT lead_origin,
       ANY_VALUE(lead_origin_group)                                 AS channel_group,
       COUNT(DISTINCT seller_id)                                    AS sellers,
       COUNT(DISTINCT order_id)                                     AS orders,
       ROUND(SUM(revenue), 2)                                       AS revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT seller_id), 2)           AS revenue_per_seller,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2)    AS pct_of_funnel_revenue
FROM v_sales
WHERE seller_from_funnel
GROUP BY lead_origin
ORDER BY revenue DESC
```

</details>

| lead_origin | channel_group | sellers | orders | revenue | revenue_per_seller | pct_of_funnel_revenue |
|---|---|---|---|---|---|---|
| unknown | Other/Unknown | 85 | 1,291 | 240,160.89 | 2,825.42 | 30.96 |
| organic_search | Organic | 113 | 1,208 | 235,956.58 | 2,088.11 | 30.41 |
| paid_search | Paid Media | 101 | 1,247 | 182,000.06 | 1,801.98 | 23.46 |
| social | Owned/Social | 31 | 392 | 51,363.47 | 1,656.89 | 6.62 |
| direct_traffic | Organic | 31 | 193 | 27,549.80 | 888.70 | 3.55 |
| referral | Referral | 9 | 69 | 19,687.84 | 2,187.54 | 2.54 |
| email | Owned/Social | 6 | 22 | 9,122.41 | 1,520.40 | 1.18 |
| other | Other/Unknown | 2 | 89 | 8,766.63 | 4,383.32 | 1.13 |
| display | Paid Media | 2 | 7 | 1,207.95 | 603.98 | 0.16 |

### (d) Which business segments did the best channels bring in?

`q10_lead_origin_revenue_d.csv` -- 25 row(s), 217 ms

<details><summary>SQL</summary>

```sql
-- (d) Which business segments did the best channels bring in? ----------
SELECT lead_origin,
       business_segment,
       COUNT(DISTINCT seller_id)            AS sellers,
       ROUND(SUM(revenue), 2)               AS revenue
FROM v_sales
WHERE seller_from_funnel
GROUP BY lead_origin, business_segment
QUALIFY ROW_NUMBER() OVER (PARTITION BY lead_origin ORDER BY SUM(revenue) DESC) <= 3
ORDER BY MAX(SUM(revenue)) OVER (PARTITION BY lead_origin) DESC,
         lead_origin, revenue DESC
```

</details>

| lead_origin | business_segment | sellers | revenue |
|---|---|---|---|
| unknown | watches | 1 | 122,261.02 |
| unknown | audio_video_electronics | 8 | 27,699.54 |
| unknown | household_utilities | 11 | 21,540.08 |
| paid_search | health_beauty | 15 | 62,196.50 |
| paid_search | home_decor | 13 | 27,272.15 |
| paid_search | construction_tools_house_garden | 7 | 13,618.90 |
| organic_search | small_appliances | 2 | 45,644.30 |
| organic_search | home_appliances | 2 | 27,065.67 |
| organic_search | household_utilities | 12 | 22,306.58 |
| social | pet | 4 | 17,455.39 |
| social | audio_video_electronics | 5 | 10,184.82 |
| social | home_office_furniture | 1 | 8,496.68 |
| direct_traffic | health_beauty | 3 | 10,235.06 |
| direct_traffic | household_utilities | 4 | 3,151.87 |
| direct_traffic | pet | 2 | 2,315.57 |
| referral | health_beauty | 2 | 8,642.82 |
| referral | stationery | 1 | 4,880.84 |
| referral | food_drink | 1 | 2,707.12 |
| other | health_beauty | 1 | 7,550.67 |
| other | home_decor | 1 | 1,215.96 |
| email | household_utilities | 1 | 7,168.41 |
| email | health_beauty | 3 | 965.11 |
| email | small_appliances | 1 | 928.70 |
| display | car_accessories | 1 | 1,063.97 |
| display | construction_tools_house_garden | 1 | 143.98 |
