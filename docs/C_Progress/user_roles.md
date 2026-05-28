# 用户权限说明

本文说明系统中的用户角色、权限控制方式以及登录注册流程。

---

# 用户角色

系统当前包含两种角色：

- `user`
- `admin`

其中：

```text
user  -> 普通用户
admin -> 管理员
```

---

# 普通用户权限

普通用户拥有基础查询权限，包括：

- 查看数据集信息
- 进行 ANN 检索与查询
- 查看检索结果

普通用户不能：

- 管理数据集
- 删除用户
- 重建索引
- 修改系统配置

即：

```text
普通用户仅拥有查询权限
```

---

# 管理员权限

管理员拥有系统管理权限，包括：

- 新增数据集
- 删除数据集
- 切换 active 数据集
- 查看用户列表
- 删除用户
- 重建向量索引

即：

```text
管理员拥有系统管理权限
```

---

# 登录注册流程

## 用户注册

用户通过接口：

```http
POST /api/register
```

创建账号。

请求示例：

```json
{
  "username": "alice",
  "password": "123456"
}
```

---

## 用户登录

用户通过接口：

```http
POST /api/login
```

使用用户名和密码进行校验。

请求示例：

```json
{
  "username": "alice",
  "password": "123456"
}
```

---

# 密码存储方式

系统不会明文保存密码。

数据库中保存的是：

```text
password_hash
```

即：

```text
哈希后的密码
```

密码处理流程：

```text
用户输入密码
    ↓
generate_password_hash()
    ↓
数据库保存哈希值
```

登录时：

```text
输入密码
    ↓
check_password_hash()
    ↓
校验是否匹配
```

---

# 权限控制方式

系统根据：

```text
users.role
```

字段判断用户权限。

逻辑如下：

```text
role == "admin"
    ↓
拥有管理员权限
```

否则：

```text
普通用户权限
```

---

# 默认管理员账号

数据库初始化时：

```bash
python database/init_db.py
```

会自动创建默认管理员账号。

默认账号：

```text
username: admin
password: admin
```

---

# 安全建议

首次登录后建议：

- 修改默认管理员密码
- 不要在生产环境使用默认密码
- 不要共享管理员账号

---

# 相关接口

| 接口 | 方法 | 功能 |
|---|---|---|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |
| `/api/logout` | POST | 用户退出 |
| `/api/users` | GET | 获取用户列表 |
| `/api/users/<username>` | DELETE | 删除用户 |

---

# 相关数据库表

系统用户信息保存在：

```text
users
```

表中。

关键字段包括：

| 字段 | 含义 |
|---|---|
| username | 用户名 |
| password_hash | 哈希密码 |
| role | 用户角色 |
| created_at | 创建时间 |