"""Dataset management: add/delete/select datasets and index records."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from src import db


class DatasetManagerError(RuntimeError):
    pass


class DatasetManager:
    def __init__(self) -> None:
        # 统一使用 UTC 时间，避免跨时区产生歧义。
        self.now = lambda: datetime.now(timezone.utc).isoformat()

    def list_datasets(self) -> List[dict[str, Any]]:
        rows = db.fetch_all("SELECT * FROM datasets ORDER BY id DESC")
        return [dict(r) for r in rows]

    def add_dataset(self, name: str, path: str, description: str = "") -> int:
        p = Path(path)
        # 先校验文件存在和后缀，再写入数据库。
        if not p.exists():
            raise DatasetManagerError("dataset path does not exist")
        if p.suffix.lower() != ".h5ad":
            raise DatasetManagerError("dataset must be a .h5ad file")

        try:
            sql = "INSERT INTO datasets(name,path,description,is_active,created_at) VALUES (?,?,?,?,?)"
            return db.execute_query(sql, (name, str(p), description, 0, self.now()), commit=True)
        except Exception as exc:
            raise DatasetManagerError(str(exc)) from exc

    def delete_dataset(self, name: str) -> None:
        # 删除数据集前先找到主键，后续再同步删除关联索引记录。
        row = db.fetch_one("SELECT id FROM datasets WHERE name=?", (name,))
        if not row:
            raise DatasetManagerError("dataset not found")
        dataset_id = row["id"]
        # 级联清理对应的索引记录，避免留下脏数据。
        db.execute_query("DELETE FROM index_records WHERE dataset_id=?", (dataset_id,), commit=True)
        db.execute_query("DELETE FROM datasets WHERE id=?", (dataset_id,), commit=True)

    def select_dataset(self, name: str) -> None:
        row = db.fetch_one("SELECT id FROM datasets WHERE name=?", (name,))
        if not row:
            raise DatasetManagerError("dataset not found")
        dataset_id = row["id"]
        # 先清空所有激活状态，再把目标数据集设为当前激活项。
        db.execute_query("UPDATE datasets SET is_active=0", (), commit=True)
        db.execute_query("UPDATE datasets SET is_active=1 WHERE id=?", (dataset_id,), commit=True)

    def get_active_dataset(self) -> Optional[dict[str, Any]]:
        row = db.fetch_one("SELECT * FROM datasets WHERE is_active=1 LIMIT 1")
        return dict(row) if row else None

    def add_index_record(
        self,
        dataset_name: str,
        index_type: str,
        index_path: str,
        metadata_path: str,
        vector_dim: Optional[int] = None,
        num_vectors: Optional[int] = None,
        build_time_ms: Optional[float] = None,
    ) -> int:
        # 索引构建完成后，把文件路径和元数据同步写入 index_records。
        row = db.fetch_one("SELECT id FROM datasets WHERE name=?", (dataset_name,))
        if not row:
            raise DatasetManagerError("dataset not found")
        dataset_id = row["id"]
        sql = """
        INSERT INTO index_records(dataset_id,index_type,index_path,metadata_path,vector_dim,num_vectors,build_time_ms,created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """
        return db.execute_query(
            sql,
            (dataset_id, index_type, index_path, metadata_path, vector_dim, num_vectors, build_time_ms, self.now()),
            commit=True,
        )

    def list_index_records(self, dataset_name: str) -> List[dict[str, Any]]:
        row = db.fetch_one("SELECT id FROM datasets WHERE name=?", (dataset_name,))
        if not row:
            raise DatasetManagerError("dataset not found")
        dataset_id = row["id"]
        rows = db.fetch_all("SELECT * FROM index_records WHERE dataset_id=? ORDER BY id DESC", (dataset_id,))
        return [dict(r) for r in rows]
