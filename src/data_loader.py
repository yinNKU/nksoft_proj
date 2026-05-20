"""Data loading and vectorization utilities.

本模块负责：
1. 读取 .h5ad 单细胞数据；
2. 从 AnnData 中提取或生成向量表示；
3. 对向量做 float32 转换和 L2 归一化；
4. 提取细胞元信息，供检索结果展示使用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class DataLoaderError(RuntimeError):
    """Raised when loading or preprocessing single-cell data fails."""


def _require_scanpy():
    """Import scanpy lazily so the project can still start without data dependencies."""

    try:
        import scanpy as sc  # type: ignore
    except ImportError as exc:
        raise DataLoaderError(
            "scanpy is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return sc


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Return L2-normalized vectors.

    归一化后，内积相似度可以近似作为余弦相似度使用。
    """

    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def load_h5ad(h5ad_path: str | Path) -> Any:
    """Load an AnnData object from .h5ad.

    TODO:
    - 增加文件大小检查。
    - 增加数据字段检查，例如 obs、var、obsm 是否存在。
    - 增加读取失败时的更细粒度错误提示。
    """

    h5ad_path = Path(h5ad_path)
    if not h5ad_path.exists():
        raise DataLoaderError(f"Data file not found: {h5ad_path}")

    sc = _require_scanpy()
    return sc.read_h5ad(h5ad_path)


def get_or_create_pca_vectors(adata: Any, n_pcs: int = 50) -> np.ndarray:
    """Extract PCA vectors from AnnData, or create them if missing.

    当前策略：
    - 如果 `adata.obsm["X_pca"]` 已存在，则直接使用；
    - 否则执行基础 scanpy 预处理并计算 PCA。

    TODO:
    - 根据真实数据集检查是否已经做过 log normalization。
    - 支持选择其他向量来源，例如 X_scVI、X_umap、原始表达矩阵。
    - 对超大数据集优化内存占用。
    - 将预处理参数写入日志或 metadata。
    """

    if "X_pca" not in adata.obsm:
        sc = _require_scanpy()

        # 基础中期流程，后续可根据数据集特点调整。
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        sc.pp.highly_variable_genes(adata, n_top_genes=2000)
        adata = adata[:, adata.var.highly_variable].copy()
        sc.pp.scale(adata)
        sc.tl.pca(adata, n_comps=n_pcs)

    vectors = adata.obsm["X_pca"][:, :n_pcs]
    return l2_normalize(vectors.astype(np.float32))


def extract_cell_metadata(adata: Any) -> pd.DataFrame:
    """Extract cell metadata from adata.obs.

    TODO:
    - 根据具体数据集筛选展示字段，避免前端表格过宽。
    - 对 category / numpy 类型做统一 JSON 序列化。
    - 增加字段中文名映射，例如 cell_type -> 细胞类型。
    """

    metadata = adata.obs.copy()
    metadata.insert(0, "cell_id", adata.obs_names.astype(str))
    return metadata


def prepare_dataset(h5ad_path: str | Path, n_pcs: int = 50) -> tuple[np.ndarray, Any, pd.DataFrame]:
    """Load .h5ad and return vectors, AnnData, and metadata."""

    adata = load_h5ad(h5ad_path)
    vectors = get_or_create_pca_vectors(adata, n_pcs=n_pcs)
    metadata = extract_cell_metadata(adata)
    return vectors, adata, metadata
