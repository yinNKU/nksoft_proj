# API Curl 参考命令(关于数据库操作)



- 由于对json解析不同，部分接口需要提供两种方式：curl 和 powershell

1. 使用 `curl` + 单引号 JSON（适用于 CMD / Git Bash）

2. 使用 `Invoke-RestMethod`（PowerShell 原生方式）

## 查看服务状态
curl.exe http://127.0.0.1:5000/api/status

---

## 查看元数据字段
curl.exe http://127.0.0.1:5000/api/metadata

---

## 添加数据集 liver.h5ad
curl.exe -X POST http://127.0.0.1:5000/api/datasets -H "Content-Type: application/json" -d "{\"name\":\"liver\",\"path\":\"data/liver.h5ad\",\"description\":\"liver h5ad dataset\"}"


$body = @{
  name = "liver"
  path = "data/liver.h5ad"
  description = "test"
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/datasets" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"

---



## 查看数据集列表
curl.exe http://127.0.0.1:5000/api/datasets

---

## 切换当前 active 数据集为 liver
curl.exe -X POST http://127.0.0.1:5000/api/datasets/select -H "Content-Type: application/json" -d "{\"name\":\"liver\"}"


$body = @{
  name = "liver"
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/datasets/select" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"

---

## 删除数据集 liver
curl.exe -X DELETE http://127.0.0.1:5000/api/datasets/liver

---

## 重建索引
curl.exe -X POST http://127.0.0.1:5000/api/rebuild-index -H "Content-Type: application/json" -d "{\"index_type\":\"hnsw\"}"



$body = @{ index_type = "hnsw" } | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/rebuild-index" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"
---

## 按 cell_index 搜索
curl.exe -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"id\",\"cell_index\":0,\"top_k\":5}"



$body = @{
  mode = "id"
  cell_index = 0
  top_k = 5
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/search" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"

---

## 按 cell_id 搜索
curl.exe -X POST http://127.0.0.1:5000/api/search -H "Content-Type: application/json" -d "{\"mode\":\"cell_id\",\"cell_id\":\"GTCAAGTCACAAGACG-1_12\",\"top_k\":5}"


$body = @{
  mode = "cell_id"
  cell_id = "GTCAAGTCACAAGACG-1_12"
  top_k = 5
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/search" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"





---

## 注册用户
curl.exe -X POST http://127.0.0.1:5000/api/register -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"pwd123\",\"role\":\"user\"}"



$body = @{
  username = "alice"
  password = "pwd123"
  role = "user"
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/register" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"

---

## 用户登录
curl.exe -X POST http://127.0.0.1:5000/api/login -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"pwd123\"}"


$body = @{
  username = "alice"
  password = "pwd123"
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/login" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"

---

## 用户登出
curl.exe -X POST http://127.0.0.1:5000/api/logout

---

## 查看用户列表
curl.exe http://127.0.0.1:5000/api/users

---

## 删除用户
curl.exe -X DELETE http://127.0.0.1:5000/api/users/alice