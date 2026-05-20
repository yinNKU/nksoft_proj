"""ANN engine built on FAISS.

本模块只负责索引和检索，不直接处理 Flask 请求，也不直接读取 .h5ad。
这样做的好处是：后续测试、替换 ANN 库、增加索引类型都更方便。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class ANNEngineError(RuntimeError):
    """Raised when ANN index operations fail."""


class ANNEngine:
    """A thin wrapper around FAISS indexes."""

    def __init__(self) -> None:
        self.index = None
        self.vectors: np.ndarray | None = None
        self.index_type: str | None = None
        self.dimension: int | None = None

    @staticmethod
    def _require_faiss():
        try:
            import faiss  # type: ignore
        except ImportError as exc:
            raise ANNEngineError(
                "faiss-cpu is not installed. Run: pip install -r requirements.txt"
            ) from exc
        return faiss

    def build_index(self, vectors: np.ndarray, index_type: str = "hnsw") -> None:
        """Build ANN index from vectors.

        Supported:
        - hnsw: 中期默认方案，精度较高，不需要训练；
        - flat: 精确检索，用作基准；
        - ivf: 倒排索引，适合更大规模数据。

        TODO:
        - 将 HNSW 的 M、efSearch 参数做成配置项。
        - 将 IVF 的 nlist、nprobe 参数做成配置项。
        - 增加 GPU FAISS 支持。
        - 增加索引构建耗时统计。
        """

        faiss = self._require_faiss()
        vectors = np.asarray(vectors, dtype=np.float32)

        if vectors.ndim != 2:
            raise ANNEngineError("vectors must be a 2D array")

        n_cells, dimension = vectors.shape
        if n_cells == 0:
            raise ANNEngineError("cannot build index from empty vectors")

        index_type = index_type.lower()

        if index_type == "flat":
            index = faiss.IndexFlatIP(dimension)

        elif index_type == "hnsw":
            hnsw_m = 32
            index = faiss.IndexHNSWFlat(dimension, hnsw_m)
            # TODO: 视数据规模调参。efSearch 越大，召回率越高，但查询越慢。
            index.hnsw.efSearch = 64

        elif index_type == "ivf":
            # 基础 IVF 版本。数据量很小时 nlist 不能过大。
            nlist = max(1, min(int(np.sqrt(n_cells)), n_cells))
            quantizer = faiss.IndexFlatIP(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
            index.train(vectors)
            index.nprobe = min(10, nlist)

        else:
            raise ANNEngineError(f"unsupported index_type: {index_type}")

        index.add(vectors)

        self.index = index
        self.vectors = vectors
        self.index_type = index_type
        self.dimension = dimension

    def search(self, query_vector: np.ndarray, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
        """Search Top-K nearest cells.

        Returns:
            similarities, indices

        TODO:
        - 对 HNSW / IVF 暴露更多运行时参数。
        - 增加批量查询接口 search_batch。
        - 增加 recall@k 评估方法。
        """

        if self.index is None or self.vectors is None:
            raise ANNEngineError("index is not built")

        query = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self.dimension:
            raise ANNEngineError(
                f"query dimension mismatch: expected {self.dimension}, got {query.shape[1]}"
            )

        k = max(1, min(int(k), self.vectors.shape[0]))
        similarities, indices = self.index.search(query, k)
        return similarities[0], indices[0]

    def save_index(self, path: str | Path) -> None:
        """Persist FAISS index to disk.

        TODO:
        - 同步保存 index_type、dimension、构建参数等 metadata。
        """

        if self.index is None:
            raise ANNEngineError("cannot save empty index")

        faiss = self._require_faiss()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path))

    def load_index(self, path: str | Path, vectors: np.ndarray, index_type: str) -> None:
        """Load FAISS index from disk.

        TODO:
        - 校验保存时的 dimension 与当前 vectors 是否一致。
        - 校验 index_type 是否一致。
        """

        faiss = self._require_faiss()
        path = Path(path)
        if not path.exists():
            raise ANNEngineError(f"index file not found: {path}")

        self.index = faiss.read_index(str(path))
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.index_type = index_type
        self.dimension = self.vectors.shape[1]
