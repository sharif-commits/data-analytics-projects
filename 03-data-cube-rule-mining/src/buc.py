"""Part 2 -- Bottom-Up Computation (BUC), in-memory.

Two implementations live here:

``buc_inmem``      the straightforward, textbook BUC of Beyer & Ramakrishnan
                   (SIGMOD'99).  Assumes the whole relation and the whole
                   iceberg cube fit in main memory.  This is the baseline
                   that the optimised version and the out-of-core version
                   are both checked against.

``buc_optimized``  the same algorithm plus four optimisations, each
                   individually switchable so the report can show an
                   ablation rather than one opaque "it got faster" number.

Neither function uses a database engine or a dataframe ``groupby``: the only
primitives are ``numpy.bincount`` (aggregation) and a radix/counting sort
(partitioning), exactly as the algorithm specifies.

--------------------------------------------------------------------------
The algorithm
--------------------------------------------------------------------------
BUC computes the iceberg cube depth-first, from the apex cell ``(*,...,*)``
downwards, fixing dimensions in *increasing index order* so that every cell
is produced exactly once::

    BUC(input, dim):
        write out aggregate(input)                  # the current cell
        for d in dim .. D-1:
            Partition(input, d)                     # counting sort on dim d
            for each partition p of input on d:
                if |p| >= minsup:                   # iceberg / Apriori prune
                    BUC(p, d + 1)

The prune is what makes it an *iceberg* cube: because COUNT is monotone, a
partition below ``minsup`` can contain no qualifying descendant, so the whole
subtree is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from cube_io import ALL, Sink, counting_sort_partition


# --------------------------------------------------------------------- stats
@dataclass
class BUCStats:
    """Instrumentation, so the performance discussion can cite real counters."""

    cells: int = 0                  # cube cells written out
    calls: int = 0                  # recursive BUC invocations
    partitions: int = 0             # Partition() calls == counting sorts done
    rows_sorted: int = 0            # rows moved by those sorts (the real cost)
    pruned_partitions: int = 0      # partitions rejected by minsup
    skipped_sorts: int = 0          # O2: sorts avoided by counting first
    constant_shortcuts: int = 0     # O3: dimension constant on the partition
    collapsed_nodes: int = 0        # O4: homogeneous partitions collapsed
    collapsed_cells: int = 0        # cells emitted by those collapses
    elapsed: float = 0.0
    dim_order: tuple[int, ...] = ()
    options: dict = field(default_factory=dict)

    def as_row(self) -> dict:
        return {
            "cells": self.cells,
            "calls": self.calls,
            "partitions": self.partitions,
            "rows_sorted": self.rows_sorted,
            "pruned_partitions": self.pruned_partitions,
            "skipped_sorts": self.skipped_sorts,
            "constant_shortcuts": self.constant_shortcuts,
            "collapsed_nodes": self.collapsed_nodes,
            "collapsed_cells": self.collapsed_cells,
            "elapsed_s": round(self.elapsed, 4),
        }


# ==================================================================== BASE
def buc_inmem(cube, minsup: int, sink: Sink) -> BUCStats:
    """Straightforward in-memory BUC producing the iceberg cube.

    Parameters
    ----------
    cube    : EncodedCube -- the dimension list (``cube.dims``), the measure
              column (``cube.measure``) and the integer-coded relation.
    minsup  : minimum support; a cell is written out only if its COUNT is
              at least this value.
    sink    : receives every qualifying cell as ``(cell, count, measure_sum)``
              where ``cell[d] == ALL`` means "aggregated over dimension d".

    Returns the instrumentation record; the cube itself goes to *sink*.
    """
    codes: np.ndarray = cube.codes
    measure: np.ndarray = cube.measure
    cards = cube.cards
    n_dims = cube.n_dims

    # a measure of all ones means COUNT -- the sum is then free
    count_measure = bool(np.all(measure == 1.0))

    stats = BUCStats(dim_order=tuple(range(n_dims)),
                     options={"variant": "baseline"})
    cell = np.full(n_dims, ALL, dtype=np.int64)

    def aggregate(rows: np.ndarray) -> float:
        return float(rows.size) if count_measure else float(measure[rows].sum())

    def recurse(rows: np.ndarray, dim: int) -> None:
        stats.calls += 1
        for d in range(dim, n_dims):
            col = codes[rows, d]

            # ---- Partition: counting sort the partition on dimension d ----
            order, starts = counting_sort_partition(col, int(cards[d]))
            sorted_rows = rows[order]
            stats.partitions += 1
            stats.rows_sorted += rows.size

            # ---- one cell per non-empty partition that clears minsup ------
            for v in range(int(cards[d])):
                lo, hi = starts[v], starts[v + 1]
                size = hi - lo
                if size == 0:
                    continue
                if size < minsup:
                    stats.pruned_partitions += 1
                    continue
                part = sorted_rows[lo:hi]
                cell[d] = v
                sink.emit(cell, int(size), aggregate(part))
                stats.cells += 1
                recurse(part, d + 1)
                cell[d] = ALL

    t0 = perf_counter()
    all_rows = np.arange(cube.n_rows, dtype=np.int64)
    if all_rows.size >= minsup:                     # the apex cell (*,...,*)
        sink.emit(cell, int(all_rows.size), aggregate(all_rows))
        stats.cells += 1
        recurse(all_rows, 0)
    stats.elapsed = perf_counter() - t0
    return stats


# =============================================================== OPTIMISED
def buc_optimized(
    cube,
    minsup: int,
    sink: Sink,
    *,
    reorder: bool = True,
    precount_prune: bool = True,
    constant_shortcut: bool = True,
    collapse: bool = True,
    collapse_max_rows: int | None = None,
) -> BUCStats:
    """BUC with four optimisations layered on the baseline.

    O1 ``reorder`` -- **dimension reordering by descending cardinality.**
        The headline optimisation.  BUC fixes dimensions in index order, so
        the dimension placed first is partitioned once, the second is
        partitioned once per surviving partition of the first, and so on.
        For an *iceberg* cube the best order is the opposite of the classic
        advice: putting the *high*-cardinality dimensions first makes each
        partition small early, so the `minsup` test prunes whole subtrees
        before they are ever sorted (fewer rows sorted, fewer partitions).
        Output is unaffected: the set of cells is identical, only the order
        in which they are produced changes (the emitted `cell` is always
        written back in the caller's original dimension order).

    O2 ``precount_prune`` -- **count before you sort.**  The baseline sorts
        the partition and only then discovers that no group reaches minsup.
        ``np.bincount`` answers that question in one linear pass with no data
        movement, so the counting sort can be skipped entirely.

    O3 ``constant_shortcut`` -- if a dimension takes a single value across
        the whole partition, its only child partition *is* the parent, so
        the sort is pure overhead: emit and recurse on the same rows.

    O4 ``collapse`` -- **homogeneous-partition collapsing.**  If every
        remaining dimension is constant on the partition, then all 2^k - 1
        descendant cells have exactly the same aggregate, so they can be
        enumerated directly instead of via 2^k recursive calls and sorts.
        Checked only for partitions of at most ``collapse_max_rows`` rows
        (default ``50 * minsup``), because that is where homogeneity is
        common and the check is cheap.
    """
    n_dims = cube.n_dims
    cards = cube.cards
    measure = cube.measure
    count_measure = bool(np.all(measure == 1.0))

    # ---- O1: permute the dimension columns, descending cardinality -------
    if reorder:
        perm = np.argsort(-cards, kind="stable")
    else:
        perm = np.arange(n_dims)
    codes = np.ascontiguousarray(cube.codes[:, perm])
    cards_p = cards[perm]
    # position j in the permuted relation corresponds to original dimension
    # perm[j]; writing straight into cell[perm[j]] means the sink always sees
    # cells in the caller's dimension order.
    orig = [int(x) for x in perm]

    if collapse_max_rows is None:
        collapse_max_rows = max(50 * minsup, 1024)

    stats = BUCStats(
        dim_order=tuple(orig),
        options={
            "variant": "optimized",
            "reorder": reorder,
            "precount_prune": precount_prune,
            "constant_shortcut": constant_shortcut,
            "collapse": collapse,
            "collapse_max_rows": collapse_max_rows,
        },
    )
    cell = np.full(n_dims, ALL, dtype=np.int64)

    def aggregate(rows: np.ndarray) -> float:
        return float(rows.size) if count_measure else float(measure[rows].sum())

    def emit_all_subsets(rows: np.ndarray, dim: int) -> None:
        """O4 helper: every non-empty subset of the remaining dimensions."""
        rem = list(range(dim, n_dims))
        k = len(rem)
        size = int(rows.size)
        agg = aggregate(rows)
        first_value = codes[rows[0]]
        for mask in range(1, 1 << k):
            touched = []
            for i in range(k):
                if mask >> i & 1:
                    j = rem[i]
                    cell[orig[j]] = int(first_value[j])
                    touched.append(orig[j])
            sink.emit(cell, size, agg)
            for od in touched:
                cell[od] = ALL
        stats.collapsed_nodes += 1
        stats.collapsed_cells += (1 << k) - 1
        stats.cells += (1 << k) - 1

    def recurse(rows: np.ndarray, dim: int) -> None:
        stats.calls += 1

        # ---- O4: is the partition homogeneous on every remaining dim? ----
        if collapse and dim < n_dims and rows.size <= collapse_max_rows:
            block = codes[rows][:, dim:]
            if bool((block == block[0]).all()):
                emit_all_subsets(rows, dim)
                return

        for d in range(dim, n_dims):
            col = codes[rows, d]
            card = int(cards_p[d])

            # ---- O2: count first; skip the sort when nothing qualifies ----
            if precount_prune or constant_shortcut:
                counts = np.bincount(col, minlength=card)
                qualifying = np.nonzero(counts >= minsup)[0]

                if precount_prune and qualifying.size == 0:
                    stats.skipped_sorts += 1
                    stats.pruned_partitions += int(np.count_nonzero(counts))
                    continue

                # ---- O3: single value on this dimension -> child == parent
                if (constant_shortcut and qualifying.size == 1
                        and counts[qualifying[0]] == rows.size):
                    v = int(qualifying[0])
                    stats.constant_shortcuts += 1
                    cell[orig[d]] = v
                    sink.emit(cell, int(rows.size), aggregate(rows))
                    stats.cells += 1
                    recurse(rows, d + 1)
                    cell[orig[d]] = ALL
                    continue

            # ---- Partition (counting sort) --------------------------------
            order, starts = counting_sort_partition(col, card)
            sorted_rows = rows[order]
            stats.partitions += 1
            stats.rows_sorted += rows.size

            for v in range(card):
                lo, hi = starts[v], starts[v + 1]
                size = hi - lo
                if size == 0:
                    continue
                if size < minsup:
                    stats.pruned_partitions += 1
                    continue
                part = sorted_rows[lo:hi]
                cell[orig[d]] = v
                sink.emit(cell, int(size), aggregate(part))
                stats.cells += 1
                recurse(part, d + 1)
                cell[orig[d]] = ALL

    t0 = perf_counter()
    all_rows = np.arange(cube.n_rows, dtype=np.int64)
    if all_rows.size >= minsup:
        sink.emit(cell, int(all_rows.size), aggregate(all_rows))
        stats.cells += 1
        recurse(all_rows, 0)
    stats.elapsed = perf_counter() - t0
    return stats
