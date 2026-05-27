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


class FakeDatasetManager:
    def __init__(self) -> None:
        self.datasets = []

    def list_datasets(self):
        return list(self.datasets)

    def add_dataset(self, name: str, path: str, description: str = "") -> None:
        if any(dataset["name"] == name for dataset in self.datasets):
            raise app_module.DatasetManagerError("dataset already exists")
        self.datasets.append(
            {
                "name": name,
                "path": path,
                "description": description,
                "is_active": 0,
            }
        )

    def delete_dataset(self, name: str) -> None:
        before = len(self.datasets)
        self.datasets = [dataset for dataset in self.datasets if dataset["name"] != name]
        if len(self.datasets) == before:
            raise app_module.DatasetManagerError("dataset not found")

    def select_dataset(self, name: str) -> None:
        found = False
        for dataset in self.datasets:
            dataset["is_active"] = 1 if dataset["name"] == name else 0
            found = found or dataset["name"] == name
        if not found:
            raise app_module.DatasetManagerError("dataset not found")


class FakeUserService:
    def __init__(self) -> None:
        self.users = [
            {"username": "admin", "password": "secret", "role": "admin"},
        ]

    def register(self, username: str, password: str, role: str = "user") -> None:
        if any(user["username"] == username for user in self.users):
            raise app_module.UserServiceError("user already exists")
        self.users.append({"username": username, "password": password, "role": role})

    def login(self, username: str, password: str) -> bool:
        return any(
            user["username"] == username and user["password"] == password for user in self.users
        )

    def list_users(self):
        return [
            {"id": idx + 1, "username": user["username"], "role": user["role"], "created_at": "now"}
            for idx, user in enumerate(self.users)
        ]

    def delete_user(self, username: str) -> None:
        before = len(self.users)
        self.users = [user for user in self.users if user["username"] != username]
        if len(self.users) == before:
            raise app_module.UserServiceError("user not found")


def _create_client(monkeypatch):
    monkeypatch.setattr(app_module, "SearchService", FakeService)
    monkeypatch.setattr(app_module, "DatasetManager", FakeDatasetManager)
    monkeypatch.setattr(app_module, "UserService", FakeUserService)
    app = app_module.create_app()
    return app.test_client()


@pytest.fixture()
def client(monkeypatch):
    # 这里把后半段路由也纳入测试，避免 app.py 只测到搜索接口。
    return _create_client(monkeypatch)


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


#C：下面的测试覆盖了 app.py 中剩余的用户和数据集相关路由，确保这些基础功能也在测试范围内。
def test_dataset_routes(client):
    add_response = client.post(
        "/api/datasets",
        json={"name": "liver", "path": "data/liver.h5ad", "description": "demo"},
    )
    assert add_response.get_json()["success"] is True

    list_response = client.get("/api/datasets")
    datasets = list_response.get_json()["datasets"]
    assert len(datasets) == 1
    assert datasets[0]["name"] == "liver"

    select_response = client.post("/api/datasets/select", json={"name": "liver"})
    assert select_response.get_json()["success"] is True

    delete_response = client.delete("/api/datasets/liver")
    assert delete_response.get_json()["success"] is True


def test_user_routes(client):
    register_response = client.post(
        "/api/register",
        json={"username": "alice", "password": "pw123", "role": "user"},
    )
    assert register_response.get_json()["success"] is True

    login_response = client.post("/api/login", json={"username": "alice", "password": "pw123"})
    assert login_response.get_json()["success"] is True

    users_response = client.get("/api/users")
    usernames = [user["username"] for user in users_response.get_json()["users"]]
    assert "alice" in usernames

    logout_response = client.post("/api/logout")
    assert logout_response.get_json()["success"] is True

    delete_response = client.delete("/api/users/alice")
    assert delete_response.get_json()["success"] is True


def test_rebuild_index_route(client):
    response = client.post("/api/rebuild-index", json={"index_type": "flat"})

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["index_type"] == "flat"
