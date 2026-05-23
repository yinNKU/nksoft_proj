# B 模块测试命令

本文档用于测试 B 负责的 ANN 索引构建、保存加载、索引切换和动态重建功能。

## 1. 环境准备

进入项目目录：

```bash
cd F:\大三上\soft_project\nksoft_proj
```

如果还没有安装依赖，先执行：

```bash
python -m pip install -r requirements.txt
```

如果使用项目内虚拟环境，则把后续命令里的 `python` 替换为：

```bash
.\.venv\Scripts\python.exe
```

例如：

```bash
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

说明：`.venv` 不需要上传 GitHub，别人 clone 后按 `requirements.txt` 安装依赖即可。

## 2. 自动化测试

运行全部测试：

```bash
python -m pytest tests -q -p no:cacheprovider
```

只运行 ANN 索引测试：

```bash
python -m pytest tests\test_ann_engine.py -q -p no:cacheprovider
```

正常结果示例：

```text
12 passed
```

## 3. 构建三种索引

构建 HNSW 索引：

```bash
python scripts\build_index.py --data data\liver.h5ad --index-type hnsw --save
```

构建 Flat 精确检索索引：

```bash
python scripts\build_index.py --data data\liver.h5ad --index-type flat --save
```

构建 IVF 索引：

```bash
python scripts\build_index.py --data data\liver.h5ad --index-type ivf --ivf-nlist 100 --ivf-nprobe 10 --save
```

查看生成文件：

```bash
dir indexes
```

应能看到类似文件：

```text
liver_hnsw.faiss
liver_hnsw.json
liver_flat.faiss
liver_flat.json
liver_ivf.faiss
liver_ivf.json
```

## 4. 启动服务

```bash
python app.py
```

看到下面内容表示启动成功：

```text
Running on http://127.0.0.1:5000
```


> 以下，都可以在网页进行测试，设置检索参数，刷新系统状态即可看到


启动窗口不要关闭，另开一个终端测试接口。

## 5. 测试状态接口

```bash
curl http://127.0.0.1:5000/api/status
```

正常返回应包含：

```text
"loaded": true
"n_cells": 69032
"n_dims": 30
"index_type": "hnsw"
```

## 6. 测试搜索和索引切换

HNSW 查询：

```bash
curl -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"id\",\"cell_index\":0,\"k\":5,\"index_type\":\"hnsw\"}"
```

Flat 查询：

```bash
curl -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"id\",\"cell_index\":0,\"k\":5,\"index_type\":\"flat\"}"
```

IVF 查询：

```bash
curl -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"id\",\"cell_index\":0,\"k\":5,\"index_type\":\"ivf\"}"
```

正常返回应包含：

```text
"index_type": "hnsw" / "flat" / "ivf"
"results": [...]
```

其中第一条结果通常是查询细胞自身，相似度接近 `1.0`。

## 7. 测试动态重建索引

```bash
curl -X POST http://127.0.0.1:5000/api/rebuild-index -H "Content-Type: application/json" -d "{\"index_type\":\"hnsw\"}"
```

正常返回应包含：

```text
"success": true
"index_type": "hnsw"
"index_path": ...
"metadata_path": ...
"build_time_ms": ...
```

也可以把 `hnsw` 换成 `flat` 或 `ivf`。

## 8. 推荐检查顺序

1. `python -m pytest tests -q -p no:cacheprovider`
2. `python scripts\build_index.py --data data\liver.h5ad --index-type hnsw --save`
3. `dir indexes`
4. `python app.py`
5. `curl http://127.0.0.1:5000/api/status`
6. 分别用 `hnsw`、`flat`、`ivf` 调用 `/api/search`
7. 调用 `/api/rebuild-index`

## 9. 常见问题


如果 `curl` 连接失败，说明 Flask 服务没有启动，需要先运行：

```bash
python app.py
```

如果 `/api/status` 返回 `loaded: false`，检查数据文件是否存在：

```bash
dir data
```
