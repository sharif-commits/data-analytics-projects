# Data Cube and Rule Mining on Census Data

Bottom-Up Cubing (BUC), in memory and out of core, and attribute-oriented induction (AOI) on a census
extract of 299,285 records, using 12 dimensions.

The raw data is not included. Put the census extract at `M26_DA_A2/M26_DA_A2_Part2.csv` at the
repository root.

Run these from `src/`:

```
python build_hierarchies.py   # learn detail hierarchies from half of the rows
python run_aoi.py             # hierarchy checks, rules, thresholds, cross-check with BUC
python verify.py              # both BUC versions against DuckDB on all 4,096 group-bys
python benchmarks.py          # timing experiments; can take over an hour
python plots.py               # draw the plots
```

Run the unit tests from this folder with `python -m unittest discover -s tests`.

| Item | Location |
|---|---|
| Report | `report/report.pdf` |
| Data loading | `src/census.py` |
| In-memory BUC | `src/buc_memory.py` |
| Out-of-core BUC | `src/buc_disk.py` |
| AOI | `src/aoi.py`, `src/run_aoi.py` |
| Concept hierarchies | `hierarchies/` |
| Verification | `src/verify.py`, results in `outputs/verification.json` |
| Benchmarks and plots | `src/benchmarks.py`, `outputs/benchmark_*.csv`, `outputs/plots/` |
