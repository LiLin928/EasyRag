# 工具参数自动拼接功能说明

## 功能更新

现在 HTTP 工具的参数会自动拼接到 URL 中，无需手动写占位符！

## 使用方式

### GET 请求（参数自动拼接到 URL）

**配置示例：**

| 字段 | 值 |
|------|-----|
| **名称** | OpenWeather 天气查询 |
| **类型** | HTTP |
| **方法** | GET |
| **URL** | `https://api.openweathermap.org/data/2.5/weather` |
| **参数** | q, appid, units |

**参数列表：**

| 参数名 | 类型 | 默认值 |
|--------|------|--------|
| q | string | Beijing |
| appid | string | your-api-key |
| units | string | metric |

**测试时传入：**
```json
{
  "q": "Shanghai",
  "appid": "your-api-key",
  "units": "metric"
}
```

**实际请求：**
```
GET https://api.openweathermap.org/data/2.5/weather?q=Shanghai&appid=your-api-key&units=metric
```

### POST 请求（参数作为 JSON 请求体）

**配置示例：**

| 字段 | 值 |
|------|-----|
| **名称** | 提交数据 |
| **类型** | HTTP |
| **方法** | POST |
| **URL** | `https://api.example.com/submit` |
| **请求头** | Content-Type: application/json |
| **参数** | name, value |

**测试时传入：**
```json
{
  "name": "test",
  "value": 123
}
```

**实际请求：**
```
POST https://api.example.com/submit
Content-Type: application/json

{
  "name": "test",
  "value": 123
}
```

## 对比说明

### ❌ 旧方式（手动占位符）

```
URL: https://api.example.com/weather?q={q}&appid={appid}
参数: q, appid
```

### ✅ 新方式（自动拼接）

```
URL: https://api.example.com/weather
参数: q, appid
```

参数会自动拼接到 URL 后面！

## 技术实现

- **GET/DELETE 请求**: 参数通过 `params` 参数传递，自动拼接到 URL
- **POST/PUT/PATCH 请求**: 参数通过 `json` 参数传递，作为请求体

## 代码修改

文件：`backend/app/core/tools/executor.py`

```python
# GET/DELETE: 参数作为查询参数
query_params = args if method in ("GET", "DELETE") else None

# POST/PUT/PATCH: 参数作为请求体
json_body = args if body_type == "json" and method in ("POST", "PUT", "PATCH") else None

resp = await client.request(
    method,
    url,
    headers=headers,
    params=query_params,  # 自动拼接到 URL
    json=json_body        # 作为请求体
)
```

## 验证测试

测试结果：
```
✅ URL: https://api.openweathermap.org/data/2.5/weather
✅ Params: q=Beijing, appid=xxx, units=metric
✅ Actual URL: https://api.openweathermap.org/data/2.5/weather?q=Beijing&appid=xxx&units=metric
✅ Status: 200
✅ Weather: scattered clouds, 29.94°C
```

---

**注意**：需要重启后端服务使更改生效。