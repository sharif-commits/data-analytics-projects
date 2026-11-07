"""Timing experiments. Each experiment appends finished rows to its CSV as it goes.

Usage: python benchmarks.py [minsup memory dims order ...]
"""
import csv
import gc
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from buc_disk import run_from_records, write_records
from buc_memory import ALL, buc_in_memory, read_cells
from census import DEFAULT_MEASURE, DIMENSIONS, load_cube_data

OUT = Path(__file__).resolve().parents[1] / "outputs"
RUNS = 3
ORDER_RUNS = 5
FIXED_MEMORY = 1 << 20
MINSUPS = [1000, 2000, 5000, 10000, 20000]
MEMORY_MINSUP = 5000
MEMORY_BUDGETS = [256 << 10, 1 << 20, 4 << 20, 16 << 20, 64 << 20]
DIMS_MINSUP = 2000
DIM_COUNTS = [2, 4, 6, 8, 10, 12]
ORDER_MINSUP = 2000


def time_memory(data, dims, minsup, out_file):
    gc.collect()
    started = time.perf_counter()
    stats = buc_in_memory(data, dims, minsup, out_file, measure=DEFAULT_MEASURE)
    return time.perf_counter() - started, stats


def time_disk(data, dims, minsup, budget, temp_dir, out_file):
    """Time the disk version from its record file, which is its natural input."""
    records = temp_dir / "relation.bin"
    write_records(data, dims, records, DEFAULT_MEASURE)
    cards = [data.cardinality(d) for d in dims]
    gc.collect()
    started = time.perf_counter()
    stats = run_from_records(records, data.n_rows, cards, minsup, out_file, budget, use_measure=True, temp_root=temp_dir)
    return time.perf_counter() - started, stats


class Table:
    """A CSV file written one row at a time, so a long run keeps what it has finished."""

    def __init__(self, name, fields):
        self._file = open(OUT / name, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=fields)
        self._writer.writeheader()

    def add(self, **row):
        self._writer.writerow(row)
        self._file.flush()
        print(row, flush=True)

    def close(self):
        self._file.close()


def summarize(times):
    return {"median_s": round(float(np.median(times)), 3), "min_s": round(min(times), 3), "max_s": round(max(times), 3)}


def experiment_minsup(data, temp_dir):
    table = Table("benchmark_minsup.csv", ["version", "minsup", "memory_bytes", "cells", "median_s", "min_s", "max_s",
                                           "bytes_read", "bytes_written", "disk_partitions"])
    out_file = temp_dir / "cells.bin"
    for minsup in MINSUPS:
        results = [time_memory(data, DIMENSIONS, minsup, out_file) for _ in range(RUNS)]
        table.add(version="memory", minsup=minsup, memory_bytes="", cells=results[0][1].cells,
                  **summarize([r[0] for r in results]), bytes_read=0, bytes_written=0, disk_partitions=0)
        results = [time_disk(data, DIMENSIONS, minsup, FIXED_MEMORY, temp_dir, out_file) for _ in range(RUNS)]
        s = results[0][1]
        table.add(version="disk", minsup=minsup, memory_bytes=FIXED_MEMORY, cells=s.cells,
                  **summarize([r[0] for r in results]), bytes_read=s.bytes_read, bytes_written=s.bytes_written,
                  disk_partitions=s.disk_partitions)
    table.close()


def experiment_memory(data, temp_dir):
    table = Table("benchmark_memory.csv", ["memory_bytes", "minsup", "cells", "median_s", "min_s", "max_s", "pages_read",
                                           "pages_written", "bytes_read", "bytes_written", "disk_partitions",
                                           "memory_partitions", "spill_files", "peak_spill_bytes"])
    out_file = temp_dir / "cells.bin"
    for budget in MEMORY_BUDGETS:
        results = [time_disk(data, DIMENSIONS, MEMORY_MINSUP, budget, temp_dir, out_file) for _ in range(RUNS)]
        s = results[0][1]
        table.add(memory_bytes=budget, minsup=MEMORY_MINSUP, cells=s.cells, **summarize([r[0] for r in results]),
                  pages_read=s.pages_read, pages_written=s.pages_written, bytes_read=s.bytes_read,
                  bytes_written=s.bytes_written, disk_partitions=s.disk_partitions,
                  memory_partitions=s.memory_partitions, spill_files=s.spill_files, peak_spill_bytes=s.peak_spill_bytes)
    table.close()


def experiment_dims(data, temp_dir):
    table = Table("benchmark_dims.csv", ["version", "dimensions", "minsup", "cells", "median_s", "min_s", "max_s"])
    out_file = temp_dir / "cells.bin"
    for count in DIM_COUNTS:
        dims = DIMENSIONS[:count]
        results = [time_memory(data, dims, DIMS_MINSUP, out_file) for _ in range(RUNS)]
        table.add(version="memory", dimensions=count, minsup=DIMS_MINSUP, cells=results[0][1].cells,
                  **summarize([r[0] for r in results]))
        results = [time_disk(data, dims, DIMS_MINSUP, FIXED_MEMORY, temp_dir, out_file) for _ in range(RUNS)]
        table.add(version="disk", dimensions=count, minsup=DIMS_MINSUP, cells=results[0][1].cells,
                  **summarize([r[0] for r in results]))
    table.close()


def entropy(codes):
    p = np.bincount(codes) / len(codes)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def dimension_orders(data):
    """The orders compared. Effective cardinality 2**H counts skew: a dominant value makes it small."""
    by_card = sorted(DIMENSIONS, key=lambda d: (data.cardinality(d), d))
    by_entropy = sorted(DIMENSIONS, key=lambda d: (entropy(data.columns[d]), d))
    return {"given (unoptimised)": list(DIMENSIONS), "ascending cardinality": by_card,
            "descending cardinality": by_card[::-1], "ascending entropy": by_entropy,
            "descending entropy": by_entropy[::-1]}


def canonical_cells(path, dims):
    """Read a cell file with its columns put back in the given order, then sort it."""
    cells = read_cells(path, len(dims))
    back = [dims.index(d) for d in DIMENSIONS]
    grid = cells["cell"][:, back]
    order = np.lexsort(grid.T[::-1])
    return grid[order], cells["count"][order], cells["sum"][order]


def experiment_order(data, temp_dir):
    table = Table("benchmark_optimization.csv", ["version", "order", "minsup", "cells", "median_s", "min_s", "max_s",
                                                 "partition_steps", "pruned_values", "sorts_skipped", "speedup_vs_given",
                                                 "same_cube_as_given", "dimension_sequence"])
    orders = dimension_orders(data)
    out_file = temp_dir / "cells.bin"
    times = {name: [] for name in orders}
    stats = {}
    for _ in range(ORDER_RUNS):        # interleaved, so slow drift hits every order equally
        for name, dims in orders.items():
            seconds, stats[name] = time_memory(data, dims, ORDER_MINSUP, out_file)
            times[name].append(seconds)

    baseline = None
    same = {}
    for name, dims in orders.items():
        time_memory(data, dims, ORDER_MINSUP, out_file)
        cube = canonical_cells(out_file, dims)
        baseline = baseline if baseline is not None else cube
        same[name] = all(np.array_equal(a, b) for a, b in zip(baseline, cube))

    given = float(np.median(times["given (unoptimised)"]))
    for name, dims in orders.items():
        s = stats[name]
        table.add(version="memory", order=name, minsup=ORDER_MINSUP, cells=s.cells, **summarize(times[name]),
                  partition_steps=s.partition_steps, pruned_values=s.pruned_values, sorts_skipped=s.sorts_skipped,
                  speedup_vs_given=round(given / float(np.median(times[name])), 3), same_cube_as_given=same[name],
                  dimension_sequence=" > ".join(dims))

    best = min(orders, key=lambda n: float(np.median(times[n])))
    disk = {}
    for name in dict.fromkeys(["given (unoptimised)", best]):
        results = [time_disk(data, orders[name], ORDER_MINSUP, FIXED_MEMORY, temp_dir, out_file) for _ in range(RUNS)]
        disk[name] = results
    given_disk = float(np.median([r[0] for r in disk["given (unoptimised)"]]))
    for name, results in disk.items():
        s = results[0][1]
        median = float(np.median([r[0] for r in results]))
        table.add(version="disk", order=name, minsup=ORDER_MINSUP, cells=s.cells, **summarize([r[0] for r in results]),
                  partition_steps=s.partition_steps, pruned_values=s.pruned_values, sorts_skipped=s.sorts_skipped,
                  speedup_vs_given=round(given_disk / median, 3), same_cube_as_given="",
                  dimension_sequence=" > ".join(orders[name]))
    table.close()


EXPERIMENTS = {"minsup": experiment_minsup, "memory": experiment_memory, "dims": experiment_dims, "order": experiment_order}


def main():
    OUT.mkdir(exist_ok=True)
    wanted = sys.argv[1:] or list(EXPERIMENTS)
    data = load_cube_data()
    with tempfile.TemporaryDirectory(prefix="buc_bench_") as tmp:
        for name in wanted:
            started = time.perf_counter()
            EXPERIMENTS[name](data, Path(tmp))
            print(f"{name} finished in {math.ceil(time.perf_counter() - started)} s", flush=True)


if __name__ == "__main__":
    main()
