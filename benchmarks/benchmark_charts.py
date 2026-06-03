#!/usr/bin/env python
"""Generate performance comparison charts from benchmark_results.json.

Usage:
    python benchmarks/benchmark_charts.py
    python benchmarks/benchmark_charts.py --results benchmarks/results/benchmark_results.json --output benchmarks/charts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# ---------------------------------------------------------------------------
# Style constants (matching the frontend colour theme)
# ---------------------------------------------------------------------------
COLORS = {"flat": "#7a8b7f", "hnsw": "#0f6f55", "ivf": "#b7791f"}
COLOR_LABELS = {"flat": "Flat (exact)", "hnsw": "HNSW", "ivf": "IVF"}
DPI = 150
FONT_FAMILY = "Microsoft YaHei, SimHei, DejaVu Sans, sans-serif"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans", "Arial"],
    "axes.unicode_minus": False,
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
    "savefig.bbox": "tight",
    "savefig.facecolor": "#fffdf7",
})


def load_results(results_path: Path) -> dict:
    return json.loads(results_path.read_text(encoding="utf-8"))


def chart_build_time(results: list[dict], output_dir: Path) -> None:
    """Build time comparison: grouped bar chart."""
    index_types = [r["index_type"] for r in results]
    build_times = [r["build_time_ms"] for r in results]
    colors = [COLORS.get(t, "#999") for t in index_types]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(index_types, build_times, color=colors, edgecolor="#111814", linewidth=0.8)
    ax.set_title("Index Build Time Comparison", fontsize=14, fontweight="bold", color="#111814")
    ax.set_ylabel("Build Time (ms)", fontsize=11)
    ax.set_xlabel("Index Type", fontsize=11)

    for bar, val in zip(bars, build_times):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(build_times) * 0.01,
                f"{val:,.1f} ms", ha="center", fontsize=10, color="#111814")

    fig.tight_layout()
    fig.savefig(output_dir / "build_time_comparison.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [chart] build_time_comparison.png")


def chart_query_latency(results: list[dict], output_dir: Path) -> None:
    """Query latency vs top_k: line chart."""
    fig, ax = plt.subplots(figsize=(8, 5))

    for r in results:
        entries = r["top_k_benchmarks"]
        k_vals = [e["top_k"] for e in entries]
        latencies = [e["mean_latency_ms"] for e in entries]
        ax.plot(k_vals, latencies, marker="o", linewidth=2, markersize=6,
                color=COLORS.get(r["index_type"], "#999"),
                label=COLOR_LABELS.get(r["index_type"], r["index_type"]))

    ax.set_title("Query Latency vs Top-K", fontsize=14, fontweight="bold", color="#111814")
    ax.set_xlabel("Top-K", fontsize=11)
    ax.set_ylabel("Mean Query Latency (ms)", fontsize=11)
    ax.legend(frameon=True, facecolor="#fffdf7", edgecolor="#ccc")
    ax.grid(True, alpha=0.3)
    ax.set_yscale("log")
    # Add value labels for the smallest and largest k
    for r in results:
        entries = r["top_k_benchmarks"]
        for e in [entries[0], entries[-1]]:
            ax.annotate(f"{e['mean_latency_ms']:.2f}",
                        (e["top_k"], e["mean_latency_ms"]),
                        textcoords="offset points", xytext=(0, 10),
                        fontsize=8, color=COLORS.get(r["index_type"], "#999"), ha="center")

    fig.tight_layout()
    fig.savefig(output_dir / "query_latency_by_top_k.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [chart] query_latency_by_top_k.png")


def chart_recall(results: list[dict], output_dir: Path) -> None:
    """Recall@k vs top_k: line chart (HNSW and IVF vs Flat ground truth)."""
    fig, ax = plt.subplots(figsize=(8, 5))

    # Reference line for Flat
    approx_results = [r for r in results if r["index_type"] != "flat"]
    if not approx_results:
        print("  [chart] recall_by_top_k.png skipped (no approx index results)")
        plt.close(fig)
        return

    k_vals_ref = [e["top_k"] for e in approx_results[0]["top_k_benchmarks"]]
    ax.axhline(y=1.0, color=COLORS["flat"], linestyle="--", linewidth=1.5,
               label=COLOR_LABELS["flat"])

    for r in approx_results:
        entries = r["top_k_benchmarks"]
        k_vals = [e["top_k"] for e in entries]
        recalls = [e.get("recall_at_k", 0) for e in entries]
        ax.plot(k_vals, recalls, marker="s", linewidth=2, markersize=6,
                color=COLORS.get(r["index_type"], "#999"),
                label=COLOR_LABELS.get(r["index_type"], r["index_type"]))

    ax.set_title("Recall@K vs Top-K (Ground Truth: Flat)", fontsize=14, fontweight="bold", color="#111814")
    ax.set_xlabel("Top-K", fontsize=11)
    ax.set_ylabel("Recall@K", fontsize=11)
    ax.set_ylim(0.0, 1.05)
    ax.legend(frameon=True, facecolor="#fffdf7", edgecolor="#ccc")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "recall_by_top_k.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [chart] recall_by_top_k.png")


def chart_latency_recall_tradeoff(results: list[dict], output_dir: Path) -> None:
    """Scatter plot: latency vs recall trade-off."""
    fig, ax = plt.subplots(figsize=(8, 6))

    for r in results:
        if r["index_type"] == "flat":
            continue
        entries = r["top_k_benchmarks"]
        latencies = [e["mean_latency_ms"] for e in entries]
        recalls = [e.get("recall_at_k", 0) for e in entries]
        k_vals = [e["top_k"] for e in entries]
        color = COLORS.get(r["index_type"], "#999")
        label = COLOR_LABELS.get(r["index_type"], r["index_type"])

        ax.scatter(latencies, recalls, c=color, s=80, label=label, edgecolors="#111814", linewidth=0.5, zorder=3)
        for k, lat, rec in zip(k_vals, latencies, recalls):
            ax.annotate(f"k={k}", (lat, rec), textcoords="offset points",
                        xytext=(5, 5), fontsize=8, color=color)

    # Flat as reference
    flat = next((r for r in results if r["index_type"] == "flat"), None)
    if flat:
        flat_lat = flat["top_k_benchmarks"][-1]["mean_latency_ms"]
        ax.axvline(x=flat_lat, color=COLORS["flat"], linestyle="--", linewidth=1, alpha=0.6)
        ax.scatter([flat_lat], [1.0], c=COLORS["flat"], s=100, marker="D",
                   label=COLOR_LABELS["flat"], edgecolors="#111814", linewidth=0.5, zorder=3)
        ax.annotate("Flat\nk=100", (flat_lat, 1.0), textcoords="offset points",
                    xytext=(10, -15), fontsize=8, color=COLORS["flat"])

    ax.set_title("Latency vs Recall Trade-off", fontsize=14, fontweight="bold", color="#111814")
    ax.set_xlabel("Mean Query Latency (ms)", fontsize=11)
    ax.set_ylabel("Recall@K", fontsize=11)
    ax.legend(frameon=True, facecolor="#fffdf7", edgecolor="#ccc")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "latency_recall_tradeoff.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [chart] latency_recall_tradeoff.png")


def chart_memory_usage(results: list[dict], output_dir: Path) -> None:
    """Memory usage comparison: bar chart."""
    index_types = [r["index_type"] for r in results]
    memories = [r["build_memory_mb"] for r in results]
    colors = [COLORS.get(t, "#999") for t in index_types]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(index_types, memories, color=colors, edgecolor="#111814", linewidth=0.8)
    ax.set_title("Peak Memory Usage During Index Build", fontsize=14, fontweight="bold", color="#111814")
    ax.set_ylabel("Memory (MB)", fontsize=11)
    ax.set_xlabel("Index Type", fontsize=11)

    for bar, val in zip(bars, memories):
        label = f"{val:.1f} MB" if val > 0 else "N/A"
        y_pos = bar.get_height() + max(memories) * 0.02
        ax.text(bar.get_x() + bar.get_width() / 2, y_pos, label, ha="center", fontsize=10, color="#111814")

    fig.tight_layout()
    fig.savefig(output_dir / "memory_usage_comparison.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [chart] memory_usage_comparison.png")


def main():
    parser = argparse.ArgumentParser(description="Benchmark chart generator")
    parser.add_argument(
        "--results",
        default=str(PROJECT_ROOT / "benchmarks" / "results" / "benchmark_results.json"),
        help="Path to benchmark_results.json",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "benchmarks" / "charts"),
        help="Output directory for chart PNGs",
    )
    args = parser.parse_args()

    PROJECT_ROOT_CHARTS = Path(__file__).resolve().parents[1]
    results_path = Path(args.results)
    if not results_path.exists():
        print(f"[ERROR] Results file not found: {results_path}")
        print("Run benchmark_runner.py first.")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[charts] Loading {results_path}")
    data = load_results(results_path)
    results = data["results"]
    metadata = data.get("metadata", {})

    print(f"[charts] Dataset: {metadata.get('n_cells', '?')} cells, "
          f"{metadata.get('n_pcs', '?')} PCs, "
          f"{metadata.get('num_queries', '?')} queries")
    print(f"[charts] Generating charts → {output_dir}")

    chart_build_time(results, output_dir)
    chart_query_latency(results, output_dir)
    chart_recall(results, output_dir)
    chart_latency_recall_tradeoff(results, output_dir)
    chart_memory_usage(results, output_dir)

    print(f"\n[charts] Done. {len(list(output_dir.glob('*.png')))} PNG files generated.")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    main()
