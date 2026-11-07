# E-commerce Data Warehouse and OLAP Analysis

A Snowflake-schema warehouse in DuckDB for the Olist Brazilian e-commerce dataset, loaded top-down
with real primary and foreign key constraints, then queried with analytical SQL.

The raw data is not included. Put the Olist CSVs in `M26_DA_A2/M26_DA_A2_Part1/` at the repository
root, or pass `--data DIR` to `etl.py`.

```
python etl.py           # staging -> dimensions (top-down) -> facts -> 24 checks
python run_queries.py   # Q1-Q10 and the reconciliation -> CSV and Markdown
```

| Item | Location |
|---|---|
| Report | `report/report.pdf` |
| ER diagram | `diagrams/er_diagram.png`, source in `er_diagram.mmd` |
| Table creation | `sql/01_schema.sql` |
| ETL steps | `sql/02_staging.sql` to `05_views.sql`, driven by `etl.py` |
| Validation | `sql/06_validate.sql`, results in `outputs/etl_report.md` |
| Queries | `sql/queries/` |
| Query outputs | `outputs/query_results.md`, `outputs/csv/` |
