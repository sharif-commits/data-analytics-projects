"""Part 1 / Task 2 -- ETL driver for the Olist snowflake warehouse (DuckDB).

Runs the five SQL stages in order and then the validation suite:

    01_create_schema.sql   DDL for the snowflake (dims + 2 fact tables)
    02_load_staging.sql    raw CSV -> stg_* tables, everything as VARCHAR
    03_load_dimensions.sql dimension levels loaded TOP-DOWN
                           (region -> state -> city -> zip -> customer/seller)
    04_load_facts.sql      fact tables, all lookups LEFT JOIN + COALESCE(-1)
    05_create_views.sql    v_sales / v_orders navigation views
    06_validate.sql        22 assertions; a single FAIL aborts the run

Usage:  python part1/etl/run_etl.py [--db PATH] [--quiet]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DB_PATH,
    OUT_DIR,
    RAW_DIR,
    SQL_DIR,
    as_markdown,
    ensure_dirs,
    render,
    split_statements,
)

STAGES = [
    ("01_create_schema.sql", "Create snowflake schema (DDL)"),
    ("02_load_staging.sql", "Extract: raw CSV -> staging"),
    ("03_load_dimensions.sql", "Transform + Load: dimensions (top-down)"),
    ("04_load_facts.sql", "Transform + Load: fact tables"),
    ("05_create_views.sql", "Create analytic views"),
]

# Tables whose row counts are reported at the end of the run, in the order
# they are loaded, so the log doubles as documentation of the load sequence.
REPORT_TABLES = [
    "dim_date", "dim_region", "dim_state", "dim_city", "dim_zip",
    "dim_customer", "dim_lead_origin", "dim_seller_acquisition", "dim_seller",
    "dim_category", "dim_product", "dim_order_status", "dim_delivery_status",
    "dim_delivery_bucket", "dim_payment_type", "dim_review",
    "fact_order_item", "fact_order_payment",
]


def run_script(con: duckdb.DuckDBPyConnection, path: Path, log) -> None:
    sql = render(path.read_text(encoding="utf-8"))
    for stmt in split_statements(sql):
        try:
            con.execute(stmt)
        except Exception as exc:                        # noqa: BLE001
            log(f"\n!! FAILED statement in {path.name}:\n{stmt[:2000]}\n")
            raise RuntimeError(f"{path.name}: {exc}") from exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ensure_dirs(OUT_DIR)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        log_lines.append(msg)
        if not args.quiet:
            print(msg, flush=True)

    if not RAW_DIR.exists():
        raise SystemExit(f"raw data folder not found: {RAW_DIR}")

    db_file = Path(args.db)
    if db_file.exists():
        db_file.unlink()                                # always a clean build

    log("=" * 72)
    log("PART 1 -- ETL into DuckDB snowflake warehouse")
    log("=" * 72)
    log(f"raw data : {RAW_DIR}")
    log(f"database : {db_file}")
    log("")

    con = duckdb.connect(str(db_file))
    con.execute("PRAGMA threads=4")

    total = time.perf_counter()
    for fname, label in STAGES:
        t0 = time.perf_counter()
        run_script(con, SQL_DIR / fname, log)
        log(f"  [{time.perf_counter() - t0:6.2f}s]  {fname:<24s} {label}")
    log(f"  {'':8s}  {'-' * 24} ")
    log(f"  [{time.perf_counter() - total:6.2f}s]  total load time")
    log("")

    # ---------------------------------------------------------------- counts
    log("Row counts after load")
    log("-" * 72)
    rows = []
    for tbl in REPORT_TABLES:
        n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        kind = "FACT" if tbl.startswith("fact_") else "dimension"
        rows.append((tbl, kind, n))
        log(f"  {tbl:<28s} {kind:<10s} {n:>10,d}")
    log("")

    # ------------------------------------------------------------ validation
    val_sql = (SQL_DIR / "06_validate.sql").read_text(encoding="utf-8")
    res = con.execute(val_sql)
    cols = [d[0] for d in res.description]
    checks = res.fetchall()
    failures = [c for c in checks if c[-1] != "PASS"]

    log("Load validation")
    log("-" * 72)
    for cid, name, exp, act, status in checks:
        flag = "OK  " if status == "PASS" else "FAIL"
        log(f"  {flag} {cid:>2d}. {name}")
        if status != "PASS":
            log(f"        expected={exp!r} actual={act!r}")
    log("")
    log(f"  {len(checks) - len(failures)}/{len(checks)} checks passed")

    # ---------------------------------------------------------------- output
    md = ["# Part 1 -- ETL run report", "",
          "## Row counts after load", "",
          as_markdown(("table", "kind", "rows"), rows), "",
          "## Load validation", "",
          as_markdown(cols, checks), ""]
    (OUT_DIR / "etl_report.md").write_text("\n".join(md), encoding="utf-8")
    (OUT_DIR / "etl_log.txt").write_text("\n".join(log_lines), encoding="utf-8")

    con.close()

    if failures:
        print(f"\nETL FAILED: {len(failures)} validation check(s) failed", file=sys.stderr)
        return 1
    log(f"\nWrote {OUT_DIR / 'etl_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
