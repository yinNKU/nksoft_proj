"""Basic tests for ANNEngine.

运行：
    pytest

说明：
- 当前测试不依赖真实 .h5ad 数据；
- 只验证 ANN 引擎的最小行为；
- 如果本地没安装 faiss-cpu，会自动跳过。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("faiss")

from src.ann_engine import ANNEngine, ANNEngineError


TEST_OUTPUT_DIR = Path(__file__).resolve().parent / "_tmp_ann_engine"


def normalized_vectors(rows: int = 100, dims: int = 16, seed: int = 42) -> np.ndarray:
    """生成单位化随机向量，模拟 data_loader 输出的 PCA 细胞向量。"""

    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(rows, dims)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors


def fresh_test_output_dir() -> Path:
    """使用项目内临时目录，避免 Windows 系统 Temp 权限问题影响测试。"""

    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(parents=True)
    return TEST_OUTPUT_DIR


def test_search_self_should_rank_first():
    vectors = normalized_vectors()

    engine = ANNEngine()
    engine.build_index(vectors, index_type="flat")

    similarities, indices = engine.search(vectors[0], k=5)

    # Flat 精确检索时，用自身向量查询必须把自身排在第一位。
    assert int(indices[0]) == 0
    assert similarities[0] > 0.99


def test_hnsw_build_and_search():
    vectors = normalized_vectors(rows=50, dims=8, seed=7)

    engine = ANNEngine()
    engine.build_index(vectors, index_type="hnsw")

    similarities, indices = engine.search(vectors[3], k=3)

    assert len(indices) == 3
    assert len(similarities) == 3


@pytest.mark.parametrize("index_type", ["flat", "hnsw", "ivf"])
def test_supported_index_types_build_and_return_top_k(index_type):
    # B 的核心要求：三种索引都能构建，并且能返回指定数量的 Top-K。
    vectors = normalized_vectors(rows=80, dims=12, seed=11)

    engine = ANNEngine()
    engine.build_index(
        vectors,
        index_type=index_type,
        params={"hnsw_m": 16, "hnsw_ef_search": 32, "ivf_nlist": 8, "ivf_nprobe": 4},
        dataset_id="dataset-a",
    )

    similarities, indices = engine.search(vectors[2], top_k=7)

    assert engine.index_type == index_type
    assert engine.dimension == 12
    assert engine.metadata["dataset_id"] == "dataset-a"
    assert engine.build_time_ms is not None
    assert len(indices) == 7
    assert len(similarities) == 7


def test_query_dimension_mismatch_should_raise():
    vectors = normalized_vectors(rows=30, dims=6, seed=12)
    engine = ANNEngine()
    engine.build_index(vectors, index_type="flat")

    with pytest.raises(ANNEngineError, match="query dimension mismatch"):
        engine.search(np.ones(5, dtype=np.float32), top_k=3)


def test_invalid_index_type_should_raise():
    vectors = normalized_vectors(rows=30, dims=6, seed=13)
    engine = ANNEngine()

    with pytest.raises(ANNEngineError, match="unsupported index_type"):
        engine.build_index(vectors, index_type="bad-index")


def test_invalid_top_k_should_raise():
    vectors = normalized_vectors(rows=30, dims=6, seed=14)
    engine = ANNEngine()
    engine.build_index(vectors, index_type="flat")

    with pytest.raises(ANNEngineError, match="top_k must be positive"):
        engine.search(vectors[0], top_k=0)


def test_save_and_load_index_with_metadata():
    # 保存/加载必须同时验证 metadata，否则容易误用其他数据集的旧索引。
    vectors = normalized_vectors(rows=40, dims=10, seed=15)
    output_dir = fresh_test_output_dir()
    index_path = output_dir / "flat.faiss"
    metadata_path = output_dir / "flat.json"

    engine = ANNEngine()
    engine.build_index(vectors, index_type="flat", dataset_id="dataset-a")
    engine.save_index(index_path, metadata_path)

    loaded = ANNEngine()
    loaded.load_index(index_path, vectors, metadata_path=metadata_path, dataset_id="dataset-a")
    similarities, indices = loaded.search(vectors[0], top_k=5)

    assert index_path.exists()
    assert metadata_path.exists()
    assert loaded.index_type == "flat"
    assert int(indices[0]) == 0
    assert similarities[0] > 0.99


def test_load_index_rejects_metadata_mismatch():
    vectors = normalized_vectors(rows=40, dims=10, seed=16)
    output_dir = fresh_test_output_dir()
    index_path = output_dir / "flat.faiss"
    metadata_path = output_dir / "flat.json"

    engine = ANNEngine()
    engine.build_index(vectors, index_type="flat", dataset_id="dataset-a")
    engine.save_index(index_path, metadata_path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    # 人为篡改 dataset_id，用来验证加载缓存时的数据集一致性检查。
    metadata["dataset_id"] = "dataset-b"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    loaded = ANNEngine()
    with pytest.raises(ANNEngineError, match="metadata dataset mismatch"):
        loaded.load_index(index_path, vectors, metadata_path=metadata_path, dataset_id="dataset-a")
