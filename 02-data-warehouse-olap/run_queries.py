"""Run every analytical query and save each result as a CSV plus one formatted Markdown file.

A query file may hold several statements. Each one starts with a line "-- @result <name>".
Usage: python run_queries.py [--db FILE]
"""
import argparse
import re
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
MAX_ROWS_IN_MARKDOWN = 40


def split_results(sql):
    """Yield (result name, statement) for each '-- @result' block in a script."""
    parts = re.split(r"^-- @result (\S+)\s*$", sql, flags=re.MULTILINE)
    for name, body in zip(parts[1::2], parts[2::2]):
        yield name, body.strip()


def to_markdown(df):
    """Render a dataframe as a Markdown table, cutting long results."""
    shown = df.head(MAX_ROWS_IN_MARKDOWN).astype(object).where(df.head(MAX_ROWS_IN_MARKDOWN).notna(), "")
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in shown.itertuples(index=False)]
    if len(df) > MAX_ROWS_IN_MARKDOWN:
        lines.append(f"\n{len(df):,} rows in total; the first {MAX_ROWS_IN_MARKDOWN} are shown. The CSV has them all.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=HERE / "warehouse.duckdb")
    args = parser.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    csv_dir = HERE / "outputs" / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)
    sections = ["# Query results\n"]
    for path in sorted((HERE / "sql" / "queries").glob("q*.sql")):
        sections.append(f"## {path.stem}\n")
        for name, statement in split_results(path.read_text(encoding="utf-8")):
            df = con.execute(statement).df()
            df.to_csv(csv_dir / f"{name}.csv", index=False)
            sections.append(f"### {name}\n\n{to_markdown(df)}\n")
            print(f"{name:34s} {len(df):7,} rows")
    (HERE / "outputs" / "query_results.md").write_text("\n".join(sections), encoding="utf-8")
    con.close()


if __name__ == "__main__":
    main()
