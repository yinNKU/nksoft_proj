from pathlib import Path

import pytest

from src import db
from src.user_service import UserService, UserServiceError


def setup_db(tmp_path, monkeypatch):
    db_file = tmp_path / "app.db"
    monkeypatch.setenv("NK_DB_PATH", str(db_file))
    schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    db.init_database(schema_path=schema)
    return db_file


def test_database_initialization_and_admin_defaults(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    assert db.fetch_one("SELECT id FROM users WHERE username='admin'") is not None
    assert db.fetch_one("SELECT role FROM users WHERE username='admin'")["role"] == "admin"
    assert db.fetch_one("SELECT id FROM datasets WHERE name='sample'") is not None


def test_user_registration_login_and_permissions(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    service = UserService()

    user_id = service.register("alice", "pwd")# 测试：注册新用户成功
    assert user_id > 0

    with pytest.raises(UserServiceError):
        service.register("alice", "pwd")# 测试：重复注册用户失败

    assert service.login("alice", "pwd") is True# 测试：登录成功
    assert service.login("alice", "wrong") is False # 测试：登录失败（密码错误）

    assert service.is_admin("admin") is True# 测试：管理员权限正确
    assert service.is_admin("alice") is False# 测试：普通用户权限错误

    users = service.list_users()
    assert any(item["username"] == "alice" for item in users)

    service.delete_user("alice")
    users = service.list_users()
    assert not any(item["username"] == "alice" for item in users)
