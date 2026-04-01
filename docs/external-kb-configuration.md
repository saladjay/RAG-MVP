# 外部知识库配置指南

## 概述

外部知识库服务需要认证 token 才能访问。

## 环境变量配置

创建或编辑 `.env` 文件：

```bash
# 外部知识库配置
EXTERNAL_KB_BASE_URL=http://128.23.77.226:6719
EXTERNAL_KB_ENDPOINT=/cloudoa-ai/ai/file-knowledge/queryKnowledge
EXTERNAL_KB_TOKEN=123456fdsaga6
EXTERNAL_KB_TIMEOUT=30
EXTERNAL_KB_MAX_RETRIES=3
EXTERNAL_KB_ENABLED=true
```

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `EXTERNAL_KB_BASE_URL` | 外部知识库服务地址 | `http://128.23.77.226:6719` |
| `EXTERNAL_KB_ENDPOINT` | API 端点路径 | `/cloudoa-ai/ai/file-knowledge/queryKnowledge` |
| `EXTERNAL_KB_TOKEN` | 认证 Token | `123456fdsaga6` |
| `EXTERNAL_KB_TIMEOUT` | 请求超时时间（秒） | `30` |
| `EXTERNAL_KB_MAX_RETRIES` | 最大重试次数 | `3` |

## 使用方法

### 1. 使用环境变量

```bash
# 设置环境变量
export EXTERNAL_KB_TOKEN=123456fdsaga6

# 运行测试
python -m e2e_test.cli external-kb \
    questions/fianl_version_qa.jsonl \
    --base-url http://128.23.77.226:6719 \
    --xtoken 123456fdsaga6
```

### 2. 使用命令行参数

```bash
python -m e2e_test.cli external-kb \
    questions/fianl_version_qa.jsonl \
    --base-url http://128.23.77.226:6719 \
    --xtoken 123456fdsaga6 \
    --output results.json \
    --limit 10
```

### 3. 使用独立测试脚本

编辑 `run_external_kb_test.py` 中的配置：

```python
xtoken = "123456fdsaga6"  # 修改为你的 token
```

然后运行：

```bash
python run_external_kb_test.py
```

## 请求头

每个请求会自动包含以下请求头：

```http
POST /cloudoa-ai/ai/file-knowledge/queryKnowledge HTTP/1.1
Host: 128.23.77.226:6719
Content-Type: application/json
xtoken: 123456fdsaga6
```

## 安全建议

1. **不要在代码中硬编码 token**
2. **使用环境变量或配置文件**
3. **将 `.env` 文件添加到 `.gitignore`**
4. **定期更换 token**

## 故障排除

### 401/403 错误

- 检查 `EXTERNAL_KB_TOKEN` 是否正确
- 确认 token 是否有效

### 404 错误

- 确认 `EXTERNAL_KB_BASE_URL` 正确
- 确认 `EXTERNAL_KB_ENDPOINT` 正确
