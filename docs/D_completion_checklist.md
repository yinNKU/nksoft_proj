# D 模块完成度核对

## 1. Coding Part 核对

| PDF 要求 | 当前实现 | 文件 |
|---|---|---|
| 登录注册页面 | 已完成。首屏为账号/密码登录；账号不存在弹窗提示注册；注册页独立切换。 | `templates/index.html`, `static/js/main.js`, `static/css/style.css` |
| 系统状态展示 | 已完成。展示 loaded、initializing、数据路径、细胞数、维度、索引类型、构建耗时。 | `templates/index.html`, `static/js/main.js` |
| 查询输入 | 已完成。支持细胞编号、cell_id、自定义 vector。 | `templates/index.html`, `static/js/main.js` |
| 条件检索 | 已完成。字段来自 `/api/metadata`，支持添加/删除 filters。 | `static/js/main.js`, `src/search_service.py` |
| Top-K 结果表格 | 已完成。展示 rank、cell_index、cell_id、score、metadata 和 query_time_ms。 | `templates/index.html`, `static/js/main.js` |
| 数据集管理页面 | 已完成。管理员可见，支持列表、添加、删除、选择 active 数据集记录。 | `templates/index.html`, `static/js/main.js`, `app.py` |
| 索引管理页面 | 已完成。管理员可见，支持选择 Flat/HNSW/IVF 并重建索引，显示耗时。 | `templates/index.html`, `static/js/main.js`, `app.py` |
| 查询耗时展示 | 已完成。搜索后显示 `query_time_ms`。 | `app.py`, `static/js/main.js` |
| PCA / UMAP 可视化 | 已完成。新增 `/api/embedding` 和 canvas 可视化，支持 UMAP/PCA、按 metadata 着色、悬浮提示、Top-K 高亮。 | `app.py`, `src/search_service.py`, `static/js/visualization.js`, `templates/index.html` |

## 2. PDF 中指定文件核对

| PDF 文件 | 当前状态 | 说明 |
|---|---|---|
| `templates/index.html` | 已完成 | 单页包含登录、注册、检索、结果、可视化、管理员区域 |
| `templates/login.html` | 未单独创建 | 当前采用单页切换实现，登录/注册视图在 `index.html` 中，功能等价 |
| `static/js/main.js` | 已完成 | 页面状态、登录注册、检索、筛选、管理功能 |
| `static/js/visualization.js` | 已完成 | PCA/UMAP canvas 可视化 |
| `static/css/style.css` | 已完成 | 简约暖灰/松绿/琥珀色 UI，响应式布局 |

## 3. Non-coding Part 核对

| PDF 要求 | 当前交付 | 说明 |
|---|---|---|
| 页面截图 | `docs/screenshots/` | 已建立目录和截图清单；当前自动化截图保存受本地权限限制，PNG 需在浏览器中按清单保存 |
| 前端使用说明 | `docs/frontend_usage.md` | 覆盖登录、状态、三种检索、Top-K、条件筛选、可视化、数据集管理、索引重建 |
| 接口交接说明 | `docs/interface_handoff.md` | 额外补充 A/B/C/D 接口、SQLite 配置、建表和本地测试流程 |

## 4. 本地验收结论

D 的主要功能要求已经完成：

1. 普通用户可以登录、检索、筛选、查看结果和可视化。
2. 管理员可以额外管理用户、数据集和索引。
3. 前端可以调用 A 的三种检索接口。
4. 前端可以调用 B 的索引重建接口。
5. 前端可以调用 C 的用户和数据集管理接口。
6. 前端新增可视化接口 `/api/embedding`，支持 UMAP/PCA 展示和 Top-K 高亮。

已知说明：

- 数据集切换当前只更新 SQLite `datasets.is_active`，搜索服务实际加载的数据仍由启动时 `SC_DATA_PATH` 或 `data/sample.h5ad` 决定。若要运行时真正切换数据文件，需要后续新增 `/api/load-data`。
- 当前登录页未拆成单独 `templates/login.html`，因为 Flask 单页应用更简单，所有视图都在 `index.html` 内按登录状态切换。
- `docs/screenshots/` 已提供截图命名清单，实际 PNG 截图需在本地浏览器运行后保存到该目录。
