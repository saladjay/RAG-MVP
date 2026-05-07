# Phase 1: 原子能力拆解 + 轻量编排器

**目标**: 把 QueryCapability（454 行上帝对象）拆成原子能力 + 可配置编排器，零新依赖。

**公式**: `Agent = Capability(原子) + Context(状态) + Tools(动态) + Policy(控制)`

---

## 1. 当前问题

`QueryCapability.execute()` 是一个 6 步硬编码管道：

```
quality.pre_process → rewrite → retrieve → generate → hallucination → quality.post_process
```

| 问题 | 表现 |
|------|------|
| **无共享 Context** | 数据通过 execute() 内局部变量传递，没有上下文对象 |
| **Strategy 是子管道** | DimensionGatherQuality 内含 6 个子步骤 + Redis 读写 + 2 次 LLM 调用 |
| **Prompt 硬编码** | _generate_answer() 第 306 行直接写死英文 prompt，其他步骤用 PromptClient |
| **Rewrite 是死代码** | 每次调用 new QueryRewriteCapability() 不传 litellm_client，永远返回原文 |
| **Streaming 重复逻辑** | stream_execute() 复制了 execute() 的大部分代码 |
| **错误处理不一致** | rewrite/hallucination 静默降级，retrieval/generation 抛异常 |
| **Policy 参数浪费** | max_regen_attempts、regen_timeout 定义了但从未使用 |

---

## 2. 目标架构

```
公式: Agent = Capability(原子) + Context(状态) + Tools(动态) + Policy(控制)

8 个原子能力:

  Planning     → 做什么（Task decomposition, Workflow planning, Tool planning, Goal management）
  Reasoning    → 为什么做（Chain-of-thought, 多步推理, 因果分析, 逻辑判断）
  Retrieval    → 去哪里找（Milvus 向量搜索, External KB HTTP API）
  Rewrite      → 怎么优化输入（查询改写, 同义词扩展, 上下文补全）
  Memory       → 记住什么（会话状态, 信念状态, 对话历史）
  Extraction   → 提取什么（维度分析, 槽位抽取, 实体识别, 结构化映射）
  Generation   → 输出什么（答案生成, 摘要生成, 格式化输出）
  Execution    → 真正执行（工具调用, API 调用, 工作流执行）

PipelineRunner = Planning 能力的实现:
  ├── steps: List[StepCapability]    ← 可配置的步骤列表
  ├── policy: PipelinePolicy          ← 控制策略（Goal management）
  └── context: PipelineContext        ← 流转上下文（一等公民）

Pipeline Steps (按执行顺序):
  1. ExtractionStep       ← 维度分析 / 槽位抽取
  2. RewriteStep          ← 查询改写（修复 wiring bug）
  3. RetrievalStep        ← 向量/HTTP 检索
  4. ReasoningStep        ← 证据综合 / 冲突消解（Phase 1 直通，后续注入 CoT）
  5. GenerationStep       ← 答案生成（prompt 外部化）
  6. VerificationStep     ← 幻觉检测
  7. ExecutionStep        ← 引用提取 / 格式化 / 工具调用（Phase 1 直通）
  Memory                   ← 独立 Protocol，贯穿全程，非步骤
```

---

## 3. PipelineContext（上下文一等公民）

当前数据流通过 7 个局部变量传递。需要统一为一个 Pydantic model：

```python
class PipelineContext(BaseModel):
    """贯穿整个管道的上下文对象。每个 StepCapability 读写这个对象。"""

    # --- 输入（初始化时设置）---
    original_query: str                          # 原始用户查询
    session_id: str = ""                         # 会话 ID
    trace_id: str = ""                           # 追踪 ID
    request_context: Optional[QueryContext] = None  # API 层上下文 (company_id 等)
    top_k: int = 10                              # 检索数量

    # --- 管道中间状态（各 step 读写）---
    processed_query: str = ""                    # 经过 extraction/rewrite 后的查询
    chunks: list[dict] = []                      # 检索到的文档块
    reasoning_result: Optional[dict] = None      # 推理结论（冲突标记、综合摘要）
    answer: str = ""                             # 生成的答案
    hallucination_status: Optional[HallucinationStatus] = None
    quality_meta: dict = {}                      # 质量元数据 + 执行结果

    # --- 控制信号 ---
    should_abort: bool = False                   # True = 追加 prompt 给用户，不继续
    abort_prompt: Optional[str] = None           # abort 时返回给用户的提示文本
    stream: bool = False                         # 是否流式输出

    # --- 计时 ---
    timing: dict[str, float] = {}                # {step_name: ms}

    class Config:
        arbitrary_types_allowed = True
```

**设计原则**:
- 每个 StepCapability 只能通过 PipelineContext 读写数据
- `should_abort` 让任意步骤可以中断管道（替代当前的 raise QueryQualityPromptRequired）
- timing 由 PipelineRunner 自动记录，各 step 不需要自己计时

---

## 4. StepCapability Protocol（原子能力接口）

```python
@runtime_checkable
class StepCapability(Protocol):
    """原子能力接口。每个能力只做一件事。"""

    @property
    def name(self) -> str:
        """步骤名称，用于日志和 timing 记录。"""
        ...

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行一步，读写 context，返回更新后的 context。

        如果需要中断管道，设置 context.should_abort = True。
        """
        ...

    async def get_health(self) -> dict[str, Any]:
        """健康检查。"""
        ...
```

**关键变化**:
- 输入输出统一为 `PipelineContext`，不再每个 step 定义不同签名
- 中断通过 `should_abort` 信号，不再抛异常控制流
- 健康 check 是可选的

---

## 5. 8 个原子能力定义

### 5.1 Planning（规划） — 做什么

**职责**: 决定执行哪些步骤、以什么顺序、用什么参数。

**核心子能力**: Task decomposition, Workflow planning, Tool planning, Goal management

**实现**: `PipelineRunner` 即 Planning 的载体。它根据 `PipelinePolicy` 和 `PipelineContext` 决定：
- 跳过哪些步骤（enable/disable）
- 步骤执行顺序（steps 列表可配置）
- 是否进入重试循环（max_regen_attempts）
- 目标是否达成（should_abort 信号）

**不是独立 Step**: Planning 融合在 PipelineRunner 中，不作为管道中的一个步骤。

### 5.2 Reasoning（推理） — 为什么做

**职责**: 对检索到的信息进行理解、推理和逻辑推导。

**核心子能力**: Chain-of-thought, 多步推理, 因果分析, 逻辑判断

**输入**: `context.chunks`, `context.processed_query`
**输出**: `context.reasoning_result`（推理结论、冲突标记、综合摘要）

**Phase 1 实现**: 直通（pass-through）。将 chunks 原样传递给 GenerationStep。Protocol 接口定义好，后续可注入：
- Chain-of-thought 推理：让 LLM 先对 chunks 做多步推理，产出推理链
- 冲突消解：检测 chunks 间矛盾信息，标记可信度
- 证据综合：从多个 chunks 中综合出一致的证据链

**外部依赖**: LLM（后续实现时）
**内存操作**: 无

### 5.3 Retrieval（检索） — 去哪里找

**职责**: 从知识库检索相关文档块。

**来源**: 当前 `RetrievalStrategy` Protocol + MilvusRetrieval + ExternalKBRetrieval（重命名）

**输入**: `context.processed_query`, `context.top_k`, `context.request_context`
**输出**: `context.chunks`

**子策略**（通过 config 选择）:
- `milvus` — Milvus 向量/混合搜索
- `external_kb` — 外部知识库 HTTP API

**外部依赖**: Milvus, External KB HTTP
**内存操作**: 无

### 5.4 Rewrite（改写） — 怎么优化输入

**职责**: 改写查询以提高检索召回率。

**来源**: 当前 `QueryCapability._rewrite_query()` + `QueryRewriteCapability`

**输入**: `context.processed_query`（或 `context.original_query`）
**输出**: `context.processed_query`（更新为改写后查询）

**修复**: 正确传入 LiteLLM client，不再 new 空实例。

**外部依赖**: LLM (via LiteLLMGateway), Prompt Service
**内存操作**: 无

### 5.5 Memory（记忆） — 记住什么

**职责**: 管理会话状态、信念状态、对话历史。

**来源**: 当前 `SessionStoreService` + `BeliefStateStoreService` + `ColloquialMapperService`

**核心子能力**: 会话持久化, 信念状态管理, 对话历史追踪, TTL 管理

**这个能力比较特殊**: 它不独立出现在管道步骤中，而是被 ExtractionStep 等内部调用。单独提取出来是为了：
- 其他能力（如 GenerationStep）未来可能也需要读写会话
- 存储交互集中管理，方便 mock 和测试
- 如果未来换存储后端（如换成内存 dict），只改这里

**输入/输出**: 独立接口，不经过 PipelineContext

```python
@runtime_checkable
class MemoryCapability(Protocol):
    async def get_session(self, session_id: str) -> Optional[dict]: ...
    async def save_session(self, session_id: str, data: dict, ttl: int = 900) -> None: ...
    async def get_belief_state(self, session_id: str) -> Optional[dict]: ...
    async def save_belief_state(self, session_id: str, data: dict, ttl: int = 900) -> None: ...
```

### 5.6 Extraction（提取） — 提取什么

**职责**: 从输入中提取结构化信息。查询维度分析、槽位抽取、实体识别。

**来源**: 当前 `QualityStrategy.pre_process()` + `QueryQualityCapability` + `ConversationalQueryCapability`

**核心子能力**: OCR, Entity extraction, Table extraction, Schema mapping

**输入**: `context.original_query`, `context.session_id`
**输出**: `context.processed_query`, `context.quality_meta`, 可能设置 `context.should_abort`

**子策略**（通过 config 选择）:
- `basic` — 直通，不修改
- `dimension_gather` — 维度分析（Redis 会话 + LLM 调用）
- `conversational` — 槽位抽取 + 信念状态（Redis + LLM 调用）

**扩展方向**（Phase 1 不实现）:
- 实体抽取：从查询中识别人名、地名、机构名
- Schema 映射：将非结构化查询映射到结构化查询参数
- 文档级提取：从 PDF/图片中提取表格、结构化数据

**外部依赖**: Redis, LLM (via PromptClient), Prompt Service
**内存操作**: 通过内部 MemoryCapability 代理

### 5.7 Generation（生成） — 输出什么

**职责**: 基于推理/检索结果生成最终答案。

**来源**: 当前 `QueryCapability._generate_answer()` + `_generate_stream()`

**输入**: `context.processed_query`, `context.chunks`, `context.reasoning_result`
**输出**: `context.answer`

**Prompt 外部化**: prompt 模板从硬编码字符串改为 PromptClient 获取（`qa_answer_generate`），与 rewrite/hallucination 统一。Fallback 保留当前英文 prompt。

**外部依赖**: LLM (via LiteLLMGateway), Prompt Service
**内存操作**: 无

### 5.8 Execution（执行） — 真正执行

**职责**: 答案生成后的动作执行。引用提取、格式化、工具调用。

**来源**: 当前 `QueryCapability` 的 response 构建逻辑 + `quality.post_process()`

**核心子能力**: Tool calling, API invoke, Workflow execute, Code execution

**输入**: `context.answer`, `context.chunks`, `context.hallucination_status`
**输出**: `context.quality_meta`（最终元数据、格式化标记）

**Phase 1 实现**: 直通（pass-through）。将现有 `quality.post_process()` 逻辑迁移到这里（当前所有实现只返回 dict）。

**扩展方向**（Phase 1 不实现）:
- 引用提取：从 answer 中提取并标注 source 引用
- 格式化：将 answer 格式化为 Markdown/JSON/结构化输出
- 工具调用：如果 answer 中包含工具调用指令，执行对应工具
- API 调用：触发外部 API（如发邮件、建工单）

**外部依赖**: 无（Phase 1）；外部 API/工具（后续）
**内存操作**: 无

---

## 6. PipelinePolicy（控制策略）

当前只有布尔开关。需要增加控制力：

```python
class PipelinePolicy(BaseModel):
    """管道执行策略。Planning 能力的配置载体。"""

    # 步骤开关（Planning 用这些决定跳过哪些步骤）
    enable_extraction: bool = True           # 是否执行 ExtractionStep
    enable_rewrite: bool = True              # 是否执行 RewriteStep
    enable_reasoning: bool = False           # Phase 1 默认关闭，直通
    enable_verification: bool = True         # 是否执行 VerificationStep
    enable_execution: bool = True            # 是否执行 ExecutionStep

    # 深度控制（Goal management）
    rewrite_depth: int = 1                   # 查询改写次数（当前只支持 1）
    max_regen_attempts: int = 0              # 幻觉检测失败后的重新生成次数

    # 阈值
    hallucination_threshold: float = 0.7     # 幻觉检测阈值
    extraction_mode: str = "basic"           # "basic" | "dimension_gather" | "conversational"
    retrieval_backend: str = "external_kb"   # "milvus" | "external_kb"
    verification_method: str = "similarity"  # "similarity" | "llm"

    # Prompt 模板 ID（集中管理）
    prompt_extraction: str = "query_dimension_analysis"
    prompt_rewrite: str = "qa_query_rewrite"
    prompt_reasoning: str = "qa_reasoning"       # Phase 1 未使用
    prompt_generation: str = "qa_answer_generate"
    prompt_verification: str = "qa_hallucination_detection"
```

**关键变化**:
- `max_regen_attempts` 终于被使用：如果 verification 失败，可以循环 regenerate → reverify
- `rewrite_depth`: 理论上可以多轮改写（当前先实现 1 轮）
- Prompt 模板 ID 集中管理，不再散落在各 step 内部

---

## 7. PipelineRunner（编排器）

```python
class PipelineRunner:
    """轻量管道编排器。执行 step 列表，传递 context，应用 policy。"""

    def __init__(
        self,
        steps: list[StepCapability],
        policy: PipelinePolicy,
    ) -> None:
        self.steps = steps
        self.policy = policy

    async def run(self, context: PipelineContext) -> PipelineContext:
        """执行管道。"""
        for step in self.steps:
            if context.should_abort:
                break

            # Policy 控制跳过
            if not self._should_run(step, self.policy):
                continue

            step_start = time.time()
            try:
                context = await step.execute(context)
            except RetrievalError:
                raise  # 核心错误，必须传播
            except GenerationError:
                raise  # 核心错误，必须传播
            except Exception as e:
                # 非核心步骤失败，记录日志但不中断
                logger.warning(f"Step {step.name} failed: {e}")
                context = self._apply_fallback(step, context)

            context.timing[step.name] = (time.time() - step_start) * 1000

        return context
```

**关键设计**:
- **步骤列表可配置** — 默认 `[Extraction, Rewrite, Retrieval, Generation, Verification]`，但可以传入不同组合
- **Policy 控制跳过** — `_should_run()` 根据 policy 决定是否执行某个 step
- **错误处理统一** — 核心错误（retrieval/generation）传播，非核心错误静默降级
- **自动计时** — 不再需要每个 step 自己 `time.time()`

---

## 8. 重构后的调用链

### 当前（硬编码）

```
POST /api/v1/query
  → unified_routes.unified_query()
    → registry.get("QueryCapability").execute(request)
      → QueryCapability.execute()          # 454 行，6 步硬编码
        → quality.pre_process()            # 内含子管道
        → _rewrite_query()                 # 死代码 bug
        → _retrieval.retrieve()
        → _generate_answer()               # 硬编码 prompt
        → _check_hallucination()
        → quality.post_process()
```

### 重构后（可配置）

```
POST /api/v1/query
  → unified_routes.unified_query()
    → registry.get("QueryCapability").execute(request)
      → QueryCapability.execute()          # ~30 行，只做编排
        → PipelineRunner.run(context)      # Planning: 决定步骤顺序和跳过策略
          → ExtractionStep.execute()       # 提取: 维度分析/槽位抽取
          → RewriteStep.execute()          # 改写: 优化查询
          → RetrievalStep.execute()        # 检索: 向量/HTTP 搜索
          → ReasoningStep.execute()        # 推理: Phase 1 直通
          → GenerationStep.execute()       # 生成: prompt 外部化
          → VerificationStep.execute()     # 验证: 幻觉检测
          → ExecutionStep.execute()        # 执行: Phase 1 直通
```

---

## 9. 文件结构

```
src/rag_service/
├── pipeline/                           ← 新目录
│   ├── __init__.py                        导出 PipelineRunner, PipelineContext, PipelinePolicy
│   ├── context.py                         PipelineContext model
│   ├── policy.py                          PipelinePolicy model
│   ├── runner.py                          PipelineRunner (Planning 能力的实现)
│   └── steps/                             8 个原子能力实现
│       ├── __init__.py                       导出所有 Step
│       ├── planning.py                       PlanningStep (委托给 PipelineRunner)
│       ├── reasoning.py                       ReasoningStep (Phase 1 直通)
│       ├── retrieval.py                      RetrievalStep (委托给 strategies/)
│       ├── rewrite.py                        RewriteStep
│       ├── memory.py                         MemoryCapability (独立 Protocol)
│       ├── extraction.py                     ExtractionStep
│       ├── generation.py                     GenerationStep
│       ├── verification.py                   VerificationStep
│       └── execution.py                       ExecutionStep (Phase 1 直通)
├── strategies/                         ← 保留，Retrieval/Quality 策略不变
├── capabilities/                       ← 保留
│   ├── query_capability.py              ← 重写为 ~30 行编排器
│   ├── management_capability.py         ← 不变
│   └── trace_capability.py              ← 不变
└── ...
```

---

## 10. 实施步骤

### Step 1: 创建 pipeline 基础设施

创建 `PipelineContext`, `PipelinePolicy`, `PipelineRunner`, `StepCapability` Protocol。
~150 行代码，不触碰现有文件。

### Step 2: 实现原子能力（每个独立文件）

按依赖关系顺序：
1. `memory.py` — MemoryCapability（无外部依赖，只封装 Redis）
2. `retrieval.py` — RetrievalStep（委托给现有 RetrievalStrategy）
3. `rewrite.py` — RewriteStep（修复 wiring bug）
4. `reasoning.py` — ReasoningStep（Phase 1 直通，~20 行）
5. `generation.py` — GenerationStep（prompt 外部化）
6. `verification.py` — VerificationStep（委托给现有 HallucinationDetectionCapability）
7. `extraction.py` — ExtractionStep（最复杂，内含子策略选择）
8. `execution.py` — ExecutionStep（Phase 1 直通，~20 行，迁移 quality.post_process）

### Step 3: 重写 QueryCapability

把 454 行的 `execute()` 缩减为 ~30 行编排代码：
- 创建 PipelineContext
- 配置 PipelinePolicy
- 构建 step 列表
- 调用 PipelineRunner.run()
- 从 context 构建 QueryResponse

### Step 4: 统一 Streaming

`stream_execute()` 不再复制 execute() 逻辑。改为：
- 复用相同 step 列表，但 GenerationStep 检测 `context.stream=True` 时走流式路径
- 或者：PipelineRunner 支持 `run_stream()` 方法，在 Generation 步骤 yield token

### Step 5: 验证

- 启动服务，确认所有路由正常
- 测试 basic / dimension_gather / conversational 三种模式
- 测试 streaming
- 测试旧端点 Deprecation 头

---

## 11. 不做的事情

- **不引入新依赖** — 全部用 stdlib `typing.Protocol` + Pydantic
- **不删除现有 strategies/** — RetrievalStrategy 和 QualityStrategy 保留，step 委托给它们
- **不修改 API 层** — unified_routes.py 不变
- **不修改 config** — PipelinePolicy 从现有 QueryConfig 构建
- **不改 ManagementCapability / TraceCapability** — 只拆 QueryCapability

---

## 12. 风险和注意事项

1. **ExtractionStep 最复杂** — DimensionGatherQuality 和 ConversationalQuality 内含子管道。先保留为"委托到旧实现"，后续再内联。

2. **max_regen_attempts 循环** — PipelineRunner 需要支持：verification 失败 → regenerate → reverify 循环。这是 policy 控制的，不是硬编码。

3. **向后兼容** — QueryCapability 的外部接口（`execute(UnifiedQueryRequest) -> QueryResponse`）不变，内部实现变了。旧 Capability（QueryQualityCapability 等）保留，被 step 委托调用。

4. **Streaming 架构** — 当前流式和同步是两套代码。理想情况是 PipelineRunner 感知 streaming，GenerationStep 内部决定同步/流式。但这个可以留到 Step 4 再处理。
