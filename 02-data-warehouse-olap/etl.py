"""Build the warehouse: staging -> dimensions (top-down) -> facts -> validation.

Usage: python etl.py [--data DIR] [--db FILE]
The run is repeatable: the database file is rebuilt from the raw CSVs each time.
"""
import argparse
import sys
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent / "M26_DA_A2" / "M26_DA_A2_Part1"
STEPS = ["01_schema.sql", "02_staging.sql", "03_dimensions.sql", "04_facts.sql", "05_views.sql"]


def render(sql_file, data_dir):
    """Read a SQL script and fill in the input folders."""
    sql = (HERE / "sql" / sql_file).read_text(encoding="utf-8")
    return sql.replace("{{DATA_DIR}}", data_dir.as_posix()).replace("{{SEED_DIR}}", (HERE / "seed").as_posix())


def table_counts(con):
    """Return (table, rows) for every warehouse table, in name order."""
    names = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY 1"
    ).fetchall()
    return [(n, con.execute(f"SELECT count(*) FROM {n}").fetchone()[0]) for (n,) in names]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--db", type=Path, default=HERE / "warehouse.duckdb")
    args = parser.parse_args()

    args.db.unlink(missing_ok=True)
    con = duckdb.connect(str(args.db))
    log = []
    for step in STEPS:
        started = time.perf_counter()
        con.execute(render(step, args.data))
        log.append(f"{step:22s} {time.perf_counter() - started:7.2f} s")
        print(log[-1])

    checks = con.execute(render("06_validate.sql", args.data)).fetchall()
    failed = [c for c in checks if c[1] != c[2]]
    out = HERE / "outputs"
    out.mkdir(exist_ok=True)
    with open(out / "etl_report.md", "w", encoding="utf-8") as f:
        f.write("# ETL report\n\n## Steps\n\n```\n" + "\n".join(log) + "\n```\n\n## Row counts\n\n")
        f.write("| Table | Rows |\n|---|---:|\n")
        for name, rows in table_counts(con):
            f.write(f"| {name} | {rows:,} |\n")
        f.write(f"\n## Validation: {len(checks) - len(failed)}/{len(checks)} passed\n\n")
        f.write("| Check | Expected | Actual | Result |\n|---|---:|---:|---|\n")
        for name, expected, actual in checks:
            f.write(f"| {name} | {expected} | {actual} | {'PASS' if expected == actual else 'FAIL'} |\n")
    print(f"validation: {len(checks) - len(failed)}/{len(checks)} passed")
    for name, expected, actual in failed:
        print(f"  FAILED {name}: expected {expected}, got {actual}")
    con.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
