# 检索 API 说明

## 1. GET /api/status
用于查询服务状态、数据集信息与索引类型。

**请求：**
```bash
curl http://127.0.0.1:5000/api/status
```

**响应示例：**
```json
{
  "success": true,
  "loaded": true,
  "data_path": "data/sample.h5ad",
  "n_cells": 69032,
  "n_dims": 30,
  "index_type": "hnsw",
  "build_time_ms": 128.5,
  "dataset": {
    "n_cells": 69032,
    "n_genes": 32397,
    "n_pcs": 30,
    "metadata_columns": ["cell_type", "donor", "disease"]
  },
  "last_error": null
}
```

## 2. POST /api/search
支持三种检索模式：按细胞下标（`id`）、按 cell_id（`cell_id`）、按向量（`vector`）。

### 2.1 按细胞下标查询
**请求：**
```bash
curl -X POST http://127.0.0.1:5000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"id\",\"cell_index\":0,\"top_k\":5}"
```

### 2.2 按 cell_id 查询
**请求：**
```bash
curl -X POST http://127.0.0.1:5000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"cell_id\",\"cell_id\":\"AAACCTGAG\",\"top_k\":5}"
```

### 2.3 按自定义向量查询
**请求：**
```bash
curl -X POST http://127.0.0.1:5000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"vector\",\"vector\":[0.1,0.2,0.3],\"top_k\":5}"
```

### 2.4 通用响应格式
```json
{
  "success": true,
  "mode": "cell_id",
  "top_k": 10,
  "filters": {
    "cell_type": "T cell"
  },
  "query_time_ms": 3.42,
  "results": [
    {
      "rank": 1,
      "cell_index": 123,
      "cell_id": "AAACCTGAG",
      "score": 0.982,
      "metadata": {
        "cell_type": "T cell",
        "donor": "donor_1"
      }
    }
  ],
  "warning": "Filtered results are fewer than top_k; returning available matches."
}
```

> `warning` 仅在条件过滤导致结果不足 Top-K 时出现。

## 3. GET /api/metadata
返回可用于过滤的元数据字段。

**请求：**
```bash
curl http://127.0.0.1:5000/api/metadata
```

**响应示例：**
```json
{
  "success": true,
  "fields": ["cell_type", "donor", "disease"]
}
```

## 4. filters 条件检索格式
`filters` 是一个字典，键为元数据字段名，值为筛选条件：

```json
{
  "mode": "id",
  "cell_index": 0,
  "top_k": 5,
  "filters": {
    "cell_type": "T cell",
    "donor": "donor_1"
  }
}
```

如果 `filters` 为空或缺省，则返回原始 Top-K 结果。

## 5. 错误信息说明
当请求无效或检索失败时，返回统一错误格式：

```json
{
  "success": false,
  "error": "cell_id not found"
}
```

常见错误：
- `cell_id not found`
- `cell_index out of range: {cell_index}`
- `vector dimension mismatch: expected X, got Y`
- `metadata field not found: {field}`

## 6. 返回结果字段说明
| 字段 | 含义 |
|---|---|
| rank | 结果排名（从 1 开始） |
| cell_index | 细胞下标（数据矩阵行号） |
| cell_id | 真实细胞 ID |
| score | 相似度得分（余弦相似度） |
| metadata | 该细胞的元信息字典 |
