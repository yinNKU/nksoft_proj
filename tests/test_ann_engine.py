"""Basic tests for ANNEngine.

运行：
    pytest

说明：
- 当前测试不依赖真实 .h5ad 数据；
- 只验证 ANN 引擎的最小行为；
- 如果本地没安装 faiss-cpu，会自动跳过。
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("faiss")

from src.ann_engine import ANNEngine


def test_search_self_should_rank_first():
    rng = np.random.default_rng(42)
    vectors = rng.normal(size=(100, 16)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    engine = ANNEngine()
    engine.build_index(vectors, index_type="flat")

    similarities, indices = engine.search(vectors[0], k=5)

    assert int(indices[0]) == 0
    assert similarities[0] > 0.99


def test_hnsw_build_and_search():
    rng = np.random.default_rng(7)
    vectors = rng.normal(size=(50, 8)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    engine = ANNEngine()
    engine.build_index(vectors, index_type="hnsw")

    similarities, indices = engine.search(vectors[3], k=3)

    assert len(indices) == 3
    assert len(similarities) == 3
