# 数据集管理说明

本文说明数据集的添加、删除、切换以及数据库中的管理方式。

---

# 数据集添加

## 接口方式

可以通过接口：

```http
POST /api/datasets
```

传入 JSON：

```json
{
  "name": "pbmc",
  "path": "data/pbmc.h5ad",
  "description": "PBMC dataset"
}
```

---

## 代码方式

也可以直接调用：

```python
DatasetManager.add_dataset(name, path, description)
```

---

# 数据集删除

## 接口方式

可以通过接口：

```http
DELETE /api/datasets/<dataset_name>
```

例如：

```http
DELETE /api/datasets/pbmc
```

---

## 代码方式

也可以直接调用：

```python
DatasetManager.delete_dataset(name)
```

---

# 切换当前数据集

## 接口方式

通过接口：

```http
POST /api/datasets/select
```

传入 JSON：

```json
{
  "name": "pbmc"
}
```

---

## 切换逻辑

切换数据集时：

- 会将所有数据集的 `is_active` 设置为 `0`
- 再将目标数据集设置为 `1`

即：

```text
当前仅允许一个 active 数据集
```

---

# 索引处理逻辑

## 切换数据集时

当前实现：

- 仅更新活动状态
- 保留已有索引记录
- 不会自动删除索引文件

---

## 删除数据集时

删除数据集会同步删除：

```text
index_records
```

中的对应记录。

即：

```text
删除 dataset
    ↓
删除关联 index_records
```

---

# 数据库中的数据集记录

每个数据集都会在：

```text
datasets
```

表中保存一条记录。

保存的信息包括：

- 数据集名称
- 数据集路径
- 描述信息
- 是否 active
- 创建时间

用于统一管理系统中的所有 h5ad 数据集。

---

# 异常情况说明

## 数据集路径不存在

如果：

```text
path 不存在
```

会抛出异常：

```text
dataset path does not exist
```

---

## 非 h5ad 文件

如果文件后缀不是：

```text
.h5ad
```

会抛出异常：

```text
dataset must be a .h5ad file
```

---

## 数据集名称重复

由于：

```text
datasets.name
```

具有：

```text
UNIQUE
```

约束。

重复名称会触发唯一约束错误。

---

# 相关接口

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/datasets` | GET | 获取数据集列表 |
| `/api/datasets` | POST | 添加数据集 |
| `/api/datasets/<name>` | DELETE | 删除数据集 |
| `/api/datasets/select` | POST | 切换 active 数据集 |

---

# 相关数据库表

- `datasets`
- `index_records`

其中：

```text
datasets 1 —— N index_records
```