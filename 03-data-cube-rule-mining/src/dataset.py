"""Part 2 -- dataset loading, discretisation and integer encoding.

The census file is 299,285 x 42, almost all of it categorical text.  Two
things have to happen before either BUC or AOI can touch it:

1.  **Discretisation.**  A handful of columns are continuous (`age`,
    `wage_per_hour`, `weeks_worked_in_year`, ...).  A cube dimension needs
    a small, finite domain, so those columns are banded into derived
    categorical dimensions.  The banding rules live here, in one place.

2.  **Integer encoding.**  Every dimension value is mapped to a dense code
    ``0 .. cardinality-1``.  BUC then works purely on an ``int32`` matrix,
    which is what makes the counting-sort partition step (and the fixed
    record width needed for the out-of-core version) possible.

`instance_weight` is a sampling weight rather than a feature and is
excluded from every dimension preset, as the assignment requires.

pandas is used for *reading and encoding only*.  No `groupby` is used
anywhere in the cube computation itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------- paths
PART2_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PART2_DIR.parent
CSV_PATH = ROOT_DIR / "M26_DA_A2" / "M26_DA_A2_Part2.csv"
OUT_DIR = PART2_DIR / "outputs"
HIER_DIR = PART2_DIR / "hierarchies"

# The sampling weight is not a feature -- never a dimension.
EXCLUDED_COLUMNS = ("instance_weight",)

CLASS_COLUMN = "income"

# --------------------------------------------------------------- band tables
# (upper_bound_inclusive, label) -- the last entry catches everything above.
AGE_BANDS = [
    (15, "00-15 child"),
    (24, "16-24 young adult"),
    (34, "25-34"),
    (44, "35-44"),
    (54, "45-54"),
    (64, "55-64"),
    (74, "65-74 senior"),
    (10**9, "75+ elderly"),
]

WAGE_BANDS = [
    (0, "no hourly wage"),
    (500, "1-500"),
    (1000, "501-1000"),
    (1500, "1001-1500"),
    (10**9, "1500+"),
]

WEEKS_BANDS = [
    (0, "0 weeks"),
    (13, "1-13 weeks"),
    (26, "14-26 weeks"),
    (39, "27-39 weeks"),
    (51, "40-51 weeks"),
    (10**9, "52 weeks"),
]

CAPITAL_BANDS = [
    (0, "none"),
    (5000, "low"),
    (20000, "medium"),
    (10**9, "high"),
]

PERSONS_BANDS = [
    (0, "0"),
    (2, "1-2"),
    (4, "3-4"),
    (10**9, "5-6"),
]

# name -> (source column, band table)
DERIVED_DIMENSIONS = {
    "age_group": ("age", AGE_BANDS),
    "wage_band": ("wage_per_hour", WAGE_BANDS),
    "weeks_worked_band": ("weeks_worked_in_year", WEEKS_BANDS),
    "capital_gains_band": ("capital_gains", CAPITAL_BANDS),
    "capital_losses_band": ("capital_losses", CAPITAL_BANDS),
    "dividends_band": ("dividends", CAPITAL_BANDS),
    "employer_size_band": ("num_persons_worked_for_employer", PERSONS_BANDS),
}

# --------------------------------------------------------------- dim presets
# The first 12 entries are the assignment's required minimum.  The list is
# ordered, and the "runtime vs number of dimensions" experiment simply takes
# the first D of them, so appending never disturbs a smaller run.
DIMENSIONS_16 = [
    "age_group",              #  8 values
    "class_of_worker",        #  9
    "education",              # 17
    "marital_status",         #  7
    "race",                   #  5
    "sex",                    #  2
    "employment_status",       #  8
    "tax_filer_status",       #  6
    "household_summary",      #  8
    "citizenship",            #  5
    "industry_code_major",    # 24
    "occupation_code_major",  # 15
    # ---- beyond the required 12, used by the scalability experiment ----
    "country_birth_self",     # 43
    "weeks_worked_band",      #  6
    "hispanic_origin",        # 10
    "region_prev_residence",  #  6
]

DEFAULT_DIMENSIONS = DIMENSIONS_16[:12]

# Detailed/summary column pairs that already encode a hierarchy in the raw
# data.  They are used to VALIDATE the generalisation code in hierarchy.py.
BUILTIN_HIERARCHY_PAIRS = [
    ("industry_code_detailed", "industry_code_major"),
    ("occupation_code_detailed", "occupation_code_major"),
    ("household_family_status", "household_summary"),
    ("state_prev_residence", "region_prev_residence"),
]


# ---------------------------------------------------------------- containers
@dataclass
class EncodedCube:
    """Integer-encoded input for the cube algorithms."""

    codes: np.ndarray          # (n, D) int32, values in [0, card[d])
    measure: np.ndarray        # (n,)   float64
    dims: list[str]            # dimension names, len == D
    levels: list[list[str]]    # levels[d][code] -> original label
    cards: np.ndarray          # (D,) int64 cardinalities
    measure_name: str

    @property
    def n_rows(self) -> int:
        return self.codes.shape[0]

    @property
    def n_dims(self) -> int:
        return self.codes.shape[1]

    def label(self, d: int, code: int) -> str:
        return self.levels[d][code]

    def slice_dims(self, k: int) -> "EncodedCube":
        """A view using only the first *k* dimensions (for the D sweep)."""
        return EncodedCube(
            codes=np.ascontiguousarray(self.codes[:, :k]),
            measure=self.measure,
            dims=self.dims[:k],
            levels=self.levels[:k],
            cards=self.cards[:k],
            measure_name=self.measure_name,
        )


# -------------------------------------------------------------------- loader
def _band(values: pd.Series, bands: list[tuple[int, str]]) -> pd.Series:
    """Map a numeric column onto its band labels."""
    v = pd.to_numeric(values, errors="coerce").fillna(-1)
    out = pd.Series(bands[-1][1], index=v.index, dtype=object)
    assigned = pd.Series(False, index=v.index)
    for upper, label in bands:
        mask = (~assigned) & (v <= upper)
        out[mask] = label
        assigned |= mask
    return out


def load_raw(csv_path: Path | str = CSV_PATH) -> pd.DataFrame:
    """Read the census CSV, trim whitespace and add the derived dimensions."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"dataset not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[])
    df.columns = [c.strip() for c in df.columns]

    # every value in this file is padded with a leading space in places
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # empty / '?' -> an explicit, countable category rather than NaN
    df = df.replace({"": "unknown", "?": "unknown"})

    for name, (src, bands) in DERIVED_DIMENSIONS.items():
        if src in df.columns:
            df[name] = _band(df[src], bands)

    # normalise the class label to two stable strings
    df[CLASS_COLUMN] = np.where(
        df[CLASS_COLUMN].str.contains("50000\\+|>\\s*50", regex=True),
        ">50K",
        "<=50K",
    )
    return df


def numeric_column(df: pd.DataFrame, col: str) -> np.ndarray:
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy(np.float64)


def encode(
    df: pd.DataFrame,
    dims: list[str] | None = None,
    measure: str = "count",
) -> EncodedCube:
    """Integer-encode *dims* and materialise the measure column.

    ``measure`` is one of
        ``count``                 -- pure support counting (default)
        ``sum:<column>``          -- SUM of a numeric column
        ``avg:<column>``          -- AVG of a numeric column
        ``rate:high_income``      -- fraction of the cell earning > $50K
    """
    dims = list(dims or DEFAULT_DIMENSIONS)
    missing = [d for d in dims if d not in df.columns]
    if missing:
        raise KeyError(f"unknown dimension(s): {missing}")
    banned = [d for d in dims if d in EXCLUDED_COLUMNS]
    if banned:
        raise ValueError(f"{banned} is a sampling weight, not a dimension")

    n = len(df)
    codes = np.empty((n, len(dims)), dtype=np.int32)
    levels: list[list[str]] = []
    for j, dim in enumerate(dims):
        cat = pd.Categorical(df[dim].astype(str))
        # sort the categories so encodings are reproducible across runs
        order = np.argsort(np.asarray(cat.categories, dtype=object).astype(str))
        remap = np.empty(len(cat.categories), dtype=np.int32)
        remap[order] = np.arange(len(cat.categories), dtype=np.int32)
        codes[:, j] = remap[cat.codes]
        levels.append([str(cat.categories[i]) for i in order])

    if measure == "count":
        m = np.ones(n, dtype=np.float64)
        mname = "COUNT(*)"
    elif measure.startswith("sum:"):
        col = measure.split(":", 1)[1]
        m = numeric_column(df, col)
        mname = f"SUM({col})"
    elif measure.startswith("avg:"):
        col = measure.split(":", 1)[1]
        m = numeric_column(df, col)
        mname = f"AVG({col})"
    elif measure == "rate:high_income":
        m = (df[CLASS_COLUMN].to_numpy() == ">50K").astype(np.float64)
        mname = "RATE(income > 50K)"
    else:
        raise ValueError(f"unsupported measure spec: {measure!r}")

    cards = np.array([len(l) for l in levels], dtype=np.int64)
    return EncodedCube(codes, m, dims, levels, cards, mname)


def profile(df: pd.DataFrame) -> pd.DataFrame:
    """Cardinality report for every candidate dimension (used in the report)."""
    rows = []
    for col in df.columns:
        if col in EXCLUDED_COLUMNS:
            continue
        nun = df[col].nunique()
        rows.append(
            {
                "column": col,
                "distinct": nun,
                "derived": col in DERIVED_DIMENSIONS,
                "in_default_12": col in DEFAULT_DIMENSIONS,
                "sample_values": ", ".join(sorted(df[col].unique())[:4]),
            }
        )
    return pd.DataFrame(rows).sort_values("distinct").reset_index(drop=True)


if __name__ == "__main__":                                   # quick profiling
    import argparse

    ap = argparse.ArgumentParser(description="profile the Part 2 dataset")
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--values", nargs="*", default=[],
                    help="dump every distinct value of these columns")
    args = ap.parse_args()

    frame = load_raw(args.csv)
    print(f"rows={len(frame):,}  columns={frame.shape[1]}")
    prof = profile(frame)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prof.to_csv(OUT_DIR / "column_profile.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_colwidth", 60,
                           "display.max_rows", 100):
        print(prof.to_string(index=False))

    for col in args.values:
        print(f"\n--- {col} ({frame[col].nunique()} distinct) ---")
        vc = frame[col].value_counts()
        for val, cnt in vc.items():
            print(f"  {cnt:>7,d}  {val}")
