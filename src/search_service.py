"""Business layer for single-cell ANN search."""

from __future__ import annotations

from typing import Any

import numpy as np

from config import Settings
from src.ann_engine import ANNEngine, ANNEngineError
from src.data_loader import DataLoaderError, l2_normalize, prepare_dataset


class SearchServiceError(RuntimeError):
    """Raised when search service cannot complete a request."""


class SearchService:
    """Coordinate data loading, ANN index, and result formatting."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = ANNEngine()
        self.adata: Any | None = None
        self.metadata = None
        self.loaded = False
        self.last_error: str | None = None

    def initialize(self, allow_missing_data: bool = False) -> None:
        """Load data and build the default index.

        TODO:
        - 增加后台缓存，避免每次启动都重复 PCA。
        - 增加索引文件存在时自动 load_index。
        - 增加初始化耗时统计。
        """

        try:
            vectors, adata, metadata = prepare_dataset(
                self.settings.data_path,
                n_pcs=self.settings.n_pcs,
            )
            self.adata = adata
            self.metadata = metadata
            self.engine.build_index(vectors, index_type=self.settings.default_index_type)
            self.loaded = True
            self.last_error = None

        except (DataLoaderError, ANNEngineError) as exc:
            if not allow_missing_data:
                raise SearchServiceError(str(exc)) from exc

            self.loaded = False
            self.last_error = str(exc)

    def status(self) -> dict[str, Any]:
        """Return current service status for frontend."""

        vectors = self.engine.vectors
        return {
            "loaded": self.loaded,
            "data_path": str(self.settings.data_path),
            "n_cells": int(vectors.shape[0]) if vectors is not None else 0,
            "n_dims": int(vectors.shape[1]) if vectors is not None else 0,
            "index_type": self.engine.index_type,
            "last_error": self.last_error,
        }

    def _ensure_ready(self) -> None:
        if not self.loaded or self.engine.vectors is None or self.metadata is None:
            raise SearchServiceError(
                "Data is not loaded. Put a .h5ad file under data/sample.h5ad or set SC_DATA_PATH."
            )

    def _ensure_index_type(self, index_type: str) -> None:
        """Rebuild index if requested index type is different."""

        self._ensure_ready()

        if self.engine.index_type == index_type:
            return

        # 当前直接重建，后续可以缓存多个索引。
        # TODO: 缓存 HNSW / IVF / Flat，避免前端切换时反复重建。
        self.engine.build_index(self.engine.vectors, index_type=index_type)

    def _validate_k(self, k: int) -> int:
        if k <= 0:
            raise SearchServiceError("k must be positive")
        return min(k, self.settings.max_top_k)

    def search_by_cell_index(self, cell_index: int, k: int, index_type: str) -> dict[str, Any]:
        """Search similar cells by integer cell index."""

        self._ensure_ready()
        self._ensure_index_type(index_type)
        k = self._validate_k(k)

        vectors = self.engine.vectors
        assert vectors is not None

        if cell_index < 0 or cell_index >= vectors.shape[0]:
            raise SearchServiceError(f"cell_index out of range: {cell_index}")

        query_vector = vectors[cell_index]
        similarities, indices = self.engine.search(query_vector, k=k)

        return {
            "query": {"mode": "id", "cell_index": cell_index},
            "index_type": self.engine.index_type,
            "results": self._format_results(similarities, indices),
        }

    def search_by_cell_id(self, cell_id: str, k: int, index_type: str) -> dict[str, Any]:
        """Search similar cells by cell ID.

        TODO:
        - 建立 cell_id -> index 的字典，避免每次线性查找。
        - 对不存在的 cell_id 返回清晰错误。
        """

        self._ensure_ready()
        assert self.metadata is not None

        matches = self.metadata.index[self.metadata["cell_id"] == cell_id].tolist()
        if not matches:
            raise SearchServiceError(f"cell_id not found: {cell_id}")

        return self.search_by_cell_index(int(matches[0]), k=k, index_type=index_type)

    def search_by_vector(self, vector: list[float], k: int, index_type: str) -> dict[str, Any]:
        """Search similar cells by a custom vector.

        TODO:
        - 前端需要保证传入向量维度等于 n_pcs。
        - 后续可支持输入原始表达向量，再走同样的 PCA 投影。
        """

        self._ensure_ready()
        self._ensure_index_type(index_type)
        k = self._validate_k(k)

        query = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self.engine.dimension:
            raise SearchServiceError(
                f"vector dimension mismatch: expected {self.engine.dimension}, got {query.shape[1]}"
            )

        query = l2_normalize(query)[0]
        similarities, indices = self.engine.search(query, k=k)

        return {
            "query": {"mode": "vector"},
            "index_type": self.engine.index_type,
            "results": self._format_results(similarities, indices),
        }

    def _format_results(self, similarities: np.ndarray, indices: np.ndarray) -> list[dict[str, Any]]:
        """Format Top-K results as JSON-serializable dictionaries."""

        assert self.metadata is not None

        results = []
        for rank, (similarity, idx) in enumerate(zip(similarities, indices), start=1):
            idx = int(idx)
            row = self.metadata.iloc[idx].to_dict()

            # 统一转成字符串/数字，避免 numpy、category 类型无法 JSON 序列化。
            metadata = {}
            for key, value in row.items():
                if hasattr(value, "item"):
                    value = value.item()
                metadata[key] = value if isinstance(value, (int, float, str, bool)) else str(value)

            results.append(
                {
                    "rank": rank,
                    "index": idx,
                    "cell_id": str(metadata.get("cell_id", idx)),
                    "similarity": float(similarity),
                    "metadata": metadata,
                }
            )

        return results
