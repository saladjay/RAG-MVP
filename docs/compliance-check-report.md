# Spec 合规性检查报告

> 检查日期: 2026-05-07
> 检查范围: specs/001-rag-service-mvp, specs/002-e2e-test-interface, specs/003-prompt-service
> 当前分支: 006-query-quality-enhancement

---

## 总览

| Feature | 完全合规 | 部分合规 | 不合规 | 代码超出规范 |
|---------|---------|---------|-------|------------|
| 001 RAG Service MVP | 21 | 9 | 4 | 12 |
| 002 E2E Test Interface | 30 | 7 | 4 | 16 |
| 003 Prompt Service | 25 | 16 | 8 | 15 |

---

# Feature 001: RAG Service MVP

## 1. 完全合规 (21项)

### 功能需求合规

| Spec 需求 | 代码位置 | 说明 |
|-----------|---------|------|
| FR-001: HTTP POST 端点 | `routes.py:97-162` | `POST /api/v1/ai/agent` |
| FR-002: 知识库检索 | `knowledge_query.py:109-183` | 通过 Milvus 向量搜索 |
| FR-003: 基于上下文生成回答 | `agent.py:271-367` | RAGAgent 检索→组装Prompt→推理 |
| FR-004: 多模型统一网关 | `gateway.py` LiteLLMGateway | 支持 OpenAI/Anthropic/Ollama |
| FR-005: 路由到合适模型 | `config.py:907` default_gateway | http/litellm/glm 三种网关 |
| FR-006: 生成唯一 trace_id | `main.py:177-197` | 中间件自动生成UUID |
| FR-007: 各阶段可观测指标 | `trace_manager.py` | create/link_retrieval/link_inference/complete |
| FR-008: 请求隔离 | `logger.py:25` ContextVar | 每请求独立trace_id |
| FR-009: 错误响应 | `exceptions.py` | 完整异常层次 + to_dict() |
| FR-010: 可配置模型端点 | `config.py` LiteLLMConfig等 | BaseSettings + 环境变量 |
| FR-012: 非阻塞追踪 | `trace_observation.py:154-168` | 异常时返回 recorded=False |
| FR-013: 统一 trace_id 传播 | `trace_propagation.py` | ContextVar + 跨层注入 |
| FR-014: LiteLLM 指标 | `litellm_observer.py` | tokens/cost/latency/routing |
| FR-015: Phidata 指标 | `phidata_observer.py` | steps/tools/reasoning/task_rate |
| FR-016: Langfuse 指标 | `langfuse_client.py` | template version/variables/docs |

### 架构合规

| 组件 | 代码位置 | 说明 |
|------|---------|------|
| Capability 接口层 | `capabilities/base.py:65` | Capability[T,T] 抽象基类 + Registry |
| 健康检查端点 | `routes.py:63-90` | GET /api/v1/health |
| 模型列表端点 | `routes.py:304-338` | GET /api/v1/models |
| 追踪查询端点 | `routes.py:434-500` | GET /api/v1/traces/{trace_id} |
| 文档管理端点 | `routes.py:345-427` | POST/PUT/DELETE /api/v1/documents |
| 异常层次 | `exceptions.py` | RAGServiceError → 子类体系 |
| 三层可观测栈 | `observability/*.py` | LiteLLM + Phidata + Langfuse 观察者 |
| Milvus 集成 | `knowledge_base.py` | 连接/搜索/插入/删除 |
| 嵌入服务 | `embeddings.py` | OpenAI text-embedding-3-small |

---

## 2. 部分合规 (9项)

### 2.1 API URL 前缀不一致

| | 规范 | 代码 |
|---|------|------|
| 路径 | `GET /health`, `POST /ai/agent` | `GET /api/v1/health`, `POST /api/v1/ai/agent` |
| **文件** | `api-contract.md` | `routes.py:56` — `prefix="/api/v1"` |

所有端点都存在且语义正确，但统一加了 `/api/v1` 前缀。规范说"v1 (implicit)"，实际用了 `/api/v1/`。

### 2.2 健康检查响应缺少字段

| | 规范要求 | 代码实际 |
|---|---------|---------|
| 字段 | `status`, `version`, `timestamp`, `dependencies` | `status`, `components`, `uptime_ms` |
| **文件** | `api-contract.md` | `schemas.py:26-31` |

缺少 `version` 和 `timestamp` 字段；`dependencies` 被命名为 `components`。

### 2.3 QueryResponse 缺少详细 metadata

| | 规范要求 | 代码实际 |
|---|---------|---------|
| metadata | `model_used`, `total_latency_ms`, `retrieval_time_ms`, `inference_time_ms`, `input_tokens`, `output_tokens`, `estimated_cost` | 仅 `query_time_ms` 顶层字段 |
| **文件** | `api-contract.md` | `schemas.py:64-75`, `routes.py:150` |

Agent 内部已计算这些指标（`agent.py:359-366`），但未完整传递到 API 响应。

### 2.4 错误响应格式不一致

| | 规范 | 代码 |
|---|------|------|
| 格式 | `{"error": "...", "message": "...", "details": {}, "trace_id": "..."}` | 全局处理器用 `message/detail`，路由用 `error/message/trace_id` |
| **文件** | `api-contract.md` | `main.py:200-211`, `routes.py:159-162` |

全局异常处理器和路由级 HTTPException 的错误字段名不一致。

### 2.5 Models 响应缺少字段

| | 规范 | 代码 |
|---|------|------|
| 字段 | `model_id`, `provider`, `type`(local/cloud), `available`(bool) | `id`, `name`, `provider`, `context_length` |
| **文件** | `api-contract.md` | `schemas.py:127-139` |

缺少 `type` 和 `available` 字段。

### 2.6 Milvus 集合 Schema 不匹配

| | 规范 | 代码 |
|---|------|------|
| 集合名 | `rag_documents` | `documents` (`knowledge_base.py:105`) |
| 字段名 | `vector`, `created_at` | `embedding`, 无 `created_at` |
| 默认维度 | 1536 | 384 (`config.py:28`)，但 `knowledge_base.py:106` 硬编码 1536 |
| 度量类型 | COSINE | L2 (`config.py` 默认)，但搜索时用 COSINE |

**注意**: `config.py` 的 `MilvusConfig.dimension` 默认 384 与 `knowledge_base.py` 的 `EMBEDDING_DIM=1536` 存在冲突，可能导致运行时维度不匹配。

### 2.7 Trace Span 缺少 parent_span

| | 规范 | 代码 |
|---|------|------|
| 字段 | `span_id`, `span_name`, `span_type`, `latency_ms`, `metadata`, `parent_span` | 有前5个，缺 `parent_span` |
| **文件** | `data-model.md` TraceSpan | `trace_manager.py:304-314` |

### 2.8 Phidata 为自定义实现而非 SDK 集成

| | 规范 | 代码 |
|---|------|------|
| 要求 | 使用 Phidata SDK 进行 Agent 编排 | 自定义 `RAGAgent` + `PhidataObserver`（仅指标采集） |
| **文件** | `spec.md` Agent Layer | `core/agent.py` |

代码实现了 spec 描述的 Agent 功能和观察模式，但未实际引入 Phidata 库。

### 2.9 CrewAI 未集成

| | 规范 | 代码 |
|---|------|------|
| 要求 | Phidata → CrewAI → LiteLLM 追踪链 | 无 CrewAI 集成 |
| **文件** | `spec.md` 追踪链 | 不存在 |

规范中提到 CrewAI 负责 "records reasoning steps"，代码中用 `PhidataObserver.record_reasoning_step()` 替代。

---

## 3. 不合规 (4项)

### 3.1 FR-011: API 文档不完整

- **规范**: "HTTP API is fully documented with examples for each endpoint"
- **代码**: FastAPI 自动生成 `/docs`，但端点描述、示例请求/响应体很少
- **文件**: `routes.py` 各路由 docstring 过于简短

### 3.2 请求头名称不匹配

- **规范**: `X-Request-ID` 头用于追踪
- **代码**: 使用 `X-Trace-ID`
- **文件**: `main.py:180`

### 3.3 Langfuse SDK 集成深度不足

- **规范**: integration-contract.md 定义了 Langfuse 追踪/跨度/持久化
- **代码**: 主要以内存存储模式运行，实际 Langfuse SDK 调用部分未实现
- **文件**: `langfuse_client.py:307` 注释 "# Actual Langfuse SDK span update would go here"

### 3.4 集成合同测试缺失

- **规范**: integration-contract.md Section 8 要求 `tests/contract/` 下有 Milvus/LiteLLM 合同测试
- **代码**: 无 `test_milvus_contract.py` 或 `test_litellm_contract.py`

---

## 4. 代码超出规范范围 (12项)

| 功能 | 说明 | 来源 |
|------|------|------|
| External KB 查询 | `POST /api/v1/external/query` + ExternalKBConfig | 业务扩展 |
| QA Pipeline | `qa_routes.py` + QAConfig (query rewrite, hallucination) | Feature 005 |
| Query Quality | `query_quality.py` + QueryQualityConfig + Redis session | Feature 006 |
| Conversational Query | `conversational_query.py` + ConversationalQueryConfig | Feature 007 |
| Milvus KB Upload | `milvus_kb_upload.py` + MilvusKBConfig (hybrid search) | 业务扩展 |
| GLM/ZhipuAI 支持 | GLMConfig (glm-4.5, glm-4.5-air) | 业务扩展 |
| Cloud Embedding/Rerank | CloudEmbeddingConfig, CloudRerankConfig, HTTPEmbeddingService | 业务扩展 |
| 流式响应 | `model_inference.py:208-267` stream_execute() | 规范明确 Out of Scope |
| Redis Session | `main.py:70-113` Redis 初始化 | Feature 006/007 |
| 可观测性聚合端点 | `GET /api/v1/observability/metrics` | 规范未定义 |
| 额外查询端点 | `POST /api/v1/query` (与 `/ai/agent` 并列) | 规范未定义 |
| Prompt Service 集成 | `agent.py` 中 prompt_client 调用 | Feature 003 |

---

# Feature 002: E2E Test Interface

## 1. 完全合规 (30项)

### 功能需求合规

| Spec 需求 | 代码位置 | 说明 |
|-----------|---------|------|
| FR-001: 文件路径输入 | `cli.py:37-41` | `run()` 命令接受 `file_path: Path` |
| FR-002: 多格式文件 | `parsers/factory.py:23-30` | JSON/CSV/YAML/Markdown 全支持 |
| FR-003: 自动格式检测 | `file_format.py:19-49` | `from_path()` 按扩展名检测 |
| FR-004: 解析测试用例 | `test_case.py:10-22` | TestCase 含 id/question/expected_answer/source_docs/tags |
| FR-005: 执行测试 | `test_runner.py:138-226` | `_run_single_test()` → RAGClient.query() |
| FR-006: 相似度评分 | `similarity.py:44-73` | Levenshtein (SequenceMatcher) [0,1] |
| FR-007: 源文档验证 | `validator.py:16-51` | EXACT/SUPERSET/SUBSET/NONE/NOT_APPLICABLE |
| FR-008: 测试报告 | `console.py:28-161`, `json_report.py:28-49` | Console + JSON 报告 |
| FR-009: 批量执行 | `cli.py:194-252` | 目录递归发现测试文件 |
| FR-010: 选择性执行 | `cli.py:78-95`, `test_runner.py:274-309` | --tag/--test-id 过滤 |
| FR-011: 格式验证+错误提示 | 各 parser 均有行号级错误报告 | JSONDecodeError/CSV row/YAML error |
| FR-012: 测试隔离 | `test_runner.py:92-96` | 每测试独立执行，无共享状态 |

### 数据模型合规

| 模型 | 代码位置 | 说明 |
|------|---------|------|
| TestCase | `test_case.py:10-22` | 全部6个字段 + ID验证 |
| FileFormat | `file_format.py:9-17` | JSON/CSV/YAML/MARKDOWN |
| TestResult | `test_result.py:29-65` | 全部9个属性 + TestStatus enum |
| TestReport | `test_result.py:68-121` | 全部10个属性 + pass_rate |
| TestConfig | `config.py:21-100` | pydantic-settings + env_prefix="E2E_TEST_" |
| OutputFormat | `config.py:14-18` | CONSOLE/JSON/HTML |

### RAG API 合同合规

| 要求 | 代码位置 | 说明 |
|------|---------|------|
| 端点 POST /api/v1/ai/agent | `rag_client.py:23` | DEFAULT_QUERY_ENDPOINT |
| 请求体 | `rag_client.py:88-91` | {"question": ..., "trace_id": ...} |
| 异常层次 | `exceptions.py` | E2ETestError → RAGConnectionError/Timeout/Server/Client |
| 超时配置 | `rag_client.py:44-55` | connect=5s, read=30s |
| 源文档匹配 | `validator.py` | 5种匹配类型与规范完全一致 |
| Trace ID 传播 | `test_runner.py:147` | "e2e-{test_id}-{uuid}" 格式 |
| 健康检查 | `rag_client.py:24,182-192` | GET /health → bool |
| 退出码 | `cli.py:149-154` | 0=全通过, 1=有失败, 2=有错误 |

---

## 2. 部分合规 (7项)

### 2.1 RAGServerError.status_code 属性位置

- **规范**: `self.status_code` 直接属性
- **代码**: 存在 `self.details["status_code"]` 中
- **文件**: `exceptions.py:58-71`

### 2.2 重试策略不符合规范

| | 规范 | 代码 |
|---|------|------|
| 连接拒绝 | 指数退避 (1s, 2s, 4s) | 线性退避 (1s, 2s, 3s) |
| 超时 | 固定 2s | 线性退避 |
| 5xx | 重试3次+指数退避 | **不重试** (直接抛出) |
| **文件** | `rag-api.md` Section 5 | `rag_client.py:160-162, 175-177` |

`config.py:64-69` 定义了 `retry_backoff` 但 `RAGClient` 未使用。

### 2.3 TestFile 模型未实现

- **规范**: data-model.md 定义 `TestFile(path, format, test_cases)`
- **代码**: 无此模型，`test_runner.py:271` 直接返回 `List[TestCase]`

### 2.4 TestResult.is_passed 未检查 source_docs_match

- **规范**: `is_passed` 应同时检查 `status == PASSED` 和 `source_docs_match`
- **代码**: 仅检查 `status`
- **文件**: `test_result.py:51-60`

功能上等价（test_runner 在判断 status 时已考虑 source_docs），但模型属性本身弱于规范。

### 2.5 超时常量缺少 total_timeout

- **规范**: connect=5s, read=30s, total=35s
- **代码**: connect=5s, read=30s, 无 total, 额外 write=5s
- **文件**: `rag_client.py:44-55`

### 2.6 CSV 解析器额外支持逗号分隔符

- **规范**: 仅分号分隔多值字段
- **代码**: 同时支持分号和逗号
- **文件**: `csv_parser.py:121-127`

### 2.7 唯一 ID 验证未在运行时调用

- **规范**: test-files.md 要求 "Test IDs must be unique within a single file"
- **代码**: `_validate_unique_ids()` 已实现但未被调用
- **文件**: `base.py:37-58` 定义了 `parse_and_validate()`，但 `test_runner.py:272` 调用的是 `parser.parse()`

---

## 3. 不合规 (4项)

### 3.1 5xx 错误完全不重试

- **规范**: `rag-api.md` 明确要求 5xx 重试3次+指数退避
- **代码**: `rag_client.py:160-162` — `RAGServerError` 立即 re-raise
- **严重程度**: 高 — 直接影响测试可靠性

### 3.2 JSON `{"tests": [...]}` 格式不支持

- **规范**: `spec.md` 附录展示 `{"tests": [...]}` 包装格式
- **代码**: `json_parser.py:56-61` 仅接受纯数组 `[...]`
- **说明**: `contracts/test-files.md` 说纯数组，`spec.md` 说有包装，规范本身有矛盾

### 3.3 唯一 ID 验证被绕过

- **规范**: test-files.md Section 5 "ID Uniqueness" 规则
- **代码**: `test_runner.py:272` 调用 `parse()` 而非 `parse_and_validate()`
- **严重程度**: 中 — 重复 ID 不会报错

### 3.4 Markdown `---` 分隔符未实现

- **规范**: test-files.md "Test delimiter: `---` between test cases"
- **代码**: `md_parser.py` 使用 ```yaml 代码块，不用 `---` 分隔测试

---

## 4. 代码超出规范范围 (16项)

| 功能 | 文件 | 说明 |
|------|------|------|
| `external-kb` CLI 命令 | `cli.py:289-410` | JSONL 外部 KB 测试 |
| `health` CLI 命令 | `cli.py:413-440` | 独立健康检查 |
| `--exclude-tag` 选项 | `cli.py:84-89` | 反向标签过滤 |
| `TestFileError` 异常 | `exceptions.py:90-110` | 含 file_path/line_number |
| `TestValidationError` 异常 | `exceptions.py:113-126` | 含 test_id |
| `SourceDocsMatch` 枚举 | `test_result.py:20-26` | data-model 中未定义此枚举 |
| `get_missing_docs/get_extra_docs` | `validator.py:79-113` | 辅助方法 |
| `TestReport.add_result()` | `test_result.py:98-121` | 增量聚合 |
| `FileFormat` YML/MD 别名 | `file_format.py:15-16` | 额外枚举值 |
| `verbose` 配置字段 | `config.py:77-80` | 详细输出模式 |
| `recursive_discovery` 配置字段 | `config.py:83-86` | 递归目录搜索 |
| `retry_backoff` 配置字段 | `config.py:64-69` | 已定义但 RAGClient 未使用 |
| `RAGClient.retry_count` 参数 | `rag_client.py:30` | 规范 RAGClient 接口未定义 |
| 语义相似度 | `similarity.py:76-112` | sentence-transformers 可选支持 |
| `external_kb_test` runner | `cli.py:22` | 额外测试运行器 |
| `latency_s` 属性 | `test_result.py:62-65` | 毫秒转秒 |

---

# Feature 003: Prompt Service

## 1. 完全合规 (25项)

### API 端点合规

| 端点 | 文件位置 | 说明 |
|------|---------|------|
| GET /health | `main.py:120-145`, `routes.py:140-174` | 含 status/version/components/uptime_ms |
| POST /prompts/{id}/retrieve | `routes.py:181-310` | 含 variables/context/docs/options |
| GET /prompts | `routes.py:317-397` | 分页+tag+search 过滤 |
| POST /prompts | `routes.py:400-496` | 返回 201 + template_id/version |
| PUT /prompts/{id} | `routes.py:499-618` | 创建新版本 |
| DELETE /prompts/{id} | `routes.py:621-687` | 软删除 |
| GET /prompts/{id}/versions | `routes.py:1354-1429` | 分页版本历史 |
| POST /prompts/{id}/rollback | `routes.py:1432+` | 回滚到指定版本 |
| POST /ab-tests | `routes.py:694-788` | 创建 A/B 测试 |
| GET /ab-tests | `routes.py:791-857` | 列表+过滤 |
| GET /ab-tests/{id} | `routes.py:860-943` | 详情 |
| POST /ab-tests/{id}/winner | `routes.py:1023-1092` | 选择胜者 |
| GET /analytics/prompts/{id} | `routes.py:1099-1203` | p50/p95/p99 + 成功率 |
| GET /analytics/traces | `routes.py:1206-1340` | 搜索+过滤+分页 |

### 功能需求合规

| FR | 文件位置 | 说明 |
|----|---------|------|
| FR-001: get_prompt 接口 | `prompt_retrieval.py:73-198` | 变量插值+上下文+版本固定 |
| FR-002: 解耦 Langfuse | `prompt_retrieval.py`, `client/sdk.py` | 业务代码不直接访问 Langfuse |
| FR-003: 在线编辑 | `prompt_management.py:142-260` | API 更新无需部署 |
| FR-004: A/B 测试 | `ab_testing.py:35-513` | SHA-256 哈希路由 |
| FR-005: 追踪分析 | `trace_analysis.py:32-520` | 指标聚合+洞察 |
| FR-006: 版本历史 | `version_control.py:44-112` | 每次变更创建快照 |
| FR-007: 版本回滚 | `version_control.py:146-292` | 创建目标版本副本 |
| FR-010: 变量插值 | `prompt_assembly.py:195-249` | Jinja2 + StrictUndefined |
| FR-015: 动态 Prompt 组装 | `prompt_assembly.py:251-306` | template + context + retrieved_docs |
| FR-017: 版本固定 | `schemas.py:80-89`, `client/models.py:27-36` | version_id 支持 |
| FR-018: Trace-Prompt 关联 | `trace.py:23-62` | 每条 trace 含 template_id + version |

### 数据模型/基础设施合规

| 组件 | 文件位置 | 说明 |
|------|---------|------|
| 7个实体模型 | `models/prompt.py`, `models/ab_test.py`, `models/trace.py` | PromptTemplate/StructuredSection/VariableDef/PromptVariant/ABTest/TraceRecord/VersionHistory |
| 异常层次 | `core/exceptions.py` | 5种错误码 + HTTP 状态映射 |
| LRU 缓存 | `middleware/cache.py` | cachetools.TTLCache |
| 结构化日志 | `core/logger.py` | ContextVar + JSON + trace_context() |
| 配置管理 | `config.py` | LangfuseConfig + CacheConfig + ServiceConfig |

---

## 2. 部分合规 (16项)

### 2.1 GET /prompts/{template_id} 端点缺失

- **规范**: api-contract.md 定义 `GET /prompts/{template_id}` 含 `?version=N` 参数
- **代码**: 无此路由
- **影响**: SDK 的 `get_prompt_info()` 通过 `list_prompts(search=template_id)` 客户端过滤，效率低且不支持 version 参数

### 2.2 A/B 测试暂停/恢复路由缺失

- **规范**: `POST /ab-tests/{id}/pause` 和 `POST /ab-tests/{id}/resume`
- **代码**: `ab_testing.py:158-222` 服务方法已实现，但无对应 HTTP 路由

### 2.3 A/B 测试初始状态

- **规范**: api-contract.md 示例显示创建后 `status: "running"`
- **代码**: `ab_testing.py` 创建时 `status=ABTestStatus.DRAFT`

### 2.4 FR-009: A/B 测试指标未在检索流程中记录

- **规范**: 系统应跟踪 A/B 测试变体指标
- **代码**: `PromptRetrievalService` 调用 `assign_variant()` 增加 impressions，但从不调用 `record_outcome()`，因此 successes 始终为 0

### 2.5 FR-011: 发布前验证不完整

- **规范**: "MUST validate prompt content before publishing"
- **代码**: `prompt_management.py:422-455` 有基本验证
- **缺失**: 无内容大小限制、无变量缺失预检查

### 2.6 FR-012: 审计日志

- **规范**: "MUST maintain audit logs for all prompt modifications"
- **代码**: 版本快照含 changed_by/change_description
- **缺失**: 无独立审计日志表，删除操作无持久审计记录

### 2.7 FR-008: 管理界面

- **规范**: "user-friendly interface" + "Visual prompt editor"
- **代码**: 仅 REST API
- **缺失**: 无 HTML/前端编辑器界面

### 2.8 FR-013: 结构化 Prompt 格式验证宽松

- **规范**: 至少需要 [角色][任务][约束][输出格式] 4 个标准 section
- **代码**: `prompt_management.py:435-438` 仅要求 "at least one standard section"

### 2.9 Client SDK 缺少 from_env()

- **规范**: `PromptClient.from_env()` 读取环境变量
- **代码**: 不存在此方法

### 2.10 Client SDK 缺少高级功能

| 缺失功能 | 规范要求 |
|---------|---------|
| `mock_mode` | 测试时使用模拟响应 |
| `trace_context()` | 追踪上下文管理器 |
| `enable_fallback` | 降级缓存 |
| `from_fallback` 响应属性 | 标识是否来自缓存 |
| `retry_backoff_factor` | 自定义退避因子 |
| `retry_status_codes` | 自定义重试状态码 |

### 2.11 响应缺少 timestamp 字段

- **规范**: "All responses include: trace_id and timestamp"
- **代码**: `TimestampedResponse` 已定义但大多数响应模型未继承使用
- **文件**: `schemas.py`

### 2.12 X-Trace-ID 头未读取

- **规范**: API 应接受客户端传入的 `X-Trace-ID` 头
- **代码**: 路由自行生成 trace_id，不从请求头读取
- **文件**: `routes.py` 各端点

### 2.13 VersionHistory 缺少 diff 字段

- **规范**: data-model.md VersionHistory 含 `diff: Optional[str]` (unified diff)
- **代码**: `prompt.py:267-290` — 无此字段，不做 diff 计算

### 2.14 VariableDef 验证未应用

- **规范**: "Validation regex applied if provided" + "Type coercion attempted"
- **代码**: `VariableDef.validation` 字段存在但 prompt_assembly 不执行

### 2.15 Trace 搜索参数名不匹配

- **规范**: `page` / `page_size` 分页参数
- **代码**: 使用 `offset` / `limit`
- **文件**: `routes.py:1206-1340`

### 2.16 list_prompts 构造函数 Bug

- **代码**: `prompt_management.py:339-348` 传递了无效的 `template=` 和 `variables=` 参数给 `PromptTemplate` 构造函数
- **影响**: 列出 prompt 时可能运行时出错

---

## 3. 不合规 (8项)

### 3.1 缺少 GET /prompts/{template_id} 端点

- **规范**: api-contract.md 明确定义此端点
- **代码**: routes.py 中不存在
- **严重程度**: 高 — 无法获取单个模板详情

### 3.2 缺少 A/B 测试暂停/恢复路由

- **规范**: api-contract.md 定义 `POST /ab-tests/{id}/pause` 和 `/resume`
- **代码**: 服务层已实现，路由层缺失
- **严重程度**: 中 — 无法通过 API 控制 A/B 测试生命周期

### 3.3 缺少 409 Conflict 处理

- **规范**: `POST /prompts` 应在 template_id 已存在时返回 409
- **代码**: `routes.py:400-496` — 不检查重复，Langfuse 会创建新版本

### 3.4 缺少速率限制

- **规范**: api-contract.md 定义速率限制（1000/min 检索，100/min 管理）
- **代码**: 完全未实现

### 3.5 缺少规范定义的错误码

| 缺失错误码 | 规范要求 |
|-----------|---------|
| `PROMPT_VERSION_NOT_FOUND` | 版本不存在 |
| `INVALID_TEMPLATE_ID` | 模板 ID 格式错误 |
| `MISSING_REQUIRED_VARIABLE` | 缺少必需变量 |
| `AB_TEST_ALREADY_RUNNING` | 测试已在运行 |
| `INSUFFICIENT_SAMPLE_SIZE` | 样本不足 |
| `RATE_LIMIT_EXCEEDED` | 超出速率限制 |

### 3.6 GET /ab-tests/{id} 响应缺少统计指标

- **规范**: 响应应含 `p_value`, `confidence_interval`, `is_significant`, `recommendation`
- **代码**: 仅返回基本变体信息，统计指标在单独的 `/results` 端点且无 `recommendation` 对象

### 3.7 缓存失效逻辑不可靠

- **代码**: `cache.py:231-238` — `invalidate()` 用 `template_id in str(entry.value)` 匹配
- **问题**: 基于字符串匹配而非确定性映射，可能遗漏或误匹配

### 3.8 Client SDK 仅有异步方法

- **规范**: client-contract.md 示例展示同步调用 `client.get_prompt()`
- **代码**: 所有方法均为 `async`

---

## 4. 代码超出规范范围 (15项)

| 功能 | 文件 | 说明 |
|------|------|------|
| Root 端点 GET / | `main.py:220-233` | 服务信息 |
| 重复 health 端点 | `main.py:120-145` + `routes.py:140-174` | /health 和 /api/v1/health |
| ABTestConfig 数据类 | `ab_test.py:259-279` | 创建配置 |
| ABTestAssignment 数据类 | `ab_test.py:240-256` | 分配记录 |
| TraceInsight 数据类 | `trace.py:132-150` | 洞察结构 |
| EvaluationMetrics 模型 | `trace.py:65-100` | 含 p50/p95/p99 |
| VariantMetrics 模型 | `ab_test.py:95-120` | Wilson 置信区间 |
| CacheEntry 统计 | `cache.py:28-63` | 访问计数/年龄 |
| LoggerAdapter | `logger.py:155-219` | 自动注入 trace_id |
| create_client() 函数 | `sdk.py:381-396` | 便捷工厂 |
| Wilson Score 计算 | `ab_test.py:198-225` | 统计显著性 |
| AB Test Results 端点 | `routes.py:946-1020` | 详细指标+置信区间 |
| Client VariableDef | `client/models.py:79-95` | 客户端侧变量定义 |
| Client PromptListResponse | `client/models.py:131-145` | 列表响应模型 |
| Client HealthStatus | `client/models.py:148-162` | 健康状态模型 |

---

# 建议优先修复的关键问题

## Feature 001 — 优先级排序

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | Milvus 嵌入维度冲突 (384 vs 1536) | 统一 config.py 默认值为 1536 |
| P0 | Milvus 度量类型默认值 (L2 vs COSINE) | 修改 config.py 默认值为 COSINE |
| P1 | QueryResponse 缺少详细 metadata | 从 agent 传递完整指标到路由 |
| P2 | 错误响应格式统一 | 全局处理器和路由使用相同字段名 |

## Feature 002 — 优先级排序

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | 5xx 错误不重试 | 在 rag_client.py 的重试循环中加入 5xx 处理 |
| P1 | 唯一 ID 验证被绕过 | test_runner.py 改用 parse_and_validate() |
| P2 | 重试退避策略 | 实现指数退避，区分错误类型 |

## Feature 003 — 优先级排序

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | GET /prompts/{id} 端点缺失 | 添加路由 |
| P0 | list_prompts 构造函数 Bug | 修复无效参数 |
| P1 | A/B 测试暂停/恢复路由缺失 | 添加路由 |
| P1 | A/B 测试 outcome 未记录 | 在检索流程中调用 record_outcome() |
| P2 | 缓存失效机制不可靠 | 改用 template_id→cache_key 反向映射 |
| P2 | 响应缺少 timestamp | 各响应模型添加 timestamp 字段 |
