# 成员 A 当前进度说明

记录时间：2026-05-24

## 1. 负责范围
根据任务分工，成员 A 负责 **检索后端与条件检索**，主要包括：

- 检索服务层（按 cell_index / cell_id / vector）。
- 条件过滤（metadata filters）。
- Flask 搜索接口与统一返回格式。
- 搜索相关测试用例。
- 检索接口文档。

## 2. 已完成内容
代码部分：

- `src/search_service.py`
  - `search_by_cell_index()`：按细胞下标检索，返回 Top-K，并支持 metadata 条件过滤。
  - `search_by_cell_id()`：按真实 cell_id 查询并复用下标检索逻辑；不存在时返回明确错误。
  - `search_by_vector()`：检查维度、L2 归一化，再检索并支持过滤。
  - `_apply_metadata_filters()`：支持按 metadata 字段过滤；字段不存在时返回错误；过滤后结果不足 Top-K 时给出 warning。
  - `_format_results()`：统一返回字段 `rank / cell_index / cell_id / score / metadata`。

- `app.py`
  - `/api/status`：统一返回 `success: true`。
  - `/api/search`：支持 `id / cell_id / vector` 三种模式；支持 `filters`，返回统一结构与 `query_time_ms`。
  - `/api/metadata`：返回可用元数据字段 `fields`。

- `tests/test_search_service.py`
  - 覆盖 cell_index / cell_id / vector 成功查询。
  - 覆盖 top_k 生效、cell_id 不存在、id 越界、向量维度错误。
  - 覆盖 filters 字段存在、字段不存在、过滤后结果不足。

- `tests/test_app.py`
  - 覆盖 `/api/status`、`/api/metadata`。
  - 覆盖三种搜索模式与错误返回格式。
  - 覆盖 filters 参数格式校验。

文档部分：

- `docs/api_search.md`
  - 完整 API 说明：/api/status、/api/search 三种模式、/api/metadata、filters 格式、错误信息与字段说明。

## 3. 检索与过滤逻辑
```
1) 取查询向量（cell_index / cell_id / vector）
2) 维度检查（vector 模式）
3) L2 normalize（vector 模式）
4) ANNEngine.search() 获取 Top-K
5) 依据 filters 对结果按 metadata 字段过滤
6) 过滤不足 Top-K 时返回 warning
```

## 4. 接口返回格式
统一成功返回：
```json
{
  "success": true,
  "mode": "cell_id",
  "top_k": 10,
  "filters": {"cell_type": "T cell"},
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

错误返回：
```json
{
  "success": false,
  "error": "cell_id not found"
}
```

## 5. 对比分工完成情况
| A 任务 | 状态 |
|---|---|
| search_by_cell_index | 已完成 |
| search_by_cell_id | 已完成 |
| search_by_vector | 已完成 |
| metadata filters | 已完成 |
| /api/status | 已完成 |
| /api/search | 已完成 |
| /api/metadata | 已完成 |
| tests/test_search_service.py | 已完成 |
| tests/test_app.py | 已完成 |
| docs/api_search.md | 已完成 |

## 6. 常用测试命令
运行 A 模块测试：
```bash
python -m pytest tests\test_search_service.py tests\test_app.py -q -p no:cacheprovider
```

运行全量测试：
```bash
python -m pytest tests -q -p no:cacheprovider
```
