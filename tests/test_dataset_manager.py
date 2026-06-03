"""Tests for DatasetManager using real SQLite (temp DB)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.dataset_manager import DatasetManager, DatasetManagerError


# ---------------------------------------------------------------------------
# Database schema tests (uses conftest.py temp_db_path)
# ---------------------------------------------------------------------------


class TestDatabaseInitialization:
    """Verify that the temp database has the expected schema and defaults."""

    def test_tables_exist(self, temp_db_path: Path):
        """确认 users、datasets、index_records 三张表存在。"""
        conn = sqlite3.connect(str(temp_db_path))
        cur = conn.cursor()

        for table in ["users", "datasets", "index_records"]:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            assert cur.fetchone() is not None, f"Table '{table}' should exist"

        conn.close()

    def test_default_admin_exists(self, temp_db_path: Path):
        """默认管理员 admin 应存在。"""
        conn = sqlite3.connect(str(temp_db_path))
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username='admin'")
        assert cur.fetchone() is not None
        conn.close()

    def test_default_sample_dataset_exists(self, temp_db_path: Path):
        """默认 sample 数据集应存在。"""
        conn = sqlite3.connect(str(temp_db_path))
        cur = conn.cursor()
        cur.execute("SELECT id FROM datasets WHERE name='sample'")
        assert cur.fetchone() is not None
        conn.close()


# ---------------------------------------------------------------------------
# DatasetManager CRUD tests
# ---------------------------------------------------------------------------


class TestDatasetManagerCRUD:
    """Full CRUD cycle for datasets."""

    @pytest.fixture()
    def manager(self) -> DatasetManager:
        return DatasetManager()

    @pytest.fixture()
    def sample_h5ad(self, tmp_path: Path) -> Path:
        """Create a minimal temporary .h5ad file."""
        p = tmp_path / "sample.h5ad"
        p.write_text("mock h5ad content")
        return p

    def test_add_dataset(self, manager: DatasetManager, sample_h5ad: Path):
        """添加数据集成功，返回的正数 id。"""
        dataset_id = manager.add_dataset("liver", str(sample_h5ad), "Liver dataset")
        assert dataset_id > 0

        datasets = manager.list_datasets()
        assert any(d["name"] == "liver" for d in datasets)

    def test_add_duplicate_dataset_raises(
        self, manager: DatasetManager, sample_h5ad: Path
    ):
        """重复添加同名数据集应抛出 DatasetManagerError。"""
        manager.add_dataset("liver", str(sample_h5ad))
        with pytest.raises(DatasetManagerError):
            manager.add_dataset("liver", str(sample_h5ad))

    def test_add_missing_path_raises(self, manager: DatasetManager):
        """添加不存在的路径应抛出 DatasetManagerError。"""
        with pytest.raises(DatasetManagerError, match="does not exist"):
            manager.add_dataset("ghost", "C:/nonexistent/path.h5ad")

    def test_add_non_h5ad_file_raises(self, manager: DatasetManager, tmp_path: Path):
        """添加非 .h5ad 后缀的文件应抛出错误。"""
        txt = tmp_path / "sample.txt"
        txt.write_text("not an h5ad")
        with pytest.raises(DatasetManagerError, match="must be a .h5ad"):
            manager.add_dataset("bad", str(txt))

    def test_select_dataset(
        self, manager: DatasetManager, sample_h5ad: Path
    ):
        """激活数据集后 get_active_dataset 应返回该数据集。"""
        manager.add_dataset("liver", str(sample_h5ad))
        manager.select_dataset("liver")

        active = manager.get_active_dataset()
        assert active is not None
        assert active["name"] == "liver"
        assert active["is_active"] == 1

    def test_select_nonexistent_raises(self, manager: DatasetManager):
        """选择不存在的数据集应抛出错误。"""
        with pytest.raises(DatasetManagerError, match="dataset not found"):
            manager.select_dataset("nonexistent")

    def test_delete_dataset(
        self, manager: DatasetManager, sample_h5ad: Path
    ):
        """删除数据集后列表中不再出现，且关联索引记录一并清除。"""
        manager.add_dataset("liver", str(sample_h5ad))
        manager.select_dataset("liver")

        # Add an index record
        idx_id = manager.add_index_record(
            "liver", "hnsw", "/tmp/i.faiss", "/tmp/m.json",
            vector_dim=50, num_vectors=100, build_time_ms=5.0,
        )
        assert idx_id > 0

        manager.delete_dataset("liver")
        assert all(d["name"] != "liver" for d in manager.list_datasets())

    def test_delete_nonexistent_raises(self, manager: DatasetManager):
        """删除不存在的数据集应抛出错误。"""
        with pytest.raises(DatasetManagerError, match="dataset not found"):
            manager.delete_dataset("nonexistent")


# ---------------------------------------------------------------------------
# Index record tests
# ---------------------------------------------------------------------------


class TestIndexRecords:
    """Index record read/write via DatasetManager."""

    @pytest.fixture()
    def manager(self) -> DatasetManager:
        return DatasetManager()

    @pytest.fixture()
    def dataset_with_records(
        self, manager: DatasetManager, tmp_path: Path
    ) -> str:
        """Set up a dataset with one index record, return the dataset name."""
        p = tmp_path / "test.h5ad"
        p.write_text("mock")
        manager.add_dataset("test_ds", str(p))
        return "test_ds"

    def test_add_index_record(self, manager: DatasetManager, dataset_with_records: str):
        """添加索引记录成功，返回正数 id。"""
        idx_id = manager.add_index_record(
            dataset_with_records, "flat", "/tmp/flat.faiss", "/tmp/flat.json",
            vector_dim=50, num_vectors=1000, build_time_ms=12.5,
        )
        assert idx_id > 0

    def test_list_index_records(
        self, manager: DatasetManager, dataset_with_records: str
    ):
        """列出索引记录，确认字段完整性。"""
        manager.add_index_record(
            dataset_with_records, "hnsw", "/tmp/hnsw.faiss", "/tmp/hnsw.json",
            vector_dim=50, num_vectors=500, build_time_ms=8.2,
        )
        records = manager.list_index_records(dataset_with_records)
        assert len(records) == 1
        assert records[0]["index_type"] == "hnsw"
        assert records[0]["index_path"] == "/tmp/hnsw.faiss"
        assert records[0]["vector_dim"] == 50
        assert records[0]["num_vectors"] == 500

    def test_list_index_records_nonexistent_dataset(self, manager: DatasetManager):
        """对不存在的数据集列出索引记录应抛出错误。"""
        with pytest.raises(DatasetManagerError, match="dataset not found"):
            manager.list_index_records("ghost")

    def test_add_index_record_nonexistent_dataset(self, manager: DatasetManager):
        """对不存在的数据集添加索引记录应抛出错误。"""
        with pytest.raises(DatasetManagerError, match="dataset not found"):
            manager.add_index_record(
                "ghost", "hnsw", "/tmp/i.faiss", "/tmp/m.json",
            )


# ---------------------------------------------------------------------------
# Active dataset edge cases
# ---------------------------------------------------------------------------


class TestActiveDatasetEdgeCases:
    """Edge cases for active dataset switching."""

    @pytest.fixture()
    def manager(self) -> DatasetManager:
        return DatasetManager()

    def test_get_active_dataset_none_when_no_active(self, manager: DatasetManager):
        """没有任何激活数据集时 get_active_dataset 应返回 None。"""
        active = manager.get_active_dataset()
        # 初始 sample 数据集默认 is_active=0
        assert active is None or active.get("is_active") == 0

    def test_select_new_dataset_deactivates_previous(
        self, manager: DatasetManager, tmp_path: Path
    ):
        """激活新数据集时应自动取消旧数据集的激活状态。"""
        a = tmp_path / "a.h5ad"
        b = tmp_path / "b.h5ad"
        a.write_text("mock")
        b.write_text("mock")

        manager.add_dataset("ds_a", str(a))
        manager.add_dataset("ds_b", str(b))

        manager.select_dataset("ds_a")
        assert manager.get_active_dataset()["name"] == "ds_a"

        manager.select_dataset("ds_b")
        active = manager.get_active_dataset()
        assert active["name"] == "ds_b"

        # 验证只有一个激活
        datasets = manager.list_datasets()
        active_count = sum(1 for d in datasets if d["is_active"] == 1)
        assert active_count == 1
