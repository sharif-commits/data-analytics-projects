"""Write the detail-level hierarchy files from a random half of the rows.

The brief says four hierarchies exist in the data as detail/summary column pairs. Their
child -> parent tables are learned from half of the rows and stored as CSV. run_aoi.py then tests
them on the other half, which keeps the check honest.

state_prev_residence.csv is separate: it is written by hand from the US Census regions and uses
no data. Comparing it with the data shows that the data's region column is not real geography.
"""
import csv
from collections import Counter, defaultdict

import numpy as np

from aoi import HIERARCHY_DIR
from census import read_census

SEED = 42
PAIRS = {
    "industry_detail.csv": ("industry_code_detailed", "industry_code_major"),
    "occupation_detail.csv": ("occupation_code_detailed", "occupation_code_major"),
    "household_detail.csv": ("household_family_status", "household_summary"),
    "state_region_detail.csv": ("state_prev_residence", "region_prev_residence"),
}


def learning_half(n_rows):
    """A boolean mask marking the half of the rows used to learn the tables."""
    mask = np.zeros(n_rows, dtype=bool)
    mask[np.random.default_rng(SEED).permutation(n_rows)[: n_rows // 2]] = True
    return mask


def main():
    frame = read_census()
    half = frame[learning_half(len(frame))]
    for filename, (child, parent) in PAIRS.items():
        votes = defaultdict(Counter)
        for c, p in zip(half[child], half[parent]):
            votes[c][p] += 1
        with open(HIERARCHY_DIR / filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["level_0", "level_1"])
            for c in sorted(votes):
                writer.writerow([c, votes[c].most_common(1)[0][0]])
        print(filename, len(votes), "values")


if __name__ == "__main__":
    main()
