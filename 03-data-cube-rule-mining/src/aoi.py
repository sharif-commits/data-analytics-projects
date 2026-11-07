"""Attribute-Oriented Induction (AOI) with characteristic and discriminant rules.

Each attribute is generalised by climbing its concept hierarchy, or removed when it has too many
values and no hierarchy left to climb. Identical generalised tuples are merged and counted.

Weights follow Han and Kamber:
    t-weight(q) = count(q in target) / total count of target
    d-weight(q) = count(q in target) / (count(q in target) + count(q in contrast))
A t-weight says how typical q is of the target. A d-weight says how much of q is target, so it
should be read against the base rate of the target class.
"""
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HIERARCHY_DIR = Path(__file__).resolve().parents[1] / "hierarchies"
ANY = "ANY"


class Hierarchy:
    """A concept hierarchy: levels[k] maps a level-0 value to its ancestor at level k."""

    def __init__(self, levels):
        self.levels = levels          # list of dicts; levels[0] is the identity on the leaves

    @property
    def height(self):
        return len(self.levels) - 1

    def generalize(self, values, level):
        """Map an array of leaf values to `level`. A value missing from the hierarchy is an error."""
        mapping = self.levels[level]
        unique, inverse = np.unique(values, return_inverse=True)
        missing = [u for u in unique.tolist() if u not in mapping]
        if missing:
            raise KeyError(f"values not in hierarchy: {missing[:5]}")
        return np.array([mapping[u] for u in unique.tolist()], dtype=object)[inverse]


def load_table(name):
    """Read a hierarchy CSV as rows of strings."""
    with open(HIERARCHY_DIR / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def hierarchy_from_table(rows):
    """Build a Hierarchy from rows with columns level_0, level_1, ..."""
    depth = sum(1 for c in rows[0] if c.startswith("level_"))
    return Hierarchy([{r["level_0"]: r[f"level_{k}"] for r in rows} for k in range(depth)])


def hierarchy_from_ranges(rows):
    """Build a Hierarchy for a numeric attribute from rows with columns low, high, level_1, ..."""
    depth = sum(1 for c in rows[0] if c.startswith("level_")) + 1
    levels = [{} for _ in range(depth)]
    for r in rows:
        for value in range(int(r["low"]), int(r["high"]) + 1):
            levels[0][str(value)] = str(value)
            for k in range(1, depth):
                levels[k][str(value)] = r[f"level_{k}"]
    return Hierarchy(levels)


def compose(detail_rows, upper_rows):
    """Join a detail -> level_1 table with a level_1 -> level_2 table into one Hierarchy."""
    upper = {r["level_1"]: r["level_2"] for r in upper_rows}
    leaves = {r["level_0"]: r["level_1"] for r in detail_rows}
    return Hierarchy([{v: v for v in leaves}, leaves, {v: upper[p] for v, p in leaves.items()}])


def standard_hierarchies():
    """Every hierarchy used for rule mining, read from the CSV files."""
    return {
        "age": hierarchy_from_ranges(load_table("age_ranges.csv")),
        "weeks_worked_in_year": hierarchy_from_ranges(load_table("weeks_worked_ranges.csv")),
        "education": hierarchy_from_table(load_table("education.csv")),
        "class_of_worker": hierarchy_from_table(load_table("class_of_worker.csv")),
        "marital_status": hierarchy_from_table(load_table("marital_status.csv")),
        "citizenship": hierarchy_from_table(load_table("citizenship.csv")),
        "race": hierarchy_from_table(load_table("race.csv")),
        "industry_code_detailed": compose(load_table("industry_detail.csv"), load_table("industry_sector.csv")),
        "occupation_code_detailed": compose(load_table("occupation_detail.csv"), load_table("occupation_sector.csv")),
    }


@dataclass
class Generalization:
    """The result of generalising a relation."""
    levels: dict          # kept attribute -> hierarchy level (0 = raw values)
    removed: list         # (attribute, reason)
    climbs: int           # hierarchy steps taken in total


def distinct_count(values, hierarchy, level):
    return len(set(hierarchy.levels[level].get(v) for v in np.unique(values).tolist())) if hierarchy \
        else len(np.unique(values))


def current_values(frame, attr, level, hierarchies):
    """An attribute's column at the given level."""
    h = hierarchies.get(attr)
    return h.generalize(frame[attr], level) if h and level else frame[attr]


def tuples_at(frame, levels, hierarchies):
    """Merge rows into distinct generalised tuples. Returns {tuple: count}."""
    attrs = list(levels)
    if not attrs:
        return {(): len(next(iter(frame.values())))}
    encoded = np.zeros(len(frame[attrs[0]]), dtype=np.int64)
    decoders = []
    for a in attrs:
        unique, codes = np.unique(current_values(frame, a, levels[a], hierarchies).astype(str), return_inverse=True)
        encoded = encoded * len(unique) + codes
        decoders.append(unique)
    keys, counts = np.unique(encoded, return_counts=True)
    merged = {}
    for key, count in zip(keys.tolist(), counts.tolist()):
        parts = []
        for unique in reversed(decoders):
            key, code = divmod(key, len(unique))
            parts.append(str(unique[code]))
        merged[tuple(reversed(parts))] = count
    return merged


def generalize_relation(frame, attributes, hierarchies, attr_threshold, rel_threshold):
    """Choose a level per attribute so the relation meets both thresholds.

    Step 1, attribute threshold: while an attribute has too many values, climb one level. With no
    level left to climb, remove the attribute.
    Step 2, relation threshold: while there are too many tuples, climb the attribute with the most
    values. An attribute that would climb to ANY is removed, because it no longer says anything.
    """
    levels, removed, climbs = {}, [], 0
    for attr in attributes:
        h = hierarchies.get(attr)
        level = 0
        while distinct_count(frame[attr], h, level) > attr_threshold:
            if h is None or level == h.height:
                break
            level += 1
            climbs += 1
        if distinct_count(frame[attr], h, level) > attr_threshold:
            removed.append((attr, "too many values and no higher concept"))
        else:
            levels[attr] = level

    while len(tuples_at(frame, levels, hierarchies)) > rel_threshold and levels:
        widest = max(levels, key=lambda a: (distinct_count(frame[a], hierarchies.get(a), levels[a]), a))
        h = hierarchies.get(widest)
        if h is None or levels[widest] == h.height:
            del levels[widest]
            removed.append((widest, f"climbed to {ANY} to meet the relation threshold"))
        else:
            levels[widest] += 1
        climbs += 1
    return Generalization(levels, removed, climbs)


def characteristic_rules(target, attributes, hierarchies, attr_threshold, rel_threshold):
    """Generalise the target class alone and attach t-weights."""
    plan = generalize_relation(target, attributes, hierarchies, attr_threshold, rel_threshold)
    merged = tuples_at(target, plan.levels, hierarchies)
    total = sum(merged.values())
    rules = [{**dict(zip(plan.levels, q)), "count": c, "t_weight": 100.0 * c / total} for q, c in merged.items()]
    rules.sort(key=lambda r: -r["count"])
    return plan, rules


def discriminant_rules(target, contrast, attributes, hierarchies, attr_threshold, rel_threshold):
    """Generalise both classes to the same levels, and attach t-weights and d-weights."""
    both = {a: np.concatenate([target[a], contrast[a]]) for a in target}
    plan = generalize_relation(both, attributes, hierarchies, attr_threshold, rel_threshold)
    in_target = tuples_at(target, plan.levels, hierarchies)
    in_contrast = tuples_at(contrast, plan.levels, hierarchies)
    total_target = sum(in_target.values())
    base_rate = total_target / (total_target + sum(in_contrast.values()))
    rules = []
    for q in set(in_target) | set(in_contrast):
        ct, cc = in_target.get(q, 0), in_contrast.get(q, 0)
        d = ct / (ct + cc)
        rules.append({**dict(zip(plan.levels, q)), "target_count": ct, "contrast_count": cc,
                      "t_weight": 100.0 * ct / total_target, "d_weight": 100.0 * d, "lift": d / base_rate})
    rules.sort(key=lambda r: (-r["target_count"], -r["contrast_count"]))
    return plan, rules, base_rate


def rule_text(rule, attrs, weight, label):
    """Format one rule condition with its weight."""
    condition = " AND ".join(f"{a}={rule[a]}" for a in attrs)
    return f"{condition} [{label}: {rule[weight]:.2f}%]"


def write_rules(path, rules):
    """Save rules as CSV."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rules[0]))
        writer.writeheader()
        writer.writerows(rules)


def write_json(path, payload):
    """Save a summary as JSON."""
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
