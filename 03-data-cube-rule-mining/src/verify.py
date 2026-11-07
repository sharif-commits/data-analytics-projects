"""Verify both BUC versions against DuckDB, on all 12 dimensions and every group-by.

For each setting this script:
  * runs the in-memory and out-of-core versions and compares the SHA-256 of their output files;
  * runs GROUP BY CUBE ... HAVING COUNT(*) >= minsup in DuckDB;
  * compares every cell, count and sum, and reports the result per group-by.
Finally it uses tracemalloc to measure what the out-of-core version really allocates.
"""
import csv
import hashlib
import itertools
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from buc_disk import run_from_records, buc_out_of_core, write_records
from buc_memory import ALL, buc_in_memory, read_cells
from census import DEFAULT_MEASURE, DIMENSIONS, load_cube_data

OUT = Path(__file__).resolve().parents[1] / "outputs"
BATCH_DIMS = 4
SETTINGS = [
    {"minsup": 1000, "measure": DEFAULT_MEASURE, "memory_bytes": 1 << 20},
    {"minsup": 1000, "measure": None, "memory_bytes": 1 << 20},
    {"minsup": 200, "measure": DEFAULT_MEASURE, "memory_bytes": 4 << 20},
    {"minsup": 5000, "measure": DEFAULT_MEASURE, "memory_bytes": 128 << 10},
]
TRACE_SETTINGS = [{"minsup": 5000, "memory_bytes": b} for b in (256 << 10, 1 << 20, 4 << 20)]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def cube_from_duckdb(con, n_dims, minsup, measure):
    """Run the reference query. Dimensions hold no NULLs, so a NULL in the result means ALL.

    One CUBE over 12 columns ran out of memory at DuckDB's 6.2 GB limit, so it runs as 16 batches.
    Each batch fixes which of the first 4 dimensions are grouped and takes a CUBE of the other 8.
    Together the 16 batches are exactly the 4,096 group-bys of the full CUBE.
    """
    names = [f"d{i}" for i in range(n_dims)]
    fixed, cubed = names[:BATCH_DIMS], names[BATCH_DIMS:]
    total = "sum(m)" if measure else "0"
    parts = []
    for size in range(len(fixed) + 1):
        for grouped in itertools.combinations(fixed, size):
            columns = [n if n in grouped or n in cubed else f"CAST(NULL AS SMALLINT) AS {n}" for n in names]
            keys = [*grouped, f"CUBE ({', '.join(cubed)})"]
            parts.append(con.execute(f"SELECT {', '.join(columns)}, count(*) AS c, {total} AS s FROM relation "
                                     f"GROUP BY {', '.join(keys)} HAVING count(*) >= {minsup}").df())
    frame = pd.concat(parts, ignore_index=True)
    cells = frame[names].fillna(ALL).to_numpy(dtype=np.int16)
    return cells, frame["c"].to_numpy(dtype=np.int64), frame["s"].to_numpy(dtype=np.float64).round().astype(np.int64)


def sort_cells(cells, counts, sums):
    order = np.lexsort(cells.T[::-1])
    return cells[order], counts[order], sums[order]


def group_by_masks(cells):
    """The group-by each cell belongs to, as a bit mask of its non-ALL dimensions."""
    bits = 1 << np.arange(cells.shape[1], dtype=np.int64)
    return ((cells != ALL) * bits).sum(axis=1)


def compare(buc_cells, duck_cells):
    """Compare every cell, and return overall and per-group-by results."""
    ours = sort_cells(buc_cells["cell"], buc_cells["count"], buc_cells["sum"])
    theirs = sort_cells(*duck_cells)
    n_dims = ours[0].shape[1]
    our_mask, their_mask = group_by_masks(ours[0]), group_by_masks(theirs[0])
    matched, non_empty, rows = 0, 0, []
    for mask in range(1 << n_dims):
        a, b = our_mask == mask, their_mask == mask
        same = (a.sum() == b.sum() and np.array_equal(ours[0][a], theirs[0][b])
                and np.array_equal(ours[1][a], theirs[1][b]) and np.array_equal(ours[2][a], theirs[2][b]))
        matched += bool(same)
        non_empty += bool(b.sum())
        rows.append((mask, int(a.sum()), int(b.sum()), bool(same)))
    identical = (ours[0].shape == theirs[0].shape and np.array_equal(ours[0], theirs[0])
                 and np.array_equal(ours[1], theirs[1]) and np.array_equal(ours[2], theirs[2]))
    return identical, matched, non_empty, rows


def measure_allocation(data, temp_dir):
    """Peak traced allocation of the out-of-core version, with only its record file as input."""
    results = []
    cards = [data.cardinality(d) for d in DIMENSIONS]
    records = temp_dir / "relation.bin"
    write_records(data, DIMENSIONS, records, DEFAULT_MEASURE)
    for setting in TRACE_SETTINGS:
        tracemalloc.start()
        stats = run_from_records(records, data.n_rows, cards, setting["minsup"], temp_dir / "trace.bin",
                                 setting["memory_bytes"], use_measure=True, temp_root=temp_dir)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        results.append({**setting, "relation_bytes": records.stat().st_size, "peak_traced_bytes": peak,
                        "peak_over_budget": round(peak / setting["memory_bytes"], 3),
                        "retained_after_run_bytes": retained,
                        "disk_partitions": stats.disk_partitions, "memory_partitions": stats.memory_partitions})
        print(results[-1], flush=True)
    return results


def main():
    OUT.mkdir(exist_ok=True)
    data = load_cube_data()
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    frame = pd.DataFrame({f"d{i}": data.columns[d].astype(np.int16) for i, d in enumerate(DIMENSIONS)})
    frame["m"] = data.measures[DEFAULT_MEASURE]
    con.register("frame", frame)
    con.execute("CREATE TABLE relation AS SELECT * FROM frame")

    summary = []
    with tempfile.TemporaryDirectory(prefix="buc_verify_") as tmp:
        temp_dir = Path(tmp)
        memory_file, disk_file = temp_dir / "memory.bin", temp_dir / "disk.bin"
        for setting in SETTINGS:
            minsup, measure, budget = setting["minsup"], setting["measure"], setting["memory_bytes"]
            started = time.perf_counter()
            memory_stats = buc_in_memory(data, DIMENSIONS, minsup, memory_file, measure=measure)
            memory_seconds = time.perf_counter() - started
            started = time.perf_counter()
            disk_stats = buc_out_of_core(data, DIMENSIONS, minsup, disk_file, budget, measure=measure, temp_root=temp_dir)
            disk_seconds = time.perf_counter() - started
            started = time.perf_counter()
            reference = cube_from_duckdb(con, len(DIMENSIONS), minsup, measure)
            duckdb_seconds = time.perf_counter() - started

            identical, matched, non_empty, rows = compare(read_cells(memory_file, len(DIMENSIONS)), reference)
            result = {
                **setting, "measure": measure or "COUNT only", "dimensions": len(DIMENSIONS),
                "cells_memory": memory_stats.cells, "cells_disk": disk_stats.cells,
                "cells_duckdb": len(reference[1]), "byte_identical": sha256(memory_file) == sha256(disk_file),
                "all_cells_equal_duckdb": bool(identical), "group_bys_total": 1 << len(DIMENSIONS),
                "group_bys_matching": matched, "group_bys_with_cells": non_empty,
                "disk_partitions": disk_stats.disk_partitions, "memory_partitions": disk_stats.memory_partitions,
                "seconds_memory": round(memory_seconds, 1), "seconds_disk": round(disk_seconds, 1),
                "seconds_duckdb": round(duckdb_seconds, 1),
            }
            summary.append(result)
            print(result, flush=True)
            if setting is SETTINGS[0]:
                with open(OUT / "verification_group_bys.csv", "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["group_by_mask", "cells_buc", "cells_duckdb", "match"])
                    writer.writerows(rows)
        trace = measure_allocation(data, temp_dir)

    (OUT / "verification.json").write_text(json.dumps({"runs": summary, "allocation": trace}, indent=2))


if __name__ == "__main__":
    main()
