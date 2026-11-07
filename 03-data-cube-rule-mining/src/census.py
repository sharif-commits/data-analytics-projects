"""Load the census CSV and encode it for the cube and AOI code."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "M26_DA_A2" / "M26_DA_A2_Part2.csv"

# Twelve raw categorical columns with no '?' values. instance_weight is a sampling weight and
# income is the class label, so neither is a dimension.
DIMENSIONS = [
    "class_of_worker", "education", "marital_status", "industry_code_major",
    "occupation_code_major", "race", "hispanic_origin", "sex",
    "employment_status", "tax_filer_status", "household_summary", "citizenship",
]
DEFAULT_MEASURE = "capital_gains"
TARGET_CLASS = ">50K"
CONTRAST_CLASS = "<=50K"


@dataclass
class CubeData:
    """Integer-encoded dimensions plus integer measure columns."""
    columns: dict      # dimension name -> uint8 codes, one per row
    labels: dict       # dimension name -> list of original values, indexed by code
    measures: dict     # measure name -> int64 values, one per row

    @property
    def n_rows(self):
        return len(next(iter(self.columns.values())))

    def cardinality(self, dim):
        return len(self.labels[dim])


def read_census(path=DEFAULT_CSV):
    """Read every column as text. 'NA' is a real value of hispanic_origin, so it must stay text."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def encode(frame, dims=DIMENSIONS, measures=(DEFAULT_MEASURE,)):
    """Turn text columns into uint8 codes, with codes in sorted order of the values."""
    columns, labels = {}, {}
    for dim in dims:
        codes, uniques = pd.factorize(frame[dim], sort=True)
        if len(uniques) > 255:
            raise ValueError(f"{dim} has too many values for a one-byte code")
        columns[dim] = codes.astype(np.uint8)
        labels[dim] = [str(u) for u in uniques]
    values = {m: frame[m].astype(np.int64).to_numpy() for m in measures}
    return CubeData(columns, labels, values)


def load_cube_data(path=DEFAULT_CSV, dims=DIMENSIONS, measures=(DEFAULT_MEASURE,)):
    """Read the CSV and encode the chosen dimensions."""
    return encode(read_census(path), dims, measures)
