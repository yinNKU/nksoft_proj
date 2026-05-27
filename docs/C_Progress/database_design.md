# 数据库设计说明

本文说明为什么需要数据库，以及各张表的设计思路。

---

# 为什么需要数据库

- 用于持久化保存数据集信息、用户信息以及索引构建记录。
- 避免程序重启后数据丢失。
- 便于统一管理数据集与 ANN 索引。

---

# SQLite 与 MySQL

- 当前项目使用 SQLite，优点是轻量、易部署、便于本地开发和测试。
- 如果后续部署到生产环境，也可以切换为 MySQL。
- 对于单机 ANN 检索平台、课程设计或中小型项目，SQLite 已经足够。

## SQLite 数据持久化说明

SQLite 数据库存储在磁盘上的：

```text
database/app.db
```

因此：

- 不会因为关闭网页而丢失
- 不会因为重启 Flask 服务而丢失
- 不会因为重启 Python 而丢失

数据会持久化保存在数据库文件中。

---

# 数据库整体结构

本项目包含三张核心表：

- `users`
- `datasets`
- `index_records`

---

# 表之间的关系

- `index_records.dataset_id` 外键关联 `datasets.id`
- 一个数据集可以对应多个索引记录

关系如下：

```text
users
  └── 用户系统（独立）

datasets
  └── 一个数据集
        └── 对应多个 index_records
```

即：

```text
datasets 1 —— N index_records
```

---

# 数据库表设计

## 1. users 表（用户表）

用于存储系统用户信息。

| 字段名 | 类型 | 约束 | 含义 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户唯一ID |
| username | TEXT | NOT NULL UNIQUE | 用户名，不能重复 |
| password_hash | TEXT | NOT NULL | 哈希后的密码 |
| role | TEXT | NOT NULL DEFAULT 'user' | 用户角色（user/admin） |
| created_at | TEXT | NOT NULL | 创建时间 |

---

## 2. datasets 表（数据集表）

用于管理所有 h5ad 数据集。

| 字段名 | 类型 | 约束 | 含义 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 数据集唯一ID |
| name | TEXT | NOT NULL UNIQUE | 数据集名称 |
| path | TEXT | NOT NULL | h5ad 文件路径 |
| description | TEXT | NULL | 数据集描述 |
| is_active | INTEGER | NOT NULL DEFAULT 0 | 是否为当前激活数据集 |
| created_at | TEXT | NOT NULL | 创建时间 |

---

## 3. index_records 表（索引记录表）

用于保存 ANN 索引元信息。

| 字段名 | 类型 | 约束 | 含义 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 索引记录ID |
| dataset_id | INTEGER | FOREIGN KEY | 所属数据集ID |
| index_type | TEXT | NOT NULL | 索引类型（HNSW/FAISS等） |
| index_path | TEXT | NOT NULL | 索引文件路径 |
| metadata_path | TEXT | NOT NULL | 元数据文件路径 |
| vector_dim | INTEGER | NULL | 向量维度 |
| num_vectors | INTEGER | NULL | 向量数量 |
| build_time_ms | REAL | NULL | 索引构建耗时 |
| created_at | TEXT | NOT NULL | 创建时间 |

---

# 表功能说明

## users

用于：

- 用户注册
- 用户登录
- 权限管理
- 管理员角色判断

---

## datasets

用于：

- 保存 h5ad 数据集信息
- 管理当前 active 数据集
- 数据集切换

---

## index_records

用于：

- 保存 ANN 索引构建信息
- 管理不同索引类型
- 记录索引路径和元数据
- 保存索引性能指标

---

# 数据库初始化方式

运行：

```bash
python database/init_db.py
```

功能：

- 创建数据库
- 创建表结构
- 初始化默认管理员账号
- 初始化默认 sample 数据集

---

# 测试命令

## 运行数据库相关测试

```bash
python -m pytest -q tests/test_dataset_manager.py
python -m pytest -q tests/test_user_service.py
python -m pytest -q tests/test_app.py
```

---

# 已完成测试项

- 数据库初始化成功
- 添加数据集成功
- 添加重复数据集失败
- 添加不存在路径失败
- 添加非 h5ad 文件失败
- 删除数据集成功
- 切换 active 数据集成功
- 写入索引记录成功
- 读取索引记录成功
- 注册用户成功
- 重复用户名注册失败
- 登录成功
- 密码错误登录失败
- 管理员权限判断成功
- 普通用户无管理权限


# 整体流程

首先如果进行数据库设置，需要
```bash
$env:NK_DB_PATH="database/app.db"
```

接着运行：
```bash
python database/init_db.py
```

然后运行：
```bash
python app.py
```

然后进行测试命令或者api调用即可。