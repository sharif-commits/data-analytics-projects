"""Part 2 -- out-of-core (paged) BUC.

The in-memory versions assume the whole relation (and every partition)
fits in RAM.  This one does not: the relation lives in temporary binary
files on disk and is processed one fixed-size page at a time, following
the limited-memory scheme of Beyer & Ramakrishnan (SIGMOD'99, Sec. 5).
Only O(page_rows + mem_budget) rows are ever resident.

External partitioning, two passes per dimension (the classic scheme):

  pass 1  count the values of dimension d page by page (np.bincount),
          which also yields the per-value measure sums -- no data movement
          and no sorting;
  pass 2  re-read the pages and route every row to the partition of its
          value, so each child partition is materialised on disk.

Two refinements:

  * column pruning -- a child partition stores only the *remaining*
    columns (d+1 .. D-1); columns already fixed by the recursion are dead
    weight, and dropping them shrinks both passes;

  * hybrid recursion -- a child whose row count fits the memory budget is
    finished with the in-memory BUC on that block (routed through an
    `OffsetSink` so the sink still sees full-width cells).  Only
    partitions larger than the budget are written to disk and recursed
    externally, which keeps the number of temporary files tiny while the
    *worst-case* memory stays bounded by the budget.

The emitted cells are identical to `buc.buc_inmem` (same counts, same
measures, same cell values), which `verify_duckdb.py` asserts by
fingerprint against both the in-memory BUC and a SQL CUBE.
"""

from __future__ import annotations

import itertools
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from buc import BUCStats, buc_inmem
from cube_io import ALL, Sink
from dataset import EncodedCube


# --------------------------------------------------------------------- stats
@dataclass
class PagedStats(BUCStats):
    """BUCStats plus the external-memory counters."""

    pages_read: int = 0
    io_bytes_read: int = 0
    io_bytes_written: int = 0
    temp_files: int = 0
    disk_children: int = 0        # partitions recursed externally
    mem_children: int = 0         # partitions finished in memory (hybrid)
    page_rows: int = 0
    mem_budget_rows: int = 0

    def as_row(self) -> dict:
        row = super().as_row()
        row.update(
            pages_read=self.pages_read,
            io_mb_read=round(self.io_bytes_read / 2**20, 2),
            io_mb_written=round(self.io_bytes_written / 2**20, 2),
            temp_files=self.temp_files,
            disk_children=self.disk_children,
            mem_children=self.mem_children,
            page_rows=self.page_rows,
            mem_budget_rows=self.mem_budget_rows,
        )
        return row


# ---------------------------------------------------------------- spill file
class SpillFile:
    """Append-only relation on disk: int32 codes (+ optional float64 measure)."""

    def __init__(self, base: Path, n_cols: int, with_measure: bool):
        self.base = Path(base)
        self.n_cols = n_cols
        self.with_measure = with_measure
        self.codes_fh = open(str(self.base) + ".codes.bin", "w+b")
        self.measure_fh = (
            open(str(self.base) + ".meas.bin", "w+b") if with_measure else None
        )
        self.n_rows = 0
        self.bytes_written = 0

    def append(self, codes: np.ndarray, measure: np.ndarray | None) -> None:
        codes = np.ascontiguousarray(codes, dtype=np.int32)
        buf = codes.tobytes()
        self.codes_fh.write(buf)
        self.bytes_written += len(buf)
        if self.measure_fh is not None:
            if measure is None:
                raise ValueError("measure required for this spill file")
            mbuf = np.ascontiguousarray(measure, dtype=np.float64).tobytes()
            self.measure_fh.write(mbuf)
            self.bytes_written += len(mbuf)
        self.n_rows += codes.shape[0]

    def iter_pages(self, page_rows: int):
        """Yield (codes_page, measure_page) sequentially from the start."""
        self.codes_fh.seek(0)
        if self.measure_fh is not None:
            self.measure_fh.seek(0)
        item = np.dtype(np.int32).itemsize
        while True:
            buf = self.codes_fh.read(page_rows * self.n_cols * item)
            if not buf:
                break
            codes = np.frombuffer(buf, dtype=np.int32).reshape(-1, self.n_cols)
            meas = None
            if self.measure_fh is not None:
                mbuf = self.measure_fh.read(codes.shape[0] * 8)
                meas = np.frombuffer(mbuf, dtype=np.float64)
            yield codes, meas

    def remove(self) -> None:
        self.codes_fh.close()
        if self.measure_fh is not None:
            self.measure_fh.close()
        for suffix in (".codes.bin", ".meas.bin"):
            try:
                Path(str(self.base) + suffix).unlink()
            except FileNotFoundError:
                pass


class DiskSrc:
    """A partition backed by a SpillFile."""

    def __init__(self, spill: SpillFile):
        self.spill = spill

    def pages(self, page_rows: int):
        yield from self.spill.iter_pages(page_rows)


class MemSrc:
    """A partition already resident in memory (hybrid path)."""

    def __init__(self, codes: np.ndarray, measure: np.ndarray | None):
        self.codes = codes
        self.measure = measure

    def pages(self, page_rows: int):
        for lo in range(0, self.codes.shape[0], page_rows):
            hi = lo + page_rows
            yield (
                self.codes[lo:hi],
                None if self.measure is None else self.measure[lo:hi],
            )


class OffsetSink(Sink):
    """Shows a sub-BUC over dims len(prefix)..D-1 as full-width cells."""

    def __init__(self, inner: Sink, prefix: tuple[int, ...]):
        self.inner = inner
        self.prefix = prefix
        self.n_cells = 0

    def emit(self, cell, count: int, measure: float) -> None:
        full = list(self.prefix) + [int(x) for x in cell]
        self.inner.emit(full, count, measure)
        self.n_cells += 1


# ------------------------------------------------------------------ the algo
def buc_paged(
    cube,
    minsup: int,
    sink: Sink,
    *,
    page_rows: int = 16384,
    mem_budget_bytes: int = 8 * 2**20,
    spill_dir: str | Path | None = None,
) -> PagedStats:
    """Out-of-core BUC producing the same iceberg cube as `buc_inmem`.

    ``mem_budget_bytes`` bounds the rows buffered for in-memory recursion
    (the hybrid path); anything larger is spilled and recursed externally.
    ``page_rows`` is the I/O granularity of every pass.
    """
    minsup = max(1, int(minsup))
    D = cube.n_dims
    cards = [int(c) for c in cube.cards]
    count_measure = bool(np.all(cube.measure == 1.0))
    row_bytes = D * 4 + (0 if count_measure else 8)
    budget_rows = max(1, mem_budget_bytes // max(row_bytes, 1))

    tmp = Path(spill_dir) if spill_dir else Path(tempfile.mkdtemp(prefix="buc_paged_"))
    tmp.mkdir(parents=True, exist_ok=True)

    stats = PagedStats(
        page_rows=page_rows,
        mem_budget_rows=budget_rows,
        options={
            "variant": "paged",
            "page_rows": page_rows,
            "mem_budget_mb": round(mem_budget_bytes / 2**20, 2),
            "count_measure": count_measure,
        },
    )
    seq = itertools.count()
    cell = np.full(D, ALL, dtype=np.int64)

    def new_spill(n_cols: int) -> SpillFile:
        stats.temp_files += 1
        return SpillFile(tmp / f"part_{next(seq):06d}", n_cols,
                         with_measure=not count_measure)

    def pages_of(src):
        for codes, meas in src.pages(page_rows):
            stats.pages_read += 1
            stats.io_bytes_read += codes.nbytes + (0 if meas is None else meas.nbytes)
            yield codes, meas

    def handle(src, dim: int) -> None:
        """src holds columns dim..D-1; local column j is global dim+j."""
        stats.calls += 1
        for d in range(dim, D):
            card = cards[d]
            local = d - dim
            counts = np.zeros(card, dtype=np.int64)
            sums = (None if count_measure else np.zeros(card, dtype=np.float64))
            for codes, meas in pages_of(src):                     # ---- pass 1
                col = codes[:, local]
                counts += np.bincount(col, minlength=card)
                if sums is not None:
                    sums += np.bincount(col, weights=meas, minlength=card)
            stats.partitions += 1

            qualifying = np.nonzero(counts >= minsup)[0]
            if qualifying.size == 0:
                stats.pruned_partitions += int(np.count_nonzero(counts))
                continue

            def agg_of(v: int) -> float:
                return float(counts[v]) if count_measure else float(sums[v])

            if d == D - 1:            # last dimension: nothing to recurse
                for v in qualifying:
                    cell[d] = int(v)
                    sink.emit(cell, int(counts[v]), agg_of(int(v)))
                    stats.cells += 1
                    cell[d] = ALL
                continue

            # ---- decide per value: finish in memory or spill to disk ----
            small: dict[int, bool] = {}
            buffered = 0
            for v in qualifying:
                vi = int(v)
                if counts[vi] <= budget_rows and buffered + counts[vi] <= budget_rows:
                    small[vi] = True
                    buffered += int(counts[vi])
                else:
                    small[vi] = False

            buffers: dict[int, tuple[list, list]] = {
                int(v): ([], []) for v in qualifying if small[int(v)]
            }
            children: dict[int, SpillFile] = {}
            for codes, meas in pages_of(src):                     # ---- pass 2
                if codes.shape[0] == 0:
                    continue
                col = codes[:, local]
                for v in qualifying:
                    vi = int(v)
                    idx = np.nonzero(col == vi)[0]
                    if idx.size == 0:
                        continue
                    stats.rows_sorted += idx.size
                    if small[vi]:
                        buffers[vi][0].append(codes[idx, local + 1:])
                        if meas is not None:
                            buffers[vi][1].append(meas[idx])
                    else:
                        if vi not in children:
                            children[vi] = new_spill(D - d - 1)
                        children[vi].append(
                            codes[idx, local + 1:],
                            None if meas is None else meas[idx],
                        )

            for v in qualifying:
                vi = int(v)
                cell[d] = vi
                if small[vi]:
                    # hybrid: run the in-memory BUC on the buffered block
                    stats.mem_children += 1
                    cbuf, mbuf = buffers[vi]
                    sub_codes = (np.concatenate(cbuf) if cbuf
                                 else np.empty((0, D - d - 1), dtype=np.int32))
                    sub_codes = np.ascontiguousarray(sub_codes, dtype=np.int32)
                    if count_measure:
                        sub_meas = np.ones(1, dtype=np.float64)   # count-only
                    else:
                        sub_meas = (np.concatenate(mbuf) if mbuf
                                    else np.empty(0, dtype=np.float64))
                    sub_cube = EncodedCube(
                        codes=sub_codes,
                        measure=sub_meas,
                        dims=cube.dims[d + 1:],
                        levels=cube.levels[d + 1:],
                        cards=cube.cards[d + 1:],
                        measure_name=cube.measure_name,
                    )
                    prefix = tuple(int(x) for x in cell[: d + 1])
                    sub = buc_inmem(sub_cube, minsup, OffsetSink(sink, prefix))
                    stats.cells += sub.cells
                    stats.calls += sub.calls
                    stats.partitions += sub.partitions
                    stats.rows_sorted += sub.rows_sorted
                    stats.pruned_partitions += sub.pruned_partitions
                else:
                    stats.disk_children += 1
                    sink.emit(cell, int(counts[vi]), agg_of(vi))
                    stats.cells += 1
                    handle(DiskSrc(children[vi]), d + 1)
                    children[vi].remove()
                cell[d] = ALL

    t0 = perf_counter()
    # ---- root relation: always materialised on disk first ----------------
    root = new_spill(D)
    for lo in range(0, cube.n_rows, page_rows):
        root.append(
            cube.codes[lo:lo + page_rows],
            None if count_measure else cube.measure[lo:lo + page_rows],
        )
    total = float(cube.n_rows) if count_measure else float(cube.measure.sum())

    if cube.n_rows >= minsup:                                     # apex cell
        sink.emit(cell, int(cube.n_rows), total)
        stats.cells += 1
        handle(DiskSrc(root), 0)
    root.remove()
    try:
        tmp.rmdir()          # remove spill dir when empty
    except OSError:
        pass
    stats.elapsed = perf_counter() - t0
    return stats


if __name__ == "__main__":                                        # smoke test
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cube_io import CountingSink, ListSink, compare
    from dataset import DEFAULT_DIMENSIONS, encode, load_raw

    df = load_raw()
    cube = encode(df, DEFAULT_DIMENSIONS[:6])
    a, b = ListSink(), ListSink()
    from buc import buc_inmem

    s1 = buc_inmem(cube, 50, a)
    s2 = buc_paged(cube, 50, b, page_rows=4096, mem_budget_bytes=64 * 2**20)
    cmp = compare(a, b)
    print("inmem :", s1.as_row())
    print("paged :", s2.as_row())
    print("equal :", cmp["equal"], "| fingerprint", cmp["fingerprint_a"], cmp["fingerprint_b"])