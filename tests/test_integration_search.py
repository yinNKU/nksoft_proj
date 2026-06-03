"""Integration tests for the search pipeline using real components.

These tests use random vectors (not liver.h5ad) so they are fast and
do not require real data.  They verify that ANNEngine, SearchService,
and data_loader work together correctly.

运行: pytest tests/test_integration_search.py -v
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("faiss")

from src.ann_engine import ANNEngine, ANNEngineError
from src.search_service import SearchService, SearchServiceError


# ---------------------------------------------------------------------------
# ANNEngine integration tests
# ---------------------------------------------------------------------------


class TestANNEngineBuildAndSearch:
    """Test that all three index types can build and return correct results."""

    @pytest.mark.parametrize("index_type", ["flat", "hnsw", "ivf"])
    def test_build_and_search_self_ranks_first(
        self, random_vectors_small: np.ndarray, index_type: str
    ):
        """用自身向量查询时，Flat 精确检索必须把自身排第一位。"""
        engine = ANNEngine()
        params = {
            "hnsw_m": 16,
            "hnsw_ef_search": 32,
            "ivf_nlist": 10,
            "ivf_nprobe": 5,
        }
        engine.build_index(
            random_vectors_small,
            index_type=index_type,
            metric="cosine",
            params=params,
        )

        similarities, indices = engine.search(random_vectors_small[0], top_k=5)

        if index_type == "flat":
            # Flat is exact — self must be rank 1.
            assert int(indices[0]) == 0, f"Flat: expected self at rank 1, got {indices[0]}"
            assert similarities[0] > 0.99, f"Flat: self similarity too low: {similarities[0]:.6f}"

        assert len(indices) == 5
        assert len(similarities) == 5
        assert engine.index_type == index_type
        assert engine.build_time_ms is not None

    def test_flat_self_always_rank_one_across_multiple_cells(
        self, random_vectors_small: np.ndarray
    ):
        """验证 Flat 索引对多个不同细胞自身查询都返回自身为 Top-1。"""
        engine = ANNEngine()
        engine.build_index(random_vectors_small, index_type="flat")

        for idx in range(0, 50, 10):
            similarities, indices = engine.search(random_vectors_small[idx], top_k=3)
            assert int(indices[0]) == idx, f"cell {idx}: self not rank 1"


class TestANNEngineSaveLoad:
    """Test index persistence and round-trip correctness."""

    def test_save_load_roundtrip_all_types(
        self, tmp_path: Path, random_vectors_small: np.ndarray
    ):
        """保存/加载三种索引，加载后搜索结果应与原索引一致。"""
        params = {"hnsw_m": 16, "hnsw_ef_search": 32, "ivf_nlist": 10, "ivf_nprobe": 5}

        for index_type in ["flat", "hnsw", "ivf"]:
            # Build and save
            engine = ANNEngine()
            engine.build_index(
                random_vectors_small,
                index_type=index_type,
                metric="cosine",
                params=params,
                dataset_id="test-dataset",
            )
            original_sim, original_idx = engine.search(random_vectors_small[3], top_k=5)
            engine.save_index(
                tmp_path / f"{index_type}.faiss",
                tmp_path / f"{index_type}.json",
            )

            # Load and compare
            loaded = ANNEngine()
            loaded.load_index(
                tmp_path / f"{index_type}.faiss",
                random_vectors_small,
                metadata_path=tmp_path / f"{index_type}.json",
                dataset_id="test-dataset",
            )
            loaded_sim, loaded_idx = loaded.search(random_vectors_small[3], top_k=5)

            assert loaded.index_type == index_type
            np.testing.assert_array_equal(loaded_idx, original_idx)
            np.testing.assert_allclose(loaded_sim, original_sim, rtol=1e-5)

    def test_load_rejects_mismatched_metadata(
        self, tmp_path: Path, random_vectors_small: np.ndarray
    ):
        """加载索引时 metadata 不一致应拒绝加载。"""
        engine = ANNEngine()
        engine.build_index(
            random_vectors_small,
            index_type="flat",
            dataset_id="dataset-a",
        )
        engine.save_index(
            tmp_path / "flat.faiss",
            tmp_path / "flat.json",
        )

        # Tamper with dataset_id
        metadata = json.loads((tmp_path / "flat.json").read_text(encoding="utf-8"))
        metadata["dataset_id"] = "dataset-b"
        (tmp_path / "flat.json").write_text(json.dumps(metadata), encoding="utf-8")

        loaded = ANNEngine()
        with pytest.raises(ANNEngineError, match="metadata dataset mismatch"):
            loaded.load_index(
                tmp_path / "flat.faiss",
                random_vectors_small,
                metadata_path=tmp_path / "flat.json",
                dataset_id="dataset-a",
            )


class TestANNEngineEdgeCases:
    """Test error handling and boundary conditions."""

    def test_build_with_empty_vectors_raises(self):
        """空向量矩阵应抛出错误。"""
        engine = ANNEngine()
        with pytest.raises(ANNEngineError, match="empty vectors"):
            engine.build_index(np.empty((0, 50), dtype=np.float32), index_type="flat")

    def test_build_with_zero_dim_vectors_raises(self):
        """零维向量应抛出错误。"""
        engine = ANNEngine()
        with pytest.raises(ANNEngineError, match="zero-dimensional"):
            engine.build_index(np.empty((100, 0), dtype=np.float32), index_type="flat")

    def test_search_before_build_raises(self, random_vectors_small: np.ndarray):
        """未构建索引时搜索应抛出错误。"""
        engine = ANNEngine()
        with pytest.raises(ANNEngineError, match="index is not built"):
            engine.search(random_vectors_small[0], top_k=5)

    def test_top_k_exceeds_dataset(self, random_vectors_small: np.ndarray):
        """请求的 top_k 超过数据量时应自动截断返回所有可用结果。"""
        engine = ANNEngine()
        engine.build_index(random_vectors_small, index_type="flat")
        n = random_vectors_small.shape[0]

        similarities, indices = engine.search(random_vectors_small[0], top_k=n + 100)

        assert len(indices) == n  # clamped to dataset size

    def test_query_dimension_mismatch_raises(self, random_vectors_small: np.ndarray):
        """查询向量维度不匹配应报错。"""
        engine = ANNEngine()
        engine.build_index(random_vectors_small, index_type="flat")

        with pytest.raises(ANNEngineError, match="query dimension mismatch"):
            engine.search(np.ones(30, dtype=np.float32), top_k=5)

    def test_invalid_index_type_raises(self, random_vectors_small: np.ndarray):
        """不支持的索引类型应报错。"""
        engine = ANNEngine()
        with pytest.raises(ANNEngineError, match="unsupported index_type"):
            engine.build_index(random_vectors_small, index_type="bad-type")

    def test_ivf_with_custom_params(self, random_vectors_small: np.ndarray):
        """验证 IVF 自定义 nlist/nprobe 参数被正确应用。"""
        engine = ANNEngine()
        engine.build_index(
            random_vectors_small,
            index_type="ivf",
            params={"ivf_nlist": 8, "ivf_nprobe": 3},
        )

        assert engine.params["ivf_nlist"] == 8
        assert engine.params["ivf_nprobe"] == 3

    def test_index_type_switch(self, random_vectors_small: np.ndarray):
        """运行时切换索引类型后搜索正常。"""
        engine = ANNEngine()

        engine.build_index(random_vectors_small, index_type="flat")
        assert engine.index_type == "flat"
        _, _ = engine.search(random_vectors_small[0], top_k=3)

        engine.build_index(random_vectors_small, index_type="hnsw")
        assert engine.index_type == "hnsw"
        similarities, indices = engine.search(random_vectors_small[0], top_k=3)
        assert len(indices) == 3


# ---------------------------------------------------------------------------
# SearchService integration tests
# ---------------------------------------------------------------------------


class TestSearchServiceWithFakeData:
    """Test SearchService with real internal components but fake vectors."""

    @staticmethod
    def _make_service(vectors: np.ndarray, settings) -> SearchService:
        """Create a SearchService wired with the given vectors and fake metadata."""
        from types import SimpleNamespace

        n = vectors.shape[0]
        metadata = pd.DataFrame(
            {
                "cell_id": [f"cell_{i}" for i in range(n)],
                "cell_type": ["T" if i % 2 == 0 else "B" for i in range(n)],
                "donor": ["d1" if i < n // 2 else "d2" for i in range(n)],
                "quality_score": [float(i % 10) / 10.0 for i in range(n)],
            }
        )
        metadata.index = metadata["cell_id"]

        service = SearchService(settings)
        service.engine = ANNEngine()
        service.engine.build_index(vectors, index_type="hnsw", metric="cosine")
        service.adata = SimpleNamespace(
            obsm={
                "X_umap": np.column_stack(
                    [
                        np.linspace(0, n - 1, n, dtype=np.float32),
                        np.random.default_rng(0).normal(size=n).astype(np.float32),
                    ]
                ),
                "X_pca": np.column_stack(
                    [
                        np.linspace(0, n - 1, n, dtype=np.float32),
                        np.random.default_rng(0).normal(size=n).astype(np.float32),
                        np.zeros(n, dtype=np.float32),
                    ]
                ),
            }
        )
        service.metadata = metadata
        service.loaded = True
        service.last_error = None
        return service

    def test_search_by_cell_index(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        result = service.search_by_cell_index(cell_index=0, top_k=5)

        assert len(result["results"]) == 5
        assert result["results"][0]["cell_index"] == 0
        assert result["results"][0]["rank"] == 1
        assert "score" in result["results"][0]
        assert "metadata" in result["results"][0]

    def test_search_by_cell_id(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        result = service.search_by_cell_id(cell_id="cell_3", top_k=5)

        assert result["results"][0]["cell_id"] == "cell_3"

    def test_search_by_vector(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        query = random_vectors_small[10].tolist()
        result = service.search_by_vector(vector=query, top_k=5)

        assert len(result["results"]) == 5

    def test_metadata_filtering(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        result = service.search_by_cell_index(
            cell_index=0, top_k=10, filters={"cell_type": "B"}
        )

        assert result["results"]
        assert all(r["metadata"]["cell_type"] == "B" for r in result["results"])

    def test_top_k_clamping(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        # max_top_k in default Settings is 100
        result = service.search_by_cell_index(cell_index=0, top_k=9999)

        assert len(result["results"]) <= 100  # clamped by service

    def test_cell_id_not_found(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        with pytest.raises(SearchServiceError, match="cell_id not found"):
            service.search_by_cell_id(cell_id="nonexistent_cell", top_k=5)

    def test_cell_index_out_of_range(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        with pytest.raises(SearchServiceError, match="cell_index out of range"):
            service.search_by_cell_index(cell_index=99999, top_k=5)

    def test_metadata_nan_to_null(self, random_vectors_small: np.ndarray, settings):
        """NaN in metadata should be serialized as None/null."""
        service = self._make_service(random_vectors_small, settings)
        # set first cell's quality_score to NaN
        service.metadata.at["cell_0", "quality_score"] = np.nan

        result = service.search_by_cell_index(cell_index=0, top_k=1)
        assert result["results"][0]["metadata"]["quality_score"] is None

    def test_filter_field_not_exist(self, random_vectors_small: np.ndarray, settings):
        service = self._make_service(random_vectors_small, settings)
        with pytest.raises(SearchServiceError, match="metadata field not found"):
            service.search_by_cell_index(
                cell_index=0, top_k=5, filters={"nonexistent_field": "x"}
            )
