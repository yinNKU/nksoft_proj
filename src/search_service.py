"""Business layer for single-cell ANN search."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

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
        """初始化当前对象所需的状态和依赖。"""
        self.settings = settings
        self.engine = ANNEngine()
        self.adata: Any | None = None
        self.metadata = None
        # 保存当前步骤需要的数据。
        self.loaded = False
        self.initializing = False
        self.last_error: str | None = None

    def initialize(self, allow_missing_data: bool = False) -> None:
        """加载数据并加载或重建默认索引。"""

        self.initializing = True
        try:
            vectors, adata, metadata = prepare_dataset(
                self.settings.data_path,
                n_pcs=self.settings.n_pcs,
            )
            # 保存当前步骤需要的数据。
            self.adata = adata
            self.metadata = metadata
            # 启动时优先加载已保存的索引缓存；缓存缺失或不匹配时再重建。
            if not self.load_cached_index(self.settings.default_index_type, vectors=vectors):
                self.rebuild_index(self.settings.default_index_type, vectors=vectors)
            self.loaded = True
            self.last_error = None

        except (DataLoaderError, ANNEngineError) as exc:
            # 根据当前条件执行对应处理。
            if not allow_missing_data:
                raise SearchServiceError(str(exc)) from exc

            self.loaded = False
            self.last_error = str(exc)
        finally:
            # 保存当前步骤需要的数据。
            self.initializing = False

    def status(self) -> dict[str, Any]:
        """返回数据与索引的当前状态。"""

        vectors = self.engine.vectors
        return {
            "loaded": self.loaded,
            "initializing": self.initializing,
            "data_path": str(self.settings.data_path),
            "n_cells": int(vectors.shape[0]) if vectors is not None else 0,
            "n_dims": int(vectors.shape[1]) if vectors is not None else 0,
            "index_type": self.engine.index_type,
            "build_time_ms": self.engine.build_time_ms,
            "dataset": get_dataset_summary(self.adata) if self.adata is not None else None,
            "last_error": self.last_error,
        }

    def metadata_columns(self) -> dict[str, Any]:
        """返回当前数据集的元数据列。"""

        self._ensure_ready()
        assert self.adata is not None
        return {"columns": get_available_metadata(self.adata)}

    def embedding_points(self, basis: str = "umap", color_by: str = "cell_type") -> dict[str, Any]:
        """整理可视化所需的二维坐标和着色值。"""

        self._ensure_ready()
        assert self.adata is not None
        assert self.metadata is not None

        # 保存当前步骤需要的数据。
        basis = basis.lower()
        obsm_key = "X_umap" if basis == "umap" else "X_pca"
        if obsm_key not in self.adata.obsm:
            raise SearchServiceError(f"{obsm_key} not found in dataset")

        # 保存当前步骤需要的数据。
        coords = np.asarray(self.adata.obsm[obsm_key], dtype=np.float32)
        if coords.ndim != 2 or coords.shape[1] < 2:
            raise SearchServiceError(f"{obsm_key} must contain at least two dimensions")

        available_fields = set(self.metadata.columns)
        # 根据当前条件执行对应处理。
        if color_by not in available_fields:
            color_by = "cell_type" if "cell_type" in available_fields else "cell_id"

        points = []
        for idx, (x, y) in enumerate(coords[:, :2]):
            # 保存当前步骤需要的数据。
            row = self.metadata.iloc[idx]
            cell_id = self._json_safe_value(row.get("cell_id", idx))
            color_value = self._json_safe_value(row.get(color_by, "unknown"))
            points.append(
                {
                    "cell_index": idx,
                    "cell_id": str(cell_id),
                    "x": self._json_safe_value(x),
                    "y": self._json_safe_value(y),
                    "color": "unknown" if color_value is None else str(color_value),
                }
            )

        # 返回当前步骤的处理结果。
        return {
            "basis": basis,
            "color_by": color_by,
            "n_points": len(points),
            "points": points,
        }

    def ensure_index_type(self, index_type: str) -> None:
        """确保当前服务使用指定类型的索引。"""

        self._ensure_index_type(index_type)

    def _ensure_ready(self) -> None:
        """检查数据、索引和元数据是否就绪。"""
        if not self.loaded or self.engine.vectors is None or self.metadata is None:
            raise SearchServiceError(
                "Data is not loaded. Put a .h5ad file under data/sample.h5ad or set SC_DATA_PATH."
            )

    def _ensure_index_type(self, index_type: str) -> None:
        """必要时加载缓存或重建指定索引。"""

        self._ensure_ready()

        if self.engine.index_type == index_type:
            # 返回当前步骤的处理结果。
            return

        # 前端切换索引类型时，先尝试复用缓存，避免反复构建大数据索引。
        if not self.load_cached_index(index_type):
            self.rebuild_index(index_type)

    def rebuild_index(self, index_type: str = "hnsw", vectors: np.ndarray | None = None) -> dict[str, Any]:
        """按指定类型重建并保存当前索引。"""

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
        # 执行当前阶段的关键处理。
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
        """校验并加载已保存的 FAISS 索引。"""

        if vectors is None:
            vectors = self.engine.vectors
        if vectors is None:
            # 返回当前步骤的处理结果。
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
            # 保存当前步骤需要的数据。
            self.last_error = str(exc)
            return False

        return True

    def _validate_k(self, k: int) -> int:
        """校验 Top-K 并限制最大返回数量。"""
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
        """使用细胞下标取得向量并执行检索。"""

        self._ensure_ready()
        if self.engine.index_type is None:
            self._ensure_index_type(self.settings.default_index_type)
        # 保存当前步骤需要的数据。
        top_k = self._validate_k(top_k)

        vectors = self.engine.vectors
        assert vectors is not None

        # 根据当前条件执行对应处理。
        if cell_index < 0 or cell_index >= vectors.shape[0]:
            raise SearchServiceError(f"cell_index out of range: {cell_index}")

        query_vector = vectors[cell_index]
        similarities, indices = self.engine.search(query_vector, k=top_k)

        # 保存当前步骤需要的数据。
        results = self._format_results(similarities, indices)
        filtered, warning = self._apply_metadata_filters(results, filters, top_k=top_k)

        return {"results": filtered, "warning": warning}

    def search_by_cell_id(
        self,
        cell_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """将真实细胞 ID 转换为下标后执行检索。"""

        self._ensure_ready()
        assert self.metadata is not None

        # metadata 的索引可能就是 cell_id，需要用位置索引保证可转成 int。
        cell_ids = self.metadata["cell_id"].astype(str).to_numpy()
        matches = np.flatnonzero(cell_ids == str(cell_id))
        if matches.size == 0:
            raise SearchServiceError("cell_id not found")

        # 返回当前步骤的处理结果。
        return self.search_by_cell_index(int(matches[0]), top_k=top_k, filters=filters)

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """校验自定义向量并执行近邻检索。"""

        self._ensure_ready()
        if self.engine.index_type is None:
            self._ensure_index_type(self.settings.default_index_type)
        # 保存当前步骤需要的数据。
        top_k = self._validate_k(top_k)

        if vector is None:
            raise SearchServiceError("vector must be a list of floats")

        # 保存当前步骤需要的数据。
        query = np.asarray(vector, dtype=np.float32)
        if query.ndim == 2 and query.shape[0] == 1:
            query = query.reshape(-1)
        if query.ndim != 1:
            raise SearchServiceError("vector must be a 1D list of floats")
        # 根据当前条件执行对应处理。
        if self.engine.dimension is None or query.shape[0] != self.engine.dimension:
            raise SearchServiceError(
                f"vector dimension mismatch: expected {self.engine.dimension}, got {query.shape[0]}"
            )

        # 保存当前步骤需要的数据。
        query = l2_normalize(query)[0]
        similarities, indices = self.engine.search(query, k=top_k)

        results = self._format_results(similarities, indices)
        filtered, warning = self._apply_metadata_filters(results, filters, top_k=top_k)

        # 返回当前步骤的处理结果。
        return {"results": filtered, "warning": warning}

    def _format_results(self, similarities: np.ndarray, indices: np.ndarray) -> list[dict[str, Any]]:
        """将 FAISS 结果整理为可序列化的细胞列表。"""

        assert self.metadata is not None

        results = []
        # 逐项处理当前数据。
        for rank, (similarity, idx) in enumerate(zip(similarities, indices), start=1):
            idx = int(idx)
            row = self.metadata.iloc[idx].to_dict()

            # 统一转成字符串/数字，避免 numpy、category 类型无法 JSON 序列化。
            metadata = {}
            for key, value in row.items():
                metadata[key] = self._json_safe_value(value)

            # 执行当前阶段的关键处理。
            results.append(
                {
                    "rank": rank,
                    "cell_index": idx,
                    "cell_id": str(metadata.get("cell_id", idx)),
                    "score": float(similarity),
                    "metadata": metadata,
                }
            )

        # 返回当前步骤的处理结果。
        return results

    def _json_safe_value(self, value: Any) -> int | float | str | bool | None:
        """将 NumPy 数值和缺失值转换为 JSON 可用类型。"""

        if pd.isna(value):
            return None
        if hasattr(value, "item"):
            # 保存当前步骤需要的数据。
            value = value.item()
        if isinstance(value, (np.bool_, bool)):
            return bool(value)
        if isinstance(value, (np.integer, int)):
            return int(value)
        # 根据当前条件执行对应处理。
        if isinstance(value, (np.floating, float)):
            return float(value) if np.isfinite(value) else None
        if isinstance(value, str):
            return value
        return str(value)

    def _apply_metadata_filters(
        self,
        results: list[dict[str, Any]],
        filters: dict[str, Any] | None,
        top_k: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """按元数据字段对候选结果进行精确筛选。"""

        if not filters:
            return results, None

        # 根据当前条件执行对应处理。
        if not isinstance(filters, dict):
            raise SearchServiceError("filters must be a dict")

        assert self.metadata is not None
        available_fields = set(self.metadata.columns)
        # 逐项处理当前数据。
        for field in filters.keys():
            if field not in available_fields:
                raise SearchServiceError(f"metadata field not found: {field}")

        filtered = [
            item
            for item in results
            if all(item.get("metadata", {}).get(key) == value for key, value in filters.items())
        ]
        # 逐项处理当前数据。
        for rank, item in enumerate(filtered, start=1):
            item["rank"] = rank

        warning = None
        if len(filtered) < top_k:
            # 保存当前步骤需要的数据。
            warning = "Filtered results are fewer than top_k; returning available matches."

        return filtered, warning
