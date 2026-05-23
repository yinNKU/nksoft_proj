"""ANN engine built on FAISS."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np


class ANNEngineError(RuntimeError):
    """Raised when ANN index operations fail."""


class ANNEngine:
    """A thin wrapper around FAISS indexes."""

    SUPPORTED_INDEX_TYPES = {"flat", "hnsw", "ivf"}

    def __init__(self) -> None:
        self.index = None
        self.vectors: np.ndarray | None = None
        self.index_type: str | None = None
        self.dimension: int | None = None
        self.metric: str | None = None
        self.params: dict[str, Any] = {}
        self.build_time_ms: float | None = None
        self.metadata: dict[str, Any] = {}

    @staticmethod
    def _require_faiss():
        try:
            import faiss  # type: ignore
        except ImportError as exc:
            raise ANNEngineError(
                "faiss-cpu is not installed. Run: pip install -r requirements.txt"
            ) from exc
        return faiss

    @staticmethod
    def _normalize_metric(metric: str) -> str:
        metric = metric.lower()
        if metric in {"cosine", "inner_product", "ip"}:
            return "cosine"
        if metric in {"l2", "euclidean"}:
            return "l2"
        raise ANNEngineError(f"unsupported metric: {metric}")

    def build_index(
        self,
        vectors: np.ndarray,
        index_type: str = "hnsw",
        metric: str = "cosine",
        params: dict[str, Any] | None = None,
        dataset_id: str | None = None,
    ) -> None:
        """Build a FAISS index from vectors.

        The default cosine mode expects L2-normalized vectors and uses inner
        product search, which is the standard FAISS setup for cosine similarity.
        """

        faiss = self._require_faiss()
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        params = params or {}

        if vectors.ndim != 2:
            raise ANNEngineError("vectors must be a 2D array")

        n_items, dimension = vectors.shape
        if n_items == 0:
            raise ANNEngineError("cannot build index from empty vectors")
        if dimension == 0:
            raise ANNEngineError("cannot build index from zero-dimensional vectors")

        index_type = index_type.lower()
        if index_type not in self.SUPPORTED_INDEX_TYPES:
            raise ANNEngineError(f"unsupported index_type: {index_type}")

        # cosine 模式要求输入向量已 L2 归一化；此时内积值就是余弦相似度。
        metric = self._normalize_metric(metric)
        faiss_metric = faiss.METRIC_INNER_PRODUCT if metric == "cosine" else faiss.METRIC_L2
        started_at = time.perf_counter()

        if index_type == "flat":
            # Flat 是精确检索基线，不做近似加速，适合用于评估 HNSW/IVF 的结果质量。
            index = faiss.IndexFlatIP(dimension) if metric == "cosine" else faiss.IndexFlatL2(dimension)

        elif index_type == "hnsw":
            # HNSW 是当前默认 ANN 索引，主要通过图结构换取更快的 Top-K 查询。
            hnsw_m = int(params.get("hnsw_m", params.get("M", 32)))
            ef_search = int(params.get("hnsw_ef_search", params.get("efSearch", 64)))
            if hnsw_m <= 0 or ef_search <= 0:
                raise ANNEngineError("hnsw_m and hnsw_ef_search must be positive")
            index = faiss.IndexHNSWFlat(dimension, hnsw_m, faiss_metric)
            index.hnsw.efSearch = ef_search

        else:
            # IVF 需要先训练聚类中心；nlist 不能超过向量数量，否则 FAISS 会报错。
            requested_nlist = int(params.get("ivf_nlist", params.get("nlist", 0)))
            nlist = requested_nlist if requested_nlist > 0 else max(1, int(np.sqrt(n_items)))
            nlist = max(1, min(nlist, n_items))
            nprobe = int(params.get("ivf_nprobe", params.get("nprobe", min(10, nlist))))
            if nprobe <= 0:
                raise ANNEngineError("ivf_nprobe must be positive")
            quantizer = faiss.IndexFlatIP(dimension) if metric == "cosine" else faiss.IndexFlatL2(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss_metric)
            index.train(vectors)
            # nprobe 控制查询时搜索多少个倒排桶，越大召回越高但查询越慢。
            index.nprobe = min(nprobe, nlist)

        index.add(vectors)
        build_time_ms = (time.perf_counter() - started_at) * 1000

        self.index = index
        self.vectors = vectors
        self.index_type = index_type
        self.dimension = dimension
        self.metric = metric
        self.params = self._effective_params(index_type, index)
        self.build_time_ms = build_time_ms
        self.metadata = self._make_metadata(dataset_id=dataset_id)

    def _effective_params(self, index_type: str, index: Any) -> dict[str, Any]:
        """Record the actual parameters accepted by FAISS after bounds checks."""

        if index_type == "hnsw":
            return {
                "hnsw_m": int(index.hnsw.nb_neighbors(0)),
                "hnsw_ef_search": int(index.hnsw.efSearch),
            }
        if index_type == "ivf":
            return {"ivf_nlist": int(index.nlist), "ivf_nprobe": int(index.nprobe)}
        return {}

    def _make_metadata(self, dataset_id: str | None = None) -> dict[str, Any]:
        if self.vectors is None or self.dimension is None:
            raise ANNEngineError("cannot create metadata without vectors")
        # metadata 用于判断缓存索引是否仍然匹配当前数据集和向量维度。
        metadata = {
            "index_type": self.index_type,
            "metric": self.metric,
            "dimension": int(self.dimension),
            "num_vectors": int(self.vectors.shape[0]),
            "params": self.params,
            "build_time_ms": self.build_time_ms,
        }
        if dataset_id is not None:
            metadata["dataset_id"] = str(dataset_id)
        return metadata

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        k: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Search Top-K nearest vectors and return similarities plus indices."""

        if self.index is None or self.vectors is None or self.dimension is None:
            raise ANNEngineError("index is not built")

        query = np.ascontiguousarray(query_vector, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self.dimension:
            raise ANNEngineError(
                f"query dimension mismatch: expected {self.dimension}, got {query.shape[1]}"
            )

        requested_k = int(k if k is not None else top_k)
        if requested_k <= 0:
            raise ANNEngineError("top_k must be positive")

        # top_k 大于数据量时自动截断，保证 API 仍返回可用结果。
        top_k = min(requested_k, self.vectors.shape[0])
        similarities, indices = self.index.search(query, top_k)
        return similarities[0], indices[0]

    def save_index(self, index_path: str | Path, metadata_path: str | Path | None = None) -> None:
        """Persist the current FAISS index and optional JSON metadata to disk."""

        if self.index is None or self.vectors is None:
            raise ANNEngineError("cannot save empty index")

        faiss = self._require_faiss()
        index_path = Path(index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        # FAISS 的 write_index 在部分 Windows 中文路径下会失败；序列化后交给 Python 写文件更稳。
        serialized = faiss.serialize_index(self.index)
        index_path.write_bytes(bytes(serialized))

        if metadata_path is not None:
            metadata_path = Path(metadata_path)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps(self.metadata or self._make_metadata(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load_index(
        self,
        index_path: str | Path,
        vectors: np.ndarray,
        metadata_path: str | Path | None = None,
        dataset_id: str | None = None,
    ) -> None:
        """Load a FAISS index from disk and bind it to the corresponding vectors."""

        faiss = self._require_faiss()
        index_path = Path(index_path)
        if not index_path.exists():
            raise ANNEngineError(f"index file not found: {index_path}")

        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] == 0 or vectors.shape[1] == 0:
            raise ANNEngineError("vectors must be a non-empty 2D array")

        metadata: dict[str, Any] = {}
        if metadata_path is not None:
            metadata_path = Path(metadata_path)
            if not metadata_path.exists():
                raise ANNEngineError(f"index metadata file not found: {metadata_path}")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self._validate_metadata(metadata, vectors, dataset_id=dataset_id)

        # 与 save_index 对应：从 Python 字节流反序列化，兼容中文项目路径。
        serialized = np.frombuffer(index_path.read_bytes(), dtype=np.uint8)
        index = faiss.deserialize_index(serialized)
        if index.d != vectors.shape[1]:
            raise ANNEngineError(
                f"index dimension mismatch: index has {index.d}, vectors have {vectors.shape[1]}"
            )

        self.index = index
        self.vectors = vectors
        self.index_type = metadata.get("index_type", "loaded")
        self.dimension = vectors.shape[1]
        self.metric = metadata.get("metric")
        self.params = metadata.get("params", {})
        self.build_time_ms = metadata.get("build_time_ms")
        self.metadata = metadata

    def _validate_metadata(
        self,
        metadata: dict[str, Any],
        vectors: np.ndarray,
        dataset_id: str | None = None,
    ) -> None:
        dimension = metadata.get("dimension")
        num_vectors = metadata.get("num_vectors")
        # 维度或数量不同意味着索引和当前向量矩阵不是同一批数据，不能继续加载。
        if dimension != int(vectors.shape[1]):
            raise ANNEngineError(
                f"metadata dimension mismatch: metadata has {dimension}, vectors have {vectors.shape[1]}"
            )
        if num_vectors != int(vectors.shape[0]):
            raise ANNEngineError(
                f"metadata vector count mismatch: metadata has {num_vectors}, vectors have {vectors.shape[0]}"
            )

        metadata_dataset_id = metadata.get("dataset_id")
        # dataset_id 默认使用数据文件绝对路径，防止误加载其他数据集生成的索引。
        if dataset_id is not None and metadata_dataset_id not in {None, str(dataset_id)}:
            raise ANNEngineError(
                f"metadata dataset mismatch: metadata has {metadata_dataset_id}, current dataset is {dataset_id}"
            )
