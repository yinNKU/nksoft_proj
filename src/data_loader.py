"""Data loading and vectorization utilities for single-cell datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class DataLoaderError(RuntimeError):
    """Raised when loading or preprocessing single-cell data fails."""


def _require_scanpy():
    """Import scanpy lazily so the app can start without data dependencies."""

    try:
        import scanpy as sc  # type: ignore
    except ImportError as exc:
        raise DataLoaderError(
            "scanpy is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return sc


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """Return float32 L2-normalized vectors."""

    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    if vectors.ndim != 2:
        raise DataLoaderError("vectors must be a 1D or 2D array")

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def load_h5ad(h5ad_path: str | Path) -> Any:
    """Load an AnnData object from a .h5ad file."""

    h5ad_path = Path(h5ad_path)
    if not h5ad_path.exists():
        raise DataLoaderError(f"Data file not found: {h5ad_path}")
    if h5ad_path.suffix.lower() != ".h5ad":
        raise DataLoaderError(f"Expected a .h5ad file, got: {h5ad_path}")

    sc = _require_scanpy()
    try:
        return sc.read_h5ad(h5ad_path)
    except Exception as exc:  # scanpy/anndata expose several read-time errors.
        raise DataLoaderError(f"Failed to read data file: {h5ad_path}") from exc


def get_or_create_pca_vectors(adata: Any, n_pcs: int = 50) -> np.ndarray:
    """Extract PCA vectors from AnnData, or create them when missing."""

    if n_pcs <= 0:
        raise DataLoaderError("n_pcs must be positive")

    if "X_pca" not in adata.obsm:
        sc = _require_scanpy()
        if adata.n_obs < 2 or adata.n_vars < 2:
            raise DataLoaderError("not enough cells or genes to compute PCA")

        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        sc.pp.highly_variable_genes(adata, n_top_genes=min(2000, adata.n_vars))

        hvg_mask = np.asarray(adata.var.highly_variable, dtype=bool)
        pca_source = adata[:, hvg_mask].copy() if hvg_mask.any() else adata.copy()
        if pca_source.n_obs < 2 or pca_source.n_vars < 2:
            raise DataLoaderError("not enough cells or selected genes to compute PCA")

        max_components = max(1, min(int(n_pcs), pca_source.n_obs - 1, pca_source.n_vars - 1))
        sc.pp.scale(pca_source)
        sc.tl.pca(pca_source, n_comps=max_components)
        adata.obsm["X_pca"] = pca_source.obsm["X_pca"]

    pca = np.asarray(adata.obsm["X_pca"], dtype=np.float32)
    if pca.ndim != 2 or pca.shape[0] == 0 or pca.shape[1] == 0:
        raise DataLoaderError("adata.obsm['X_pca'] must be a non-empty 2D matrix")

    usable_pcs = min(int(n_pcs), pca.shape[1])
    return l2_normalize(pca[:, :usable_pcs])


def extract_cell_metadata(adata: Any) -> pd.DataFrame:
    """Extract cell metadata from adata.obs with a leading cell_id column."""

    metadata = adata.obs.copy()
    metadata.insert(0, "cell_id", adata.obs_names.astype(str))
    return metadata


def get_metadata(adata: Any, cell_idx: int) -> dict[str, Any]:
    """Return JSON-serializable metadata for one cell."""

    if cell_idx < 0 or cell_idx >= adata.n_obs:
        raise DataLoaderError(f"cell_idx out of range: {cell_idx}")

    row = adata.obs.iloc[cell_idx]
    info: dict[str, Any] = {"cell_id": str(adata.obs_names[cell_idx])}
    for col, value in row.items():
        if hasattr(value, "item"):
            value = value.item()
        info[str(col)] = value if isinstance(value, (int, float, str, bool)) else str(value)
    return info


def get_available_metadata(adata: Any) -> list[str]:
    """Return available metadata column names from adata.obs."""

    return [str(col) for col in adata.obs.columns]


def get_dataset_summary(adata: Any) -> dict[str, Any]:
    """Return a compact summary of the loaded dataset."""

    pca = adata.obsm.get("X_pca")
    return {
        "n_cells": int(adata.n_obs),
        "n_genes": int(adata.n_vars),
        "n_pcs": int(pca.shape[1]) if pca is not None and getattr(pca, "ndim", 0) == 2 else 0,
        "metadata_columns": get_available_metadata(adata),
    }


def load_and_preprocess(
    h5ad_path: str | Path = "data/sample.h5ad",
    n_pcs: int = 50,
) -> tuple[np.ndarray, Any]:
    """Compatibility helper returning vectors and AnnData."""

    adata = load_h5ad(h5ad_path)
    vectors = get_or_create_pca_vectors(adata, n_pcs=n_pcs)
    return vectors, adata


def prepare_dataset(h5ad_path: str | Path, n_pcs: int = 50) -> tuple[np.ndarray, Any, pd.DataFrame]:
    """Load .h5ad and return vectors, AnnData, and metadata."""

    vectors, adata = load_and_preprocess(h5ad_path, n_pcs=n_pcs)
    metadata = extract_cell_metadata(adata)
    return vectors, adata, metadata
