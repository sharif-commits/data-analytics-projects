"""Run AOI: hierarchy checks, rules, threshold sensitivity, and the cross-check against BUC."""
import csv
import tempfile
import time
from pathlib import Path

import numpy as np

import aoi
from buc_memory import ALL, buc_in_memory, read_cells
from build_hierarchies import PAIRS, learning_half
from census import CONTRAST_CLASS, TARGET_CLASS, CubeData, read_census

OUT = Path(__file__).resolve().parents[1] / "outputs"
ATTRIBUTES = [
    "age", "education", "class_of_worker", "marital_status", "occupation_code_detailed",
    "industry_code_detailed", "sex", "weeks_worked_in_year", "country_birth_self", "wage_per_hour",
]
ATTR_THRESHOLD = 6
REL_THRESHOLD = 80


def check_hierarchy(frame, child, parent, hierarchy, name, test_rows):
    """Generalise `child` with the real code path and compare with the `parent` column."""
    rows = frame[test_rows]
    known = rows[child].isin(list(hierarchy.levels[1])).to_numpy()
    generalized = hierarchy.generalize(rows[child].to_numpy()[known], 1)
    actual = rows[parent].to_numpy()[known]
    wrong = generalized != actual
    bad_values = sorted(set(rows[child].to_numpy()[known][wrong].tolist()))
    unmapped = sorted(set(rows[child].to_numpy()[~known].tolist()))
    return {"pair": name, "rows_tested": int(known.sum()), "rows_mismatched": int(wrong.sum()),
            "pct_match": round(100.0 * (1 - wrong.mean()), 4), "values_mismatched": "; ".join(bad_values),
            "rows_not_in_hierarchy": int((~known).sum()), "values_not_in_hierarchy": "; ".join(unmapped)}


def hierarchy_checks(frame):
    """Test the four known pairs on the unseen half, then compare the data with real geography."""
    unseen = ~learning_half(len(frame))
    results = []
    for filename, (child, parent) in PAIRS.items():
        hierarchy = aoi.hierarchy_from_table(aoi.load_table(filename))
        results.append(check_hierarchy(frame, child, parent, hierarchy, f"{child} -> {parent}", unseen))
    state = aoi.hierarchy_from_table(aoi.load_table("state_prev_residence.csv"))
    results.append(check_hierarchy(frame, "state_prev_residence", "region_prev_residence", state,
                                   "state_prev_residence -> US Census region (hand-written, all rows)",
                                   np.ones(len(frame), dtype=bool)))
    return results


def split_classes(frame, keep=None):
    """Column dictionaries for the target and contrast classes."""
    rows = frame if keep is None else frame[keep]
    is_target = (rows["income"] == TARGET_CLASS).to_numpy()
    is_contrast = (rows["income"] == CONTRAST_CLASS).to_numpy()
    columns = {a: rows[a].to_numpy(dtype=object) for a in ATTRIBUTES}
    return ({a: v[is_target] for a, v in columns.items()}, {a: v[is_contrast] for a, v in columns.items()})


def run_discriminant(target, contrast, hierarchies, suffix):
    plan, rules, base_rate = aoi.discriminant_rules(target, contrast, ATTRIBUTES, hierarchies,
                                                    ATTR_THRESHOLD, REL_THRESHOLD)
    aoi.write_rules(OUT / f"aoi_discriminant_rules{suffix}.csv", rules)
    return {"levels": plan.levels, "removed": plan.removed, "rules": len(rules),
            "rules_with_target": sum(r["target_count"] > 0 for r in rules), "base_rate_pct": 100 * base_rate,
            "target_rows": sum(r["target_count"] for r in rules),
            "contrast_rows": sum(r["contrast_count"] for r in rules)}


def cross_check_with_buc(target, plan, hierarchies):
    """AOI's generalised relation is the base cuboid of a cube on the generalised attributes."""
    attrs = list(plan.levels)
    columns, labels = {}, {}
    for a in attrs:
        values = aoi.current_values(target, a, plan.levels[a], hierarchies).astype(str)
        labels[a], codes = np.unique(values, return_inverse=True)
        columns[a] = codes.astype(np.uint8)
    data = CubeData(columns, {a: list(v) for a, v in labels.items()}, {})
    path = Path(tempfile.gettempdir()) / "aoi_cross_check.bin"
    started = time.perf_counter()
    stats = buc_in_memory(data, attrs, 1, path)
    seconds = time.perf_counter() - started
    cells = read_cells(path, len(attrs))
    path.unlink()
    base = cells[(cells["cell"] != ALL).all(axis=1)]
    from_buc = {tuple(str(labels[a][c]) for a, c in zip(attrs, row["cell"])): int(row["count"]) for row in base}
    return {"aoi_tuples": None, "buc_cells_all": stats.cells, "buc_base_cells": len(from_buc),
            "buc_seconds": seconds}, from_buc


def main():
    OUT.mkdir(exist_ok=True)
    frame = read_census()

    checks = hierarchy_checks(frame)
    with open(OUT / "aoi_hierarchy_checks.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(checks[0]))
        writer.writeheader()
        writer.writerows(checks)
    for c in checks:
        print(c)

    hierarchies = aoi.standard_hierarchies()
    target, contrast = split_classes(frame)

    started = time.perf_counter()
    plan, rules = aoi.characteristic_rules(target, ATTRIBUTES, hierarchies, ATTR_THRESHOLD, REL_THRESHOLD)
    characteristic_seconds = time.perf_counter() - started
    aoi.write_rules(OUT / "aoi_characteristic_rules.csv", rules)

    started = time.perf_counter()
    discriminant = run_discriminant(target, contrast, hierarchies, "")
    discriminant_seconds = time.perf_counter() - started

    adult_target, adult_contrast = split_classes(frame, frame["age"].astype(int).to_numpy() >= 18)
    adults = run_discriminant(adult_target, adult_contrast, hierarchies, "_adults")

    sensitivity = []
    for threshold in [5, 10, 20, 30, 50, 100, 200]:
        started = time.perf_counter()
        p, r = aoi.characteristic_rules(target, ATTRIBUTES, hierarchies, ATTR_THRESHOLD, threshold)
        sensitivity.append({"rel_threshold": threshold, "rules": len(r), "attributes_kept": len(p.levels),
                            "climbs": p.climbs, "top_rule_t_weight": round(r[0]["t_weight"], 2),
                            "seconds": round(time.perf_counter() - started, 3)})
    aoi.write_rules(OUT / "aoi_thresholds.csv", sensitivity)

    cross, from_buc = cross_check_with_buc(target, plan, hierarchies)
    from_aoi = aoi.tuples_at(target, plan.levels, hierarchies)
    cross["aoi_tuples"] = len(from_aoi)
    cross["counts_identical"] = from_aoi == from_buc

    aoi.write_json(OUT / "aoi_summary.json", {
        "attributes": ATTRIBUTES, "attr_threshold": ATTR_THRESHOLD, "rel_threshold": REL_THRESHOLD,
        "characteristic": {"levels": plan.levels, "removed": plan.removed, "rules": len(rules),
                           "t_weight_total": sum(r["t_weight"] for r in rules),
                           "target_rows": sum(r["count"] for r in rules), "seconds": characteristic_seconds},
        "discriminant": {**discriminant, "seconds": discriminant_seconds},
        "discriminant_adults": adults,
        "cross_check_with_buc": cross,
    })
    print(plan.levels, plan.removed, len(rules))
    print(discriminant)
    print(adults)
    print(cross)
    for row in sensitivity:
        print(row)


if __name__ == "__main__":
    main()
