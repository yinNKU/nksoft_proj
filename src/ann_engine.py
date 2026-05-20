"""ANN engine built on FAISS."""

from __future__ import annotations

from pathlib import Path

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
        """Build a FAISS index from normalized vectors."""

        faiss = self._require_faiss()
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)

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

        if index_type == "flat":
            index = faiss.IndexFlatIP(dimension)

        elif index_type == "hnsw":
            index = faiss.IndexHNSWFlat(dimension, 32, faiss.METRIC_INNER_PRODUCT)
            index.hnsw.efSearch = 64

        else:
            nlist = max(1, min(int(np.sqrt(n_items)), n_items))
            quantizer = faiss.IndexFlatIP(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
            index.train(vectors)
            index.nprobe = min(10, nlist)

        index.add(vectors)

        self.index = index
        self.vectors = vectors
        self.index_type = index_type
        self.dimension = dimension

    def search(self, query_vector: np.ndarray, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
        """Search Top-K nearest vectors and return similarities plus indices."""

        if self.index is None or self.vectors is None or self.dimension is None:
            raise ANNEngineError("index is not built")

        query = np.ascontiguousarray(query_vector, dtype=np.float32).reshape(1, -1)
        if query.shape[1] != self.dimension:
            raise ANNEngineError(
                f"query dimension mismatch: expected {self.dimension}, got {query.shape[1]}"
            )

        k = max(1, min(int(k), self.vectors.shape[0]))
        similarities, indices = self.index.search(query, k)
        return similarities[0], indices[0]

    def save_index(self, path: str | Path) -> None:
        """Persist the current FAISS index to disk."""

        if self.index is None:
            raise ANNEngineError("cannot save empty index")

        faiss = self._require_faiss()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path))

    def load_index(
        self,
        path: str | Path,
        vectors: np.ndarray,
        index_type: str | None = None,
    ) -> None:
        """Load a FAISS index from disk and bind it to the corresponding vectors."""

        faiss = self._require_faiss()
        path = Path(path)
        if not path.exists():
            raise ANNEngineError(f"index file not found: {path}")

        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] == 0 or vectors.shape[1] == 0:
            raise ANNEngineError("vectors must be a non-empty 2D array")

        index = faiss.read_index(str(path))
        if index.d != vectors.shape[1]:
            raise ANNEngineError(
                f"index dimension mismatch: index has {index.d}, vectors have {vectors.shape[1]}"
            )

        if index_type is not None:
            index_type = index_type.lower()
            if index_type not in self.SUPPORTED_INDEX_TYPES:
                raise ANNEngineError(f"unsupported index_type: {index_type}")

        self.index = index
        self.vectors = vectors
        self.index_type = index_type or "loaded"
        self.dimension = vectors.shape[1]
