# 单细胞 ANN 检索系统

这是一个面向单细胞高维向量数据的 Web 检索系统。程序读取 AnnData 的 `.h5ad` 文件，提取或计算 PCA 向量，使用 FAISS 构建 Flat、HNSW 或 IVF 索引，并返回 Top-K 相似细胞及其元数据。

系统同时提供用户登录、条件筛选、PCA/UMAP 可视化、数据集记录管理、索引重建和自动化测试。当前演示数据包含 69,032 个细胞，检索使用 30 维 PCA 向量。

## 主要功能

- 读取 `.h5ad` 数据，优先使用 `adata.obsm['X_pca']`，缺失时通过 Scanpy 计算 PCA。
- 对检索向量执行 L2 归一化，使用内积表示余弦相似度。
- 支持 Flat、HNSW、IVF 三种 FAISS 索引及索引缓存。
- 支持按细胞下标、真实 `cell_id`、自定义 PCA 向量查询。
- 支持 Top-K 设置和元数据精确筛选。
- 提供 PCA/UMAP 散点图、元数据着色和检索结果高亮。
- 使用 SQLite 保存用户、数据集和索引记录。
- 区分普通用户与管理员权限。
- 提供 pytest 自动化测试。

## 运行环境

建议使用 Python 3.10--3.12。主要依赖包括 Flask、NumPy、Pandas、Scanpy、AnnData、FAISS CPU 和 pytest，具体版本范围见 `requirements.txt`。

## 安装

以下命令均假设当前终端已经进入克隆或解压后的项目根目录，即包含 `app.py` 和 `requirements.txt` 的目录。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

若 PowerShell 禁止执行激活脚本，可以在当前终端临时执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

FAISS 的可用版本与 Python、操作系统有关。如果 `faiss-cpu` 安装失败，建议使用 Python 3.10 或 3.11 创建新的虚拟环境后重试。

## 准备数据

默认数据文件位置为：

```text
data/sample.h5ad
```

如果该文件不存在，程序会选择 `data/` 下按文件名排序后的第一个 `.h5ad` 文件。也可以显式设置数据文件。

Windows PowerShell：

```powershell
$env:SC_DATA_PATH='data\your_dataset.h5ad'
```

macOS / Linux：

```bash
export SC_DATA_PATH='data/your_dataset.h5ad'
```

数据要求：

- 每个细胞具有唯一观察索引，该索引会作为 `cell_id`。
- 推荐在 `adata.obsm['X_pca']` 中预先保存 PCA 结果。
- 可视化需要 `adata.obsm['X_umap']` 或至少二维的 `X_pca`。
- 条件筛选和着色字段来自 `adata.obs`。

如果数据中没有 `X_pca`，程序会执行基础 Scanpy 预处理并计算 PCA。大型表达矩阵在这一阶段可能占用较多时间和内存。

## 配置项

配置主要来自 `config.py` 和环境变量。

| 环境变量 | 默认值 | 作用 |
|---|---:|---|
| `SC_DATA_PATH` | `data/sample.h5ad` | 指定 `.h5ad` 数据文件。 |
| `SC_INDEX_DIR` | `indexes/` | 指定 FAISS 索引和 JSON 元数据目录。 |
| `SC_N_PCS` | `50` | 数据缺少 PCA 时计划计算的主成分数量。 |
| `SC_INDEX_TYPE` | `hnsw` | 启动时使用的索引类型。 |
| `SC_TOP_K` | `10` | 默认 Top-K。 |
| `SC_MAX_TOP_K` | `100` | 单次查询允许的最大 Top-K。 |
| `SC_HNSW_M` | `32` | HNSW 的 `M` 参数。 |
| `SC_HNSW_EF_SEARCH` | `64` | HNSW 的 `efSearch` 参数。 |
| `SC_IVF_NLIST` | `100` | IVF 聚类中心数量。 |
| `SC_IVF_NPROBE` | `10` | IVF 查询时访问的倒排区域数量。 |
| `NK_DB_PATH` | `database/app.db` | Flask 应用使用的 SQLite 文件。 |
| `NK_SECRET_KEY` | `nksoft-dev-secret` | Flask 会话签名密钥。 |
| `NK_SYNC_INIT` | 未设置 | 设置为 `1` 时同步加载数据，主要用于测试。 |

用于非本地演示时，应设置独立的 `NK_SECRET_KEY`，并更换默认管理员凭据。

## 初始化数据库

Flask 应用启动时会自动调用 `src.db.init_database()`，创建 `users`、`datasets` 和 `index_records` 三张表。

默认管理员为：

```text
用户名：admin
密码：admin
角色：admin
```

使用默认数据库时，也可以手动初始化：

```powershell
python database\init_db.py
```

`database/init_db.py` 固定初始化 `database/app.db`。使用自定义 `NK_DB_PATH` 时无需运行该脚本，直接启动 Flask，应用会在指定位置自动建库。

## 启动

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
$env:NK_SECRET_KEY='replace-with-a-local-secret'
python app.py
```

macOS / Linux：

```bash
source .venv/bin/activate
export NK_SECRET_KEY='replace-with-a-local-secret'
python app.py
```

浏览器访问：

```text
http://127.0.0.1:5000
```

程序默认监听 5000 端口。数据加载和索引初始化默认在后台线程执行，因此页面可能先显示，检索功能稍后才可用。登录后应等待“系统状态”中的数据状态变为“已加载”。

## 页面使用

### 登录与注册

1. 使用 `admin/admin` 登录可进入管理员页面。
2. 普通用户可以点击“注册新账号”。
3. 未登录用户只能注册 `user` 角色。
4. 管理员可以在管理区域创建普通用户或管理员。

### 执行检索

页面支持三种查询方式：

- 按细胞编号：输入从 0 开始的 `cell_index`。
- 按细胞 ID：输入真实 `cell_id`。
- 按自定义向量：输入与当前 PCA 维度一致的逗号分隔向量。

设置 Top-K 和索引类型后点击“开始检索”。结果表格会显示 `rank`、`cell_index`、`cell_id`、`score`、`metadata` 和 `query_time_ms`。

### 条件筛选

筛选字段来自当前数据的 `adata.obs`。选择字段、输入完整值并点击“添加”，再执行检索。例如：

```text
cell_type = hepatocyte
donor_id = C102
sex = female
```

筛选采用精确匹配。如果筛选后结果少于 Top-K，系统返回已有结果并附带提示。

### PCA / UMAP 可视化

在可视化区域选择 `PCA` 或 `UMAP`，再选择元数据着色字段并点击“加载图”。检索完成后，查询细胞和 Top-K 结果会自动高亮。鼠标悬浮可以查看细胞 ID、下标、相似度和着色字段值。

### 管理员功能

管理员可以查看、增加、删除数据集记录，设置 `datasets.is_active`，管理用户，以及选择 Flat、HNSW、IVF 并重建索引。

当前数据集“选择”操作只更新 SQLite 记录，不会立即重新加载搜索服务。需要切换实际数据时，应设置新的 `SC_DATA_PATH` 并重启程序。

## API 示例

### 查看状态与元数据字段

```powershell
curl.exe http://127.0.0.1:5000/api/status
curl.exe http://127.0.0.1:5000/api/metadata
```

### 按细胞下标查询

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search `
  -H "Content-Type: application/json" `
  -d '{"mode":"id","cell_index":0,"top_k":10,"index_type":"hnsw"}'
```

### 按真实 cell_id 查询

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search `
  -H "Content-Type: application/json" `
  -d '{"mode":"cell_id","cell_id":"AAACCTGAGCAGGTCA-1_2","top_k":10}'
```

### 按自定义向量查询

下面的向量长度只是格式示例，实际长度必须与 `/api/status` 返回的 `n_dims` 一致。

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search `
  -H "Content-Type: application/json" `
  -d '{"mode":"vector","vector":[0.1,0.2,0.3],"top_k":5}'
```

### 条件筛选

```powershell
curl.exe -X POST http://127.0.0.1:5000/api/search `
  -H "Content-Type: application/json" `
  -d '{"mode":"id","cell_index":0,"top_k":10,"filters":{"cell_type":"hepatocyte"}}'
```

## 主要 API

| 方法 | 地址 | 说明 | 权限 |
|---|---|---|---|
| GET | `/` | Web 页面。 | 公开 |
| GET | `/api/status` | 数据与索引状态。 | 公开 |
| GET | `/api/metadata` | 可用元数据字段。 | 公开 |
| GET | `/api/embedding` | PCA/UMAP 二维坐标。 | 公开 |
| POST | `/api/search` | 三种方式的 Top-K 检索。 | 公开 |
| POST | `/api/register` | 注册普通用户。 | 公开 |
| POST | `/api/login` | 登录并建立会话。 | 公开 |
| POST | `/api/logout` | 清除会话。 | 公开 |
| GET | `/api/session` | 当前会话用户。 | 公开 |
| GET | `/api/datasets` | 数据集记录列表。 | 公开 |
| POST | `/api/datasets` | 添加数据集记录。 | 管理员 |
| DELETE | `/api/datasets/<dataset_name>` | 删除数据集及关联索引记录。 | 管理员 |
| POST | `/api/datasets/select` | 设置激活数据集记录。 | 管理员 |
| GET | `/api/users` | 用户列表。 | 管理员 |
| DELETE | `/api/users/<username>` | 删除用户。 | 管理员 |
| POST | `/api/rebuild-index` | 重建并保存指定索引。 | 管理员 |

## 自动化测试

运行全部测试：

```powershell
python -m pytest -q -p no:cacheprovider
```

当前测试结果：

```text
39 passed
```

分文件运行：

```powershell
python -m pytest tests\test_data_loader.py -q -p no:cacheprovider
python -m pytest tests\test_ann_engine.py -q -p no:cacheprovider
python -m pytest tests\test_search_service.py -q -p no:cacheprovider
python -m pytest tests\test_app.py -q -p no:cacheprovider
python -m pytest tests\test_dataset_manager.py -q -p no:cacheprovider
python -m pytest tests\test_user_service.py -q -p no:cacheprovider
```

## 项目结构

```text
nksoft_proj/
├── app.py                       # Flask 入口和 Web API
├── config.py                    # 数据、索引和查询配置
├── database/
│   ├── init_db.py               # 默认数据库初始化脚本
│   └── schema.sql               # SQLite 表结构
├── data/                        # .h5ad 数据，不提交到 Git
├── indexes/                     # .faiss 和索引 JSON，不提交到 Git
├── src/
│   ├── ann_engine.py            # FAISS 索引构建、查询、保存和加载
│   ├── data_loader.py           # AnnData 读取、PCA 和元数据处理
│   ├── dataset_manager.py       # 数据集与索引记录管理
│   ├── db.py                    # SQLite 访问
│   ├── search_service.py        # 查询、筛选和结果整理
│   └── user_service.py          # 用户、密码和角色管理
├── static/
│   ├── css/style.css
│   └── js/
│       ├── main.js              # 页面状态和 API 调用
│       └── visualization.js     # PCA/UMAP Canvas 绘制
├── templates/index.html         # 单页前端
├── tests/                       # pytest 测试
├── requirements.txt
└── README.md
```

## 常见问题

### 页面可以打开，但无法检索

检查 `/api/status`。如果 `loaded` 为 `false`：

- 确认 `.h5ad` 文件存在。
- 检查 `SC_DATA_PATH`。
- 查看响应中的 `last_error`。
- 首次计算 PCA 或构建索引时继续等待。

### `vector dimension mismatch`

自定义向量长度与 `n_dims` 不一致。先访问 `/api/status` 获取当前维度。

### `cell_id not found`

输入值不在 AnnData 的观察索引中。`cell_id` 区分大小写并要求完全匹配。

### 筛选结果少于 Top-K

当前实现先取得 ANN 候选结果，再应用元数据精确筛选。条件较严格时会返回已有结果和 warning。

### 切换数据集后仍显示旧数据

`/api/datasets/select` 只更新数据库记录。设置新的 `SC_DATA_PATH` 后重启 Flask。

### pytest 出现 `PermissionError`

Windows 可能仍有 Flask、Python、SQLite journal 或 FAISS 文件被占用。关闭相关进程后重新运行测试；必要时为 pytest 指定可写的临时目录。
