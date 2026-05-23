# 成员 B 当前进度说明

记录时间：2026-05-23

## 1. 负责范围

根据 `分工.pdf`，成员 B 负责 **ANN 索引构建与动态索引管理**，主要包括：

- 构建 FAISS 索引。
- 支持 HNSW、Flat、IVF 三种索引类型。
- 支持 Top-K 检索。
- 支持索引保存和加载。
- 支持索引类型切换。
- 支持动态重建索引。
- 补充索引设计说明和流程图。

## 2. 已完成内容

代码部分：

- `src/ann_engine.py`
  - 支持 `flat`、`hnsw`、`ivf`。
  - 默认使用 L2 归一化 + 内积检索，实现余弦相似度。
  - 支持 HNSW 和 IVF 参数配置。
  - 支持索引保存为 `.faiss`，metadata 保存为 `.json`。
  - 加载索引时会校验向量维度、向量数量和数据集标识。

- `config.py`
  - 增加默认索引类型、HNSW/IVF 参数、索引文件后缀等配置。
  - 支持自动识别 `data/` 下的 `.h5ad` 数据文件。

- `scripts/build_index.py`
  - 支持命令行构建索引。
  - 支持 `--data`、`--index-type`、`--hnsw-m`、`--hnsw-ef-search`、`--ivf-nlist`、`--ivf-nprobe`、`--save` 等参数。

- `src/search_service.py`
  - 增加 `load_cached_index()`：优先加载已有索引。
  - 增加 `rebuild_index()`：动态重建并保存索引。
  - 搜索时如果切换索引类型，会优先加载缓存；缓存不存在则自动重建。

- `app.py`
  - 新增 `POST /api/rebuild-index`，用于动态重建索引。

- `tests/test_ann_engine.py`
  - 覆盖三种索引构建、Top-K 搜索、维度错误、非法索引类型、保存加载和 metadata 不匹配。

文档部分：

- `docs/index_design.md`：索引设计说明。
- `docs/figures/index_workflow.png`：中文索引流程图。
- `docs/b_test_commands.md`：B 模块测试命令。

## 3. 构建与加载逻辑

索引流程：

```text
data/liver.h5ad
   ↓
提取 X_pca 向量
   ↓
构建 HNSW / Flat / IVF 索引
   ↓
保存 .faiss 索引文件和 .json metadata
   ↓
启动 Web 服务
   ↓
搜索时加载或使用对应索引
```

如果已经存在：

```text
indexes/liver_hnsw.faiss
indexes/liver_hnsw.json
```

启动系统或选择 HNSW 搜索时，会优先加载这个已构建索引；如果索引不存在或 metadata 不匹配，才会重新构建。

切换索引类型时同理：

- HNSW 使用 `liver_hnsw.faiss`
- Flat 使用 `liver_flat.faiss`
- IVF 使用 `liver_ivf.faiss`

## 4. 真实数据验证

当前数据：

```text
data/liver.h5ad
```

数据规模：

```text
细胞数：69032
基因数：32397
PCA 维度：30
```

已验证：

- HNSW 索引可构建并保存。
- Flat 索引可构建并保存。
- `/api/status` 返回 `loaded: True`。
- `/api/search` 按 `cell_index=0` 查询成功。
- Top-K 返回数量正确。
- 查询自身时第一名相似度为 `1.0`。

## 5. 对比分工完成情况

| B 任务 | 状态 |
|---|---|
| 构建索引 | 已完成 |
| 使用 FAISS 检索 | 已完成 |
| 支持至少一种 ANN 算法 | 已完成，默认 HNSW |
| 支持 Flat 精确检索 | 已完成 |
| 支持 IVF 索引 | 已完成 |
| 支持索引保存和加载 | 已完成 |
| 支持动态重建索引 | 已完成 |
| 支持切换索引类型 | 已完成 |
| `scripts/build_index.py` 命令行构建 | 已完成 |
| `tests/test_ann_engine.py` 测试 | 已完成 |
| `docs/index_design.md` | 已完成 |
| `docs/figures/index_workflow.png` | 已完成 |

结论：按照 `分工.pdf`，成员 B 的代码和文档交付内容已经完成。

## 6. 常用测试命令

运行测试：

```bash
python -m pytest tests -q -p no:cacheprovider
```

构建 HNSW 索引：

```bash
python scripts\build_index.py --data data\liver.h5ad --index-type hnsw --save
```

启动服务：

```bash
python app.py
```

测试状态接口：

```bash
curl http://127.0.0.1:5000/api/status
```

动态重建索引：

```bash
curl -X POST http://127.0.0.1:5000/api/rebuild-index -H "Content-Type: application/json" -d "{\"index_type\":\"hnsw\"}"
```
