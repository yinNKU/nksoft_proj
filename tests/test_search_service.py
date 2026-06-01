from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config import Settings
from src.search_service import SearchService, SearchServiceError


class FakeEngine:
    def __init__(self, vectors: np.ndarray) -> None:
        self.vectors = vectors
        self.dimension = vectors.shape[1]
        self.index_type = "hnsw"

    def search(self, query_vector: np.ndarray, top_k: int = 10, k: int | None = None):
        # 简化版搜索：用内积做相似度，保证测试可重复。
        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        scores = self.vectors @ query
        size = int(k if k is not None else top_k)
        indices = np.argsort(-scores)[:size]
        return scores[indices], indices


class FakeAdata:
    def __init__(self) -> None:
        self.obsm = {
            "X_umap": np.array(
                [
                    [0.0, 0.0],
                    [1.0, 1.0],
                    [2.0, 0.5],
                    [3.0, 1.5],
                ],
                dtype=np.float32,
            ),
            "X_pca": np.array(
                [
                    [0.0, 0.0, 1.0],
                    [1.0, 1.0, 1.0],
                    [2.0, 0.5, 1.0],
                    [3.0, 1.5, 1.0],
                ],
                dtype=np.float32,
            ),
        }


def make_service() -> SearchService:
    settings = Settings()
    # 构造小型向量和元数据，便于覆盖过滤与边界条件。
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    metadata = pd.DataFrame(
        {
            "cell_id": ["cell_a", "cell_b", "cell_c", "cell_d"],
            "cell_type": ["T", "B", "T", "B"],
            "donor": ["d1", "d1", "d2", "d2"],
            "quality_score": [np.nan, 0.8, 0.9, 1.0],
        }
    )
    # 模拟真实数据：metadata 的索引就是 cell_id 字符串。
    metadata.index = metadata["cell_id"]
    service = SearchService(settings)
    service.engine = FakeEngine(vectors)
    service.adata = FakeAdata()
    service.metadata = metadata
    service.loaded = True
    service.last_error = None
    return service


def test_search_by_cell_index_success():
    service = make_service()

    result = service.search_by_cell_index(cell_index=0, top_k=3)

    assert len(result["results"]) == 3
    assert result["results"][0]["rank"] == 1
    assert result["results"][0]["cell_index"] == 0


def test_metadata_nan_is_json_null():
    service = make_service()

    result = service.search_by_cell_index(cell_index=0, top_k=1)

    assert result["results"][0]["metadata"]["quality_score"] is None


def test_embedding_points_success():
    service = make_service()

    result = service.embedding_points(basis="umap", color_by="cell_type")

    assert result["basis"] == "umap"
    assert result["color_by"] == "cell_type"
    assert result["n_points"] == 4
    assert result["points"][0]["cell_id"] == "cell_a"
    assert result["points"][0]["color"] == "T"


def test_search_by_cell_id_success():
    service = make_service()

    result = service.search_by_cell_id(cell_id="cell_b", top_k=2)

    assert result["results"][0]["cell_id"] == "cell_b"


def test_search_by_vector_success():
    service = make_service()

    result = service.search_by_vector(vector=[1.0, 0.0, 0.0], top_k=2)

    assert len(result["results"]) == 2


def test_top_k_effective():
    service = make_service()

    result = service.search_by_cell_index(cell_index=1, top_k=1)

    assert len(result["results"]) == 1


def test_cell_id_not_found():
    service = make_service()

    with pytest.raises(SearchServiceError, match="cell_id not found"):
        service.search_by_cell_id(cell_id="missing", top_k=3)


def test_cell_index_out_of_range():
    service = make_service()

    with pytest.raises(SearchServiceError, match="cell_index out of range"):
        service.search_by_cell_index(cell_index=99, top_k=3)


def test_vector_dimension_error():
    service = make_service()

    with pytest.raises(SearchServiceError, match="vector dimension mismatch"):
        service.search_by_vector(vector=[1.0, 0.0], top_k=3)


def test_filters_field_exists():
    service = make_service()

    result = service.search_by_cell_index(cell_index=0, top_k=4, filters={"cell_type": "T"})

    assert result["results"]
    assert all(item["metadata"]["cell_type"] == "T" for item in result["results"])


def test_filters_field_not_exist():
    service = make_service()

    with pytest.raises(SearchServiceError, match="metadata field not found"):
        service.search_by_cell_index(cell_index=0, top_k=4, filters={"bad_field": "x"})


def test_filtered_results_insufficient():
    service = make_service()

    result = service.search_by_cell_index(cell_index=0, top_k=3, filters={"cell_type": "B"})

    assert len(result["results"]) == 2
    assert result["warning"]
