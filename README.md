# Data Analytics Projects

Four projects from the Data Analytics I course at IIIT Hyderabad (Monsoon 2026),
done in a team of two. Each folder has the code, the report (PDF) and the outputs
behind every number in it. The datasets are not included; see [Data](#data).

The data warehouse and data cube projects were rebuilt from scratch after the course to
follow the assignment brief more closely. The original team submission is in the git
history at commit `7a2a9c4`.

| Project | What it does | Key results | Stack |
|---|---|---|---|
| [Movie recommender](04-movie-recommender/) | Association rules on MovieLens "liked-movie" baskets, FP-growth and Apriori written from scratch, rules used to recommend movies | 100,836 ratings; FP-growth up to 6.4x faster than Apriori; precision@10 = 0.209, 19% above a popularity baseline | Python, pandas, NumPy |
| [E-commerce data warehouse](02-data-warehouse-olap/) | Snowflake schema, ETL and OLAP queries on the Olist Brazilian e-commerce dataset | 2 fact tables, 18 dimension and level tables; 112,650 order items loaded with no rows lost; 24/24 data-quality checks pass; 10 business questions in SQL | SQL, DuckDB, Python |
| [Data cube and rule mining](03-data-cube-rule-mining/) | Bottom-Up Cubing (in-memory and out-of-core) and attribute-oriented induction on census data | 299,285 records x 12 dimensions; 4,096/4,096 group-bys match DuckDB `CUBE`; discriminant rules for income > 50K | Python, DuckDB |
| [Statistical EDA](01-statistical-eda/) | Exploratory and statistical analysis of bank marketing calls and NYC Airbnb listings | 11,162 bank records, 30,259 listings; chi-square, ANOVA and Mann-Whitney U tests | pandas, SciPy, Seaborn |

## Data

The data is not redistributed here. To run the code, download it and place it as follows.

- **Movie recommender:** the notebook downloads MovieLens `ml-latest-small` from
  [GroupLens](https://grouplens.org/datasets/movielens/) itself.
- **Data warehouse:** the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  CSVs go in `M26_DA_A2/M26_DA_A2_Part1/` at the repository root. Then run
  `python 02-data-warehouse-olap/etl.py && python 02-data-warehouse-olap/run_queries.py`.
- **Data cube:** the course census extract goes in `M26_DA_A2/M26_DA_A2_Part2.csv`. Then follow
  the steps in [its README](03-data-cube-rule-mining/README.md).
- **Statistical EDA:** `bank.csv` (bank term-deposit marketing) and `listings.csv`
  (Inside Airbnb, New York City) go next to the notebooks.

Requirements: Python 3 with `pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn` and `duckdb`.
