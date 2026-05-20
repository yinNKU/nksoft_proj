# 架构说明

## 1. 分层设计

```text
浏览器页面
   ↓
Flask API：app.py
   ↓
业务服务层：src/search_service.py
   ↓
ANN 引擎：src/ann_engine.py
   ↓
数据加载与向量化：src/data_loader.py
   ↓
.h5ad 单细胞数据
```

## 2. 各模块职责

### app.py

负责 Web 路由和 API：

- `/`
- `/api/status`
- `/api/search`

不直接处理 PCA、FAISS、AnnData 细节。

### src/data_loader.py

负责数据相关逻辑：

- 读取 `.h5ad`
- 提取 `X_pca`
- 必要时计算 PCA
- L2 归一化
- 提取 `adata.obs` 元信息

### src/ann_engine.py

负责 ANN 索引：

- 构建索引
- 执行 Top-K 检索
- 保存 / 加载索引

### src/search_service.py

负责业务流程整合：

- 初始化数据和索引
- 根据请求切换索引类型
- 按细胞编号 / ID / 向量检索
- 格式化返回结果

## 3. 后续扩展方向

- 支持多个数据集。
- 支持缓存多个索引。
- 支持批量查询。
- 支持检索结果可视化。
- 支持 recall、latency 等评测指标。
