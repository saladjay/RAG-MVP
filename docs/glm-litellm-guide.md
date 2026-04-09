# GLM + LiteLLM 使用指南

本文档说明如何通过 LiteLLM 使用智谱 AI (GLM) 模型。

> **注意**: LiteLLM 目前没有内置 GLM 支持，需要将其配置为 OpenAI 兼容端点。

## 配置方式

### 方式 1: 环境变量 (推荐)

在 `.env` 文件中添加：

```bash
# GLM API Key
GLM_API_KEY=your-glm-api-key-here

# LiteLLM 配置文件路径（可选）
LITELLM_CONFIG_PATH=litellm_config.yaml
```

### 方式 2: 配置文件

`litellm_config.yaml` 已包含 GLM 模型配置（使用 OpenAI 兼容格式）：

```yaml
model_list:
  - model_name: glm-4.5-air
    litellm_params:
      model: openai/glm-4.5-air
      api_base: https://open.bigmodel.cn/api/paas/v4
      api_key: ${GLM_API_KEY}
    metadata:
      provider: zhipu
      context_length: 128000
```

## 使用方法

### 方法 1: 直接调用 LiteLLM (OpenAI 兼容格式)

```python
from litellm import acompletion

# GLM 使用 OpenAI 兼容 API，需要指定 api_base
response = await acompletion(
    model="openai/glm-4.5-air",  # 使用 openai/ 前缀
    api_base="https://open.bigmodel.cn/api/paas/v4",  # GLM API 地址
    messages=[{"role": "user", "content": "你好"}],
    api_key=os.getenv("GLM_API_KEY"),
)
print(response.choices[0].message.content)
```

### 方法 2: 使用 RAG Service Gateway

```python
from rag_service.inference import get_gateway

gateway = await get_gateway()
result = await gateway.acomplete(
    prompt="你好",
    model_hint="glm-4.5-air",
)
print(result.text)
```

### 方法 3: 使用 GLM Gateway (直接 HTTP，推荐)

```python
from rag_service.inference import get_glm_gateway

gateway = await get_glm_gateway()
result = await gateway.acomplete(
    prompt="你好",
)
print(result.text)
```

## 支持的模型

| 模型标识 (LiteLLM) | 说明 | 上下文长度 |
|---------|------|-----------|
| `openai/glm-4.5` | 最新旗舰模型 | 128K |
| `openai/glm-4.5-air` | 高性价比模型（推荐） | 128K |
| `openai/glm-4-flash` | 轻量级快速模型 | 128K |

## API 参数

```python
response = await acompletion(
    model="openai/glm-4.5-air",
    api_base="https://open.bigmodel.cn/api/paas/v4",
    messages=[{"role": "user", "content": "问题"}],
    api_key=os.getenv("GLM_API_KEY"),
    max_tokens=4096,      # 最大输出 tokens
    temperature=0.7,      # 温度 (0-2)
    top_p=0.9,           # 核采样
    stream=False,        # 是否流式输出
)
```

## 测试

```bash
# 运行测试脚本
uv run python test_litellm_glm.py

# 或使用 GLM Gateway 测试（推荐）
uv run python test_glm_integration.py
```

## 参考

- [智谱 AI 开放平台](https://open.bigmodel.cn/)
- [GLM API 文档](https://open.bigmodel.cn/api/paas/v4/chat/completions)
