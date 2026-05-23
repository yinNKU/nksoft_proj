"""Command-line helper for building an ANN index."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # 允许直接运行 python scripts/build_index.py，不要求用户先手动设置 PYTHONPATH。
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Settings
from src.ann_engine import ANNEngine
from src.data_loader import prepare_dataset


def parse_args() -> argparse.Namespace:
    settings = Settings()
    parser = argparse.ArgumentParser(description="Build a FAISS ANN index for a .h5ad dataset.")
    parser.add_argument("--data", default=str(settings.data_path), help="Path to .h5ad data file.")
    parser.add_argument(
        "--index-type",
        choices=sorted(ANNEngine.SUPPORTED_INDEX_TYPES),
        default=settings.default_index_type,
        help="Index type to build.",
    )
    # 这些参数都给 B 的索引模块使用，便于展示不同索引参数下的效果差异。
    parser.add_argument("--n-pcs", type=int, default=settings.n_pcs, help="Number of PCA dimensions.")
    parser.add_argument("--hnsw-m", type=int, default=settings.hnsw_m, help="HNSW M parameter.")
    parser.add_argument(
        "--hnsw-ef-search",
        type=int,
        default=settings.hnsw_ef_search,
        help="HNSW efSearch parameter.",
    )
    parser.add_argument("--ivf-nlist", type=int, default=settings.ivf_nlist, help="IVF nlist parameter.")
    parser.add_argument("--ivf-nprobe", type=int, default=settings.ivf_nprobe, help="IVF nprobe parameter.")
    parser.add_argument(
        "--save",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Save the FAISS index and metadata JSON.",
    )
    parser.add_argument("--output-dir", default=str(settings.index_dir), help="Directory for index files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.data)
    output_dir = Path(args.output_dir)

    started_at = time.perf_counter()
    # prepare_dataset 会优先使用数据中已有的 X_pca；liver.h5ad 已包含 X_pca，因此不会重算 PCA。
    vectors, _, _ = prepare_dataset(data_path, n_pcs=args.n_pcs)
    load_time_ms = (time.perf_counter() - started_at) * 1000

    # 命令行参数统一映射到 ANNEngine 的 params，便于后续做性能对比实验。
    params = {
        "hnsw_m": args.hnsw_m,
        "hnsw_ef_search": args.hnsw_ef_search,
        "ivf_nlist": args.ivf_nlist,
        "ivf_nprobe": args.ivf_nprobe,
    }
    engine = ANNEngine()
    engine.build_index(
        vectors,
        index_type=args.index_type,
        metric="cosine",
        params=params,
        dataset_id=str(data_path.resolve()),
    )

    index_path = output_dir / f"{data_path.stem}_{args.index_type}.faiss"
    metadata_path = output_dir / f"{data_path.stem}_{args.index_type}.json"
    if args.save:
        # 保存索引和 metadata，后续 Web 启动或切换索引时可以直接复用缓存。
        engine.save_index(index_path, metadata_path)

    print(f"Index type: {args.index_type}")
    print(f"Vector count: {vectors.shape[0]}")
    print(f"Vector dimension: {vectors.shape[1]}")
    print(f"Data load/preprocess time ms: {load_time_ms:.2f}")
    print(f"Index build time ms: {engine.build_time_ms:.2f}")
    if args.save:
        print(f"Index saved to: {index_path}")
        print(f"Metadata saved to: {metadata_path}")


if __name__ == "__main__":
    main()
