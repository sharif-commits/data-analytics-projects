"""Part 2 -- Attribute-Oriented Induction (AOI).

AOI (Han, Cai & Cercone, KDD'93) generalises a query relation into a small
number of characteristic rules by walking each attribute up a **concept
hierarchy** and merging identical tuples.  Unlike BUC it produces a
*fixed-size* output: at most ``max_relations`` generalised rows, whatever
the input size.

Algorithm (per the original paper):

 1. **Attribute removal.**  An attribute that carries only a record id
    (a distinct value per record) cannot be generalised usefully and is
    dropped from the relation.
 2. **Hierarchy climbing / threshold control.**  While the relation has
    more distinct tuples than ``max_relations``, or some attribute has
    more distinct values than ``attr_threshold``, the next value up the
    hierarchy is substituted for the offending attribute(s) and identical
    tuples are merged, summing their weights (counts).
 3. **Root control.**  A value whose parent is ``ANY`` is already fully
    generalised and stays put; climbing stops when nothing changes.

Hierarchies are loaded from simple ``value,parent`` CSV files in
``part2/hierarchies`` (one per attribute, >= 5 attributes as required).
`validate_builtin_hierarchies` checks the generalisation machinery against
the four detailed/summary column pairs that ship with the dataset itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Mapping

import numpy as np
import pandas as pd

from dataset import BUILTIN_HIERARCHY_PAIRS, HIER_DIR


# --------------------------------------------------------------------- stats
@dataclass
class AOIStats:
    """Counters mirroring BUCStats so the report can line them up."""

    n_tuples_in: int = 0
    n_tuples_out: int = 0
    attributes_in: int = 0
    attributes_out: int = 0
    generalisations: int = 0          # value->parent substitutions performed
    climb_steps: int = 0              # full relation-level climb rounds
    merges: int = 0                   # tuples lost to merging
    distinct_in: int = 0
    distinct_out: int = 0
    elapsed: float = 0.0
    kept_attributes: list = field(default_factory=list)
    dropped_attributes: list = field(default_factory=list)
    levels_used: dict = field(default_factory=dict)   # attr -> final level
    climb_rounds: dict = field(default_factory=dict)  # attr -> #climbs (or "ANY")

    def as_row(self) -> dict:
        return {
            "tuples_in": self.n_tuples_in,
            "tuples_out": self.n_tuples_out,
            "attributes_in": self.attributes_in,
            "attributes_out": self.attributes_out,
            "generalisations": self.generalisations,
            "climb_steps": self.climb_steps,
            "merges": self.merges,
            "distinct_in": self.distinct_in,
            "distinct_out": self.distinct_out,
            "elapsed_s": round(self.elapsed, 4),
        }


# ------------------------------------------------------------- hierarchies
class Hierarchy:
    """A concept hierarchy: leaf values -> parent -> ... -> ANY.

    The file format is a two-column CSV ``value,parent``.  A row
    ``a,b`` says a's parent is b; a row ``b,ANY`` makes b the root of
    its branch.  Values absent from the file are leaves that cannot be
    climbed (their parent is themselves).
    """

    ANY = "ANY"

    def __init__(self, name: str, mapping: dict[str, str]):
        self.name = name
        # climbable edges only (parent is a real value, not ANY/"")
        self.mapping = {
            k: v for k, v in mapping.items() if v not in ("", self.ANY)
        }
        self.roots = {k for k, v in mapping.items() if v == self.ANY}
        self.has_any = bool(self.roots)

    def parent_of(self, value: str) -> str | None:
        """Parent of *value*, or None when it cannot be climbed."""
        return self.mapping.get(value)

    def parent_of_many(self, values: np.ndarray) -> np.ndarray | None:
        """Parents of every value; ``None`` when nothing can be climbed."""
        s = pd.Series(values)
        parents = s.map(self.mapping)             # NaN where no parent
        if parents.isna().all():
            return None
        out = parents.where(parents.notna(), s).to_numpy()
        if bool((out == values).all()):
            return None
        return out

    def level_of(self, value: str) -> int:
        """Depth of *value* from the leaf of its branch (leaf = 0)."""
        depth, cur, seen = 0, value, set()
        while cur in self.mapping and cur not in seen:
            seen.add(cur)
            cur = self.mapping[cur]
            depth += 1
        return depth

    def height(self) -> int:
        return max((self.level_of(v) for v in self.mapping), default=0) + 1

    def describe(self) -> dict:
        return {
            "attribute": self.name,
            "climbable_values": len(self.mapping),
            "height": self.height(),
            "roots": len(self.roots) if self.roots else "-",
        }


def load_hierarchy(path: Path) -> Hierarchy:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    if len(df.columns) < 2:
        raise ValueError(f"{path}: need at least value,parent columns")
    mapping = dict(zip(df.iloc[:, 0].str.strip(), df.iloc[:, 1].str.strip()))
    return Hierarchy(Path(path).stem, mapping)


def load_hierarchies(dirpath: Path = HIER_DIR) -> dict[str, Hierarchy]:
    out = {}
    for p in sorted(Path(dirpath).glob("*.csv")):
        out[p.stem] = load_hierarchy(p)
    return out


# --------------------------------------------------------------- the engine
def aoi(
    df: pd.DataFrame,
    hierarchies: Mapping[str, Hierarchy],
    weights: str = "count",          # "count" or a numeric column to sum
    attr_threshold: int = 5,
    max_relations: int = 20,
    drop_ids: bool = True,
) -> tuple[pd.DataFrame, AOIStats]:
    """Run AOI on *df* restricted to the attributes of *hierarchies*.

    ``attr_threshold``   maximum distinct values kept per attribute; more
                         distinct values than this triggers a climb.
    ``max_relations``    maximum number of generalised tuples in the result.
    ``drop_ids``         remove attributes with a distinct value per record
                         before generalisation (attribute-removal step).
    """
    attrs = [a for a in hierarchies if a in df.columns]
    stats = AOIStats(
        n_tuples_in=len(df),
        attributes_in=len(attrs),
        kept_attributes=list(attrs),
    )
    t0 = perf_counter()

    # ---- weight column: tuple multiplicity ------------------------------
    if weights == "count":
        wname = "count"
    else:
        wname = f"sum({weights})"

    # ---- step 1: attribute removal (ids / near-unique attributes) -------
    work: dict[str, np.ndarray] = {}
    for a in attrs:
        vals = df[a].to_numpy()
        if drop_ids and pd.unique(vals).size >= len(df) * 0.99:
            stats.dropped_attributes.append(a)
            stats.kept_attributes.remove(a)
            continue
        work[a] = vals
        stats.levels_used[a] = 0

    if not work:                                   # nothing left to do
        stats.elapsed = perf_counter() - t0
        return pd.DataFrame(), stats

    keys = pd.DataFrame(work)
    if weights == "count":
        keys["_w"] = 1.0
    else:
        keys["_w"] = pd.to_numeric(
            df[weights], errors="coerce"
        ).fillna(0.0).to_numpy(float)

    stats.distinct_in = len(keys.drop_duplicates(subset=list(work)))

    # ---- step 2: climb + merge until both thresholds are satisfied -------
    while True:
        cols = list(work)
        n_distinct = len(keys.drop_duplicates(subset=cols))
        over_attr = [a for a in cols if keys[a].nunique() > attr_threshold]
        if n_distinct <= max_relations and not over_attr:
            break

        progressed = False
        # climb the offending attributes first; if the relation is still
        # too wide, climb every attribute one round (relation threshold)
        targets = over_attr if over_attr else cols
        for a in targets:
            parent = hierarchies[a].parent_of_many(keys[a].to_numpy())
            if parent is not None:
                keys[a] = parent
                stats.generalisations += len(keys)
                stats.levels_used[a] = hierarchies[a].level_of(parent[0])
                stats.climb_rounds[a] = stats.climb_rounds.get(a, 0) + 1
                progressed = True

        if not progressed:
            # ---- last resort: generalise the widest attribute to ANY ----
            # (classic AOI threshold control: when no hierarchy climbing
            # is possible but the relation is still too wide, the
            # attribute with the most distinct values is dropped to ANY)
            if n_distinct > max_relations:
                widest = max(cols, key=lambda a: keys[a].nunique())
                if keys[widest].nunique() > 1:
                    keys[widest] = Hierarchy.ANY
                    stats.generalisations += len(keys)
                    stats.levels_used[widest] = "ANY"
                    stats.climb_rounds[widest] = "ANY"
                    progressed = True
            if not progressed:
                break                               # fully generalised

        # merge identical tuples, summing weights
        before = len(keys)
        keys = (
            keys.groupby(cols, sort=False, dropna=False)["_w"]
            .sum()
            .reset_index()
        )
        stats.merges += before - len(keys)
        stats.climb_steps += 1
        if stats.climb_steps > 50:                 # safety valve
            break

    # ---- final relation --------------------------------------------------
    out = keys.rename(columns={"_w": wname})
    out = out.sort_values(wname, ascending=False).reset_index(drop=True)
    stats.n_tuples_out = len(out)
    stats.attributes_out = len(work)
    stats.distinct_out = len(out)
    stats.elapsed = perf_counter() - t0
    return out, stats


# ------------------------------------------------- class comparison (t/d)
def generalize_to_levels(
    df: pd.DataFrame,
    hierarchies: Mapping[str, Hierarchy],
    climb_rounds: Mapping[str, int | str],
    attrs: list[str] | None = None,
) -> pd.DataFrame:
    """Apply exactly the generalisation recorded in *climb_rounds*.

    Used by `aoi_class_rules` to push the contrasting class through the
    SAME concept-hierarchy levels the target class ended up at, so that
    t-weights and d-weights are computed over comparable rules.
    """
    cols = attrs if attrs is not None else [a for a in hierarchies if a in df.columns]
    work: dict[str, np.ndarray] = {}
    for a in cols:
        rounds = climb_rounds.get(a, 0)
        if rounds == "ANY":
            work[a] = np.full(len(df), Hierarchy.ANY, dtype=object)
            continue
        vals = df[a].to_numpy()
        for _ in range(int(rounds)):
            parent = hierarchies[a].parent_of_many(vals)
            if parent is None:
                break
            vals = parent
        work[a] = vals
    keys = pd.DataFrame(work)
    keys["count"] = 1.0
    return keys.groupby(cols, sort=False, dropna=False)["count"].sum().reset_index()


def aoi_class_rules(
    df: pd.DataFrame,
    hierarchies: Mapping[str, Hierarchy],
    class_col: str,
    target_label: str,
    contrast_label: str | None = None,
    attr_threshold: int = 5,
    max_relations: int = 20,
) -> tuple[pd.DataFrame, AOIStats]:
    """Class-comparison AOI: characteristic rules with **t-weights** for the
    target class and **discriminant rules** with **d-weights** against the
    contrasting class (Han, Cai & Cercone, KDD'93; class comparison).

    The target class is generalised first; the contrasting class is then
    pushed through the *same* hierarchy levels, and every generalised tuple
    of the target class becomes one rule row:

        t-weight = count_target(rule) / |target class|      (typicality)
        d-weight = count_contrast(rule) / |contrast class|  (discriminability)

    A rule with a high t-weight and a low d-weight is a strong signature of
    the target class; a high d-weight means the condition is just as common
    in the contrasting class and discriminates poorly.
    """
    target = df[df[class_col] == target_label]
    contrast = (
        df[df[class_col] != target_label]
        if contrast_label is None
        else df[df[class_col] == contrast_label]
    )

    gen_t, stats = aoi(
        target, hierarchies, "count",
        attr_threshold=attr_threshold, max_relations=max_relations,
    )
    if gen_t.empty:
        return gen_t, stats

    attrs = [c for c in gen_t.columns if c != "count"]
    gen_c = generalize_to_levels(contrast, hierarchies, stats.climb_rounds, attrs)

    rules = gen_t.merge(
        gen_c, on=attrs, how="left", suffixes=("_target", "_contrast")
    )
    rules["count_contrast"] = rules["count_contrast"].fillna(0.0)
    total_t, total_c = len(target), len(contrast)
    rules["t_weight_%"] = (rules["count_target"] / total_t * 100).round(2)
    rules["d_weight_%"] = (rules["count_contrast"] / total_c * 100).round(2)
    rules = rules.sort_values("count_target", ascending=False).reset_index(drop=True)
    return rules, stats


# ----------------------------------------------------------- validation aid
def validate_builtin_hierarchies(
    df: pd.DataFrame, verbose: bool = True
) -> list[dict]:
    """Validate the generalisation machinery on the dataset's own
    detailed -> summary column pairs (industry, occupation, household,
    state).  If lifting the detailed column one level up its induced
    hierarchy reproduces the summary column, the machinery is sound."""
    results = []
    for det, summ in BUILTIN_HIERARCHY_PAIRS:
        if det not in df.columns or summ not in df.columns:
            continue
        # induce value -> parent from the data itself (majority parent)
        mapping = (
            df.groupby(det)[summ]
            .agg(lambda s: s.mode().iat[0] if not s.mode().empty else None)
            .to_dict()
        )
        h = Hierarchy(det, {k: v for k, v in mapping.items() if v})
        lifted = df[det].map(lambda v: h.parent_of(v))
        agreement = float((lifted == df[summ]).mean())
        results.append(
            {
                "detailed": det,
                "summary": summ,
                "pairs": len(h.mapping),
                "agreement": round(agreement, 4),
                "ok": agreement >= 0.90,
            }
        )
        if verbose:
            print(
                f"  {det:34s} -> {summ:28s} "
                f"pairs={len(h.mapping):4d}  agreement={agreement:.2%}"
            )
    return results


if __name__ == "__main__":                                        # smoke test
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from dataset import load_raw

    df = load_raw()
    print("validating built-in hierarchies (detailed -> summary):")
    validate_builtin_hierarchies(df)
    hier = load_hierarchies()
    print(f"\nloaded {len(hier)} hierarchies: {sorted(hier)}")
    for name, h in hier.items():
        print(f"  {name:24s} {h.describe()}")