"""Part 2 -- cube cell representation, output sinks and comparison helpers.

A cube cell is a tuple of D integers where ``ALL`` (-1) marks a dimension
that is aggregated over (the ``*`` of a group-by cube).  Both the in-memory
and the out-of-core BUC implementations emit cells through the same `Sink`
interface, which is what makes "both versions must produce the same output"
cheap to assert: run each into a `ListSink` and compare fingerprints.
"""

from __future__ import annotations

import csv
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

ALL = -1
ALL_LABEL = "*"


# --------------------------------------------------------------------- sinks
class Sink(ABC):
    """Receives one cube cell at a time.

    `cell` is a *mutable, reused* buffer -- implementations must copy it if
    they intend to keep it.
    """

    n_cells: int = 0

    @abstractmethod
    def emit(self, cell: Sequence[int], count: int, measure: float) -> None: ...

    def close(self) -> None:  # pragma: no cover - default no-op
        pass


class CountingSink(Sink):
    """Counts cells without materialising them -- used for benchmarking.

    Also maintains an order-independent checksum so two runs can be compared
    cheaply even when they emit cells in a different order.
    """

    def __init__(self) -> None:
        self.n_cells = 0
        self.checksum = 0
        self.total_count = 0

    def emit(self, cell: Sequence[int], count: int, measure: float) -> None:
        self.n_cells += 1
        self.total_count += count
        h = hash((tuple(cell), count, round(float(measure), 6)))
        self.checksum = (self.checksum + h) & 0xFFFFFFFFFFFFFFFF


class ListSink(Sink):
    """Materialises every cell -- used for correctness comparisons."""

    def __init__(self) -> None:
        self.cells: list[tuple[tuple[int, ...], int, float]] = []

    @property
    def n_cells(self) -> int:  # type: ignore[override]
        return len(self.cells)

    def emit(self, cell: Sequence[int], count: int, measure: float) -> None:
        self.cells.append((tuple(int(x) for x in cell), int(count), float(measure)))

    # -- comparison helpers ------------------------------------------------
    def canonical(self) -> list[tuple[tuple[int, ...], int, float]]:
        return sorted((c, n, round(m, 6)) for c, n, m in self.cells)

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for cell, n, m in self.canonical():
            h.update(f"{cell}|{n}|{m:.6f}\n".encode())
        return h.hexdigest()[:16]


class CsvSink(Sink):
    """Streams cells straight to disk, so an iceberg cube never has to fit
    in memory even when the caller wants it persisted."""

    def __init__(self, path: Path | str, dims: Sequence[str],
                 levels: Sequence[Sequence[str]], measure_name: str = "measure"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.levels = levels
        self._fh = open(self.path, "w", encoding="utf-8", newline="")
        self._w = csv.writer(self._fh)
        self._w.writerow(list(dims) + ["count", measure_name])
        self.n_cells = 0

    def emit(self, cell: Sequence[int], count: int, measure: float) -> None:
        row = [
            ALL_LABEL if v == ALL else self.levels[d][v]
            for d, v in enumerate(cell)
        ]
        row.append(count)
        row.append(round(float(measure), 6))
        self._w.writerow(row)
        self.n_cells += 1

    def close(self) -> None:
        self._fh.close()


class MultiSink(Sink):
    """Fan one emission out to several sinks (e.g. count + CSV)."""

    def __init__(self, *sinks: Sink):
        self.sinks = sinks

    @property
    def n_cells(self) -> int:  # type: ignore[override]
        return self.sinks[0].n_cells if self.sinks else 0

    def emit(self, cell: Sequence[int], count: int, measure: float) -> None:
        for s in self.sinks:
            s.emit(cell, count, measure)

    def close(self) -> None:
        for s in self.sinks:
            s.close()


# ----------------------------------------------------------------- utilities
def cells_to_labels(
    cells: Iterable[tuple[tuple[int, ...], int, float]],
    levels: Sequence[Sequence[str]],
) -> list[tuple]:
    """Translate integer cells back into their human-readable labels."""
    out = []
    for cell, n, m in cells:
        out.append(
            tuple(ALL_LABEL if v == ALL else levels[d][v] for d, v in enumerate(cell))
            + (n, m)
        )
    return out


def compare(a: ListSink, b: ListSink, atol: float = 1e-6) -> dict:
    """Structured diff between two cube results."""
    ca, cb = a.canonical(), b.canonical()
    sa = {c: (n, m) for c, n, m in ca}
    sb = {c: (n, m) for c, n, m in cb}
    only_a = sorted(set(sa) - set(sb))
    only_b = sorted(set(sb) - set(sa))
    mismatched = [
        (c, sa[c], sb[c])
        for c in (set(sa) & set(sb))
        if sa[c][0] != sb[c][0] or abs(sa[c][1] - sb[c][1]) > atol
    ]
    return {
        "equal": not (only_a or only_b or mismatched),
        "n_a": len(ca),
        "n_b": len(cb),
        "only_in_a": only_a[:10],
        "only_in_b": only_b[:10],
        "n_only_in_a": len(only_a),
        "n_only_in_b": len(only_b),
        "n_mismatched": len(mismatched),
        "mismatched_sample": mismatched[:10],
        "fingerprint_a": a.fingerprint(),
        "fingerprint_b": b.fingerprint(),
    }


def subsets_nonempty(items: Sequence[int]) -> Iterable[tuple[int, ...]]:
    """All 2^k - 1 non-empty subsets of *items*, as index tuples."""
    k = len(items)
    for mask in range(1, 1 << k):
        yield tuple(items[i] for i in range(k) if mask >> i & 1)


def counting_sort_partition(col: np.ndarray, card: int) -> tuple[np.ndarray, np.ndarray]:
    """The BUC ``Partition`` primitive.

    Returns ``(order, starts)`` where ``order`` permutes the rows so that
    equal values of *col* are contiguous, and ``starts`` holds the
    ``card + 1`` group boundaries into that permutation.

    numpy's stable integer argsort is a radix sort, so this is O(n) in the
    number of rows -- the same complexity as the counting sort the BUC paper
    specifies, without dropping into a Python-level loop.
    """
    counts = np.bincount(col, minlength=card)
    starts = np.empty(card + 1, dtype=np.int64)
    starts[0] = 0
    np.cumsum(counts, out=starts[1:])
    order = np.argsort(col, kind="stable")
    return order, starts
