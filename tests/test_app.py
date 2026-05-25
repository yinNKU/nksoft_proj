from __future__ import annotations

from types import SimpleNamespace

import pytest

import app as app_module
from src.search_service import SearchServiceError


def _build_results(top_k: int):
    # 生成固定结构的假结果，便于断言返回格式。
    return [
        {
            "rank": idx + 1,
            "cell_index": idx,
            "cell_id": f"cell_{idx}",
            "score": 1.0 - idx * 0.01,
            "metadata": {"cell_type": "T", "donor": "d1"},
        }
        for idx in range(top_k)
    ]


class FakeService:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.engine = SimpleNamespace(index_type=settings.default_index_type)

    def initialize(self, allow_missing_data: bool = False) -> None:
        return None

    def status(self):
        return {
            "loaded": True,
            "n_cells": 3,
            "n_dims": 2,
            "index_type": self.engine.index_type,
            "dataset": None,
            "data_path": "fake",
        }

    def metadata_columns(self):
        return {"columns": ["cell_type", "donor"]}

    def ensure_index_type(self, index_type: str) -> None:
        self.engine.index_type = index_type

    def search_by_cell_index(self, cell_index: int, top_k: int, filters=None):
        return {"results": _build_results(top_k), "warning": None}

    def search_by_cell_id(self, cell_id: str, top_k: int, filters=None):
        if cell_id == "missing":
            raise SearchServiceError("cell_id not found")
        return {"results": _build_results(top_k), "warning": None}

    def search_by_vector(self, vector: list[float], top_k: int, filters=None):
        if len(vector) != 2:
            raise SearchServiceError("vector dimension mismatch: expected 2, got 1")
        return {"results": _build_results(top_k), "warning": None}

    def rebuild_index(self, index_type: str = "hnsw"):
        return {"index_type": index_type, "build_time_ms": 1.0}


@pytest.fixture()
def client(monkeypatch):
    # 用 FakeService 替换真实 SearchService，避免依赖真实数据文件。
    monkeypatch.setattr(app_module, "SearchService", FakeService)
    app = app_module.create_app()
    return app.test_client()


def test_status_endpoint(client):
    response = client.get("/api/status")

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["loaded"] is True


def test_metadata_endpoint(client):
    response = client.get("/api/metadata")

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["fields"] == ["cell_type", "donor"]


def test_search_by_cell_index(client):
    response = client.post(
        "/api/search",
        json={"mode": "id", "cell_index": 0, "top_k": 2, "filters": {"cell_type": "T"}},
    )

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["mode"] == "id"
    assert payload["top_k"] == 2
    assert payload["filters"] == {"cell_type": "T"}
    assert len(payload["results"]) == 2


def test_search_by_cell_index_with_id_alias(client):
    response = client.post(
        "/api/search",
        json={"mode": "id", "id": 1, "top_k": 2},
    )

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["mode"] == "id"
    assert len(payload["results"]) == 2


def test_search_by_cell_id_not_found(client):
    response = client.post(
        "/api/search",
        json={"mode": "cell_id", "cell_id": "missing", "top_k": 2},
    )

    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"] == "cell_id not found"


def test_search_by_vector_dimension_error(client):
    response = client.post(
        "/api/search",
        json={"mode": "vector", "vector": [0.1], "top_k": 2},
    )

    payload = response.get_json()
    assert payload["success"] is False
    assert "vector dimension mismatch" in payload["error"]


def test_filters_payload_validation(client):
    response = client.post(
        "/api/search",
        json={"mode": "id", "cell_index": 0, "top_k": 2, "filters": ["bad"]},
    )

    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"] == "filters must be a dict"
