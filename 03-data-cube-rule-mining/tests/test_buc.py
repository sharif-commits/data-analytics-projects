"""Check both BUC versions against a brute-force cube on small random data.

Run from part2/: python -m unittest discover -s tests
"""
import hashlib
import itertools
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from buc_disk import buc_out_of_core  # noqa: E402
from buc_memory import ALL, buc_in_memory, read_cells  # noqa: E402
from census import CubeData  # noqa: E402


def random_data(rng, n_rows, cards):
    columns = {f"d{i}": rng.integers(0, c, n_rows).astype(np.uint8) for i, c in enumerate(cards)}
    labels = {f"d{i}": [str(v) for v in range(c)] for i, c in enumerate(cards)}
    return CubeData(columns, labels, {"m": rng.integers(0, 1000, n_rows).astype(np.int64)})


def brute_force(data, dims, minsup):
    """Every group-by computed the slow, obvious way."""
    cube = {}
    for size in range(len(dims) + 1):
        for subset in itertools.combinations(range(len(dims)), size):
            groups = defaultdict(lambda: [0, 0])
            for row in range(data.n_rows):
                key = [ALL] * len(dims)
                for i in subset:
                    key[i] = int(data.columns[dims[i]][row])
                groups[tuple(key)][0] += 1
                groups[tuple(key)][1] += int(data.measures["m"][row])
            cube.update({k: tuple(v) for k, v in groups.items() if v[0] >= minsup})
    return cube


def as_dict(cells):
    return {tuple(int(x) for x in c["cell"]): (int(c["count"]), int(c["sum"])) for c in cells}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BucTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_in_memory_matches_brute_force(self):
        rng = np.random.default_rng(1)
        for n_rows, cards, minsup in [(300, [3, 4, 2], 1), (500, [2, 5, 3, 4], 5), (800, [6, 2, 3, 2, 3], 20)]:
            data = random_data(rng, n_rows, cards)
            dims = list(data.columns)
            buc_in_memory(data, dims, minsup, self.tmp / "m.bin", measure="m")
            got = read_cells(self.tmp / "m.bin", len(dims))
            self.assertEqual(len(got), len(as_dict(got)), "a cell was emitted twice")
            self.assertEqual(as_dict(got), brute_force(data, dims, minsup))

    def test_disk_is_byte_identical_at_every_budget(self):
        rng = np.random.default_rng(2)
        data = random_data(rng, 3000, [4, 3, 5, 2, 3])
        dims = list(data.columns)
        buc_in_memory(data, dims, 10, self.tmp / "m.bin", measure="m")
        expected = digest(self.tmp / "m.bin")
        for budget in [512, 2048, 16384, 65536, 1 << 22]:
            stats = buc_out_of_core(data, dims, 10, self.tmp / "d.bin", budget, measure="m", temp_root=self.tmp)
            self.assertEqual(digest(self.tmp / "d.bin"), expected, f"budget {budget}")
            if budget <= 16384:
                self.assertGreater(stats.disk_partitions, 0, "small budget should have spilled")

    def test_budget_too_small_is_rejected(self):
        data = random_data(np.random.default_rng(3), 100, [2, 2])
        with self.assertRaises(ValueError):
            buc_out_of_core(data, list(data.columns), 1, self.tmp / "d.bin", 8, temp_root=self.tmp)

    def test_minsup_above_row_count_gives_empty_cube(self):
        data = random_data(np.random.default_rng(4), 50, [2, 3])
        stats = buc_in_memory(data, list(data.columns), 51, self.tmp / "m.bin")
        self.assertEqual(stats.cells, 0)
        self.assertEqual(buc_out_of_core(data, list(data.columns), 51, self.tmp / "d.bin", 4096,
                                         temp_root=self.tmp).cells, 0)

    def test_spill_files_are_cleaned_up(self):
        data = random_data(np.random.default_rng(5), 2000, [3, 3, 3])
        buc_out_of_core(data, list(data.columns), 5, self.tmp / "d.bin", 1024, temp_root=self.tmp)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["d.bin"])

    def test_dimension_order_does_not_change_the_cube(self):
        data = random_data(np.random.default_rng(6), 1500, [5, 2, 4, 3])
        dims = list(data.columns)
        buc_in_memory(data, dims, 8, self.tmp / "a.bin", measure="m")
        reordered = dims[::-1]
        buc_in_memory(data, reordered, 8, self.tmp / "b.bin", measure="m")
        a = as_dict(read_cells(self.tmp / "a.bin", 4))
        b = {k[::-1]: v for k, v in as_dict(read_cells(self.tmp / "b.bin", 4)).items()}
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
