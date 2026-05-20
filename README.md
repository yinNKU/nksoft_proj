# 单细胞 ANN 检索系统：项目基础框架

本项目是一个面向中期实验要求的**最小可维护开发框架**。当前版本不追求完整功能实现，而是先把项目目录、模块边界、接口形式、TODO 任务和代码管理结构搭好，后续可以在此基础上逐步补全。

## 1. 当前框架覆盖的中期要求

| 中期要求 | 当前对应模块 | 当前状态 |
|---|---|---|
| 单细胞数据读取 | `src/data_loader.py` | 已预留 `.h5ad` 读取入口 |
| 数据向量化表示 | `src/data_loader.py` | 已预留 PCA / 归一化流程 |
| ANN 索引构建 | `src/ann_engine.py` | 已封装 FAISS 索引接口 |
| 相似细胞检索 | `src/search_service.py` | 已封装按细胞编号查询接口 |
| 至少一种 ANN 算法/库 | `src/ann_engine.py` | 默认 FAISS HNSW |
| Top-K 搜索 + 细胞信息 | `app.py` / `src/search_service.py` | 已预留 JSON 返回结构 |

## 2. 项目结构

```text
single_cell_ann_search/
├── app.py                         # Flask 入口，定义 Web 页面和 API
├── config.py                      # 统一配置文件
├── requirements.txt               # Python 依赖
├── .gitignore                     # Git 忽略规则
├── README.md                      # 项目说明
├── TODO.md                        # 后续开发任务清单
├── data/
│   └── .gitkeep                   # 数据目录；不要把大数据直接提交到 Git
├── indexes/
│   └── .gitkeep                   # 索引文件保存目录
├── src/
│   ├── __init__.py
│   ├── data_loader.py             # .h5ad 读取与向量化
│   ├── ann_engine.py              # ANN 索引构建与检索
│   └── search_service.py          # 业务层：连接数据、索引、结果格式化
├── templates/
│   └── index.html                 # 前端页面
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── scripts/
│   └── build_index.py             # 命令行构建索引脚本
├── tests/
│   └── test_ann_engine.py         # 检索引擎基础测试
└── docs/
    ├── architecture.md            # 架构说明
    └── development_plan.md        # 后续开发计划
```

## 3. 环境安装

```bash
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 4. 数据放置

把单细胞数据文件放到：

```text
data/sample.h5ad
```

也可以通过环境变量指定路径：

```bash
# Windows PowerShell
$env:SC_DATA_PATH="data/your_file.h5ad"

# macOS / Linux
export SC_DATA_PATH="data/your_file.h5ad"
```

## 5. 启动项目

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

如果 `data/sample.h5ad` 暂时不存在，项目仍然可以启动，但 `/api/status` 会显示数据未加载；后续放入数据后再重启即可。

## 6. API 说明

### 6.1 查看状态

```bash
curl http://127.0.0.1:5000/api/status
```

### 6.2 按细胞编号检索

```bash
curl -X POST http://127.0.0.1:5000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"mode\":\"id\",\"cell_index\":0,\"k\":5,\"index_type\":\"hnsw\"}"
```

返回结构示例：

```json
{
  "results": [
    {
      "rank": 1,
      "index": 0,
      "cell_id": "cell_0",
      "similarity": 1.0,
      "metadata": {}
    }
  ],
  "index_type": "hnsw"
}
```

## 7. 推荐 Git 提交顺序

```bash
git init
git add README.md TODO.md .gitignore requirements.txt config.py app.py
git add src templates static scripts tests docs data/.gitkeep indexes/.gitkeep
git commit -m "chore: initialize single-cell ANN search project scaffold"
```

后续建议按功能分支开发：

```bash
git switch -c feature/data-loader
git switch -c feature/faiss-index
git switch -c feature/search-api
git switch -c feature/frontend
```
