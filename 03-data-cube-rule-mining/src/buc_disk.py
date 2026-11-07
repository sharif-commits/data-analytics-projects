"""Out-of-core BUC: the same cube as buc_memory, under a fixed memory budget.

The relation lives in a file of fixed-width records. For a partition that fits the budget, the
records are loaded and the in-memory recursion finishes it. For a partition that does not fit:

  1. One streaming pass gets its count, its sum and a histogram of every remaining dimension.
  2. Its cell is emitted.
  3. For each remaining dimension, another pass distributes the rows of frequent values into one
     spill file per value, through bounded write buffers. This is BUC's counting sort done on disk.
  4. Each spill file is processed recursively, in ascending value order, and then deleted.

Cells leave in the same depth-first order as the in-memory version, so the two output files
must be byte-identical.

memory_bytes bounds the data buffers this code allocates: record chunks, spill buffers, the cell
buffer and the arrays of a loaded partition. It does not bound the Python interpreter itself.
"""
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from buc_memory import ALL, BucStats, CellWriter, cell_format, expand_partition

DEFAULT_PAGE_BYTES = 8192
# Per-row temporaries of a partition step: the column (1), bincount's cast to intp (8), the argsort
# result (8) and the work array of numpy's stable radix sort (8).
PARTITION_TEMP_BYTES = 25


def record_dtype(n_dims):
    """One relation row on disk: a byte per dimension, then the measure."""
    return np.dtype([("codes", "u1", (n_dims,)), ("measure", "<i8")])


def write_records(data, dims, path, measure=None):
    """Store the relation as fixed-width records. This is the input file of the disk algorithm."""
    records = np.zeros(data.n_rows, dtype=record_dtype(len(dims)))
    for i, dim in enumerate(dims):
        records["codes"][:, i] = data.columns[dim]
    if measure:
        records["measure"] = data.measures[measure]
    records.tofile(path)


@dataclass
class DiskStats:
    """I/O and work counters for one out-of-core run."""
    cells: int = 0
    pages_read: int = 0
    pages_written: int = 0
    bytes_read: int = 0
    bytes_written: int = 0
    spill_files: int = 0
    disk_partitions: int = 0      # partitions too large for the budget
    memory_partitions: int = 0    # partitions small enough to load
    peak_spill_bytes: int = 0     # largest amount of spill data on disk at one time
    partition_steps: int = 0
    pruned_values: int = 0
    sorts_skipped: int = 0


class SpillBuffer:
    """Bounded write buffer for one spill file."""

    def __init__(self, path, dtype, capacity, engine):
        self.path = path
        self._buffer = np.empty(capacity, dtype=dtype)
        self._raw = self._buffer.view(np.uint8)   # the same memory as bytes, so a flush copies nothing
        self._record_bytes = dtype.itemsize
        self._used = 0
        self._engine = engine
        self._file = open(path, "wb", buffering=0)

    def append(self, rows):
        start = 0
        while start < len(rows):
            take = min(len(rows) - start, len(self._buffer) - self._used)
            self._buffer[self._used: self._used + take] = rows[start: start + take]
            self._used += take
            start += take
            if self._used == len(self._buffer):
                self.flush()

    def flush(self):
        if self._used:
            n_bytes = self._used * self._record_bytes
            self._file.write(self._raw[:n_bytes])
            self._engine.count_write(n_bytes)
            self._used = 0

    def close(self):
        self.flush()
        self._file.close()
        self._buffer = self._raw = None


class DiskBuc:
    """State of one out-of-core run."""

    def __init__(self, n_dims, cards, minsup, memory_bytes, writer, temp_dir, use_measure, page_bytes):
        self.n_dims = n_dims
        self.cards = cards
        self.minsup = minsup
        self.writer = writer
        self.temp_dir = str(temp_dir)
        self.use_measure = use_measure
        self.dtype = record_dtype(n_dims)
        self.page_bytes = page_bytes
        self.stats = DiskStats()
        self._spill_on_disk = 0
        self._next_spill = 0

        record = self.dtype.itemsize
        cell_bytes = cell_format(n_dims).size
        # A share of the budget is kept for the output buffer, and the rest for one job at a time.
        self.work_bytes = memory_bytes - max(cell_bytes, memory_bytes // 16)
        # While distributing, a third goes to the chunk being read and a third to the spill buffers.
        # A chunk row costs its record twice (the chunk and its sorted copy) plus the partition
        # temporaries. The last third is headroom for allocations this code does not control.
        self.read_rows = max(1, (self.work_bytes // 3) // (2 * record + PARTITION_TEMP_BYTES))
        self.write_bytes = self.work_bytes // 3
        if self.work_bytes // 3 < 2 * record + PARTITION_TEMP_BYTES or self.write_bytes < record:
            raise ValueError(f"memory_bytes={memory_bytes} is too small to hold a single record")

    def count_read(self, n_bytes):
        self.stats.bytes_read += n_bytes
        self.stats.pages_read += -(-n_bytes // self.page_bytes)

    def count_write(self, n_bytes):
        self.stats.bytes_written += n_bytes
        self.stats.pages_written += -(-n_bytes // self.page_bytes)

    def bytes_per_row(self, start_dim):
        """Conservative in-memory cost of a row for a partition starting at `start_dim`.

        Dimension bytes and the measure, then per recursion level an int32 index array (4) and the
        column (1), then the temporaries of one partition step.
        """
        levels = self.n_dims - start_dim + 1
        return self.n_dims + 8 + 5 * levels + PARTITION_TEMP_BYTES

    def chunks(self, path):
        """Stream a partition file in bounded chunks."""
        with open(path, "rb", buffering=0) as f:
            while True:
                chunk = np.fromfile(f, dtype=self.dtype, count=self.read_rows)
                if len(chunk) == 0:
                    return
                self.count_read(chunk.nbytes)
                yield chunk

    def run_in_memory(self, path, start_dim, cell):
        """Load a partition that fits the budget and finish it with the in-memory recursion."""
        self.stats.memory_partitions += 1
        records = np.fromfile(path, dtype=self.dtype)
        self.count_read(records.nbytes)
        codes = [np.ascontiguousarray(records["codes"][:, d]) for d in range(self.n_dims)]
        measure = np.ascontiguousarray(records["measure"]) if self.use_measure else None
        idx = np.arange(len(records), dtype=np.int32)
        del records
        work = BucStats()
        expand_partition(codes, self.cards, measure, idx, start_dim, cell, self.minsup, self.writer, work)
        self.stats.partition_steps += work.partition_steps
        self.stats.pruned_values += work.pruned_values
        self.stats.sorts_skipped += work.sorts_skipped

    def scan(self, path, start_dim):
        """One pass over a partition: its count, sum, and a histogram of each remaining dimension."""
        hist = {d: np.zeros(self.cards[d], dtype=np.int64) for d in range(start_dim, self.n_dims)}
        count, total = 0, 0
        for chunk in self.chunks(path):
            count += len(chunk)
            if self.use_measure:
                total += int(chunk["measure"].sum())
            for d in hist:
                hist[d] += np.bincount(chunk["codes"][:, d], minlength=self.cards[d])
        return count, total, hist

    def distribute(self, path, dim, frequent):
        """Split a partition into one spill file per frequent value of `dim`."""
        capacity = max(1, (self.write_bytes // len(frequent)) // self.dtype.itemsize)
        spills = {}
        for value in frequent:
            self._next_spill += 1
            # A plain string on purpose: pathlib interns path parts, and the intern table grew by
            # about 2 MB over tens of thousands of unique spill names and never shrank.
            spill_path = os.path.join(self.temp_dir, f"spill_{self._next_spill}.bin")
            spills[value] = SpillBuffer(spill_path, self.dtype, capacity, self)
        self.stats.spill_files += len(frequent)

        for chunk in self.chunks(path):
            column = chunk["codes"][:, dim]
            order = np.argsort(column, kind="stable")
            grouped = chunk[order]
            counts = np.bincount(column, minlength=self.cards[dim])
            ends = np.cumsum(counts)
            for value in frequent:
                if counts[value]:
                    spills[value].append(grouped[ends[value] - counts[value]: ends[value]])
        for spill in spills.values():
            spill.close()
        return {value: spill.path for value, spill in spills.items()}

    def process(self, path, n_rows, start_dim, cell):
        """Compute the cube of one partition file. The caller guarantees n_rows >= minsup."""
        if n_rows * self.bytes_per_row(start_dim) <= self.work_bytes:
            self.run_in_memory(path, start_dim, cell)
            return

        self.stats.disk_partitions += 1
        count, total, hist = self.scan(path, start_dim)
        self.writer.add(cell, count, total)

        for dim in range(start_dim, self.n_dims):
            self.stats.partition_steps += 1
            frequent = np.flatnonzero(hist[dim] >= self.minsup).tolist()
            self.stats.pruned_values += int(np.count_nonzero(hist[dim])) - len(frequent)
            if not frequent:
                self.stats.sorts_skipped += 1
                continue

            spill_paths = self.distribute(path, dim, frequent)
            sizes = {v: int(hist[dim][v]) for v in frequent}
            spill_bytes = sum(sizes.values()) * self.dtype.itemsize
            self._spill_on_disk += spill_bytes
            self.stats.peak_spill_bytes = max(self.stats.peak_spill_bytes, self._spill_on_disk)
            for value in frequent:
                if os.path.getsize(spill_paths[value]) != sizes[value] * self.dtype.itemsize:
                    raise RuntimeError(f"spill for value {value} of dimension {dim} does not match its histogram")
                cell[dim] = value
                self.process(spill_paths[value], sizes[value], dim + 1, cell)
                os.remove(spill_paths[value])
                self._spill_on_disk -= sizes[value] * self.dtype.itemsize
            cell[dim] = ALL


def run_from_records(record_path, n_rows, cards, minsup, out_path, memory_bytes, use_measure=False,
                     page_bytes=DEFAULT_PAGE_BYTES, temp_root=None):
    """Compute the iceberg cube of a record file under `memory_bytes`. Returns DiskStats."""
    n_dims = len(cards)
    temp_dir = Path(tempfile.mkdtemp(prefix="buc_spill_", dir=temp_root))
    record = cell_format(n_dims).size
    writer = CellWriter(out_path, n_dims, buffer_bytes=max(record, memory_bytes // 16))
    try:
        engine = DiskBuc(n_dims, cards, minsup, memory_bytes, writer, temp_dir, use_measure, page_bytes)
        if n_rows >= minsup:
            engine.process(record_path, n_rows, 0, [ALL] * n_dims)
    finally:
        writer.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
    engine.stats.cells = writer.cells
    return engine.stats


def buc_out_of_core(data, dims, minsup, out_path, memory_bytes, measure=None,
                    page_bytes=DEFAULT_PAGE_BYTES, temp_root=None):
    """Same interface as buc_in_memory, plus the memory budget in bytes."""
    temp_dir = Path(tempfile.mkdtemp(prefix="buc_input_", dir=temp_root))
    try:
        record_path = temp_dir / "relation.bin"
        write_records(data, dims, record_path, measure)
        cards = [data.cardinality(d) for d in dims]
        return run_from_records(record_path, data.n_rows, cards, minsup, out_path, memory_bytes,
                                use_measure=measure is not None, page_bytes=page_bytes, temp_root=temp_root)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
