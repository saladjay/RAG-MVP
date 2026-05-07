# Dev Log: 008-RAG-Architecture-Refactor

**Date**: 2026-05-07
**Branch**: `008-query-quality-enhancement` (008 spec 在此分支下工作)
**Scope**: RAG Service 架构重构实施 + Agent 架构评估

---

## 一、实施完成：50 Tasks, 7 Phases

### 变更摘要

| 维度 | 变更前 | 变更后 |
|------|--------|--------|
| Config 类 | 16 个 | 5 个 (Milvus / LiteLLM / Langfuse / Server / Query) |
| Capability | 13+ 个 | 3 个 (Query / Management / Trace) |
| Gateway | 3 个并行入口 | 1 个 LiteLLMGateway + 内部 provider 路由 |
| API 端点 | 15+ 个分散 | 6 个统一 (/api/v1/*) + 旧端点带 Deprecation 头 |
| Config 行数 | 941 行 | 718 行 (含 ~175 行向后兼容别名) |
| E2E Client | 指向旧端点 | 指向统一端点 |
| 新依赖 | — | 零 (全部用 stdlib typing.Protocol) |

### Phase 1: Setup (T001-T005)

创建策略协议和统一 Schema:

- `src/rag_service/strategies/__init__.py` — 导出 RetrievalStrategy, QualityStrategy
- `src/rag_service/strategies/retrieval.py` — RetrievalStrategy Protocol + MilvusRetrieval + ExternalKBRetrieval
- `src/rag_service/strategies/quality.py` — QualityStrategy Protocol + BasicQuality + DimensionGatherQuality + ConversationalQuality
- `src/rag_service/api/unified_schemas.py` — UnifiedQueryRequest, QueryResponse, DocumentRequest

### Phase 2: Foundational (T006-T016)

Config 合并 + 策略实现:

- `src/rag_service/config.py` — 16 类 → 5 类 (MilvusConfig, LiteLLMConfig, LangfuseConfig, ServerConfig, QueryConfig)
  - `LiteLLMConfig.load_legacy_providers()` — 从 CLOUD_COMPLETION_*/GLM_* 旧环境变量加载
  - `QueryConfig.load_legacy_config()` — 从 QA_*/QUERY_QUALITY_*/CONVERSATIONAL_QUERY_*/EXTERNAL_KB_* 加载
  - `Settings` 类添加 ~12 个 `@property` 别名保持向后兼容
  - 模块级 stub class aliases 让旧 import 不报错
- 5 个策略实现: MilvusRetrieval, ExternalKBRetrieval, BasicQuality, DimensionGatherQuality, ConversationalQuality

### Phase 3: Gateway 合并 (T017-T023)

LiteLLMGateway 成为唯一入口:

- `src/rag_service/inference/gateway.py`
  - `LiteLLMGateway` 新增 `provider` 参数
  - 内部持有 `_http_gateway`, `_glm_gateway`, `_embedding_gateway`
  - `complete_routed()` / `acomplete_routed()` 根据 `config.litellm.provider` 路由
  - `embed()` 委托给内部 HTTPEmbeddingGateway
  - `get_gateway()` 成为唯一工厂函数
  - `get_http_gateway()` / `get_glm_gateway()` 改为委托到统一网关

### Phase 4: Capability 合并 (T024-T031)

3 个统一 Capability 替代 13+ 个:

- `src/rag_service/capabilities/query_capability.py`
  - Pipeline: quality.pre_process → rewrite → retrieve → generate → hallucination → quality.post_process
  - 从 QueryConfig 读取 retrieval_backend 和 quality_mode 创建策略
  - `stream_execute()` 支持流式输出
- `src/rag_service/capabilities/management_capability.py`
  - 文档上传/删除/更新 + 模型列表
- `src/rag_service/capabilities/trace_capability.py`
  - 健康检查 + Trace 观察
- `src/rag_service/main.py`
  - 注册 3 个统一 Capability + 保留旧 Capability 做过渡

### Phase 5: API 统一 (T032-T042)

6 个统一端点 + 旧端点 Deprecation:

- `src/rag_service/api/unified_routes.py`
  - POST /api/v1/query — 统一查询
  - POST /api/v1/query/stream — 流式查询
  - POST /api/v1/documents — 文档管理
  - GET /api/v1/health — 健康检查
  - GET /api/v1/traces/{id} — Trace 查看
  - GET /api/v1/models — 模型列表
- `src/rag_service/api/routes.py` — 添加 `Depends(_deprecation_header)` 中间件
- `src/rag_service/api/qa_routes.py` — 同上
- `src/rag_service/api/kb_upload_routes.py` — 同上
- `src/rag_service/main.py` — `app.include_router(unified_router, prefix="/api/v1")` 先于旧路由注册
- `src/e2e_test/clients/rag_client.py` — 改用 /api/v1/query

### Phase 6: Config 完善 (T043-T046)

- `src/rag_service/config.py` — 为旧环境变量添加 `warnings.warn(DeprecationWarning)`
- `.env.example` — 重写为 5 个统一 Section + 废弃变量映射表
- 最小配置验证: 仅 MILVUS_HOST + LITELLM_PROVIDER + LITELLM_MODEL + SERVER_PORT 即可启动

### Phase 7: 文档和验证 (T047-T050)

- `docs/architecture.md` — 更新为 3-Capability 架构图、策略模式图、5-Section 配置图
- 验证三层 Observability 栈未受影响
- 验证统一端点和旧端点共存正常

### 遇到的问题及修复

1. **`Concent_elements` 拼写错误** — models/__init__.py 和 conversational_query.py 中预存的 typo，修复为 ContentElements
2. **`QueryQualityConfig` ImportError** — 旧代码 import 已不存在的类，通过在 config.py 底部添加 stub class aliases 解决
3. **`APIRouter.middleware` 不存在** — FastAPI 的 APIRouter 没有 middleware 方法，改用 `dependencies=[Depends(...)]` 方式添加 Deprecation 头
4. **路由冲突** — 统一路由和旧路由都在 /api/v1/query 注册，通过统一路由先注册（FastAPI first-match）解决，旧路由自动退化为 deprecated

---

## 二、架构评估讨论

### 评估公式

```
Agent = Capability(原子) + Context(状态) + Tools(动态注入) + Policy(控制策略)
```

### 当前差距分析

| 维度 | 目标 | 当前 | 差距 |
|------|------|------|------|
| Capability | 8+ 原子能力 | 3 个粗粒度上帝对象 | 粗了 2 级 |
| 组合方式 | 运行时动态 | 编译时硬编码管道 | 无灵活性 |
| Prompt | 动态注入 | _generate_answer() 内硬编码 | 不可配置 |
| Tools | 动态注入 | 各方法硬编码 import | 不可扩展 |
| Policy | 迭代次数/深度 | 仅 enable/disable 布尔开关 | 无控制力 |
| Context | 一等公民 | dict 传递 | 无类型安全 |

### 组件调研结论

| 组件 | 角色 | 推荐度 | 理由 |
|------|------|--------|------|
| LiteLLM | Model Gateway | 保持 | 生产就绪 v1.82+，已集成 |
| Langfuse | Prompt & Trace | 保持 | 生产就绪，已集成 |
| Phidata/Agno | Agent Runtime | 谨慎评估 | 更名中，不如现有 Capability Registry 实用 |
| CrewAI | Reasoning Engine | 不引入 | pre-release，对 RAG 服务 overkill |
| RAGFlow | Retrieval | 按需考虑 | 全栈服务，非可嵌入库 |
| LangGraph | Agent Runtime | 不引入（现阶段） | 引入 LangChain 依赖链过重 |
| Pydantic AI | Agent Runtime | 不引入（现阶段） | 先用 stdlib Protocol 自建 |

### 共识决策

- **现阶段不引入** LangGraph、LangChain、Pydantic AI 等外部 Agent 框架
- **下一步方向**: 将 QueryCapability 拆解为原子能力 + 轻量编排器，用 `typing.Protocol` + Pydantic model 实现，零新依赖
- LiteLLM + Langfuse 继续保持和扩展

---

## 三、文件变更清单

### 新建文件

| 文件 | 用途 |
|------|------|
| `src/rag_service/strategies/__init__.py` | 策略协议导出 |
| `src/rag_service/strategies/retrieval.py` | RetrievalStrategy Protocol + 实现 |
| `src/rag_service/strategies/quality.py` | QualityStrategy Protocol + 实现 |
| `src/rag_service/api/unified_schemas.py` | 统一 API Schema |
| `src/rag_service/api/unified_routes.py` | 6 个统一端点 |
| `src/rag_service/capabilities/query_capability.py` | 统一查询能力 |
| `src/rag_service/capabilities/management_capability.py` | 统一管理能力 |
| `src/rag_service/capabilities/trace_capability.py` | 统一追踪能力 |
| `src/rag_service/models/query_quality.py` | 维度分析数据模型 |
| `src/rag_service/models/conversational_query.py` | 对话查询数据模型 |
| `src/rag_service/models/__init__.py` | 模型导出 |
| `src/rag_service/services/session_store.py` | Redis 会话存储 |
| `src/rag_service/services/belief_state_store.py` | 信念状态存储 |
| `src/rag_service/services/colloquial_mapper.py` | 口语词汇映射 |
| `specs/008-rag-architecture-refactor/` | 设计文档全套 |

### 重写文件

| 文件 | 变更 |
|------|------|
| `src/rag_service/config.py` | 16 类 → 5 类 + 向后兼容 |
| `docs/architecture.md` | 更新为 3-Capability 架构 |
| `.env.example` | 重写为 5 Section 统一格式 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/rag_service/main.py` | 注册统一能力 + 统一路由 |
| `src/rag_service/inference/gateway.py` | 统一网关 + provider 路由 |
| `src/rag_service/api/routes.py` | Deprecation header |
| `src/rag_service/api/qa_routes.py` | Deprecation header |
| `src/rag_service/api/kb_upload_routes.py` | Deprecation header |
| `src/rag_service/services/__init__.py` | 新服务导出 |
| `src/rag_service/core/exceptions.py` | 新异常类型 |
| `src/e2e_test/clients/rag_client.py` | 改用统一端点 |
| `src/rag_service/models/__init__.py` | 修复 typo + 新模型导出 |
| `pyproject.toml` | 依赖更新 |
