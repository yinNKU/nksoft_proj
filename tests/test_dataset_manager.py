# from pathlib import Path

# import pytest

# # from src import db
# import sqlite3

# conn = sqlite3.connect(setup_db)
# cur = conn.cursor()
# cur.execute("SELECT ...")
# from src.dataset_manager import DatasetManager, DatasetManagerError
# import pytest
# from database.init_db import init_db
# @pytest.fixture()
# def setup_db(tmp_path, monkeypatch):
#     # 强制把数据库指向 pytest 临时目录
#     test_db = tmp_path / "test.db"

#     monkeypatch.setenv("NK_DB_PATH", str(test_db))

#     # 关键：执行 schema.sql，创建 users / datasets 表
#     init_db(test_db)

#     return test_db
# # def setup_db(tmp_path, monkeypatch):
# #     db_file = tmp_path / "app.db"
# #     monkeypatch.setenv("NK_DB_PATH", str(db_file))
# #     schema = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
# #     db.init_database(schema_path=schema)
# #     return db_file


# def test_database_initialization_success(setup_db, monkeypatch):
# # 测试：setup_db(tmp_path, monkeypatch)
# # 数据库初始化成功
#     assert db.fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
#     assert db.fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'")
#     assert db.fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='index_records'")
#     assert db.fetch_one("SELECT id FROM users WHERE username='admin'")
#     assert db.fetch_one("SELECT id FROM datasets WHERE name='sample'")


# # def test_dataset_manager_crud_and_validation(tmp_path, monkeypatch):
# #     setup_db(tmp_path, monkeypatch)
# def test_dataset_manager_crud_and_validation(setup_db, monkeypatch):
#     manager = DatasetManager()

#     sample = tmp_path / "sample.h5ad"
#     sample.write_text("x")
#     non_h5ad = tmp_path / "sample.txt"
#     non_h5ad.write_text("x")
#     missing = tmp_path / "missing.h5ad"

#     dataset_id = manager.add_dataset("ds1", str(sample), "desc")
#     assert dataset_id > 0       # 测试：添加数据集成功
#     assert any(item["name"] == "ds1" for item in manager.list_datasets())

#     with pytest.raises(DatasetManagerError):       # 测试：重复添加数据集失败
#         manager.add_dataset("ds1", str(sample), "dup")

#     with pytest.raises(DatasetManagerError):       # 测试：添加不存在路径失败
#         manager.add_dataset("ds_missing", str(missing), "missing")

#     with pytest.raises(DatasetManagerError):       # 测试：添加非H5AD文件失败
#         manager.add_dataset("ds_bad", str(non_h5ad), "bad")

#     manager.select_dataset("ds1")     # 测试：切换 active 数据集成功
#     active = manager.get_active_dataset()
#     assert active is not None and active["name"] == "ds1"

#     index_id = manager.add_index_record(     # 测试：写入索引记录成功
#         "ds1",
#         "hnsw",
#         "i.faiss",
#         "m.json",
#         vector_dim=50,
#         num_vectors=1000,
#         build_time_ms=12.3,
#     )
#     assert index_id > 0

#     records = manager.list_index_records("ds1")  # 测试：查询索引记录成功
#     assert len(records) == 1
#     assert records[0]["index_type"] == "hnsw"
#     assert records[0]["index_path"] == "i.faiss"

#     manager.delete_dataset("ds1")     # 测试：删除数据集成功
#     assert all(item["name"] != "ds1" for item in manager.list_datasets())
#     assert db.fetch_one("SELECT id FROM index_records WHERE dataset_id=(SELECT id FROM datasets WHERE name='ds1')") is None
from pathlib import Path
import pytest

from database.init_db import init_db
from src.dataset_manager import DatasetManager, DatasetManagerError



# 1. 初始化测试数据库
@pytest.fixture()
def setup_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"

    # 设置环境变量（项目是靠这个读取 DB）
    monkeypatch.setenv("NK_DB_PATH", str(test_db))

    # 初始化数据库（创建 users / datasets / index_records）
    init_db(test_db)

    return test_db


# 2. 测试数据库结构
def test_database_initialization_success(setup_db):
    import sqlite3

    conn = sqlite3.connect(setup_db)
    cur = conn.cursor()

    # 检查表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    assert cur.fetchone() is not None

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'")
    assert cur.fetchone() is not None

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='index_records'")
    assert cur.fetchone() is not None

    # 检查默认数据
    cur.execute("SELECT id FROM users WHERE username='admin'")
    assert cur.fetchone() is not None

    cur.execute("SELECT id FROM datasets WHERE name='sample'")
    assert cur.fetchone() is not None

    conn.close()


# 3. DatasetManager 测试
def test_dataset_manager_crud_and_validation(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setenv("NK_DB_PATH", str(test_db))
    init_db(test_db)

    manager = DatasetManager()

    sample = tmp_path / "sample.h5ad"
    sample.write_text("x")

    non_h5ad = tmp_path / "sample.txt"
    non_h5ad.write_text("x")

    missing = tmp_path / "missing.h5ad"

    #  add dataset 
    dataset_id = manager.add_dataset("ds1", str(sample), "desc")
    assert dataset_id > 0

    assert any(d["name"] == "ds1" for d in manager.list_datasets())

    #  duplicate 
    with pytest.raises(DatasetManagerError):
        manager.add_dataset("ds1", str(sample), "dup")

    #  invalid path 
    with pytest.raises(DatasetManagerError):
        manager.add_dataset("ds_missing", str(missing), "missing")

    #  invalid format 
    with pytest.raises(DatasetManagerError):
        manager.add_dataset("ds_bad", str(non_h5ad), "bad")

    #  select 
    manager.select_dataset("ds1")
    active = manager.get_active_dataset()
    assert active is not None
    assert active["name"] == "ds1"

    #  index record 
    index_id = manager.add_index_record(
        "ds1",
        "hnsw",
        "i.faiss",
        "m.json",
        vector_dim=50,
        num_vectors=1000,
        build_time_ms=12.3,
    )
    assert index_id > 0

    records = manager.list_index_records("ds1")
    assert len(records) == 1
    assert records[0]["index_type"] == "hnsw"

    #  delete 
    manager.delete_dataset("ds1")
    assert all(d["name"] != "ds1" for d in manager.list_datasets())