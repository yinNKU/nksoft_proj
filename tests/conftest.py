"""Shared pytest fixtures for unit, integration, and real-data tests.

Fixtures are organized in three tiers:
- Lightweight (function-scoped): random vectors, pre-built engines
- Medium (session-scoped): medium random vectors
- Heavy (session-scoped): real liver.h5ad data (loaded once per test run)
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def _venv_python() -> str:
    """Return the path to the venv Python interpreter."""
    venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    return str(venv_python) if venv_python.exists() else sys.executable


# ---------------------------------------------------------------------------
# Lightweight fixtures (function-scoped, fast)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def temp_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect NK_DB_PATH to a temp SQLite file for every test.

    This is autouse so no test accidentally touches a real database file.
    """
    db_file = tmp_path / "test_app.db"
    monkeypatch.setenv("NK_DB_PATH", str(db_file))
    # Also init the database schema so db.init_database() works correctly.
    from database.init_db import init_db

    init_db(db_file)
    return db_file


@pytest.fixture()
def random_vectors_small() -> np.ndarray:
    """200 x 50 random L2-normalized float32 vectors for fast unit tests."""
    rng = np.random.default_rng(42)
    vectors = rng.normal(size=(200, 50)).astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@pytest.fixture(scope="session")
def random_vectors_medium() -> np.ndarray:
    """2000 x 50 random L2-normalized float32 vectors for integration tests."""
    rng = np.random.default_rng(99)
    vectors = rng.normal(size=(2000, 50)).astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@pytest.fixture()
def engine_flat(random_vectors_small: np.ndarray):
    """ANNEngine pre-built with flat index on small random vectors."""
    from src.ann_engine import ANNEngine

    engine = ANNEngine()
    engine.build_index(random_vectors_small, index_type="flat", metric="cosine")
    return engine


@pytest.fixture()
def engine_hnsw(random_vectors_small: np.ndarray):
    """ANNEngine pre-built with HNSW index on small random vectors."""
    from src.ann_engine import ANNEngine

    engine = ANNEngine()
    engine.build_index(
        random_vectors_small,
        index_type="hnsw",
        metric="cosine",
        params={"hnsw_m": 16, "hnsw_ef_search": 32},
    )
    return engine


@pytest.fixture()
def engine_ivf(random_vectors_small: np.ndarray):
    """ANNEngine pre-built with IVF index on small random vectors."""
    from src.ann_engine import ANNEngine

    engine = ANNEngine()
    engine.build_index(
        random_vectors_small,
        index_type="ivf",
        metric="cosine",
        params={"ivf_nlist": 10, "ivf_nprobe": 5},
    )
    return engine


@pytest.fixture()
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Settings instance pointing to a temporary data path."""
    from config import Settings

    # Override index dir to temp so tests don't write to real indexes/
    monkeypatch.setenv("SC_INDEX_DIR", str(tmp_path / "indexes"))
    return Settings()


# ---------------------------------------------------------------------------
# Heavy fixtures (session-scoped, require liver.h5ad)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _liver_data() -> tuple[np.ndarray, Any, Any]:
    """(private) Load liver.h5ad once per session.

    Returns (vectors, adata, metadata).  Skips the entire session if
    faiss is not installed or the data file is missing.
    """
    pytest.importorskip("faiss")

    from config import _default_data_path
    from src.data_loader import prepare_dataset

    data_path = _default_data_path()
    if not data_path.exists():
        pytest.skip(f"Real data file not found: {data_path}")

    return prepare_dataset(data_path, n_pcs=int(os.getenv("SC_N_PCS", "50")))


@pytest.fixture(scope="session")
def liver_vectors(_liver_data: tuple) -> np.ndarray:
    """Real PCA vectors from data/liver.h5ad (session-scoped)."""
    return _liver_data[0]


@pytest.fixture(scope="session")
def liver_adata(_liver_data: tuple) -> Any:
    """Real AnnData object from data/liver.h5ad (session-scoped)."""
    return _liver_data[1]


@pytest.fixture(scope="session")
def liver_metadata(_liver_data: tuple) -> Any:
    """Real cell metadata DataFrame from data/liver.h5ad (session-scoped)."""
    return _liver_data[2]


@pytest.fixture(scope="session")
def sample_query_indices(liver_vectors: np.ndarray) -> list[int]:
    """Evenly-spaced query indices from the real dataset."""
    n = liver_vectors.shape[0]
    step = max(1, n // 20)
    indices = list(range(0, n, step))[:20]
    return indices


# ---------------------------------------------------------------------------
# Flask test client
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Flask test client wired to a temp database.

    Uses the real SearchService (backed by random vectors) so tests
    exercise the full stack without liver.h5ad.
    """
    import app as app_module

    app = app_module.create_app()
    app.config["TESTING"] = True
    return app.test_client()
