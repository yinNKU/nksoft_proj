"""User management service: register, login, list, delete, role checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from werkzeug.security import generate_password_hash, check_password_hash

from src import db


class UserServiceError(RuntimeError):
    pass


class UserService:
    def __init__(self) -> None:
        # 用户创建时间统一写入 UTC，便于审计和排查问题。
        self.now = lambda: datetime.now(timezone.utc).isoformat()

    def register(self, username: str, password: str, role: str = "user") -> int:
        if not username or not password:
            raise UserServiceError("username and password required")
        if role not in {"user", "admin"}:
            raise UserServiceError("role must be user or admin")
        # 注册前先查重，避免用户名重复。
        existing = db.fetch_one("SELECT id FROM users WHERE username=?", (username,))
        if existing:
            raise UserServiceError("username already exists")
        # 密码不能明文入库，这里只保存哈希值。
        pwd_hash = generate_password_hash(password)
        sql = "INSERT INTO users(username,password_hash,role,created_at) VALUES (?,?,?,?)"
        return db.execute_query(sql, (username, pwd_hash, role, self.now()), commit=True)

    def login(self, username: str, password: str) -> bool:
        # 先取出哈希，再用校验函数比对，避免直接比较明文密码。
        row = db.fetch_one("SELECT password_hash FROM users WHERE username=?", (username,))
        if not row:
            return False
        return check_password_hash(row["password_hash"], password)

    def user_exists(self, username: str) -> bool:
        row = db.fetch_one("SELECT id FROM users WHERE username=?", (username,))
        return row is not None

    def authenticate(self, username: str, password: str) -> Optional[dict[str, Any]]:
        row = db.fetch_one(
            "SELECT id,username,password_hash,role,created_at FROM users WHERE username=?",
            (username,),
        )
        if not row or not check_password_hash(row["password_hash"], password):
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"],
        }

    def get_user(self, username: str) -> Optional[dict[str, Any]]:
        row = db.fetch_one("SELECT id,username,role,created_at FROM users WHERE username=?", (username,))
        return dict(row) if row else None

    def list_users(self) -> List[dict[str, Any]]:
        rows = db.fetch_all("SELECT id,username,role,created_at FROM users ORDER BY id DESC")
        return [dict(r) for r in rows]

    def delete_user(self, username: str) -> None:
        # 删除前先确认用户存在，避免误删或返回不清晰的错误。
        row = db.fetch_one("SELECT id FROM users WHERE username=?", (username,))
        if not row:
            raise UserServiceError("user not found")
        db.execute_query("DELETE FROM users WHERE id=?", (row["id"],), commit=True)

    def is_admin(self, username: str) -> bool:
        row = db.fetch_one("SELECT role FROM users WHERE username=?", (username,))
        if not row:
            return False
        return row["role"] == "admin"
