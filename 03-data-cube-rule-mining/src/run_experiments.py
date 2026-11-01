"""Part 2 -- experiment driver: correctness vs CUBE, scalability, and plots.

Running this script produces every Part 2 deliverable under
``part2/outputs``:

  1. ``correctness_inmem.csv`` / ``correctness_paged.csv``
     every group-by combination of the first 8 dimensions, computed by
     DuckDB ``GROUP BY CUBE`` AND by both BUC implementations, with a
     match flag per combination (exact cell-set + COUNT equality).
  2. ``benchmark_minsup.csv``   BUC runtime & cube size vs minsup.
  3. ``benchmark_dims.csv``     runtime & cube size vs #dimensions.
  4. ``benchmark_memory.csv``   paged BUC vs memory budget (spill I/O).
  5. ``benchmark_optimizations.csv`` effect of each optimization
     (dimension reordering, pre-count pruning, constant shortcut,
     node collapsing) on runtime / cells / calls.
  6. ``aoi_rules.csv``          AOI output (characteristic rules),
     ``aoi_thresholds.csv`` and ``buc_vs_aoi.csv`` comparison table.
  7. PNG plots for each of the above in ``outputs/plots/``.

Usage:  python run_experiments.py [--quick]
"""

from __future__ import annotations

import argparse
import statistics
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aoi import aoi, aoi_class_rules, load_hierarchies  # noqa: E402
from buc import buc_inmem, buc_optimized  # noqa: E402
from buc_paged import buc_paged  # noqa: E402
from cube_io import ListSink, cells_to_labels  # noqa: E402
from dataset import (  # noqa: E402
    CLASS_COLUMN,
    DEFAULT_DIMENSIONS,
    OUT_DIR,
    EncodedCube,
    encode,
    load_raw,
)

PLOT_DIR = OUT_DIR / "plots"
SPILL_DIR = OUT_DIR / "spill"
MIN_SUP_DEFAULT = 50


# ------------------------------------------------------------------ helpers
def _subcube(cube: EncodedCube, idxs: list[int]) -> EncodedCube:
    """A view of *cube* restricted to the dimension positions *idxs*."""
    return EncodedCube(
        codes=np.ascontiguousarray(cube.codes[:, idxs]),
        measure=cube.measure,
        dims=[cube.dims[i] for i in idxs],
        levels=[cube.levels[i] for i in idxs],
        cards=cube.cards[idxs],
        measure_name=cube.measure_name,
    )


def _cube_of(sink: ListSink, cube: EncodedCube) -> pd.DataFrame:
    """Materialise a BUC sink as a labelled DataFrame."""
    rows = cells_to_labels(sink.cells, cube.levels)
    return pd.DataFrame(rows, columns=cube.dims + ["count", "measure"])


def _duckdb_cube(df: pd.DataFrame, dims: list[str], minsup: int) -> pd.DataFrame:
    """Reference iceberg cube from DuckDB GROUP BY CUBE."""
    import duckdb

    group_cols = ", ".join(dims)
    sql = (
        f"SELECT {group_cols}, count(*) AS count FROM df "
        f"GROUP BY CUBE ({group_cols}) HAVING count(*) >= {minsup}"
    )
    out = duckdb.sql(sql).df()
    for c in dims:                                   # normalise NULLs to *
        out[c] = out[c].fillna("*").astype(str)
    return out


def _compare_with_duckdb(
    buc_df: pd.DataFrame, ref: pd.DataFrame, dims: list[str]
) -> tuple[bool, int, int, int]:
    """Cell-set equality between a BUC cube and the DuckDB reference."""
    a = buc_df.groupby(dims, as_index=False)["count"].sum()
    b = ref.groupby(dims, as_index=False)["count"].sum()
    m = a.merge(b, on=dims, how="outer", suffixes=("_a", "_b"), indicator=True)
    only_a = int((m["_merge"] == "left_only").sum())
    only_b = int((m["_merge"] == "right_only").sum())
    both = m[m["_merge"] == "both"]
    mismatched = int((both["count_a"] != both["count_b"]).sum())
    ok = only_a == 0 and only_b == 0 and mismatched == 0
    return ok, only_a, only_b, mismatched


# --------------------------------------------------- 1. correctness vs CUBE
def run_correctness(quick: bool) -> None:
    print("== 1. correctness: BUC (in-mem & paged) vs DuckDB CUBE ==")
    df = load_raw()
    dims = DEFAULT_DIMENSIONS[:5] if quick else DEFAULT_DIMENSIONS[:8]
    cube = encode(df, dims)
    ref = _duckdb_cube(df, dims, MIN_SUP_DEFAULT)
    print(f"  DuckDB CUBE over {len(dims)} dims @minsup>={MIN_SUP_DEFAULT}: "
          f"{len(ref)} cells")

    combos = [
        c for r in range(1, len(dims) + 1) for c in combinations(dims, r)
    ]
    rows = []
    for combo in combos:
        cl = list(combo)
        idxs = [dims.index(c) for c in cl]
        sub = _subcube(cube, idxs)
        a = ListSink()
        buc_inmem(sub, MIN_SUP_DEFAULT, a)
        a_df = _cube_of(a, sub)
        # reference for this combo = full-cube rows with all other dims ALL
        outside = [d for d in dims if d not in cl]
        ref_sub = ref[(ref[outside] == "*").all(axis=1)] if outside else ref
        ok, oa, ob, mm = _compare_with_duckdb(a_df, ref_sub, cl)
        rows.append(
            {
                "dimensions": " | ".join(cl),
                "n_dims": len(cl),
                "buc_cells": len(a_df),
                "duckdb_cells": len(ref_sub),
                "only_in_buc": oa,
                "only_in_duckdb": ob,
                "count_mismatches": mm,
                "match": ok,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "correctness_inmem.csv", index=False)
    n_ok = int(out["match"].sum())
    print(f"  in-mem BUC: {n_ok}/{len(out)} combinations match DuckDB CUBE")

    # --- paged BUC on a spread of the same combos ------------------------
    rows = []
    for combo in combos[:: max(1, len(combos) // 12)]:
        cl = list(combo)
        idxs = [dims.index(c) for c in cl]
        sub = _subcube(cube, idxs)
        b = ListSink()
        buc_paged(sub, MIN_SUP_DEFAULT, b, page_rows=8192,
                  mem_budget_bytes=256 * 1024, spill_dir=SPILL_DIR)
        b_df = _cube_of(b, sub)
        outside = [d for d in dims if d not in cl]
        ref_sub = ref[(ref[outside] == "*").all(axis=1)] if outside else ref
        ok, oa, ob, mm = _compare_with_duckdb(b_df, ref_sub, cl)
        rows.append(
            {
                "dimensions": " | ".join(cl),
                "n_dims": len(cl),
                "buc_cells": len(b_df),
                "duckdb_cells": len(ref_sub),
                "only_in_buc": oa,
                "only_in_duckdb": ob,
                "count_mismatches": mm,
                "match": ok,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "correctness_paged.csv", index=False)
    print(f"  paged BUC:  {int(out['match'].sum())}/{len(out)} "
          f"spot-checked combinations match DuckDB CUBE")


# ------------------------------------------------- 2. scalability benchmarks
def run_minsup_benchmark(quick: bool) -> None:
    print("== 2. benchmark: runtime vs minimum support ==")
    df = load_raw()
    dims = DEFAULT_DIMENSIONS[:8]
    cube = encode(df, dims)
    minsups = [5, 10, 25, 50, 100, 250, 500, 1000] if not quick else [50, 100]
    rows = []
    for ms in minsups:
        a, b = ListSink(), ListSink()
        s1 = buc_inmem(cube, ms, a)
        s2 = buc_paged(cube, ms, b, mem_budget_bytes=256 * 1024,
                       spill_dir=SPILL_DIR)
        rows.append(
            {
                "minsup": ms,
                "inmem_elapsed_s": round(s1.elapsed, 3),
                "inmem_cells": s1.cells,
                "paged_elapsed_s": round(s2.elapsed, 3),
                "paged_cells": s2.cells,
            }
        )
        print(f"  minsup={ms:5d}  in-mem={s1.elapsed:7.2f}s "
              f"({s1.cells:6d} cells)  paged={s2.elapsed:7.2f}s "
              f"({s2.cells:6d} cells)")
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "benchmark_minsup.csv", index=False)
    _plot(out, "minsup", ["inmem_elapsed_s", "paged_elapsed_s"],
          ["BUC in-memory", "BUC out-of-core (256 KB budget)"],
          "Runtime vs minimum support (8 dimensions)",
          "minsup_runtime.png", logx=True)
    _plot(out, "minsup", ["inmem_cells", "paged_cells"],
          ["BUC in-memory", "BUC out-of-core"],
          "Iceberg cube size vs minimum support",
          "minsup_cells.png", logx=True)


def run_dims_benchmark(quick: bool) -> None:
    print("== 3. benchmark: runtime vs number of dimensions ==")
    df = load_raw()
    cube = encode(df, DEFAULT_DIMENSIONS[:12])
    rows = []
    max_d = 10 if not quick else 6
    for n in range(2, max_d + 1):
        sub = cube.slice_dims(n)
        a = ListSink()
        s1 = buc_inmem(sub, MIN_SUP_DEFAULT, a)
        rows.append(
            {
                "n_dims": n,
                "dims": ", ".join(sub.dims),
                "elapsed_s": round(s1.elapsed, 3),
                "cells": s1.cells,
                "calls": s1.calls,
                "rows_sorted": s1.rows_sorted,
                "pruned_partitions": s1.pruned_partitions,
            }
        )
        print(f"  {n:2d} dims  {s1.elapsed:8.2f}s  cells={s1.cells:7d} "
              f"calls={s1.calls:8d}")
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "benchmark_dims.csv", index=False)
    _plot(out, "n_dims", ["elapsed_s"], ["BUC in-memory (minsup=50)"],
          "Runtime vs number of dimensions", "dims_runtime.png")
    _plot(out, "n_dims", ["cells", "calls"],
          ["iceberg cells", "BUC recursive calls"],
          "Work vs number of dimensions", "dims_cells.png", logy=True)


def run_memory_benchmark(quick: bool) -> None:
    print("== 4. benchmark: paged BUC vs memory budget ==")
    df = load_raw()
    dims = DEFAULT_DIMENSIONS[:8]
    cube = encode(df, dims)
    budgets = (
        [64 * 2**10, 128 * 2**10, 256 * 2**10, 512 * 2**10,
         1 * 2**20, 2 * 2**20, 8 * 2**20]
        if not quick else [128 * 2**10, 1 * 2**20]
    )
    rows = []
    for budget in budgets:
        b = ListSink()
        s = buc_paged(cube, MIN_SUP_DEFAULT, b, mem_budget_bytes=budget,
                      spill_dir=SPILL_DIR)
        rows.append(
            {
                "budget_kb": budget / 1024,
                "elapsed_s": round(s.elapsed, 3),
                "pages_read": s.pages_read,
                "io_mb_read": round(s.io_bytes_read / 2**20, 1),
                "io_mb_written": round(s.io_bytes_written / 2**20, 1),
                "temp_files": s.temp_files,
                "disk_children": s.disk_children,
                "mem_children": s.mem_children,
                "cells": s.cells,
            }
        )
        print(f"  budget={budget / 1024:7.0f}KB  {s.elapsed:7.2f}s  "
              f"reads={s.pages_read:6d} "
              f"({s.io_bytes_read / 2**20:7.1f}MB)  "
              f"disk_children={s.disk_children}")
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "benchmark_memory.csv", index=False)
    _plot(out, "budget_kb", ["elapsed_s"], ["out-of-core BUC"],
          "Runtime vs memory budget (8 dimensions, minsup=50)",
          "memory_runtime.png", logx=True)
    _plot(out, "budget_kb", ["io_mb_read"],
          ["temporary-file I/O read (MB)"],
          "Spill I/O vs memory budget", "memory_io.png", logx=True)


def run_optimization_benchmark(quick: bool) -> None:
    print("== 5. benchmark: contribution of each optimization ==")
    df = load_raw()
    dims = DEFAULT_DIMENSIONS[:8]
    cube = encode(df, dims)
    configs = {
        "none": dict(reorder=False, precount_prune=False,
                     constant_shortcut=False, collapse=False),
        "+reorder": dict(reorder=True, precount_prune=False,
                         constant_shortcut=False, collapse=False),
        "+precount prune": dict(reorder=True, precount_prune=True,
                                constant_shortcut=False, collapse=False),
        "+constant shortcut": dict(reorder=True, precount_prune=True,
                                   constant_shortcut=True, collapse=False),
        "+collapse (all)": dict(reorder=True, precount_prune=True,
                                constant_shortcut=True, collapse=True),
    }
    repeats = 1 if quick else 3          # median-of-N for stable timings
    rows = []
    for name, kw in configs.items():
        times = []
        s = None
        for _ in range(repeats):
            a = ListSink()
            s = buc_optimized(cube, MIN_SUP_DEFAULT, a, **kw)
            times.append(s.elapsed)
        elapsed = statistics.median(times) if times else s.elapsed
        rows.append(
            {
                "configuration": name,
                "elapsed_s": round(elapsed, 3),
                "elapsed_runs_s": ";".join(f"{t:.2f}" for t in times),
                "cells": s.cells,
                "calls": s.calls,
                "partitions": s.partitions,
                "rows_sorted": s.rows_sorted,
                "pruned_partitions": s.pruned_partitions,
                "skipped_sorts": s.skipped_sorts,
                "constant_shortcuts": s.constant_shortcuts,
                "collapsed_nodes": s.collapsed_nodes,
            }
        )
        print(f"  {name:20s} {elapsed:7.2f}s  cells={s.cells:7d}  "
              f"calls={s.calls:8d}"
              + (f"  runs={[round(t, 2) for t in times]}" if repeats > 1
                 else ""))
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "benchmark_optimizations.csv", index=False)
    _bars(out, "configuration", ["elapsed_s"], ["runtime (s, median of 3)"],
          "Runtime by optimization configuration (8 dims, minsup=50)",
          "optimizations_runtime.png")


# ------------------------------------------------------ 6. AOI + comparison
def run_aoi(quick: bool) -> None:
    print("== 6. AOI characteristic rules + BUC vs AOI comparison ==")
    df = load_raw()
    hier = load_hierarchies()
    attrs = [a for a in ["education", "class_of_worker", "marital_status",
                         "age_group", "race", "sex"] if a in hier]
    target, contrast = ">50K", "<=50K"
    print(f"  class-comparison AOI on {CLASS_COLUMN}: "
          f"target={target}, contrast={contrast}")
    rules, stats = aoi_class_rules(
        df, {a: hier[a] for a in attrs}, CLASS_COLUMN, target, contrast,
        attr_threshold=12, max_relations=40,
    )
    rules.to_csv(OUT_DIR / "aoi_rules.csv", index=False)
    print(f"  AOI: {stats.n_tuples_in} tuples -> {len(rules)} rules "
          f"({stats.climb_steps} climbs, {stats.generalisations} value "
          f"generalisations, {stats.elapsed:.2f}s)")
    with pd.option_context("display.width", 220, "display.max_colwidth", 36):
        print(rules.to_string(index=False))

    # whole-population characteristic rules (no class split), for reference
    out, _stats = aoi(df, {a: hier[a] for a in attrs},
                      attr_threshold=12, max_relations=40)
    out.to_csv(OUT_DIR / "aoi_char_rules_population.csv", index=False)

    # BUC on the same attributes for the comparison table
    cube = encode(df, attrs)
    a = ListSink()
    s = buc_inmem(cube, MIN_SUP_DEFAULT, a)
    b = ListSink()
    sp = buc_paged(cube, MIN_SUP_DEFAULT, b, mem_budget_bytes=256 * 1024,
                   spill_dir=SPILL_DIR)

    comp = pd.DataFrame(
        [
            {"aspect": "input tuples", "buc_inmem": len(df),
             "buc_paged": len(df), "aoi": len(df)},
            {"aspect": "output rows", "buc_inmem": s.cells,
             "buc_paged": sp.cells, "aoi": len(out)},
            {"aspect": "runtime (s)", "buc_inmem": round(s.elapsed, 2),
             "buc_paged": round(sp.elapsed, 2),
             "aoi": round(stats.elapsed, 2)},
            {"aspect": "output bounded by", "buc_inmem": "minsup",
             "buc_paged": "minsup", "aoi": "max_relations"},
            {"aspect": "needs concept hierarchies", "buc_inmem": "no",
             "buc_paged": "no", "aoi": "yes"},
            {"aspect": "exact iceberg counts", "buc_inmem": "yes",
             "buc_paged": "yes", "aoi": "yes (per rule)"},
            {"aspect": "out-of-core (disk spill)", "buc_inmem": "no",
             "buc_paged": "yes", "aoi": "no"},
        ]
    )
    comp.to_csv(OUT_DIR / "buc_vs_aoi.csv", index=False)
    print(comp.to_string(index=False))

    # threshold sensitivity for AOI
    rows = []
    for mr in ([5, 10, 20, 50] if not quick else [10, 20]):
        o2, st2 = aoi(df, {a: hier[a] for a in attrs},
                      attr_threshold=12, max_relations=mr)
        rows.append({"max_relations": mr, "tuples_out": len(o2),
                     "climb_steps": st2.climb_steps,
                     "generalisations": st2.generalisations,
                     "elapsed_s": round(st2.elapsed, 3)})
        print(f"  max_relations={mr:3d} -> {len(o2):2d} rules, "
              f"{st2.climb_steps} climbs, {st2.elapsed:.2f}s")
    pd.DataFrame(rows).to_csv(OUT_DIR / "aoi_thresholds.csv", index=False)


# ------------------------------------------------------------------ plots
def _plot(df, x, ys, labels, title, fname, logx=False, logy=False):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for y, lab in zip(ys, labels):
        ax.plot(df[x], df[y], marker="o", label=lab)
    if logx:
        ax.set_xscale("log")
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(x)
    ax.set_ylabel(ys[0] if len(ys) == 1 else "value")
    ax.set_title(title, fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  plot -> plots/{fname}")


def _bars(df, x, ys, labels, title, fname):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.2))
    xpos = np.arange(len(df))
    for i, (y, lab) in enumerate(zip(ys, labels)):
        ax.bar(xpos + i * 0.4, df[y], width=0.4, label=lab)
    ax.set_xticks(xpos)
    ax.set_xticklabels(df[x], rotation=20, ha="right")
    ax.set_ylabel(ys[0])
    ax.set_title(title, fontsize=11)
    ax.grid(alpha=0.3, axis="y")
    ax.legend()
    fig.tight_layout()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_DIR / fname, dpi=150)
    plt.close(fig)
    print(f"  plot -> plots/{fname}")


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="smaller grids for a fast smoke run")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SPILL_DIR.mkdir(parents=True, exist_ok=True)

    run_correctness(args.quick)
    run_minsup_benchmark(args.quick)
    run_dims_benchmark(args.quick)
    run_memory_benchmark(args.quick)
    run_optimization_benchmark(args.quick)
    run_aoi(args.quick)

    print(f"\nall experiments complete -> {OUT_DIR}")


if __name__ == "__main__":
    main()