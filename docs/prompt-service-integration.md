# Prompt Service 集成完成

## 概述

已将 RAG Service 中所有零散的 prompt 纳入 **Prompt Service** 集中管理，支持：
- ✅ 版本控制
- ✅ A/B 测试
- ✅ 在线编辑（无需重新部署）
- ✅ Trace 分析
- ✅ 降级回退（Prompt Service 不可用时使用本地 fallback）

## 文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `config/rag_prompts.yaml` | Prompt 模板配置文件（6 个模板） |
| `src/rag_service/services/prompt_client.py` | Prompt 客户端 wrapper |
| `src/rag_service/services/__init__.py` | 服务模块导出 |

### 更新文件

| 文件 | 变更 |
|------|------|
| `src/rag_service/capabilities/query_rewrite.py` | 使用 Prompt Client |
| `src/rag_service/capabilities/hallucination_detection.py` | 使用 Prompt Client |
| `src/rag_service/capabilities/qa_pipeline.py` | 使用 Prompt Client |
| `src/rag_service/core/agent.py` | 使用 Prompt Client |

## Prompt 模板列表

| Template ID | 名称 | 用途 |
|-------------|------|------|
| `qa_query_rewrite` | QA Query Rewrite | 查询重写 |
| `qa_answer_generation` | QA Answer Generation | 标准答案生成 |
| `qa_answer_generation_strict` | QA Answer Generation (Strict) | 严格答案生成（防幻觉） |
| `qa_hallucination_detection` | QA Hallucination Detection | 幻觉检测 |
| `rag_agent_instructions` | RAG Agent Instructions | RAG Agent 系统指令 |
| `qa_fallback_response` | QA Fallback Response | 知识库不可用时默认回复 |

## 使用方式

### 基本用法

```python
from rag_service.services.prompt_client import (
    get_prompt_client,
    TEMPLATE_QUERY_REWRITE,
)

# 获取 Prompt Client
prompt_client = await get_prompt_client()

# 获取并渲染 prompt
prompt = await prompt_client.get_prompt(
    template_id=TEMPLATE_QUERY_REWRITE,
    variables={
        "original_query": "春节放假",
        "current_year": "2026",
        "current_month": "4",
    },
    trace_id="my-trace-id",
)
```

### 在 Capability 中使用

```python
class MyCapability(Capability):
    async def _get_prompt_client(self):
        if self._prompt_client is None:
            self._prompt_client = await get_prompt_client()
        return self._prompt_client

    async def execute(self, input_data):
        prompt_client = await self._get_prompt_client()
        prompt = await prompt_client.get_prompt(
            template_id="my_template",
            variables={"var": "value"},
            trace_id=input_data.trace_id,
        )
        # 使用 prompt...
```

## 配置管理

### Prompt 模板配置文件

`config/rag_prompts.yaml` 包含所有 prompt 模板定义：

```yaml
templates:
  - template_id: qa_query_rewrite
    name: QA Query Rewrite
    description: 查询重写 prompt
    version: 1
    sections:
      - name: role
        content: 你是一个专业的查询优化助手...
      - name: input
        content: 原始查询: {{original_query}}...
    variables:
      original_query:
        description: 原始用户查询
        type: string
        is_required: true
```

### 环境变量

```bash
# Prompt Service 配置（可选）
PROMPT_SERVICE_ENABLED=true
PROMPT_SERVICE_URL=http://localhost:8001
PROMPT_SERVICE_TIMEOUT=5.0
```

## 版本控制

### 创建新版本

1. 修改 `config/rag_prompts.yaml` 中的 `version` 字段
2. 更新相应 section 的 `content`
3. 添加 `change_description`

### 回滚版本

在 Prompt Service 中：

```python
from prompt_service.services.version_control import get_version_control_service

vc_service = get_version_control_service()
vc_service.rollback("qa_query_rewrite", target_version=1)
```

## A/B 测试

### 配置 A/B 测试

`config/rag_prompts.yaml` 中已预配置示例：

```yaml
ab_tests:
  - test_id: qa_generation_ab_test
    template_id: qa_answer_generation
    variants:
      - variant_id: control
        template_id: qa_answer_generation
        weight: 50
      - variant_id: treatment
        template_id: qa_answer_generation_strict
        weight: 50
```

### 获取分配的变体

```python
result = await prompt_client.get_prompt(
    template_id="qa_answer_generation",
    variant_id=None,  # 自动分配
    trace_id=trace_id,
)
# result.variant_id 将包含分配的变体 ID
```

## 监控和 Trace

### Trace ID 传播

所有 prompt 请求都支持 `trace_id` 参数，用于关联整个请求链路。

### 日志示例

```
2026-04-03 15:30:00 | abc123 | INFO | Prompt retrieved from service
extra={
    "template_id": "qa_query_rewrite",
    "version": 1,
    "variant_id": "control",
    "from_cache": false
}
```

## 降级回退

Prompt Client 内置降级机制：

1. **优先使用 Prompt Service** - 集中管理、版本控制
2. **Prompt Service 不可用时** - 自动使用本地 fallback prompt
3. **Fallback prompts** - 硬编码在 `prompt_client.py` 中

### 健康检查

```python
health = await prompt_client.check_health()
# {
#     "enabled": true,
#     "service_available": true,
#     "fallback_mode": false
# }
```

## 迁移状态

| Prompt | 原位置 | 现位置 | 状态 |
|--------|--------|--------|------|
| Query Rewrite | `query_rewrite.py:234` | `TEMPLATE_QUERY_REWRITE` | ✅ 已迁移 |
| Answer Generation | `qa_pipeline.py:567` | `TEMPLATE_ANSWER_GENERATION` | ✅ 已迁移 |
| Strict Generation | `qa_pipeline.py:591` | `TEMPLATE_ANSWER_GENERATION_STRICT` | ✅ 已迁移 |
| Hallucination Detection | `hallucination_detection.py:303` | `TEMPLATE_HALLUCINATION_DETECTION` | ✅ 已迁移 |
| RAG Agent Instructions | `agent.py:223` | `TEMPLATE_RAG_AGENT_INSTRUCTIONS` | ✅ 已迁移 |
| Fallback Response | N/A | `TEMPLATE_FALLBACK_RESPONSE` | ✅ 新增 |

## 下一步

1. **部署 Prompt Service** - 如果尚未部署
2. **配置 Langfuse** - 用于持久化存储
3. **初始化 Prompt** - 将 `config/rag_prompts.yaml` 导入 Prompt Service
4. **测试集成** - 运行测试验证功能
5. **启用 A/B 测试** - 配置并启动 A/B 测试

## 相关文档

- Prompt Service API: `src/prompt_service/api/routes.py`
- Prompt SDK: `src/prompt_service/client/sdk.py`
- A/B Testing: `src/prompt_service/services/ab_testing.py`
- Version Control: `src/prompt_service/services/version_control.py`
