"""Shared helpers for the Part 1 DuckDB warehouse scripts.

Kept deliberately small: a SQL-script splitter that is aware of string
literals and comments, a template substituter for the {RAW}/{SEED}
placeholders, and a markdown table formatter used to write the query
outputs that the assignment asks to be submitted as result tables.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Iterator, Sequence

# --------------------------------------------------------------------- paths
PART1_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PART1_DIR.parent
RAW_DIR = ROOT_DIR / "M26_DA_A2" / "M26_DA_A2_Part1"
SEED_DIR = PART1_DIR / "seed"
SQL_DIR = PART1_DIR / "sql"
QUERY_DIR = SQL_DIR / "queries"
OUT_DIR = PART1_DIR / "outputs"
DB_PATH = PART1_DIR / "olist_dw.duckdb"


def duckdb_path(p: Path) -> str:
    """DuckDB wants forward slashes inside SQL string literals, on every OS."""
    return str(p).replace("\\", "/")


def render(sql: str) -> str:
    """Substitute the {RAW} / {SEED} placeholders used by the load scripts."""
    return sql.replace("{RAW}", duckdb_path(RAW_DIR)).replace(
        "{SEED}", duckdb_path(SEED_DIR)
    )


# ----------------------------------------------------------------- splitting
def split_statements(script: str) -> Iterator[str]:
    """Yield individual SQL statements from a script.

    A plain ``script.split(';')`` would break on semicolons that appear
    inside string literals or comments, so this walks the text tracking
    which context it is in.
    """
    buf: list[str] = []
    i, n = 0, len(script)
    in_str = in_line_comment = in_block_comment = False

    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 1
                in_block_comment = False
        elif in_str:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":            # '' is an escaped quote
                    buf.append(nxt)
                    i += 1
                else:
                    in_str = False
        else:
            if ch == "-" and nxt == "-":
                in_line_comment = True
                buf.append(ch)
            elif ch == "/" and nxt == "*":
                in_block_comment = True
                buf.append(ch)
            elif ch == "'":
                in_str = True
                buf.append(ch)
            elif ch == ";":
                stmt = "".join(buf).strip()
                if _is_executable(stmt):
                    yield stmt
                buf = []
            else:
                buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if _is_executable(tail):
        yield tail


def _is_executable(stmt: str) -> bool:
    """True unless the chunk is empty or nothing but comments."""
    stripped = re.sub(r"--[^\n]*", "", stmt)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
    return bool(stripped.strip())


# ------------------------------------------------------------------ markdown
def as_markdown(columns: Sequence[str], rows: Iterable[Sequence], max_rows: int | None = None) -> str:
    """Render a result set as a GitHub-flavoured markdown table."""
    rows = list(rows)
    truncated = 0
    if max_rows is not None and len(rows) > max_rows:
        truncated = len(rows) - max_rows
        rows = rows[:max_rows]

    def fmt(v) -> str:
        if v is None:
            return "*(ALL)*"
        if isinstance(v, float):
            return f"{v:,.2f}"
        if isinstance(v, int) and not isinstance(v, bool):
            return f"{v:,}"
        return str(v).replace("|", "\\|")

    out = ["| " + " | ".join(str(c) for c in columns) + " |",
           "|" + "|".join("---" for _ in columns) + "|"]
    for r in rows:
        out.append("| " + " | ".join(fmt(v) for v in r) + " |")
    if truncated:
        out.append(f"\n*({truncated:,} further rows omitted)*")
    return "\n".join(out)


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)
