"""Part 2 -- build the concept-hierarchy CSVs used by AOI.

Each hierarchy is a two-column ``value,parent`` CSV in
``part2/hierarchies``.  Chains encode multi-level trees, e.g.

    9th grade,Less than HS
    Less than HS,ANY

means 9th grade -> Less than HS -> ANY (root).

Ten attributes are covered (assignment asks for >= 5).  The script also
validates that every leaf value actually occurs in the dataset, so a
typo in a label can never silently produce a dead branch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset import HIER_DIR, load_raw  # noqa: E402

# ------------------------------------------------------------ hierarchies
HIERARCHIES: dict[str, list[tuple[str, str]]] = {
    # ---- education: school level -> education stage -> ANY ---------------
    "education": [
        ("Less than 1st grade", "No HS diploma"),
        ("1st 2nd 3rd or 4th grade", "No HS diploma"),
        ("5th or 6th grade", "No HS diploma"),
        ("7th and 8th grade", "No HS diploma"),
        ("9th grade", "No HS diploma"),
        ("10th grade", "No HS diploma"),
        ("11th grade", "No HS diploma"),
        ("12th grade no diploma", "No HS diploma"),
        ("High school graduate", "HS graduate"),
        ("Some college but no degree", "Some college/Associates"),
        ("Associates degree-academic program", "Some college/Associates"),
        ("Associates degree-occup /vocational", "Some college/Associates"),
        ("Bachelors degree(BA AB BS)", "Bachelors"),
        ("Masters degree(MA MS MEng MEd MSW MBA)", "Graduate/Professional"),
        ("Prof school degree (MD DDS DVM LLB JD)", "Graduate/Professional"),
        ("Doctorate degree(PhD EdD)", "Graduate/Professional"),
        ("Children", "Children/NA"),
        ("No HS diploma", "ANY"),
        ("HS graduate", "ANY"),
        ("Some college/Associates", "ANY"),
        ("Bachelors", "ANY"),
        ("Graduate/Professional", "ANY"),
        ("Children/NA", "ANY"),
    ],
    # ---- class_of_worker: employer type -> sector -> ANY -----------------
    "class_of_worker": [
        ("Private", "Private sector"),
        ("Federal government", "Government"),
        ("State government", "Government"),
        ("Local government", "Government"),
        ("Self-employed-incorporated", "Self-employed"),
        ("Self-employed-not incorporated", "Self-employed"),
        ("Without pay", "Unpaid/Not in universe"),
        ("Never worked", "Unpaid/Not in universe"),
        ("Not in universe", "Unpaid/Not in universe"),
        ("Private sector", "ANY"),
        ("Government", "ANY"),
        ("Self-employed", "ANY"),
        ("Unpaid/Not in universe", "ANY"),
    ],
    # ---- marital_status: status -> ever married -> ANY -------------------
    "marital_status": [
        ("Married-civilian spouse present", "Married"),
        ("Married-A F spouse present", "Married"),
        ("Married-spouse absent", "Married"),
        ("Divorced", "Previously married"),
        ("Separated", "Previously married"),
        ("Widowed", "Previously married"),
        ("Never married", "Never married"),
        ("Married", "Ever married"),
        ("Previously married", "Ever married"),
        ("Never married", "ANY"),
        ("Ever married", "ANY"),
    ],
    # ---- employment_status: schedule -> working -> ANY -------------------
    "employment_status": [
        ("Full-time schedules", "Full-time"),
        ("PT for econ reasons usually FT", "Part-time"),
        ("PT for econ reasons usually PT", "Part-time"),
        ("PT for non-econ reasons usually FT", "Part-time"),
        ("Unemployed full-time", "Unemployed"),
        ("Unemployed part- time", "Unemployed"),
        ("Not in labor force", "Not in labor force"),
        ("Children or Armed Forces", "Not in labor force"),
        ("Full-time", "Employed"),
        ("Part-time", "Employed"),
        ("Unemployed", "Not employed"),
        ("Not in labor force", "Not employed"),
        ("Employed", "ANY"),
        ("Not employed", "ANY"),
    ],
    # ---- age_group: band -> life stage -> ANY ----------------------------
    "age_group": [
        ("00-15 child", "Minor"),
        ("16-24 young adult", "Young adult"),
        ("25-34", "Prime working age"),
        ("35-44", "Prime working age"),
        ("45-54", "Older working age"),
        ("55-64", "Older working age"),
        ("65-74 senior", "Senior"),
        ("75+ elderly", "Senior"),
        ("Minor", "ANY"),
        ("Young adult", "ANY"),
        ("Prime working age", "ANY"),
        ("Older working age", "ANY"),
        ("Senior", "ANY"),
    ],
    # ---- weeks_worked_band: band -> attachment -> ANY --------------------
    "weeks_worked_band": [
        ("0 weeks", "Not working"),
        ("1-13 weeks", "Part year"),
        ("14-26 weeks", "Part year"),
        ("27-39 weeks", "Most/full year"),
        ("40-51 weeks", "Most/full year"),
        ("52 weeks", "Most/full year"),
        ("Not working", "ANY"),
        ("Part year", "ANY"),
        ("Most/full year", "ANY"),
    ],
    # ---- race: race -> ANY ----------------------------------------------
    "race": [
        ("White", "ANY"),
        ("Black", "ANY"),
        ("Asian or Pacific Islander", "ANY"),
        ("Amer Indian Aleut or Eskimo", "ANY"),
        ("Other", "ANY"),
    ],
    # ---- hispanic_origin: origin -> hispanic -> ANY ----------------------
    "hispanic_origin": [
        ("Mexican (Mexicano)", "Mexican origin"),
        ("Mexican-American", "Mexican origin"),
        ("Chicano", "Mexican origin"),
        ("Puerto Rican", "Hispanic non-Mexican"),
        ("Cuban", "Hispanic non-Mexican"),
        ("Central or South American", "Hispanic non-Mexican"),
        ("Other Spanish", "Hispanic non-Mexican"),
        ("All other", "Not Hispanic/unknown"),
        ("Do not know", "Not Hispanic/unknown"),
        ("NA", "Not Hispanic/unknown"),
        ("Mexican origin", "Hispanic"),
        ("Hispanic non-Mexican", "Hispanic"),
        ("Hispanic", "ANY"),
        ("Not Hispanic/unknown", "ANY"),
    ],
    # ---- citizenship: status -> nativity -> ANY --------------------------
    "citizenship": [
        ("Native- Born in the United States", "Native born"),
        ("Native- Born in Puerto Rico or U S Outlying", "Native born"),
        ("Native- Born abroad of American Parent(s)", "Native born"),
        ("Foreign born- U S citizen by naturalization", "Foreign born"),
        ("Foreign born- Not a citizen of U S", "Foreign born"),
        ("Native born", "ANY"),
        ("Foreign born", "ANY"),
    ],
    # ---- household_summary: role -> relatedness -> ANY -------------------
    "household_summary": [
        ("Child under 18 never married", "Child"),
        ("Child under 18 ever married", "Child"),
        ("Child 18 or older", "Child"),
        ("Spouse of householder", "Other relative"),
        ("Other relative of householder", "Other relative"),
        ("Householder", "Householder"),
        ("Nonrelative of householder", "Nonrelative"),
        ("Group Quarters- Secondary individual", "Nonrelative"),
        ("Child", "Related to householder"),
        ("Other relative", "Related to householder"),
        ("Householder", "ANY"),
        ("Nonrelative", "ANY"),
        ("Related to householder", "ANY"),
    ],
}


def main() -> None:
    HIER_DIR.mkdir(parents=True, exist_ok=True)
    df = load_raw()

    n_bad = 0
    for attr, edges in HIERARCHIES.items():
        path = HIER_DIR / f"{attr}.csv"
        pd.DataFrame(edges, columns=["value", "parent"]).to_csv(
            path, index=False
        )
        # every leaf must exist in the dataset
        leaves = [v for v, p in edges if v not in {pp for _, pp in edges} or True]
        dataset_vals = set(df[attr].unique()) if attr in df.columns else set()
        missing = sorted(
            {v for v, _ in edges} - dataset_vals - {"ANY"}
        )
        # internal nodes are allowed to be absent from the data
        missing_leaves = [m for m in missing if m not in {p for _, p in edges}]
        status = "OK " if not missing_leaves else "BAD"
        if missing_leaves:
            n_bad += 1
        print(f"  {status} {path.name:28s} edges={len(edges):3d}"
              + (f"  missing leaves: {missing_leaves}" if missing_leaves else ""))

    print(f"\nwrote {len(HIERARCHIES)} hierarchy files to {HIER_DIR}")
    if n_bad:
        raise SystemExit(f"{n_bad} hierarchies have leaves not in the dataset")


if __name__ == "__main__":
    main()