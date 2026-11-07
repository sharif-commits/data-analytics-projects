"""Draw the performance plots from the benchmark CSVs."""
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "outputs"
PLOTS = OUT / "plots"
COLORS = {"memory": "#2a6f97", "disk": "#c8553d"}
LABELS = {"memory": "in-memory", "disk": "out-of-core (1 MB)"}


def with_spread(ax, frame, x, label, color):
    """Plot the median with a bar from the fastest to the slowest run."""
    ax.errorbar(frame[x], frame["median_s"],
                yerr=[frame["median_s"] - frame["min_s"], frame["max_s"] - frame["median_s"]],
                marker="o", capsize=3, label=label, color=color)


def finish(ax, name, xlabel, title):
    ax.set_xlabel(xlabel)
    ax.set_ylabel("runtime (s)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.figure.tight_layout()
    ax.figure.savefig(PLOTS / name, dpi=160)
    plt.close(ax.figure)


def plot_minsup():
    data = pd.read_csv(OUT / "benchmark_minsup.csv")
    _, ax = plt.subplots(figsize=(6, 3.6))
    for version in ["memory", "disk"]:
        with_spread(ax, data[data.version == version], "minsup", LABELS[version], COLORS[version])
    ax.set_xscale("log")
    ax.legend()
    finish(ax, "minsup_runtime.png", "minsup (log scale)", "Runtime vs minsup, 12 dimensions")


def plot_memory():
    data = pd.read_csv(OUT / "benchmark_memory.csv")
    data["memory_mb"] = data.memory_bytes / (1 << 20)
    _, ax = plt.subplots(figsize=(6, 3.6))
    with_spread(ax, data, "memory_mb", "out-of-core", COLORS["disk"])
    ax.set_xscale("log", base=2)
    ax.set_xticks(data.memory_mb)
    ax.set_xticklabels([f"{m:g}" for m in data.memory_mb])
    minsup = int(data.minsup.iloc[0])
    finish(ax, "memory_runtime.png", "memory budget (MB, log scale)", f"Runtime vs memory budget, minsup = {minsup}")


def plot_dims():
    data = pd.read_csv(OUT / "benchmark_dims.csv")
    _, ax = plt.subplots(figsize=(6, 3.6))
    for version in ["memory", "disk"]:
        with_spread(ax, data[data.version == version], "dimensions", LABELS[version], COLORS[version])
    ax.set_yscale("log")
    ax.legend()
    minsup = int(data.minsup.iloc[0])
    finish(ax, "dims_runtime.png", "number of dimensions", f"Runtime vs dimensions, minsup = {minsup} (log scale)")


def plot_orders():
    data = pd.read_csv(OUT / "benchmark_optimization.csv")
    data = data[data.version == "memory"].sort_values("median_s", ascending=False)
    _, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(data["order"], data["median_s"], color=COLORS["memory"],
            xerr=[data["median_s"] - data["min_s"], data["max_s"] - data["median_s"]], capsize=3)
    ax.set_xlabel("runtime (s)")
    ax.set_title("Dimension order, in-memory BUC")
    ax.grid(alpha=0.3, axis="x")
    ax.figure.tight_layout()
    ax.figure.savefig(PLOTS / "order_runtime.png", dpi=160)
    plt.close(ax.figure)


def main():
    PLOTS.mkdir(parents=True, exist_ok=True)
    plot_minsup()
    plot_memory()
    plot_dims()
    plot_orders()


if __name__ == "__main__":
    main()
