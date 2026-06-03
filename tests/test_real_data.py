"""Tests that require the real data/liver.h5ad file and real FAISS.

These tests are marked with @pytest.mark.real_data and @pytest.mark.slow.
They are skipped by default.  Run with:

    pytest -m real_data
    pytest -m slow

Requirements: data/liver.h5ad must exist and faiss-cpu must be installed.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("faiss")

from src.ann_engine import ANNEngine
from src.search_service import SearchService


# ---------------------------------------------------------------------------
# Data loading tests
# ---------------------------------------------------------------------------

@pytest.mark.real_data
@pytest.mark.slow
class TestRealDataLoading:
    """Verify that liver.h5ad can be loaded and produces valid vectors."""

    def test_vectors_have_expected_shape(self, liver_vectors: np.ndarray):
        """加载真实数据后验证向量矩阵形状合理。"""
        assert liver_vectors.ndim == 2
        assert liver_vectors.shape[0] > 100  # at least 100 cells
        assert liver_vectors.shape[1] > 0  # at least 1 PC
        assert liver_vectors.dtype == np.float32

    def test_vectors_are_normalized(self, liver_vectors: np.ndarray):
        """验证向量是 L2 归一化的（范数 ≈ 1.0）。"""
        sample = liver_vectors[: min(100, liver_vectors.shape[0])]
        norms = np.linalg.norm(sample, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_metadata_not_empty(self, liver_metadata):
        """验证元数据非空且包含 cell_id 列。"""
        assert liver_metadata is not None
        assert len(liver_metadata) > 0
        assert "cell_id" in liver_metadata.columns

    def test_sample_query_indices_valid(self, liver_vectors, sample_query_indices):
        """验证预选查询索引都在有效范围内。"""
        n = liver_vectors.shape[0]
        for idx in sample_query_indices:
            assert 0 <= idx < n, f"query index {idx} out of range [0, {n})"


# ---------------------------------------------------------------------------
# Index build and search tests on real data
# ---------------------------------------------------------------------------

@pytest.mark.real_data
@pytest.mark.slow
class TestRealDataIndexBuild:
    """Build each index type on real data and verify basic correctness."""

    @pytest.mark.parametrize("index_type", ["flat", "hnsw", "ivf"])
    def test_build_index_on_real_data(
        self, liver_vectors: np.ndarray, index_type: str
    ):
        """在真实数据上构建每种索引，验证基本属性。"""
        engine = ANNEngine()
        engine.build_index(
            liver_vectors,
            index_type=index_type,
            metric="cosine",
            dataset_id="liver-real",
        )

        assert engine.index_type == index_type
        assert engine.dimension == liver_vectors.shape[1]
        assert engine.metadata["num_vectors"] == liver_vectors.shape[0]
        assert engine.build_time_ms is not None
        assert engine.build_time_ms > 0

        # Quick search to verify it works
        similarities, indices = engine.search(liver_vectors[0], top_k=3)
        assert len(indices) == 3

    def test_flat_search_self_on_real_data(self, liver_vectors: np.ndarray):
        """Flat 精确检索：在真实数据上用自身查询，自身应排第一。"""
        engine = ANNEngine()
        engine.build_index(liver_vectors, index_type="flat", metric="cosine")

        test_indices = [0, 100, 500, 1000]
        for idx in test_indices:
            if idx >= liver_vectors.shape[0]:
                continue
            similarities, indices = engine.search(liver_vectors[idx], top_k=5)
            assert int(indices[0]) == idx, (
                f"Flat self-search: expected {idx} at rank 1, got {indices[0]}"
            )
            assert similarities[0] > 0.999, (
                f"Flat self-similarity too low for cell {idx}: {similarities[0]:.8f}"
            )


# ---------------------------------------------------------------------------
# Recall benchmarks against Flat (Flat = ground truth)
# ---------------------------------------------------------------------------

@pytest.mark.real_data
@pytest.mark.slow
class TestRecallVsFlat:
    """Measure HNSW and IVF recall against Flat (exact search)."""

    @pytest.fixture(scope="class")
    def flat_engine(self, liver_vectors: np.ndarray) -> ANNEngine:
        """Flat index on real data (ground truth)."""
        engine = ANNEngine()
        engine.build_index(liver_vectors, index_type="flat", metric="cosine")
        return engine

    @pytest.fixture(scope="class")
    def hnsw_engine(self, liver_vectors: np.ndarray) -> ANNEngine:
        """HNSW index on real data."""
        engine = ANNEngine()
        engine.build_index(
            liver_vectors,
            index_type="hnsw",
            metric="cosine",
            params={"hnsw_m": 32, "hnsw_ef_search": 64},
        )
        return engine

    @pytest.fixture(scope="class")
    def ivf_engine(self, liver_vectors: np.ndarray) -> ANNEngine:
        """IVF index on real data."""
        engine = ANNEngine()
        n = liver_vectors.shape[0]
        nlist = max(1, min(100, int(np.sqrt(n))))
        engine.build_index(
            liver_vectors,
            index_type="ivf",
            metric="cosine",
            params={"ivf_nlist": nlist, "ivf_nprobe": min(10, nlist)},
        )
        return engine

    @staticmethod
    def _recall_at_k(approx_indices: np.ndarray, exact_indices: np.ndarray, k: int) -> float:
        """Compute recall@k: fraction of exact top-k found in approx top-k."""
        exact_set = set(exact_indices[:k])
        approx_set = set(approx_indices[:k])
        intersection = exact_set & approx_set
        return len(intersection) / k if k > 0 else 1.0

    def test_hnsw_recall_at_10(
        self,
        liver_vectors: np.ndarray,
        flat_engine: ANNEngine,
        hnsw_engine: ANNEngine,
        sample_query_indices: list[int],
    ):
        """HNSW recall@10 should be ≥ 0.90 vs Flat ground truth."""
        recalls = []
        for idx in sample_query_indices:
            _, exact_idx = flat_engine.search(liver_vectors[idx], top_k=10)
            _, approx_idx = hnsw_engine.search(liver_vectors[idx], top_k=10)
            r = self._recall_at_k(approx_idx, exact_idx, 10)
            recalls.append(r)

        mean_recall = float(np.mean(recalls))
        assert mean_recall >= 0.90, (
            f"HNSW mean recall@10 = {mean_recall:.4f}, expected ≥ 0.90"
        )

    def test_ivf_recall_at_10(
        self,
        liver_vectors: np.ndarray,
        flat_engine: ANNEngine,
        ivf_engine: ANNEngine,
        sample_query_indices: list[int],
    ):
        """IVF recall@10 should be ≥ 0.80 vs Flat ground truth."""
        recalls = []
        for idx in sample_query_indices:
            _, exact_idx = flat_engine.search(liver_vectors[idx], top_k=10)
            _, approx_idx = ivf_engine.search(liver_vectors[idx], top_k=10)
            r = self._recall_at_k(approx_idx, exact_idx, 10)
            recalls.append(r)

        mean_recall = float(np.mean(recalls))
        assert mean_recall >= 0.80, (
            f"IVF mean recall@10 = {mean_recall:.4f}, expected ≥ 0.80"
        )

    def test_hnsw_build_time_recorded(self, hnsw_engine: ANNEngine):
        """验证 HNSW 构建耗时已记录且为正数。"""
        assert hnsw_engine.build_time_ms is not None
        assert hnsw_engine.build_time_ms > 0

    def test_ivf_build_time_recorded(self, ivf_engine: ANNEngine):
        """验证 IVF 构建耗时已记录且为正数。"""
        assert ivf_engine.build_time_ms is not None
        assert ivf_engine.build_time_ms > 0
