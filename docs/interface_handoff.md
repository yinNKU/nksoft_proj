# 单细胞 ANN 检索系统接口与本地部署交接文档

本文档用于组内交接和本地验收，覆盖 A/B/C 已实现后端接口、D 新增前端与可视化接口、SQLite 配置、建表方式和本地测试流程。

## 1. 模块分工对应关系

| 成员 | 模块 | 主要代码文件 | 交接重点 |
|---|---|---|---|
| A | 检索后端与条件检索 | `src/search_service.py`, `app.py` | `/api/search`, `/api/status`, `/api/metadata`, filters 条件检索 |
| B | ANN 索引构建与动态索引管理 | `src/ann_engine.py`, `config.py` | Flat/HNSW/IVF, 保存加载索引, 重建索引 |
| C | 数据集管理、用户管理、数据库 | `src/db.py`, `src/dataset_manager.py`, `src/user_service.py`, `database/schema.sql`, `database/init_db.py` | SQLite 表结构、用户/数据集 API、权限控制 |
| D | Web 前端与可视化展示 | `templates/index.html`, `static/js/main.js`, `static/js/visualization.js`, `static/css/style.css` | 登录注册页面、检索界面、结果表格、条件筛选、数据集/索引管理、PCA/UMAP 可视化 |

## 2. 本地环境配置

### 2.1 Python 环境

推荐 Python 3.10+。Windows PowerShell 示例：

```powershell
cd D:\SE_Final\nksoft_proj
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

当前依赖位于 `requirements.txt`：

```text
flask>=3.0.0
numpy>=1.24.0
pandas>=2.0.0
scanpy>=1.9.0
anndata>=0.10.0
faiss-cpu>=1.7.4
pytest>=8.0.0
```

### 2.2 数据文件

默认数据路径为：

```text
data/sample.h5ad
```

也可以通过环境变量指定其他 `.h5ad`：

```powershell
$env:SC_DATA_PATH="D:\path\to\your_data.h5ad"
```

### 2.3 SQLite 数据库配置

默认数据库位置为：

```text
database/app.db
```

为了避免污染默认库，演示和测试建议显式指定：

```powershell
$env:NK_DB_PATH="D:\SE_Final\nksoft_proj\database\frontend_runtime2.db"
```

数据库由 `src/db.py` 和 `database/init_db.py` 初始化。应用启动时会自动调用 `db.init_database()`，如果数据库不存在，会执行 `database/schema.sql` 并写入默认数据。

如需手动初始化：

```powershell
python database/init_db.py
```

默认管理员账号：

```text
username: admin
password: admin
role: admin
```

## 3. SQLite 建表说明

建表脚本：`database/schema.sql`

### 3.1 users 表

用于保存登录账号和权限角色。

```sql
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);
```

字段说明：

| 字段 | 含义 |
|---|---|
| `id` | 用户主键 |
| `username` | 用户名，唯一 |
| `password_hash` | 哈希后的密码，不保存明文 |
| `role` | `user` 或 `admin` |
| `created_at` | UTC 创建时间 |

### 3.2 datasets 表

用于保存数据集记录。

```sql
CREATE TABLE IF NOT EXISTS datasets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
```

字段说明：

| 字段 | 含义 |
|---|---|
| `id` | 数据集主键 |
| `name` | 数据集名称，唯一 |
| `path` | `.h5ad` 文件路径 |
| `description` | 数据集描述 |
| `is_active` | 是否为当前激活数据集 |
| `created_at` | UTC 创建时间 |

### 3.3 index_records 表

用于保存索引文件和索引 metadata 文件记录。

```sql
CREATE TABLE IF NOT EXISTS index_records(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    index_type TEXT NOT NULL,
    index_path TEXT NOT NULL,
    metadata_path TEXT NOT NULL,
    vector_dim INTEGER,
    num_vectors INTEGER,
    build_time_ms REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(dataset_id) REFERENCES datasets(id)
);
```

字段说明：

| 字段 | 含义 |
|---|---|
| `dataset_id` | 关联 `datasets.id` |
| `index_type` | `flat`, `hnsw`, `ivf` |
| `index_path` | `.faiss` 索引文件路径 |
| `metadata_path` | `.json` 索引 metadata 路径 |
| `vector_dim` | 向量维度 |
| `num_vectors` | 向量数量 |
| `build_time_ms` | 索引构建耗时 |

## 4. 启动方式

Windows PowerShell：

```powershell
cd D:\SE_Final\nksoft_proj
$env:NK_DB_PATH="D:\SE_Final\nksoft_proj\database\frontend_runtime2.db"
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

注意：`data/sample.h5ad` 较大时，应用会先启动前端，再后台加载数据和索引。此时 `/api/status` 中可能显示：

```json
{
  "loaded": false,
  "initializing": true
}
```

等待 `loaded: true` 后，检索、条件筛选和可视化可完整使用。

## 5. A：检索后端接口

### 5.1 GET /api/status

用途：查看数据集加载、索引、向量维度和构建耗时。

请求：

```powershell
curl.exe http://127.0.0.1:5000/api/status
```

响应示例：

```json
{
  "success": true,
  "loaded": true,
  "initializing": false,
  "data_path": "D:\\SE_Final\\nksoft_proj\\data\\sample.h5ad",
  "n_cells": 69032,
  "n_dims": 30,
  "index_type": "hnsw",
  "build_time_ms": 249.86,
  "dataset": {
    "n_cells": 69032,
    "n_genes": 32397,
    "n_pcs": 30,
    "metadata_columns": ["cell_type", "donor_id", "sex"]
  },
  "last_error": null
}
```

### 5.2 GET /api/metadata

用途：返回可用于条件筛选和表格展示的 metadata 字段。

```powershell
curl.exe http://127.0.0.1:5000/api/metadata
```

响应：

```json
{
  "success": true,
  "fields": ["cell_type", "donor_id", "sex", "tissue"]
}
```

### 5.3 POST /api/search

用途：统一检索入口，支持三种检索方式和 metadata 条件过滤。

通用请求字段：

| 字段 | 类型 | 是否必需 | 说明 |
|---|---|---|---|
| `mode` | string | 是 | `id`, `cell_id`, `vector` |
| `top_k` | int | 否 | 返回数量，默认读取配置 |
| `index_type` | string | 否 | `hnsw`, `flat`, `ivf` |
| `filters` | object | 否 | metadata 条件过滤 |

按细胞编号：

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"id\",\"cell_index\":4,\"top_k\":10,\"index_type\":\"hnsw\"}"
```

按真实 cell_id：

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"cell_id\",\"cell_id\":\"AAACCTGTCATAAAGG-1_2\",\"top_k\":10}"
```

按自定义 PCA 向量：

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"vector\",\"vector\":[2.2930813,27.493592,2.5815551,7.6082674,-3.4993581,-2.0830045,-0.21141971,-3.4404183,2.0747137,-12.857695,-2.2665378,0.11963992,1.7292324,1.487157,0.3431908,0.58974461,3.847756,10.807111,0.65465985,-2.8503491,1.6966989,0.60788797,0.37084127,1.0063659,-0.20603992,-0.034288398,0.15471178,1.2135784,-0.16843452,-0.70989546],\"top_k\":10}"
```

条件筛选示例：

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"id\",\"cell_index\":4,\"top_k\":10,\"filters\":{\"cell_type\":\"T cell\"}}"
```

响应字段：

```json
{
  "success": true,
  "mode": "id",
  "top_k": 10,
  "filters": {"cell_type": "T cell"},
  "query_time_ms": 2.31,
  "index_type": "hnsw",
  "results": [
    {
      "rank": 1,
      "cell_index": 4,
      "cell_id": "AAACCTGTCATAAAGG-1_2",
      "score": 1.0,
      "metadata": {
        "cell_type": "T cell",
        "donor_id": "C102"
      }
    }
  ]
}
```

常见错误：

| 错误 | 原因 |
|---|---|
| `cell_id not found` | 输入的 cell_id 不存在 |
| `cell_index out of range` | 细胞下标越界 |
| `vector dimension mismatch` | 自定义向量维度和 PCA 维度不一致 |
| `metadata field not found` | filters 字段不是合法 metadata |

## 6. B：索引管理接口

### 6.1 POST /api/rebuild-index

用途：管理员触发当前数据集索引重建。

需要管理员登录 session。前端管理员区会自动调用。

请求：

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/rebuild-index -H "Content-Type: application/json" -d "{\"index_type\":\"hnsw\"}"
```

响应：

```json
{
  "success": true,
  "index_type": "hnsw",
  "index_path": "D:\\SE_Final\\nksoft_proj\\indexes\\sample_hnsw.faiss",
  "metadata_path": "D:\\SE_Final\\nksoft_proj\\indexes\\sample_hnsw.json",
  "build_time_ms": 249.86
}
```

支持索引类型：

| 类型 | 说明 |
|---|---|
| `flat` | 精确检索，对照基线 |
| `hnsw` | 默认 ANN 方法 |
| `ivf` | 倒排文件索引 |

索引参数位于 `config.py`：

```python
DEFAULT_INDEX_TYPE = "hnsw"
HNSW_M = 32
HNSW_EF_SEARCH = 64
IVF_NLIST = 100
IVF_NPROBE = 10
INDEX_DIR = BASE_DIR / "indexes"
```

## 7. C：用户、数据集与数据库接口

### 7.1 POST /api/register

注册普通用户，或管理员创建用户。

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/register -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"pwd123\",\"role\":\"user\"}"
```

说明：

- 未登录时只允许注册 `role=user`。
- `role=admin` 需要当前 session 是管理员。
- 密码通过 Werkzeug 哈希后写入 `users.password_hash`。

### 7.2 POST /api/login

登录后后端根据数据库 role 自动区分普通用户和管理员。

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin\"}"
```

成功响应：

```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "created_at": "..."
  }
}
```

失败响应：

```json
{"success": false, "code": "account_not_found", "error": "account not found"}
```

```json
{"success": false, "code": "invalid_password", "error": "invalid password"}
```

### 7.3 POST /api/logout

清空 Flask session。

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/logout
```

### 7.4 GET /api/session

前端启动时读取当前登录状态。

```powershell
curl.exe http://127.0.0.1:5000/api/session
```

### 7.5 GET /api/users

管理员查看用户列表。

```powershell
curl.exe http://127.0.0.1:5000/api/users
```

### 7.6 DELETE /api/users/<username>

管理员删除用户。

```powershell
curl.exe -X DELETE http://127.0.0.1:5000/api/users/alice
```

### 7.7 GET /api/datasets

查看 SQLite 中记录的数据集。

```powershell
curl.exe http://127.0.0.1:5000/api/datasets
```

### 7.8 POST /api/datasets

管理员添加数据集记录。

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/datasets -H "Content-Type: application/json" -d "{\"name\":\"sample\",\"path\":\"D:\\\\SE_Final\\\\nksoft_proj\\\\data\\\\sample.h5ad\",\"description\":\"default sample\"}"
```

后端会检查：

- 路径存在。
- 后缀是 `.h5ad`。
- 名称不重复。

### 7.9 POST /api/datasets/select

管理员切换 active 数据集记录。

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/datasets/select -H "Content-Type: application/json" -d "{\"name\":\"sample\"}"
```

注意：当前实现切换 SQLite 的 `is_active` 记录；实际加载数据仍以启动时 `SC_DATA_PATH` 或 `data/sample.h5ad` 为准，切换后建议重启服务或后续补 `/api/load-data`。

### 7.10 DELETE /api/datasets/<dataset_name>

管理员删除数据集记录，并同步删除相关 `index_records`。

```powershell
curl.exe -X DELETE http://127.0.0.1:5000/api/datasets/sample
```

## 8. D：前端与可视化接口

### 8.1 页面入口

```text
GET /
```

返回 `templates/index.html`。当前项目采用单页前端，不单独维护 `templates/login.html`；登录和注册视图都在 `index.html` 中通过 JS 切换显示。

### 8.2 GET /api/embedding

用途：D 新增可视化数据接口，供 `static/js/visualization.js` 绘制 PCA/UMAP 散点图。

请求参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `basis` | `umap` | `umap` 使用 `adata.obsm["X_umap"]`；`pca` 使用 `adata.obsm["X_pca"]` 前两维 |
| `color_by` | `cell_type` | 按指定 metadata 字段着色 |

请求：

```powershell
curl.exe "http://127.0.0.1:5000/api/embedding?basis=umap&color_by=cell_type"
```

响应：

```json
{
  "success": true,
  "basis": "umap",
  "color_by": "cell_type",
  "n_points": 69032,
  "points": [
    {
      "cell_index": 0,
      "cell_id": "AAACCTGAGCAGGTCA-1_2",
      "x": 1.23,
      "y": -0.45,
      "color": "hepatocyte"
    }
  ]
}
```

前端行为：

- 登录后系统加载完成，会自动或手动加载可视化。
- 可在 UMAP/PCA 间切换。
- 可按 metadata 字段着色。
- 鼠标悬浮显示 `cell_id`, `cell_index`, 当前着色字段值。
- 搜索成功后自动高亮 Top-K 结果。
- `mode=id` 和 `mode=cell_id` 查询时额外高亮查询细胞。

## 9. 前端本地验收用例

### 9.1 登录与权限

1. 打开 `http://127.0.0.1:5000`。
2. 输入 `admin/admin`，登录后应显示管理员区。
3. 退出。
4. 注册普通用户，再登录，普通用户不应看到管理员区。
5. 输入不存在账号，应弹出“需要先注册”。

### 9.2 三种检索方式

按细胞编号：

```text
4
```

按 cell_id：

```text
AAACCTGTCATAAAGG-1_2
```

按 vector：

```text
2.2930813,27.493592,2.5815551,7.6082674,-3.4993581,-2.0830045,-0.21141971,-3.4404183,2.0747137,-12.857695,-2.2665378,0.11963992,1.7292324,1.487157,0.3431908,0.58974461,3.847756,10.807111,0.65465985,-2.8503491,1.6966989,0.60788797,0.37084127,1.0063659,-0.20603992,-0.034288398,0.15471178,1.2135784,-0.16843452,-0.70989546
```

### 9.3 条件筛选

字段：

```text
cell_type
```

筛选值：

```text
T cell
```

或：

```text
hepatocyte
```

## 10. 测试命令

核心接口和服务层测试：

```powershell
python -m pytest tests\test_app.py tests\test_search_service.py -q -p no:cacheprovider
```

全量测试：

```powershell
python -m pytest tests -q -p no:cacheprovider
```

说明：Windows 环境中若旧的 pytest 临时目录、SQLite journal 或 FAISS 文件被系统锁住，可能出现 `PermissionError`。这属于本地文件锁问题，可关闭 Python/Flask 进程后重试。

