#!/usr/bin/env python
"""Single-cell ANN search benchmark runner.

Runs Flat, HNSW, and IVF index benchmarks on a real .h5ad dataset.
Measures build time, query latency (p50/p95/p99), memory usage, and
recall@k (using Flat as ground truth).

Usage:
    python benchmarks/benchmark_runner.py
    python benchmarks/benchmark_runner.py --num-queries 20 --top-k-values 1,5,10
    python benchmarks/benchmark_runner.py --index-types hnsw,ivf
    python benchmarks/benchmark_runner.py --data-path data/other.h5ad
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Allow running from project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import DEFAULT_INDEX_TYPE, HNSW_M, HNSW_EF_SEARCH, IVF_NLIST, IVF_NPROBE  # noqa: E402
from src.ann_engine import ANNEngine  # noqa: E402
from src.data_loader import l2_normalize, prepare_dataset  # noqa: E402


def get_memory_mb() -> float:
    """Return current process RSS memory in MB."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return -1.0


def recall_at_k(approx_indices: np.ndarray, exact_indices: np.ndarray, k: int) -> float:
    """Compute recall@k: fraction of exact top-k found in approx top-k."""
    exact_set = set(int(i) for i in exact_indices[:k])
    approx_set = set(int(i) for i in approx_indices[:k])
    return len(exact_set & approx_set) / k if k > 0 else 1.0


def percentile(values: list[float], p: float) -> float:
    """Compute p-th percentile of a list."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = (len(sorted_vals) - 1) * p / 100.0
    lower = int(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    frac = idx - lower
    return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac


def build_and_benchmark(
    vectors: np.ndarray,
    index_type: str,
    top_k_values: list[int],
    query_indices: list[int],
    flat_results: dict[int, np.ndarray] | None = None,
) -> dict:
    """Build one index type and run latency/recall benchmarks.

    Parameters
    ----------
    vectors : (n, d) float32 L2-normalized array.
    index_type : "flat" | "hnsw" | "ivf".
    top_k_values : e.g. [1, 5, 10, 20, 50, 100].
    query_indices : list of cell indices to use as queries.
    flat_results : if provided, use Flat results as ground truth for recall.

    Returns
    -------
    dict with keys: index_type, params, build_time_ms, build_memory_mb, top_k_benchmarks.
    """
    engine = ANNEngine()

    # --- Build -----------------------------------------------------------
    params = {}
    if index_type == "hnsw":
        params = {"hnsw_m": HNSW_M, "hnsw_ef_search": HNSW_EF_SEARCH}
    elif index_type == "ivf":
        nlist = max(1, min(IVF_NLIST, vectors.shape[0]))
        params = {"ivf_nlist": nlist, "ivf_nprobe": min(IVF_NPROBE, nlist)}

    mem_before = get_memory_mb()
    engine.build_index(
        vectors,
        index_type=index_type,
        metric="cosine",
        params=params,
        dataset_id="benchmark",
    )
    mem_after = get_memory_mb()
    build_memory_mb = max(0, mem_after - mem_before)

    # --- Query benchmarks ------------------------------------------------
    top_k_benchmarks = []
    max_k = max(top_k_values)

    for k in top_k_values:
        latencies: list[float] = []
        recalls: list[float] = []

        for query_idx in query_indices:
            query = vectors[query_idx]
            started_at = time.perf_counter()
            similarities, indices = engine.search(query, top_k=k)
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            latencies.append(elapsed_ms)

            if flat_results is not None and index_type != "flat":
                exact_idx = flat_results.get(query_idx)
                if exact_idx is not None:
                    r = recall_at_k(indices, exact_idx, k)
                    recalls.append(r)

        entry = {
            "top_k": k,
            "num_queries": len(query_indices),
            "mean_latency_ms": round(float(np.mean(latencies)), 4),
            "p50_latency_ms": round(percentile(latencies, 50), 4),
            "p95_latency_ms": round(percentile(latencies, 95), 4),
            "p99_latency_ms": round(percentile(latencies, 99), 4),
            "min_latency_ms": round(min(latencies), 4),
            "max_latency_ms": round(max(latencies), 4),
        }
        if recalls:
            entry["recall_at_k"] = round(float(np.mean(recalls)), 4)
        elif index_type == "flat":
            entry["recall_at_k"] = 1.0  # Flat is ground truth

        top_k_benchmarks.append(entry)

    return {
        "index_type": index_type,
        "params": engine.params,
        "build_time_ms": round(engine.build_time_ms, 2),
        "build_memory_mb": round(build_memory_mb, 2),
        "top_k_benchmarks": top_k_benchmarks,
    }


def main():
    parser = argparse.ArgumentParser(description="ANN benchmark runner")
    parser.add_argument(
        "--data-path",
        default=str(PROJECT_ROOT / "data" / "liver.h5ad"),
        help="Path to .h5ad file",
    )
    parser.add_argument(
        "--num-queries", type=int, default=50,
        help="Number of query cells (default: 50)",
    )
    parser.add_argument(
        "--top-k-values", default="1,5,10,20,50,100",
        help="Comma-separated top_k values (default: 1,5,10,20,50,100)",
    )
    parser.add_argument(
        "--index-types", default="flat,hnsw,ivf",
        help="Comma-separated index types (default: flat,hnsw,ivf)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "benchmarks" / "results"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--n-pcs", type=int, default=50,
        help="Number of PCA components (default: 50)",
    )
    args = parser.parse_args()

    data_path = Path(args.data_path)
    if not data_path.exists():
        print(f"[ERROR] Data file not found: {data_path}")
        sys.exit(1)

    index_types = [t.strip() for t in args.index_types.split(",")]
    top_k_values = [int(k) for k in args.top_k_values.split(",")]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Load data -------------------------------------------------------
    print(f"[benchmark] Loading {data_path} ...")
    os.environ["SC_DATA_PATH"] = str(data_path)
    vectors, adata, metadata = prepare_dataset(data_path, n_pcs=args.n_pcs)
    n_cells, n_pcs = vectors.shape
    print(f"[benchmark] Dataset: {n_cells} cells, {n_pcs} dimensions")

    # --- Select query indices --------------------------------------------
    step = max(1, n_cells // args.num_queries)
    query_indices = list(range(0, n_cells, step))[: args.num_queries]
    print(f"[benchmark] Query indices: {len(query_indices)} cells")

    # --- Run benchmarks --------------------------------------------------
    results = []
    flat_results_cache: dict[int, np.ndarray] | None = None

    for index_type in index_types:
        print(f"\n[benchmark] Building {index_type.upper()} index ...")
        t0 = time.perf_counter()

        result = build_and_benchmark(
            vectors, index_type, top_k_values, query_indices,
            flat_results=flat_results_cache,
        )
        elapsed_s = time.perf_counter() - t0
        print(f"  Build: {result['build_time_ms']:.2f} ms")
        print(f"  Memory: {result['build_memory_mb']:.2f} MB")
        for entry in result["top_k_benchmarks"]:
            recall_str = f" recall={entry.get('recall_at_k', 'N/A')}" if index_type != "flat" else " recall=1.0 (ground truth)"
            print(f"  k={entry['top_k']:3d}  mean={entry['mean_latency_ms']:8.4f} ms  "
                  f"p50={entry['p50_latency_ms']:8.4f} ms  p99={entry['p99_latency_ms']:8.4f} ms{recall_str}")

        results.append(result)

        # Cache Flat results as ground truth for subsequent index types
        if index_type == "flat":
            flat_results_cache = {}
            engine_flat = ANNEngine()
            engine_flat.build_index(vectors, index_type="flat", metric="cosine")
            for idx in query_indices:
                _, indices = engine_flat.search(vectors[idx], top_k=max(top_k_values))
                flat_results_cache[idx] = indices

    # --- Write output ----------------------------------------------------
    metadata_out = {
        "dataset": str(data_path.resolve()),
        "n_cells": n_cells,
        "n_pcs": n_pcs,
        "num_queries": len(query_indices),
        "top_k_values": top_k_values,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
    output = {"metadata": metadata_out, "results": results}

    json_path = output_dir / "benchmark_results.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[benchmark] Results written to {json_path}")

    # CSV summary for quick inspection in Excel
    csv_path = output_dir / "benchmark_results.csv"
    csv_lines = ["index_type,top_k,mean_latency_ms,p50_latency_ms,p95_latency_ms,p99_latency_ms,recall_at_k,build_time_ms,build_memory_mb"]
    for r in results:
        for entry in r["top_k_benchmarks"]:
            csv_lines.append(
                f"{r['index_type']},{entry['top_k']},"
                f"{entry['mean_latency_ms']},{entry['p50_latency_ms']},"
                f"{entry['p95_latency_ms']},{entry['p99_latency_ms']},"
                f"{entry.get('recall_at_k', '')},"
                f"{r['build_time_ms']},{r['build_memory_mb']}"
            )
    csv_path.write_text("\n".join(csv_lines), encoding="utf-8")
    print(f"[benchmark] CSV written to {csv_path}")


if __name__ == "__main__":
    main()
