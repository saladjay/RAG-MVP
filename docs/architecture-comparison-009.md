# 架构对比：原子化管道重构

**特性**: 009-atomic-pipeline | **日期**: 2026-05-07

---

## 一、重构前：单体 QueryCapability（454 行）

```
┌─────────────────────────────────────────────────────────────────┐
│                        API 层 (FastAPI)                          │
│  POST /api/v1/query ──▶ unified_routes.py                      │
│                           │                                     │
│                           │ registry.get("QueryCapability")     │
│                           ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         QueryCapability.execute()     [454 行]           │   │
│  │                                                          │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  第1步: quality.pre_process(query, session_id)     │  │   │
│  │  │    ├─ BasicQuality          → (query, None)        │  │   │
│  │  │    ├─ DimensionGatherQuality → QueryQualityCap     │  │   │
│  │  │    └─ ConversationalQuality → ConversationalQueryCap│  │   │
│  │  │    ┌─ 抛出 QueryQualityPromptRequired ◀── BUG      │  │   │
│  │  │    │   (用异常做流程控制，违反设计原则)              │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                     │                                     │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  第2步: _rewrite_query(query, trace_id)            │  │   │
│  │  │    └─ QueryRewriteCapability()                     │  │   │
│  │  │       └─ BUG: 没有传入 litellm_client              │  │   │
│  │  │          → 永远返回原始查询，改写从未生效            │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                     │                                     │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  第3步: _retrieval.retrieve(query, top_k, ctx)     │  │   │
│  │  │    ├─ MilvusRetrieval                              │  │   │
│  │  │    └─ ExternalKBRetrieval                          │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                     │                                     │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  第4步: _generate_answer(query, chunks, trace_id)  │  │   │
│  │  │    └─ 硬编码 PROMPT（第 306-313 行）               │  │   │
│  │  │    └─ LiteLLMGateway.acomplete_routed()            │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                     │                                     │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  第5步: _check_hallucination(answer, chunks)       │  │   │
│  │  │    └─ HallucinationDetectionCapability()           │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                     │                                     │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  第6步: quality.post_process(answer, chunks)       │  │   │
│  │  │    └─ 所有实现: return {}  （形同虚设）             │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                     │                                     │   │
│  │              手动拼装 QueryResponse                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  stream_execute()  [完整复制管道逻辑]                     │   │
│  │    └─ 复制: pre_process + rewrite + retrieval             │   │
│  │    └─ 复制: prompt 拼装 + generation                      │   │
│  │    └─ 唯一区别: 用 astream_complete() 流式输出             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

问题清单:
  ✗ 上帝对象 — 454 行堆在一个类里
  ✗ 用异常做流程控制（QueryQualityPromptRequired）
  ✗ Rewrite 接线 Bug — 永远返回原始查询
  ✗ 生成步骤硬编码 Prompt — 无法热更新
  ✗ 流式响应完整复制管道逻辑 — 维护负担翻倍
  ✗ 无法独立增删/替换步骤（必须改 454 行）
  ✗ 手动 time.time() 计时（每个步骤自己管）
  ✗ 无法对单个步骤做独立单元测试
```

---

## 二、重构后：原子化管道架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API 层 (FastAPI)                            │
│  POST /api/v1/query ──▶ unified_routes.py                          │
│                           │                                         │
│                           │ registry.get("QueryCapability")         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │     QueryCapability.execute()     [22 行，纯编排]            │   │
│  │                                                              │   │
│  │     context = PipelineContext.from_request(input_data)       │   │
│  │     context = await runner.run(context)                      │   │
│  │     if context.should_abort: return prompt_response          │   │
│  │     return query_response(context)                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   PipelineRunner [规划能力]                   │   │
│  │                                                              │   │
│  │  for step in steps:                                          │   │
│  │    if context.should_abort: break        ◀── 中止信号       │   │
│  │    if not policy._should_run(step): skip ◀── 策略控制       │   │
│  │    context = await step.execute(context)                     │   │
│  │    context.timing[step.name] = elapsed_ms ◀── 自动计时      │   │
│  │                                                              │   │
│  │  再生循环 (当 max_regen_attempts > 0):                      │   │
│  │    └─ 检测到幻觉时，重新执行生成 + 验证                      │   │
│  │                                                              │   │
│  │  run_stream():                                               │   │
│  │    └─ 同样的步骤 → 从 GenerationStep 流式输出 token          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│         │          PipelinePolicy 控制每步开关                       │
│         │          PipelineContext 承载全部状态                      │
│         ▼                                                           │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     7 个原子步骤                                │ │
│  │                                                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │ │
│  │  │ ① 提取步骤    │  │ ② 改写步骤    │  │ ③ 检索步骤    │         │ │
│  │  │  Extraction   │  │  Rewrite      │  │  Retrieval    │         │ │
│  │  │              │  │              │  │              │         │ │
│  │  │ 读取:        │  │ 读取:        │  │ 读取:        │         │ │
│  │  │  原始查询     │  │  处理后查询   │  │  处理后查询   │         │ │
│  │  │  会话ID       │  │              │  │  top_k       │         │ │
│  │  │              │  │ 写入:        │  │  请求上下文   │         │ │
│  │  │ 写入:        │  │  处理后查询   │  │              │         │ │
│  │  │  处理后查询   │  │  (已更新)     │  │ 写入:        │         │ │
│  │  │  质量元数据   │  │              │  │  chunks      │         │ │
│  │  │              │  │ 委托:        │  │              │         │ │
│  │  │ 委托:        │  │  QueryRewrite│  │ 委托:        │         │ │
│  │  │  质量策略     │  │  [已修复]    │  │  检索策略     │         │ │
│  │  │  (3种模式)    │  │  PromptClnt  │  │  (Milvus/    │         │ │
│  │  │              │  │              │  │   ExtKB)      │         │ │
│  │  │ 可中止:      │  │ 降级策略:    │  │              │         │ │
│  │  │  should_     │  │  退回原始    │  │ 错误:         │         │ │
│  │  │  abort=True  │  │  查询        │  │  抛异常(核心) │         │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │ │
│  │                                                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │ │
│  │  │ ④ 推理步骤    │  │ ⑤ 生成步骤    │  │ ⑥ 验证步骤    │         │ │
│  │  │  Reasoning    │  │  Generation   │  │  Verification │         │ │
│  │  │              │  │              │  │              │         │ │
│  │  │ 阶段1:       │  │ 读取:        │  │ 读取:        │         │ │
│  │  │  直通(空操作) │  │  处理后查询   │  │  answer      │         │ │
│  │  │              │  │  chunks      │  │  chunks      │         │ │
│  │  │ 写入:        │  │              │  │              │         │ │
│  │  │  reasoning_  │  │ 写入:        │  │ 写入:        │         │ │
│  │  │  result=None │  │  answer      │  │  幻觉检测    │         │ │
│  │  │              │  │              │  │  _status     │         │ │
│  │  │ 未来扩展:    │  │ 委托:        │  │              │         │ │
│  │  │  思维链       │  │  PromptClnt  │  │ 委托:        │         │ │
│  │  │  证据综合     │  │  (已外部化!) │  │  幻觉检测    │         │ │
│  │  │              │  │  LiteLLM     │  │  Capability  │         │ │
│  │  │              │  │  Gateway     │  │              │         │ │
│  │  │              │  │              │  │ 降级策略:    │         │ │
│  │  │              │  │ + 流式支持   │  │  标记未检查  │         │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘         │ │
│  │                                                                │ │
│  │  ┌──────────────┐                                             │ │
│  │  │ ⑦ 执行步骤    │                                             │ │
│  │  │  Execution    │                                             │ │
│  │  │              │                                             │ │
│  │  │ 读取:        │                                             │ │
│  │  │  answer      │                                             │ │
│  │  │  chunks      │                                             │ │
│  │  │  验证结果     │                                             │ │
│  │  │              │                                             │ │
│  │  │ 写入:        │                                             │ │
│  │  │  quality_meta │                                             │ │
│  │  │  (最终确认)   │                                             │ │
│  │  │              │                                             │ │
│  │  │ 未来扩展:    │                                             │ │
│  │  │  工具调用     │                                             │ │
│  │  │  工作流执行   │                                             │ │
│  │  └──────────────┘                                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、Agent 公式映射

```
Agent = Capability(原子能力) + Context(状态) + Tools(动态工具) + Policy(控制策略)
```

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent = RAG 查询智能体                      │
│                                                              │
│  ┌──────────────────┐                                       │
│  │   Capability     │  8 个原子能力                           │
│  │   (原子能力)      │  ├─ Planning  (做什么)  → PipelineRunner│
│  │                  │  ├─ Extraction(提取什么) → ExtractionStep│
│  │                  │  ├─ Rewrite   (怎么优化) → RewriteStep   │
│  │                  │  ├─ Retrieval (去哪找)   → RetrievalStep │
│  │                  │  ├─ Reasoning (为什么)   → ReasoningStep │
│  │                  │  ├─ Generation(输出什么) → GenerationStep│
│  │                  │  ├─ Verification(对不对) → VerificationStep│
│  │                  │  └─ Execution (执行什么) → ExecutionStep │
│  └──────────────────┘                                       │
│                                                              │
│  ┌──────────────────┐                                       │
│  │   Context        │  PipelineContext                       │
│  │   (共享状态)      │  original_query    原始查询             │
│  │                  │  processed_query   处理后查询           │
│  │                  │  chunks            检索结果             │
│  │                  │  answer            生成答案             │
│  │                  │  hallucination_status  验证状态         │
│  │                  │  quality_meta      质量元数据           │
│  │                  │  timing            各步骤耗时           │
│  │                  │  should_abort      中止信号             │
│  └──────────────────┘                                       │
│                                                              │
│  ┌──────────────────┐                                       │
│  │   Tools          │  复用现有策略（委托调用）                │
│  │   (动态工具)      │  ├─ RetrievalStrategy  Milvus/ExtKB   │
│  │                  │  ├─ QualityStrategy     3种质量模式     │
│  │                  │  ├─ LiteLLMGateway      模型推理        │
│  │                  │  ├─ PromptClient        提示词管理      │
│  │                  │  └─ HallucinationDetection 幻觉检测     │
│  └──────────────────┘                                       │
│                                                              │
│  ┌──────────────────┐                                       │
│  │   Policy         │  PipelinePolicy                        │
│  │   (控制策略)      │  enable_rewrite          改写开关       │
│  │                  │  enable_verification     验证开关       │
│  │                  │  extraction_mode          提取模式       │
│  │                  │  retrieval_backend        检索后端       │
│  │                  │  max_regen_attempts       最大重试次数   │
│  │                  │  hallucination_threshold  幻觉阈值       │
│  │                  │  prompt_*                 提示词模板ID   │
│  └──────────────────┘                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 四、数据流对比

### 重构前

```
请求
  │
  ▼
QueryCapability.execute() ──── 454 行，全部在一个方法里
  │
  ├─ quality.pre_process()
  │   └─ 需要更多信息时抛异常 ◀── 用异常做控制流
  │
  ├─ _rewrite_query()
  │   └─ 永远返回原始查询 ◀── 接线 Bug
  │
  ├─ retrieval.retrieve()
  │
  ├─ _generate_answer()
  │   └─ 硬编码 Prompt 字符串 ◀── 无法热管理
  │
  ├─ _check_hallucination()
  │
  ├─ quality.post_process()
  │   └─ 永远返回 {} ◀── 形同虚设
  │
  └─ 手动拼装响应（逐字段映射）

stream_execute()
  └─ 完整复制上述所有逻辑 ◀── 代码重复
```

### 重构后

```
请求
  │
  ▼
QueryCapability.execute() ──── 22 行，纯编排
  │
  ├─ PipelineContext.from_request()    ◀── 类型化状态对象
  │
  ├─ PipelineRunner.run(context)       ◀── 规划能力（自动编排）
  │   │
  │   ├─ ExtractionStep  ─▶ 处理后查询 + 中止判断
  │   ├─ RewriteStep     ─▶ 优化后查询     [Bug 已修复]
  │   ├─ RetrievalStep   ─▶ 检索结果 chunks
  │   ├─ ReasoningStep   ─▶ 推理结果（阶段1: 直通）
  │   ├─ GenerationStep  ─▶ 生成答案       [Prompt 已外部化]
  │   ├─ VerificationStep─▶ 幻觉检测结果
  │   ├─ ExecutionStep   ─▶ 最终质量元数据
  │   │
  │   └─ 再生循环（检测到幻觉时自动重试）
  │
  └─ 从 context 构建响应

stream_execute()
  └─ PipelineRunner.run_stream() ── 复用同样的步骤，流式输出
```

---

## 五、目录结构对比

```
重构前（扁平）                          重构后（分层）
────────────────                        ─────────────────

capabilities/                           capabilities/
  query_capability.py  [454 行]           query_capability.py  [225 行]
    ├─ execute()       [130 行]             ├─ execute()        [22 行]
    ├─ stream_execute()[100+ 行]            ├─ stream_execute() [5 行]
    ├─ _rewrite_query()                    └─ 响应构建方法
    ├─ _generate_answer()
    ├─ _check_hallucination()
    └─ validate_input()
                                        pipeline/          ← 新增包
                                          ├── __init__.py
                                          ├── context.py      [PipelineContext]
                                          ├── policy.py       [PipelinePolicy]
                                          ├── protocols.py    [StepCapability + MemoryCapability]
                                          ├── runner.py       [PipelineRunner]
                                          └── steps/
                                              ├── __init__.py
                                              ├── extraction.py
                                              ├── rewrite.py
                                              ├── retrieval.py
                                              ├── reasoning.py
                                              ├── generation.py
                                              ├── verification.py
                                              └── execution.py
```

---

## 六、关键指标

| 指标 | 重构前 | 重构后 | 变化 |
|------|--------|--------|------|
| QueryCapability 总行数 | 454 | 225 | -51% |
| execute() 行数 | ~130 | 22 | -83% |
| 包含管道逻辑的文件数 | 1 | 13（模块化） | +12 |
| 流式代码重复 | 完整复制 | 共享步骤 | 已修复 |
| 硬编码 Prompt | 1 处（生成步骤） | 0（全部走 PromptClient） | 已修复 |
| Rewrite Bug | 永远返回原始 | 正确接线 | 已修复 |
| 流程控制方式 | 异常驱动 | should_abort 信号 | 已修复 |
| 各步骤计时 | 手动 time.time() | Runner 自动记录 | 已改进 |
| 新增步骤 | 编辑 454 行 | 创建 1 个文件 + 加 1 行 | 已改进 |
| 替换步骤实现 | 编辑 454 行 | 改 1 行步骤列表 | 已改进 |
| 独立测试步骤 | 不可能 | Mock PipelineContext 即可 | 已改进 |
| 新增外部依赖 | 0 | 0（用 stdlib Protocol） | 保持 |

---

## 七、可扩展性示例

### 重构前（修改 454 行文件）

```python
# 必须直接编辑 query_capability.py 的 execute() 方法
# 风险：破坏现有逻辑、合并冲突、无隔离

async def execute(self, input_data):
    # ... 已有 130 行管道逻辑 ...
    # 在哪插入？必须理解所有上下文代码
    new_result = await self._my_new_step(...)
    # ... 剩余管道逻辑 ...
```

### 重构后（创建 1 个文件，添加 1 行）

```python
# 第1步: 创建 src/rag_service/pipeline/steps/my_step.py（约 20 行）
class MyStep:
    @property
    def name(self) -> str:
        return "my_step"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        context.quality_meta["my_data"] = "value"
        return context

    async def get_health(self) -> dict[str, Any]:
        return {"step": "my_step", "status": "healthy"}

# 第2步: 在 query_capability.py 的步骤列表中加一行
steps = [
    ExtractionStep(),
    RewriteStep(),
    RetrievalStep(),
    MyStep(),              # ← 加这一行即可
    GenerationStep(),
    ...
]
```

无需修改 Runner、Context、Policy 或任何其他步骤。

---

## 八、修复的 3 个 Bug 详情

### Bug 1: 异常做流程控制

```
重构前:
  quality.pre_process() 返回 prompt_info 时
    → 抛出 QueryQualityPromptRequired 异常
    → unified_routes.py 用 except 捕获
    → 手动拼 JSONResponse 返回

重构后:
  ExtractionStep 设置 context.should_abort = True
    → PipelineRunner 检查后自动中断
    → QueryCapability 用 _build_prompt_response() 构建响应
    → unified_routes.py 收到正常 QueryResponse（含 action="prompt"）
```

### Bug 2: Rewrite 永远返回原始查询

```
重构前:
  QueryRewriteCapability() 构造时没传 litellm_client
    → 内部检查 if self._litellm_client is None
    → 直接返回原始查询，LLM 调用从未执行

重构后:
  RewriteStep 先获取 gateway = await get_gateway()
    → 传入 QueryRewriteCapability(litellm_client=gateway)
    → Rewrite 功能正确执行
```

### Bug 3: 硬编码生成 Prompt

```
重构前:
  _generate_answer() 第 306-313 行直接写死 prompt 字符串
    → 修改需要重新部署
    → 无法 A/B 测试

重构后:
  GenerationStep 通过 PromptClient 加载模板
    → 支持热更新
    → 支持严格模式（再生循环用）
    → PromptClient 不可用时自动回退默认模板
```
