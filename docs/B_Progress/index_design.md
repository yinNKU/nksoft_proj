# ANN 索引设计说明

## 1. 支持的索引类型

当前索引层由 `src/ann_engine.py` 中的 `ANNEngine` 统一封装，底层使用 FAISS，支持三类索引：

- `flat`：精确检索，使用 `IndexFlatIP`，作为 recall 对比基线。
- `hnsw`：图结构近似最近邻索引，使用 `IndexHNSWFlat`，作为默认 ANN 方案。
- `ivf`：倒排文件索引，使用 `IndexIVFFlat`，作为可选 ANN 方案。

默认度量为 `cosine`。实现上先对向量做 L2 归一化，再用 FAISS 内积检索，因此内积分数可以近似看作余弦相似度。

## 2. 为什么选择 HNSW

HNSW 查询速度快，召回率通常较高，并且不需要像 IVF 那样强依赖聚类训练参数。对于中期展示和课程项目来说，HNSW 更适合作为默认索引：构建流程清晰、查询效果稳定、参数数量少。

Flat 保留为精确检索基线，方便后续性能评测时比较 HNSW/IVF 的结果重合率。IVF 适合更大规模数据，但需要调节 `nlist` 和 `nprobe`。

## 3. 三种索引区别

| 索引 | 特点 | 适用场景 |
|---|---|---|
| Flat | 暴力精确检索，结果最准确，速度随数据量线性下降 | 小数据集、评测基线 |
| HNSW | 基于近邻图搜索，速度快，召回率高 | 默认在线检索 |
| IVF | 先聚类再局部检索，可调速度和召回 | 大数据集、需要控制搜索范围 |

## 4. 索引构建流程

1. `data_loader.prepare_dataset()` 读取 `.h5ad`。
2. 优先读取 `adata.obsm["X_pca"]`，没有则计算 PCA。
3. 对 PCA 向量做 L2 归一化。
4. `ANNEngine.build_index()` 根据 `index_type` 创建 FAISS 索引。
5. 写入向量并记录构建耗时 `build_time_ms`。
6. 生成索引 metadata。

## 5. 保存和加载流程

保存时会生成两个文件：

- `.faiss`：FAISS 原生索引文件。
- `.json`：索引 metadata 文件。

metadata 字段包括：

- `index_type`
- `metric`
- `dimension`
- `num_vectors`
- `params`
- `build_time_ms`
- `dataset_id`

加载时会检查：

- 索引文件是否存在。
- metadata 文件是否存在。
- metadata 中的向量维度是否匹配当前向量。
- metadata 中的向量数量是否匹配当前数据集。
- 如果提供 `dataset_id`，还会检查数据集标识是否一致。

## 6. 动态重建索引

`SearchService.rebuild_index(index_type)` 用于动态重建索引。流程为：

1. 检查当前数据是否已经加载。
2. 使用当前数据向量重新构建指定类型索引。
3. 保存 `.faiss` 文件。
4. 保存 `.json` metadata 文件。
5. 返回索引类型、保存路径和构建耗时。

`SearchService.load_cached_index(index_type)` 会优先尝试加载已有缓存。如果缓存不存在或 metadata 不匹配，则回退到重新构建索引。

## 7. 命令行构建

可以使用：

```bash
python scripts/build_index.py --data data/liver.h5ad --index-type hnsw
```

常用参数：

- `--data`
- `--index-type`
- `--hnsw-m`
- `--hnsw-ef-search`
- `--ivf-nlist`
- `--ivf-nprobe`
- `--save` / `--no-save`

命令会输出索引类型、向量数量、向量维度、数据加载耗时、索引构建耗时、索引保存路径和 metadata 保存路径。
