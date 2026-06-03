# 截图操作指南

启动服务后按以下步骤截图，保存到 `presentation/screenshots/` 目录。

## 启动

```powershell
cd c:\Users\H\project\软件工程\soft_proj
$env:SC_DATA_PATH="data/liver.h5ad"
venv/Scripts/python.exe app.py
```

打开浏览器访问 `http://127.0.0.1:5000`

## 截图清单

| # | 文件名 | 操作 | 说明 |
|---|--------|------|------|
| 1 | `01_login.png` | 打开首页 | 展示登录表单、账号密码输入框 |
| 2 | `02_status.png` | 登录后查看系统状态 | 展示 loaded、n_cells、index_type、build_time_ms 等信息卡片 |
| 3 | `03_search_result.png` | 按细胞编号检索 cell_index=0, top_k=10 | 展示结果表格（rank/cell_index/cell_id/score/metadata）和查询耗时 |
| 4 | `04_filtered_search.png` | 添加 metadata 筛选 `cell_type = T cell` 后检索 | 展示筛选条件和过滤后的结果 |
| 5 | `05_umap_viz.png` | 点击"加载图"，选择 UMAP，按 cell_type 着色 | 展示 canvas 图中细胞分布和右侧图例 |
| 6 | `06_topk_highlight.png` | 检索后查看可视化区域 | 展示 Top-K 结果在图中高亮（编号标记） |
| 7 | `07_admin_panel.png` | 用 admin/admin 登录，查看管理员区域 | 展示数据集管理、索引重建、用户管理三个面板 |
| 8 | `08_index_rebuild.png` | 管理员点击"重建当前索引" | 展示重建成功后的 index_type 和 build_time_ms |

## 常见 metadata 筛选值

```
cell_type = T cell
cell_type = hepatocyte
donor_id = C102
sex = female
```

## 注意事项

- 首次启动可能较慢，等待状态显示 `loaded: true` 后再操作
- 可视化需要先点"加载图"才会渲染 canvas
- 截图建议使用浏览器全屏截图（F11 全屏模式下按 PrintScreen 或使用开发者工具）
