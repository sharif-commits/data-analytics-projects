"""In-memory Bottom-Up Cube (BUC), after Beyer and Ramakrishnan (1999).

BUC computes an iceberg cube depth-first. It aggregates a partition, then for each remaining
dimension it splits the partition by value and recurses only into values that reach minsup.
A partition below minsup cannot contain a cell that reaches it, so the whole branch is skipped.

The partition step is a counting sort written with numpy (bincount plus a stable argsort).
No database or dataframe groupby takes part in the cube computation.
"""
import struct
from dataclasses import dataclass

import numpy as np

ALL = -1   # marks a dimension that is aggregated away in a cell


def cell_format(n_dims):
    """Binary layout of one output cell: one int16 code per dimension, then count and sum."""
    return struct.Struct(f"<{n_dims}hqq")


def cell_dtype(n_dims):
    """The same layout as a numpy dtype, for reading a cell file back."""
    return np.dtype([("cell", "<i2", (n_dims,)), ("count", "<i8"), ("sum", "<i8")])


def read_cells(path, n_dims):
    """Load a cell file into a structured array."""
    return np.fromfile(path, dtype=cell_dtype(n_dims))


class CellWriter:
    """Streams cells to a binary file through one fixed-size buffer."""

    def __init__(self, path, n_dims, buffer_bytes=1 << 20):
        self._format = cell_format(n_dims)
        self._capacity = max(1, buffer_bytes // self._format.size)
        self._buffer = bytearray(self._capacity * self._format.size)
        self._used = 0
        self._file = open(path, "wb", buffering=0)
        self.cells = 0

    def add(self, cell, count, total):
        self._format.pack_into(self._buffer, self._used * self._format.size, *cell, count, total)
        self._used += 1
        self.cells += 1
        if self._used == self._capacity:
            self.flush()

    def flush(self):
        if self._used:
            self._file.write(memoryview(self._buffer)[: self._used * self._format.size])
            self._used = 0

    def close(self):
        self.flush()
        self._file.close()


@dataclass
class BucStats:
    """Work counters for one in-memory run."""
    cells: int = 0
    partition_steps: int = 0    # (partition, dimension) pairs examined
    pruned_values: int = 0      # dimension values skipped because they fell below minsup
    sorts_skipped: int = 0      # steps where no value reached minsup, so no sort was needed


def expand_partition(codes, cards, measure, idx, start_dim, cell, minsup, writer, stats):
    """Emit the cell for rows `idx`, then recurse into each frequent value of later dimensions.

    The caller guarantees len(idx) >= minsup. `cell` holds the fixed values of this partition
    and is restored before returning.
    """
    total = int(measure[idx].sum()) if measure is not None else 0
    writer.add(cell, len(idx), total)

    for dim in range(start_dim, len(codes)):
        stats.partition_steps += 1
        column = codes[dim][idx]
        counts = np.bincount(column, minlength=cards[dim])
        frequent = np.flatnonzero(counts >= minsup)
        stats.pruned_values += int(np.count_nonzero(counts)) - len(frequent)
        if frequent.size == 0:
            stats.sorts_skipped += 1
            continue

        grouped = idx[np.argsort(column, kind="stable")]
        ends = np.cumsum(counts)
        for value in frequent.tolist():
            cell[dim] = value
            expand_partition(codes, cards, measure, grouped[ends[value] - counts[value]: ends[value]],
                             dim + 1, cell, minsup, writer, stats)
        cell[dim] = ALL


def buc_in_memory(data, dims, minsup, out_path, measure=None):
    """Compute the iceberg cube of `dims` and write it to `out_path`.

    data     CubeData holding the columns.
    dims     dimension names; their order is the processing order and the column order of the output.
    minsup   a cell is kept when COUNT(*) >= minsup. This test always uses the count.
    measure  None for COUNT only, or the name of an integer column to SUM alongside the count.
    """
    codes = [data.columns[d] for d in dims]
    cards = [data.cardinality(d) for d in dims]
    values = data.measures[measure] if measure else None
    stats = BucStats()
    writer = CellWriter(out_path, len(dims))
    if data.n_rows >= minsup:
        idx = np.arange(data.n_rows, dtype=np.int32)
        expand_partition(codes, cards, values, idx, 0, [ALL] * len(dims), minsup, writer, stats)
    writer.close()
    stats.cells = writer.cells
    return stats
