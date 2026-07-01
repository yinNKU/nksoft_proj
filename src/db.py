"""Simple SQLite helper utilities for the project."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from werkzeug.security import generate_password_hash

from config import Settings


DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "app.db"


def get_db_path() -> Path:
    # 优先使用环境变量，便于测试和不同环境切换数据库文件。
    """返回环境变量或默认数据库位置。"""
    from os import getenv

    p = getenv("NK_DB_PATH")
    if p:
        # 返回当前步骤的处理结果。
        return Path(p)
    return DEFAULT_DB


def get_connection() -> sqlite3.Connection:
    # 每次查询都新建连接，简单且适合当前项目规模。
    """创建并配置 SQLite 连接。"""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=OFF")
    # 保存当前步骤需要的数据。
    conn.row_factory = sqlite3.Row
    return conn


def init_database(schema_path: Optional[Path] = None) -> None:
    """创建数据库表并初始化默认记录。"""
    if schema_path is None:
        # 默认从项目根目录下的 database/schema.sql 读取建表脚本。
        schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        # 执行当前阶段的关键处理。
        conn.execute("PRAGMA journal_mode=OFF")
        with open(schema_path, "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())
        # 建表后顺手写入默认管理员和示例数据集，避免空库启动。
        _insert_default_rows(conn)


def _insert_default_rows(conn: sqlite3.Connection) -> None:
    # 这部分只负责补齐初始化数据，不影响已有数据。
    """在数据库为空时补充默认管理员和数据集。"""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cur.execute("SELECT COUNT(1) FROM users WHERE username=?", ("admin",))
    # 根据当前条件执行对应处理。
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)",
            ("admin", generate_password_hash("admin"), "admin", now),
        )

    # 执行当前阶段的关键处理。
    cur.execute("SELECT COUNT(1) FROM datasets")
    if cur.fetchone()[0] == 0:
        sample_path = Path(__file__).resolve().parents[1] / "data" / "sample.h5ad"
        cur.execute(
            "INSERT INTO datasets(name,path,description,is_active,created_at) VALUES (?,?,?,?,?)",
            ("sample", str(sample_path), "Default sample dataset", 0, now),
        )

    # 执行当前阶段的关键处理。
    conn.commit()


def execute_query(sql: str, params: Iterable[Any] | None = None, commit: bool = False) -> int:
    # 统一的写操作入口，业务层尽量不要直接操作 sqlite3 API。
    """执行写操作并返回新增记录主键。"""
    params = params or ()
    with get_connection() as conn:
        cur = conn.execute(sql, tuple(params))
        if commit:
            # 执行当前阶段的关键处理。
            conn.commit()
        return cur.lastrowid


def fetch_one(sql: str, params: Iterable[Any] | None = None) -> Optional[sqlite3.Row]:
    # 查询一条记录，返回 sqlite Row，便于调用方按字段名取值。
    """执行查询并返回第一条记录。"""
    params = params or ()
    with get_connection() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()


def fetch_all(sql: str, params: Iterable[Any] | None = None) -> List[sqlite3.Row]:
    # 查询多条记录，统一封装成 list 返回。
    """执行查询并返回全部记录。"""
    params = params or ()
    with get_connection() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()
