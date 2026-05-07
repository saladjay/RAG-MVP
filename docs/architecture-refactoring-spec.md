# RAG Service 架构重构需求说明书

> 文档编号: RAG-ARCH-001
> 日期: 2026-05-07
> 状态: Draft
> 关联文档: `docs/compliance-check-report.md`, `docs/architecture.md`

---

## 1. 背景与动机

### 1.1 现状

RAG Service (Feature 001) 原始设计为一个 MVP 服务，包含 4 个 API 端点、7 个 Capability、1 套推理网关。经过 Feature 005/006/007 的迭代，当前代码已严重偏离原始架构：

| 指标 | MVP 设计 (001 Spec) | 当前代码 | 增幅 |
|------|---------------------|---------|------|
| API 端点 | 4 | 15+ | 3.7x |
| Capability | 7 | 13+ | 1.9x |
| Config 类 | 5 | 15+ | 3x |
| config.py 行数 | ~200 (预估) | 941 | 4.7x |
| 推理网关 | 1 (LiteLLM) | 3 (并列暴露) | 3x |

### 1.2 触发原因

1. **合规性检查**（`docs/compliance-check-report.md`）发现 12 项代码超出 001 规范范围，多为后续 feature 未按架构原则集成
2. **Gateway 设计意图偏离** — LiteLLM 应为唯一推理入口，HTTP Cloud / GLM 应是其内部 provider，当前代码将三者并列暴露
3. **Capability 职责膨胀** — KnowledgeQuery、ExternalKBQuery、QAPipeline、QueryQuality、ConversationalQuery 5 个 Capability 做的是同一件事：接收问题、检索知识、生成回答

### 1.3 目标

在不损失现有功能的前提下，将架构收拢到清晰的边界：
- **3 个 Capability**（而非 13+）
- **1 个推理入口**（LiteLLM，而非 3 个并列 Gateway）
- **4 个核心端点**（而非 15+）
- config.py 控制在 ~300 行以内

---

## 2. 架构变更

### 2.1 总体架构（变更前后对比）

```
变更前（当前）:                              变更后（目标）:

API Layer                                   API Layer
  ├── POST /api/v1/ai/agent                   ├── POST /api/v1/query
  ├── POST /api/v1/query                      ├── GET /api/v1/models
  ├── POST /api/v1/external/query             ├── GET /api/v1/traces/{id}
  ├── POST /api/v1/qa/query                   └── GET /api/v1/health
  ├── POST /api/v1/qa/query/stream
  ├── GET /api/v1/qa/health                 Capability Layer
  ├── POST /api/v1/documents                  ├── QueryCapability
  ├── PUT /api/v1/documents/{id}               │   策略: retrieval( milvus | external_kb )
  ├── DELETE /api/v1/documents/{id}            │   策略: quality( basic | dimension_gather | conversational )
  ├── POST /api/v1/kb/upload                   │   策略: generation( standard | streaming )
  ├── GET /api/v1/models                       │   内含: query_rewrite, hallucination_detection
  ├── GET /api/v1/traces/{id}                  │
  ├── GET /api/v1/health                       ├── ManagementCapability
  └── GET /api/v1/observability/metrics          │   文档 CRUD + KB 上传
                                                └── TraceCapability
Capability Layer                                   追踪查询 + 可观测性指标
  ├── HealthCheckCapability
  ├── KnowledgeQueryCapability               Infrastructure
  ├── ExternalKBQueryCapability                ├── Gateway
  ├── MilvusKBQueryCapability                  │   LiteLLM (唯一入口)
  ├── MilvusKBUploadCapability                 │   ├── provider: ollama
  ├── ModelInferenceCapability                 │   ├── provider: openai
  ├── ModelDiscoveryCapability                 │   ├── provider: claude
  ├── TraceObservationCapability               │   ├── provider: glm (内部实现)
  ├── DocumentManagementCapability             │   └── provider: http_cloud (内部实现)
  ├── QueryQualityCapability                   │
  ├── ConversationalQueryCapability            ├── Store
  ├── QAPipelineCapability                     │   策略: milvus | external_kb
  └── ...                                      │
                                               └── Observer
Gateway                                          litellm + phidata + langfuse
  ├── LiteLLMGateway (三选一)
  ├── HTTPCompletionGateway (三选一)
  └── GLMGateway (三选一)
```

### 2.2 Capability 合并方案

#### 2.2.1 合并为 QueryCapability

将以下 5 个 Capability 合并为 1 个 `QueryCapability`：

| 原 Capability | 处理方式 |
|--------------|---------|
| KnowledgeQueryCapability | 合并为 retrieval 子流程 |
| ExternalKBQueryCapability | 合并为 retrieval 策略（external_kb 模式） |
| QAPipelineCapability | 合并为 query 主流程编排 |
| QueryQualityCapability (006) | 合并为 quality 策略（dimension_gather 模式） |
| ConversationalQueryCapability (007) | 合并为 quality 策略（conversational 模式） |

**合并后的 QueryCapability 内部结构**：

```python
class QueryCapability(Capability[QueryInput, QueryOutput]):
    """统一的查询能力 — 调用者唯一入口"""

    def __init__(self, config: QueryConfig):
        # 检索策略（内部切换，调用者不可见）
        self.retrieval = RetrievalStrategy.create(
            backend=config.retrieval_backend,  # "milvus" | "external_kb"
        )
        # 质量增强策略（内部切换，调用者不可见）
        self.quality = QualityStrategy.create(
            mode=config.quality_mode,  # "basic" | "dimension_gather" | "conversational"
        )
        # 推理 — 始终通过 LiteLLM
        self.gateway = LiteLLMGateway(config.litellm)
        # 内含子流程：query_rewrite, hallucination_detection
        self.rewriter = QueryRewriter(...)
        self.verifier = HallucinationDetector(...)

    async def execute(self, input_data: QueryInput) -> QueryOutput:
        question = input_data.question
        # 1. 质量增强（可选）
        question = await self.quality.enhance(question, session=...)
        # 2. 查询改写（可选）
        question = await self.rewriter.rewrite(question)
        # 3. 检索
        chunks = await self.retrieval.search(question)
        # 4. 生成
        answer = await self.gateway.complete(prompt=..., context=chunks)
        # 5. 幻觉检测（可选）
        answer = await self.verifier.verify(answer, chunks)
        return QueryOutput(answer=answer, chunks=chunks, ...)
```

**调用者视角变化**：

```python
# 变更前：调用者需要知道用哪个 Capability
registry.get("QAPipelineCapability")       # 还是 KnowledgeQueryCapability？
registry.get("ExternalKBQueryCapability")   # 还是 MilvusKBQueryCapability？
registry.get("QueryQualityCapability")      # 还是 ConversationalQueryCapability？

# 变更后：调用者只关心一件事
registry.get("QueryCapability")
# 内部用哪个 retrieval 后端、哪个 quality 策略，由配置决定，调用者不需要知道
```

#### 2.2.2 合并为 ManagementCapability

| 原 Capability | 处理方式 |
|--------------|---------|
| DocumentManagementCapability | 保留核心逻辑 |
| MilvusKBUploadCapability | 合并为 upload 子操作 |
| ModelDiscoveryCapability | 合并为 models 子操作 |

#### 2.2.3 合并为 TraceCapability

| 原 Capability | 处理方式 |
|--------------|---------|
| TraceObservationCapability | 保留核心逻辑 |
| HealthCheckCapability | 合并为 health 子操作 |

#### 2.2.4 不参与合并的 Capability

| 原 Capability | 处理方式 |
|--------------|---------|
| ModelInferenceCapability | **删除** — 推理统一通过 LiteLLM Gateway，不再需要独立 Capability 封装 |

---

### 2.3 Gateway 收拢方案

**核心原则**：LiteLLM 是唯一推理入口。HTTP Cloud 和 GLM 是 LiteLLM 内部的 provider 实现，不是并列的 Gateway。

#### 变更前

```python
# config.py — 三选一
default_gateway: str = "http"  # "litellm" | "http" | "glm"

# gateway.py — 三个独立类
class LiteLLMGateway: ...
class HTTPCompletionGateway: ...
class GLMGateway: ...  # (隐含在 HTTP 中)

# ModelInferenceCapability — 调用者需要指定 backend
input_data = ModelInferenceInput(..., gateway_backend="http")
```

#### 变更后

```python
# config.py — 单一配置段
class LiteLLMConfig(BaseSettings):
    """唯一推理网关配置"""
    api_key: str
    api_base: str
    model: str

    # 内部 provider 路由（调用者不可见）
    providers: Dict[str, ProviderConfig] = {
        "default": {"type": "litellm", "model": "openai/gpt-4o-mini"},
        "glm": {"type": "http", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
        "cloud": {"type": "http", "base_url": "https://api.example.com/v1"},
    }
    default_provider: str = "default"

# gateway.py — 一个类
class LiteLLMGateway:
    """唯一推理入口 — GLM/HTTP Cloud 是内部实现"""

    async def complete(self, prompt: str, provider: str = None) -> CompletionResult:
        provider = provider or self.config.default_provider
        provider_config = self.config.providers[provider]

        if provider_config.type == "litellm":
            return await self._litellm_complete(prompt, provider_config)
        elif provider_config.type == "http":
            return await self._http_complete(prompt, provider_config)
```

#### 删除的配置类

| 删除 | 行数 (config.py) | 说明 |
|------|-------------------|------|
| CloudCompletionConfig | ~60 行 | 合并入 LiteLLMConfig.providers |
| GLMConfig | ~80 行 | 合并入 LiteLLMConfig.providers |
| CloudEmbeddingConfig | ~20 行 | 合并入 LiteLLMConfig |
| CloudRerankConfig | ~20 行 | 合并入 LiteLLMConfig |

预估 config.py 减少 ~180 行。

---

### 2.4 API 端点收拢方案

#### 变更前 → 变更后映射

| 原端点 | 变更后 | 说明 |
|--------|-------|------|
| `POST /api/v1/ai/agent` | **合并入** `POST /api/v1/query` | 功能完全相同 |
| `POST /api/v1/query` | `POST /api/v1/query` | 保留，作为唯一查询入口 |
| `POST /api/v1/external/query` | **合并入** `POST /api/v1/query` | 通过 request body 区分 retrieval_backend |
| `POST /api/v1/qa/query` | **合并入** `POST /api/v1/query` | QA pipeline 是 QueryCapability 的默认行为 |
| `POST /api/v1/qa/query/stream` | `POST /api/v1/query/stream` | 保留流式端点（如需要） |
| `GET /api/v1/qa/health` | **合并入** `GET /api/v1/health` | 健康检查统一 |
| `GET /api/v1/health` | `GET /api/v1/health` | 保留 |
| `GET /api/v1/models` | `GET /api/v1/models` | 保留 |
| `GET /api/v1/traces/{id}` | `GET /api/v1/traces/{id}` | 保留 |
| `GET /api/v1/observability/metrics` | **合并入** `GET /api/v1/health` (detailed) | 或保留为独立端点 |
| `POST /api/v1/documents` | `POST /api/v1/documents` | 保留 |
| `PUT /api/v1/documents/{id}` | `PUT /api/v1/documents/{id}` | 保留 |
| `DELETE /api/v1/documents/{id}` | `DELETE /api/v1/documents/{id}` | 保留 |
| `POST /api/v1/kb/upload` | **合并入** `POST /api/v1/documents` | 上传是文档管理的子操作 |

#### 合并后的统一查询请求

```python
class QueryRequest(BaseModel):
    """统一查询请求 — 替代原 QueryRequest / ExternalKBQueryRequest / QAQueryRequest"""
    question: str

    # 检索策略（可选，默认由配置决定）
    retrieval_backend: Optional[str] = None  # None=默认, "milvus", "external_kb"
    comp_id: Optional[str] = None            # external_kb 专用
    file_type: Optional[str] = None          # external_kb 专用

    # 质量增强（可选，默认由配置决定）
    quality_mode: Optional[str] = None       # None=默认, "basic", "dimension_gather", "conversational"
    session_id: Optional[str] = None         # 多轮会话

    # 通用参数
    top_k: int = 5
    model_hint: Optional[str] = None
    stream: bool = False
    trace_id: Optional[str] = None
```

---

### 2.5 目录结构变更

```
src/rag_service/
│
├── main.py                          # 不变
├── config.py                        # 大幅精简: 15 Config 类 → ~5 个
│
├── api/
│   ├── routes.py                    # 精简: 合并端点
│   └── schemas.py                   # 精简: 统一 QueryRequest/Response
│   (删除 qa_routes.py, qa_schemas.py, kb_upload_routes.py)
│
├── capabilities/
│   ├── base.py                      # 不变
│   ├── query.py                     # 新: 合并 KnowledgeQuery + ExternalKB + QA + QueryQuality + Conversational
│   ├── management.py                # 新: 合并 DocumentManagement + MilvusKBUpload + ModelDiscovery
│   ├── trace.py                     # 新: 合并 TraceObservation + HealthCheck
│   │
│   ├── query/                       # QueryCapability 内部策略
│   │   ├── retrieval.py             # 检索策略基类 + Milvus/ExternalKB 实现
│   │   ├── quality.py               # 质量增强策略基类 + Basic/DimensionGather/Conversational 实现
│   │   ├── rewrite.py               # 查询改写（从 query_rewrite.py 迁入）
│   │   └── verification.py          # 幻觉检测（从 hallucination_detection.py 迁入）
│   │
│   (删除: knowledge_query.py, external_kb_query.py, milvus_kb_query.py,
│    milvus_kb_upload.py, model_inference.py, model_discovery.py,
│    trace_observation.py, document_management.py, health_check.py,
│    query_quality.py, conversational_query.py, qa_pipeline.py,
│    query_rewrite.py, hallucination_detection.py)
│
├── core/
│   ├── agent.py                     # 精简: 直接使用 QueryCapability 内部组件
│   ├── exceptions.py                # 不变
│   └── logger.py                    # 不变
│
├── inference/
│   └── gateway.py                   # 精简: 3 Gateway 类 → 1 LiteLLMGateway + 内部 provider
│   (删除 inference/models.py 如存在)
│
├── retrieval/
│   ├── knowledge_base.py            # 不变 (作为 retrieval 策略的实现)
│   └── embeddings.py                # 不变
│
├── observability/                   # 不变 — 三层观测栈保持不变
│   ├── trace_manager.py
│   ├── trace_propagation.py
│   ├── litellm_observer.py
│   ├── phidata_observer.py
│   └── langfuse_client.py
│
├── services/
│   ├── prompt_client.py             # 不变
│   ├── default_fallback.py          # 不变
│   ├── session_store.py             # 不变 (被 quality 策略使用)
│   ├── belief_state_store.py        # 不变 (被 quality 策略使用)
│   └── colloquial_mapper.py         # 不变 (被 quality 策略使用)
│
├── clients/
│   └── external_kb_client.py        # 不变 (被 retrieval 策略使用)
│
├── models/                          # 不变 — 006/007 的数据模型保留，由 quality 策略使用
│   ├── query_quality.py
│   └── conversational_query.py
│
└── utils/                           # 不变
```

---

## 3. 配置精简方案

### 3.1 变更前 (config.py 941 行, 15+ Config 类)

```
MilvusConfig, LiteLLMConfig, CloudCompletionConfig, GLMConfig,
CloudEmbeddingConfig, CloudRerankConfig, LangfuseConfig,
EmbeddingConfig, ServerConfig, CORSConfig, ExternalKBConfig,
QAConfig, QueryQualityConfig, ConversationalQueryConfig, MilvusKBConfig
```

### 3.2 变更后 (目标 ~300 行, ~5 Config 类)

```
MilvusConfig          # 不变 — 向量库连接
LiteLLMConfig         # 扩展 — 吞并 CloudCompletion/GLM/CloudEmbedding/CloudRerank
LangfuseConfig        # 不变 — 可观测性
ServerConfig          # 不变 — 服务配置（含 CORS）
QueryConfig           # 新建 — 吞并 QA/QueryQuality/ConversationalQuery/ExternalKB/MilvusKB 的行为开关
```

#### QueryConfig 设计

```python
class RetrievalBackendConfig(BaseModel):
    backend: str = "milvus"                          # "milvus" | "external_kb"
    external_kb: Optional[ExternalKBConfig] = None   # backend="external_kb" 时使用
    milvus: Optional[MilvusKBConfig] = None          # backend="milvus" 时使用

class QualityModeConfig(BaseModel):
    mode: str = "basic"                              # "basic" | "dimension_gather" | "conversational"
    dimension_gather: Optional[DimensionGatherConfig] = None
    conversational: Optional[ConversationalConfig] = None

class QueryConfig(BaseModel):
    """查询行为配置 — 替代 QAConfig + QueryQualityConfig + ConversationalQueryConfig"""
    retrieval: RetrievalBackendConfig = RetrievalBackendConfig()
    quality: QualityModeConfig = QualityModeConfig()
    enable_query_rewrite: bool = False
    enable_hallucination_detection: bool = False
    default_top_k: int = 5
```

### 3.3 删除的配置类与预估行数节省

| 删除 | 预估行数 |
|------|---------|
| CloudCompletionConfig | ~60 |
| GLMConfig | ~80 |
| CloudEmbeddingConfig | ~20 |
| CloudRerankConfig | ~20 |
| QAConfig (合并入 QueryConfig) | ~60 |
| QueryQualityConfig (合并入 QueryConfig) | ~80 |
| ConversationalQueryConfig (合并入 QueryConfig) | ~170 |
| ExternalKBConfig (合并入 QueryConfig.retrieval) | ~50 |
| MilvusKBConfig (合并入 QueryConfig.retrieval) | ~90 |
| **总计** | **~630** |

config.py 从 941 行精简到约 300 行。

---

## 4. 不变的部分

以下组件**保持不变**，不参与重构：

| 组件 | 原因 |
|------|------|
| `observability/` 全部文件 | 三层观测栈架构清晰，功能独立 |
| `retrieval/knowledge_base.py` | 作为 retrieval 策略的实现者保留 |
| `retrieval/embeddings.py` | 嵌入服务独立于查询流程 |
| `core/exceptions.py` | 异常层次设计合理 |
| `core/logger.py` | 结构化日志 + trace_id 传播 |
| `services/` 全部文件 | session_store/belief_state/colloquial_mapper 被 quality 策略使用 |
| `models/` 全部文件 | 006/007 的数据模型被 quality 策略使用 |
| `clients/external_kb_client.py` | 被 external_kb retrieval 策略使用 |
| `capabilities/base.py` | Capability 基类和 Registry 不变 |

---

## 5. 实施策略

### 5.1 分阶段执行

```
Phase 1: Gateway 收拢 (风险最低，收益最高)
  ├── 将 HTTPCompletionGateway / GLM 逻辑内化到 LiteLLMGateway
  ├── 删除 CloudCompletionConfig / GLMConfig
  ├── 所有调用方统一使用 LiteLLMGateway
  └── 预估: config.py -180 行, gateway.py 精简

Phase 2: Capability 合并 — QueryCapability
  ├── 创建 capabilities/query/ 目录
  ├── 实现 RetrievalStrategy (milvus | external_kb)
  ├── 实现 QualityStrategy (basic | dimension_gather | conversational)
  ├── 迁移 query_rewrite / hallucination_detection 为子模块
  ├── 创建 QueryCapability 整合以上策略
  └── 预估: 删除 11 个 Capability 文件, 新增 4 个

Phase 3: API 端点合并
  ├── 合并 /ai/agent + /query + /external/query + /qa/query → /query
  ├── 合并 /health + /qa/health → /health
  ├── 合并 /kb/upload → /documents
  ├── 统一 QueryRequest / QueryResponse
  └── 预估: routes.py 精简, 删除 qa_routes.py / kb_upload_routes.py

Phase 4: 配置精简
  ├── 创建 QueryConfig 替代 QAConfig / QueryQualityConfig / ConversationalQueryConfig
  ├── 合并 ExternalKBConfig / MilvusKBConfig 入 QueryConfig.retrieval
  ├── 清理 Settings 类
  └── 预估: config.py 从 941 行 → ~300 行

Phase 5: 清理与测试
  ├── 更新单元测试
  ├── 更新集成测试
  ├── 更新 E2E 测试客户端 (Feature 002)
  └── 更新 CLAUDE.md 和文档
```

### 5.2 风险控制

| 风险 | 缓解措施 |
|------|---------|
| Phase 2 合并范围大 | 每个 Strategy 独立迁移，保留旧 Capability 作兼容直到全部迁移完成 |
| API 端点合并影响外部调用方 | 旧端点添加 deprecation header，保留 1 个版本的兼容期 |
| 配置变更影响 .env 文件 | 新旧配置同时支持，旧配置标记 deprecated |
| E2E 测试框架 (002) 依赖 /ai/agent 端点 | Phase 3 同步更新 RAGClient |

### 5.3 兼容性保证

```python
# Phase 3 过渡期 — 旧端点转发到新端点
@router.post("/ai/agent", deprecated=True)
async def query_agent_deprecated(request: QueryRequest):
    """Deprecated: Use POST /api/v1/query instead."""
    return await query_unified(request)

@router.post("/external/query", deprecated=True)
async def query_external_deprecated(request: ExternalKBQueryRequest):
    """Deprecated: Use POST /api/v1/query with retrieval_backend='external_kb'."""
    unified = QueryRequest(
        question=request.query,
        retrieval_backend="external_kb",
        comp_id=request.comp_id,
        ...
    )
    return await query_unified(unified)
```

---

## 6. 预期收益

| 指标 | 变更前 | 变更后 | 改善 |
|------|--------|--------|------|
| API 端点数 | 15+ | 4-5 | -67% |
| Capability 数 | 13+ | 3 | -77% |
| config.py 行数 | 941 | ~300 | -68% |
| 推理网关数 | 3 (并列暴露) | 1 (LiteLLM) | 符合设计意图 |
| capabilities/ 文件数 | 13+ | 3 + 4 策略 | -46% |
| 新人理解成本 | 高（需理解 13 个 Capability 的区别） | 低（3 个 Capability，每个意图清晰） | 显著降低 |

---

## 7. 影响范围

### 7.1 受影响的 Feature

| Feature | 影响 | 说明 |
|---------|------|------|
| 001 RAG Service MVP | **重构主体** | Capability / Gateway / API / Config 全面精简 |
| 002 E2E Test | **需同步更新** | RAGClient 端点路径变更 |
| 003 Prompt Service | **无影响** | 独立服务，不参与重构 |
| 005 QA Pipeline | **合并入 001** | 成为 QueryCapability 默认流程 |
| 006 Query Quality | **合并入 001** | 成为 QueryCapability 的 quality 策略 |
| 007 Conversational Query | **合并入 001** | 成为 QueryCapability 的 quality 策略 |

### 7.2 不受影响

- `src/prompt_service/` — 独立服务，不涉及
- `src/e2e_test/` — 仅需更新 RAGClient 的默认端点 URL
- `observability/` — 三层观测栈保持不变
- `services/` — session_store 等服务被质量策略复用，不变
- `models/` — 006/007 数据模型保留，被质量策略使用
