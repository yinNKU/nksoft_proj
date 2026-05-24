"""Business layer for single-cell ANN search."""

from __future__ import annotations

from typing import Any

import numpy as np

from config import Settings
from src.ann_engine import ANNEngine, ANNEngineError
from src.data_loader import (
    DataLoaderError,
    get_available_metadata,
    get_dataset_summary,
    l2_normalize,
    prepare_dataset,
)


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
            # 启动时优先加载已保存的索引缓存；缓存缺失或不匹配时再重建。
            if not self.load_cached_index(self.settings.default_index_type, vectors=vectors):
                self.rebuild_index(self.settings.default_index_type, vectors=vectors)
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
            "build_time_ms": self.engine.build_time_ms,
            "dataset": get_dataset_summary(self.adata) if self.adata is not None else None,
            "last_error": self.last_error,
        }

    def metadata_columns(self) -> dict[str, Any]:
        """Return available metadata fields for frontend filters and tables."""

        self._ensure_ready()
        assert self.adata is not None
        return {"columns": get_available_metadata(self.adata)}

    def ensure_index_type(self, index_type: str) -> None:
        """Ensure the requested index type is available before searching."""

        self._ensure_index_type(index_type)

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

        # 前端切换索引类型时，先尝试复用缓存，避免反复构建大数据索引。
        if not self.load_cached_index(index_type):
            self.rebuild_index(index_type)

    def rebuild_index(self, index_type: str = "hnsw", vectors: np.ndarray | None = None) -> dict[str, Any]:
        """Rebuild and cache the current dataset index."""

        if vectors is None:
            # 外部 API 调用重建时通常不会传 vectors，此时直接使用服务中已加载的数据向量。
            self._ensure_ready()
            vectors = self.engine.vectors
        assert vectors is not None

        # 重建后立即写入 .faiss 和 .json，供下一次启动或切换索引时复用。
        self.engine.build_index(
            vectors,
            index_type=index_type,
            metric="cosine",
            params=self.settings.ann_params(),
            dataset_id=str(self.settings.data_path.resolve()),
        )
        self.engine.save_index(
            self.settings.index_path(index_type),
            self.settings.index_metadata_path(index_type),
        )
        return {
            "index_type": self.engine.index_type,
            "index_path": str(self.settings.index_path(index_type)),
            "metadata_path": str(self.settings.index_metadata_path(index_type)),
            "build_time_ms": self.engine.build_time_ms,
        }

    def load_cached_index(
        self,
        index_type: str = "hnsw",
        vectors: np.ndarray | None = None,
    ) -> bool:
        """Load a cached FAISS index when both index and metadata files match."""

        if vectors is None:
            vectors = self.engine.vectors
        if vectors is None:
            return False

        index_path = self.settings.index_path(index_type)
        metadata_path = self.settings.index_metadata_path(index_type)
        if not index_path.exists() or not metadata_path.exists():
            # 必须同时存在索引和 metadata；缺任意一个都视为缓存不可用。
            return False

        try:
            # load_index 会校验 metadata，防止加载到维度或数据集不一致的旧索引。
            self.engine.load_index(
                index_path,
                vectors,
                metadata_path=metadata_path,
                dataset_id=str(self.settings.data_path.resolve()),
            )
        except ANNEngineError as exc:
            self.last_error = str(exc)
            return False

        return True

    def _validate_k(self, k: int) -> int:
        if k <= 0:
            raise SearchServiceError("k must be positive")
        # 服务层限制最大 Top-K，避免前端误传过大数值导致检索或响应过重。
        return min(k, self.settings.max_top_k)

    def search_by_cell_index(
        self,
        cell_index: int,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search similar cells by integer cell index."""

        self._ensure_ready()
        if self.engine.index_type is None:
            self._ensure_index_type(self.settings.default_index_type)
        top_k = self._validate_k(top_k)

        vectors = self.engine.vectors
        assert vectors is not None

        if cell_index < 0 or cell_index >= vectors.shape[0]:
            raise SearchServiceError(f"cell_index out of range: {cell_index}")

        query_vector = vectors[cell_index]
        similarities, indices = self.engine.search(query_vector, k=top_k)

        results = self._format_results(similarities, indices)
        filtered, warning = self._apply_metadata_filters(results, filters, top_k=top_k)

        return {"results": filtered, "warning": warning}

    def search_by_cell_id(
        self,
        cell_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search similar cells by cell ID.

        TODO:
        - 建立 cell_id -> index 的字典，避免每次线性查找。
        - 对不存在的 cell_id 返回清晰错误。
        """

        self._ensure_ready()
        assert self.metadata is not None

        matches = self.metadata.index[self.metadata["cell_id"] == cell_id].tolist()
        if not matches:
            raise SearchServiceError("cell_id not found")

        return self.search_by_cell_index(int(matches[0]), top_k=top_k, filters=filters)

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search similar cells by a custom vector.

        TODO:
        - 前端需要保证传入向量维度等于 n_pcs。
        - 后续可支持输入原始表达向量，再走同样的 PCA 投影。
        """

        self._ensure_ready()
        if self.engine.index_type is None:
            self._ensure_index_type(self.settings.default_index_type)
        top_k = self._validate_k(top_k)

        if vector is None:
            raise SearchServiceError("vector must be a list of floats")

        query = np.asarray(vector, dtype=np.float32)
        if query.ndim == 2 and query.shape[0] == 1:
            query = query.reshape(-1)
        if query.ndim != 1:
            raise SearchServiceError("vector must be a 1D list of floats")
        if self.engine.dimension is None or query.shape[0] != self.engine.dimension:
            raise SearchServiceError(
                f"vector dimension mismatch: expected {self.engine.dimension}, got {query.shape[0]}"
            )

        query = l2_normalize(query)[0]
        similarities, indices = self.engine.search(query, k=top_k)

        results = self._format_results(similarities, indices)
        filtered, warning = self._apply_metadata_filters(results, filters, top_k=top_k)

        return {"results": filtered, "warning": warning}

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
                    "cell_index": idx,
                    "cell_id": str(metadata.get("cell_id", idx)),
                    "score": float(similarity),
                    "metadata": metadata,
                }
            )

        return results

    def _apply_metadata_filters(
        self,
        results: list[dict[str, Any]],
        filters: dict[str, Any] | None,
        top_k: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Filter results by metadata fields and return optional warning."""

        if not filters:
            return results, None

        if not isinstance(filters, dict):
            raise SearchServiceError("filters must be a dict")

        assert self.metadata is not None
        available_fields = set(self.metadata.columns)
        for field in filters.keys():
            if field not in available_fields:
                raise SearchServiceError(f"metadata field not found: {field}")

        filtered = [
            item
            for item in results
            if all(item.get("metadata", {}).get(key) == value for key, value in filters.items())
        ]
        for rank, item in enumerate(filtered, start=1):
            item["rank"] = rank

        warning = None
        if len(filtered) < top_k:
            warning = "Filtered results are fewer than top_k; returning available matches."

        return filtered, warning
