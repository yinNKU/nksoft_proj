"""Initialize SQLite database using schema.sql and create default records."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "app.db"
SCHEMA = ROOT / "database" / "schema.sql"


def init_db(db_path: Path = DB_PATH, schema_path: Path = SCHEMA) -> None:
    # 初始化脚本入口：先指定数据库路径，再复用 src.db 里的建库逻辑。
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        # 先执行 schema.sql，确保所有表结构都已创建。
        with schema_path.open("r", encoding="utf-8") as fh:
            sql = fh.read()
        conn.executescript(sql)
        # 初始化默认管理员，方便首次登录和后续权限管理。
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM users WHERE username=?", ("admin",))
        if cur.fetchone()[0] == 0:
            now = datetime.now(timezone.utc).isoformat()
            pwd = generate_password_hash("admin")
            cur.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)",
                ("admin", pwd, "admin", now),
            )
        # 初始化一个示例数据集，便于项目开箱即用。
        cur.execute("SELECT COUNT(1) FROM datasets")
        if cur.fetchone()[0] == 0:
            now = datetime.now(timezone.utc).isoformat()
            sample_path = ROOT / "data" / "sample.h5ad"
            cur.execute(
                "INSERT INTO datasets(name,path,description,is_active,created_at) VALUES (?,?,?,?,?)",
                ("sample", str(sample_path), "Default sample dataset", 0, now),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    # 允许直接执行：python database/init_db.py
    init_db()
    print(f"Initialized database at {DB_PATH}")
