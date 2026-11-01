"""Part 1 / Task 3 -- run the ten analytical queries and capture outputs.

Each part1/sql/queries/qNN_*.sql file may contain several statements; every
statement that returns rows is captured as a labelled sub-result (a), (b),
(c) ...  For each one we write

    outputs/csv/qNN_x.csv        machine-readable result table
    outputs/query_results.md     all results as markdown tables (submission)

Usage:  python part1/etl/run_queries.py [--db PATH] [--max-rows N]
"""

from __future__ import annotations

import argparse
import string
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DB_PATH,
    OUT_DIR,
    QUERY_DIR,
    as_markdown,
    ensure_dirs,
    split_statements,
)

# How many rows of each result to embed in the markdown document.  The CSVs
# always hold the complete result.
DEFAULT_MAX_ROWS = 40
MAX_ROWS_OVERRIDE = {
    "q01_revenue_by_time_rollup.sql": 100,   # 3 years x (4 quarters + months)
    "q05_geography_rollup.sql": 120,
    "q08_cube_region_category_year.sql": 60,
}


def leading_comment(sql: str) -> str:
    """Pull the '-- (a) ...' label off the front of a statement, if present."""
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--"):
            text = s.lstrip("-").strip().rstrip("-").strip()
            if text and not set(text) <= {"=", "-"}:
                return text
        elif s:
            break
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    args = ap.parse_args()

    csv_dir = OUT_DIR / "csv"
    ensure_dirs(OUT_DIR, csv_dir)

    db_file = Path(args.db)
    if not db_file.exists():
        raise SystemExit(f"warehouse not found: {db_file}  (run run_etl.py first)")

    con = duckdb.connect(str(db_file), read_only=False)
    con.execute("PRAGMA threads=4")

    files = sorted(QUERY_DIR.glob("q*.sql"))
    if not files:
        raise SystemExit(f"no query files in {QUERY_DIR}")

    doc: list[str] = [
        "# Part 1 / Task 3 -- Analytical query outputs",
        "",
        "Revenue is defined throughout as `price + freight_value`.",
        "Every query runs against the snowflake warehouse through the",
        "`v_sales` / `v_orders` navigation views (see `sql/05_create_views.sql`).",
        "Complete result sets are in `outputs/csv/`; the tables below are",
        "truncated where a result is long.",
        "",
    ]
    index: list[str] = ["## Contents", ""]
    manifest: list[tuple[str, str, int, float]] = []

    for path in files:
        qid = path.stem.split("_")[0]                     # 'q01'
        title = path.stem.split("_", 1)[1].replace("_", " ")
        header = path.read_text(encoding="utf-8")
        # the block comment at the top of the file describes the question
        question = "\n".join(
            ln.lstrip("- ").rstrip()
            for ln in header.splitlines()
            if ln.startswith("--") and set(ln.strip()) != {"-", "="}
               and not ln.strip().startswith("-- (")
        ).strip()
        # stop the description at the first blank-ish separator
        question_lines = [l for l in question.splitlines() if l.strip()]
        # drop the '====' rows
        question_lines = [l for l in question_lines if not set(l.strip()) <= {"="}]

        anchor = path.stem.replace("_", "-").lower()
        index.append(f"- [{qid.upper()} -- {title}](#{anchor})")
        doc.append(f"## {qid.upper()} -- {title}")
        doc.append("")
        doc.append("> " + "\n> ".join(question_lines))
        doc.append("")

        statements = list(split_statements(header))
        letters = iter(string.ascii_lowercase)
        print(f"\n{'=' * 70}\n{path.name}\n{'=' * 70}")

        for stmt in statements:
            t0 = time.perf_counter()
            try:
                res = con.execute(stmt)
            except Exception as exc:                       # noqa: BLE001
                print(f"  !! FAILED: {exc}")
                print(stmt[:1500])
                return 1
            elapsed = time.perf_counter() - t0

            if res.description is None:                    # DDL such as CREATE TEMP TABLE
                continue
            cols = [d[0] for d in res.description]
            rows = res.fetchall()
            letter = next(letters)
            label = leading_comment(stmt) or f"({letter})"
            out_name = f"{path.stem}_{letter}.csv"

            # ---- csv ----
            with open(csv_dir / out_name, "w", encoding="utf-8", newline="") as fh:
                import csv as _csv

                w = _csv.writer(fh)
                w.writerow(cols)
                w.writerows(rows)

            # ---- markdown ----
            cap = MAX_ROWS_OVERRIDE.get(path.name, args.max_rows)
            doc.append(f"### {label}")
            doc.append("")
            doc.append(f"`{out_name}` -- {len(rows):,} row(s), {elapsed * 1000:.0f} ms")
            doc.append("")
            doc.append("<details><summary>SQL</summary>")
            doc.append("")
            doc.append("```sql")
            doc.append(stmt.strip())
            doc.append("```")
            doc.append("")
            doc.append("</details>")
            doc.append("")
            doc.append(as_markdown(cols, rows, max_rows=cap))
            doc.append("")

            manifest.append((path.name, label, len(rows), elapsed))
            print(f"  {letter}) {len(rows):>6,d} rows  {elapsed * 1000:7.0f} ms  {label}")

    (OUT_DIR / "query_results.md").write_text(
        "\n".join(index + [""] + doc), encoding="utf-8"
    )
    con.close()

    print(f"\n{len(manifest)} result sets written")
    print(f"  {OUT_DIR / 'query_results.md'}")
    print(f"  {csv_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
