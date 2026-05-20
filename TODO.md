# TODO：后续开发任务清单

本文档用于代码管理和后续开发分工。当前项目已经搭好最小框架，后续开发按模块推进即可。

## 1. 数据读取与预处理

位置：`src/data_loader.py`

### 需要实现 / 完善

- [ ] 确认 `.h5ad` 文件字段结构：
  - `adata.X`
  - `adata.obs`
  - `adata.var`
  - `adata.obsm`
- [ ] 判断数据中是否已有 `X_pca`：
  - 如果已有，直接读取；
  - 如果没有，执行标准预处理流程。
- [ ] 完善标准预处理流程：
  - normalize_total
  - log1p
  - highly_variable_genes
  - scale
  - PCA
- [ ] 支持稀疏矩阵输入，避免大数据集转 dense 导致内存爆炸。
- [ ] 记录预处理参数：
  - `n_pcs`
  - `n_top_genes`
  - 是否归一化
  - 是否使用已有 `X_pca`
- [ ] 保存预处理后的向量，避免每次启动都重新计算。

## 2. ANN 索引模块

位置：`src/ann_engine.py`

### 需要实现 / 完善

- [ ] 默认完成 HNSW 索引构建。
- [ ] 增加 Flat 精确检索，作为 recall 对比基准。
- [ ] 增加 IVF 索引：
  - `nlist`
  - `nprobe`
  - train / add 流程
- [ ] 增加索引持久化：
  - `save_index()`
  - `load_index()`
- [ ] 增加索引参数配置：
  - HNSW 的 `M`
  - HNSW 的 `efSearch`
  - IVF 的 `nlist` 和 `nprobe`
- [ ] 增加异常处理：
  - 未构建索引时搜索
  - 查询向量维度不匹配
  - k 超过数据量
- [ ] 后续可选：增加 GPU FAISS 支持。

## 3. 检索服务层

位置：`src/search_service.py`

### 需要实现 / 完善

- [ ] 按细胞编号查询：
  - 输入 `cell_index`
  - 返回 Top-K 相似细胞
- [ ] 按细胞 ID 查询：
  - 输入 `cell_id`
  - 根据 `adata.obs_names` 定位细胞
- [ ] 按自定义向量查询：
  - 输入逗号分隔向量
  - 校验维度
  - 做 L2 归一化
- [ ] 返回细胞元信息：
  - `cell_type`
  - `batch`
  - `sample`
  - `disease`
  - 具体字段按真实数据集决定
- [ ] 增加查询耗时统计。
- [ ] 增加错误信息格式统一。

## 4. Flask 后端 API

位置：`app.py`

### 需要实现 / 完善

- [ ] `/api/status`
  - 返回数据是否加载
  - 细胞数量
  - 向量维度
  - 当前索引类型
- [ ] `/api/search`
  - 支持按编号检索
  - 支持按 ID 检索
  - 支持按自定义向量检索
- [ ] `/api/rebuild-index`
  - 前端切换索引类型时重建索引
- [ ] `/api/metadata`
  - 返回可用元信息字段
- [ ] 增加参数校验：
  - `k`
  - `cell_index`
  - `index_type`
  - `mode`

## 5. 前端页面

位置：

- `templates/index.html`
- `static/css/style.css`
- `static/js/main.js`

### 需要实现 / 完善

- [ ] 显示系统状态。
- [ ] 输入细胞编号进行检索。
- [ ] 设置 Top-K。
- [ ] 选择索引类型：
  - HNSW
  - IVF
  - Flat
- [ ] 展示结果表格：
  - 排名
  - 细胞 ID
  - 相似度
  - 元信息
- [ ] 显示查询耗时。
- [ ] 增加错误提示。
- [ ] 后续可选：增加结果可视化，例如 UMAP 坐标展示。

## 6. 测试与验证

位置：`tests/`

### 需要实现 / 完善

- [ ] 测试随机向量能成功建索引。
- [ ] 测试用自身向量查询时，自身排在第一位。
- [ ] 测试 `k` 值边界。
- [ ] 测试错误输入：
  - 负数 cell_index
  - 超范围 cell_index
  - 空向量
  - 维度不匹配
- [ ] 测试 API 返回 JSON 格式。

## 7. 报告与展示材料

位置：`docs/`

### 需要补充

- [ ] 系统架构图。
- [ ] 数据处理流程说明。
- [ ] ANN 算法选择理由。
- [ ] 检索 API 说明。
- [ ] 页面截图。
- [ ] 查询结果截图。
- [ ] Git 提交记录截图。
