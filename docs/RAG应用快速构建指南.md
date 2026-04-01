# RAG 应用快速构建指南

**基于 Spec 1/2/3 架构框架**

本文档说明如何基于现有的 RAG Service MVP (Spec 1)、E2E Test Framework (Spec 2) 和 Prompt Service (Spec 3) 快速构建一个新的 RAG 应用。

---

## 目录

1. [架构概览](#架构概览)
2. [核心能力层](#核心能力层)
3. [可复用组件](#可复用组件)
4. [快速开始步骤](#快速开始步骤)
5. [代码模板](#代码模板)
6. [E2E 测试集成](#e2e-测试集成)
7. [常用命令](#常用命令)

---

## 架构概览

### 核心设计原则

```
HTTP Routes → Capabilities → Components
```

**关键原则**：
- HTTP 端点**只与 Capability 接口**交互
- 组件（Phidata、LiteLLM、Milvus、Langfuse）**永远不会直接暴露**给 API 层
- Capability 提供清晰的抽象边界
- 可以轻松交换组件而不影响 API

### 三层可观测性

```
trace_id (统一追踪 ID)
    ↓
┌─────────────────────────────────────────────────────────┐
│  LLM Layer (LiteLLM)   - 成本、性能、路由决策           │
│  Agent Layer (Phidata)  - 执行步骤、工具调用、推理路径   │
│  Prompt Layer (Langfuse) - 模板版本、变量插值、检索集成  │
└─────────────────────────────────────────────────────────┘
```

---

## 核心能力层

### 已有核心能力

| 能力类 | 功能 | 模块路径 |
|--------|------|----------|
| `KnowledgeQueryCapability` | 知识库向量查询 | `rag_service/capabilities/knowledge_query.py` |
| `ExternalKBQueryCapability` | 外部 HTTP 知识库查询 | `rag_service/capabilities/external_kb_query.py` |
| `ModelInferenceCapability` | 模型推理网关 | `rag_service/capabilities/model_inference.py` |
| `DocumentManagementCapability` | 文档 CRUD 管理 | `rag_service/capabilities/document_management.py` |
| `TraceObservationCapability` | 可观测性追踪 | `rag_service/capabilities/trace_observation.py` |
| `HealthCheckCapability` | 健康检查 | `rag_service/capabilities/health_check.py` |
| `ModelDiscoveryCapability` | 模型发现 | `rag_service/capabilities/model_discovery.py` |

### 能力接口定义

```python
# 基类：rag_service/capabilities/base.py
class Capability(ABC, Generic[InputT, OutputT]):
    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT:
        """执行能力业务逻辑"""
        pass

    def validate_input(self, input_data: InputT) -> CapabilityValidationResult:
        """输入验证"""
        pass

    async def safe_execute(self, input_data: InputT) -> tuple[OutputT, Optional[Exception]]:
        """带错误处理的执行"""
        pass
```

---

## 可复用组件

### 1. 基础设施

| 组件 | 路径 | 功能 |
|------|------|------|
| 统一日志 | `rag_service/core/logger.py` | 结构化 JSON 日志，trace_id 传播 |
| 异常处理 | `rag_service/core/exceptions.py` | 自定义异常层次 |
| 配置管理 | `rag_service/config.py` | Pydantic Settings |

### 2. 可观测性

| 组件 | 路径 | 功能 |
|------|------|------|
| Trace 管理器 | `rag_service/observability/trace_manager.py` | 统一 trace_id 管理 |
| LiteLLM 观察者 | `rag_service/observability/litellm_observer.py` | 模型调用指标 |
| Phidata 观察者 | `rag_service/observability/phidata_observer.py` | Agent 执行指标 |
| Langfuse 客户端 | `rag_service/observability/langfuse_client.py` | Prompt 模板追踪 |

### 3. HTTP 客户端

| 客户端 | 路径 | 功能 |
|--------|------|------|
| 外部 KB 客户端 | `rag_service/clients/external_kb_client.py` | 外部知识库 HTTP 调用 |
| RAG API 客户端 | `e2e_test/clients/rag_client.py` | RAG 服务测试客户端 |

### 4. E2E 测试框架

| 组件 | 路径 | 功能 |
|------|------|------|
| 测试运行器 | `e2e_test/runners/test_runner.py` | 异步测试执行 |
| 文件解析器 | `e2e_test/parsers/` | JSON/CSV/YAML/MD 解析 |
| 相似度计算 | `e2e_test/comparators/similarity.py` | 字符串相似度对比 |
| 控制台报告 | `e2e_test/reporters/console.py` | Rich 格式化输出 |
| JSON 报告 | `e2e_test/reporters/json_report.py` | JSON 结果导出 |

### 5. Prompt Service

| 组件 | 路径 | 功能 |
|------|------|------|
| Python SDK | `prompt_service/client/sdk.py` | 业务代码集成 |
| Prompt 管理 | `prompt_service/services/prompt_management.py` | 模板 CRUD |
| A/B 测试 | `prompt_service/services/ab_testing.py` | 确定性哈希路由 |
| 缓存中间件 | `prompt_service/middleware/cache.py` | L1 内存缓存 |

---

## 快速开始步骤

### 步骤 1: 创建项目结构

```bash
# 创建新应用目录
mkdir your_rag_app
cd your_rag_app

# 创建标准结构
mkdir -p src/your_app/{capabilities,api,clients}
mkdir -p tests
touch pyproject.toml
touch README.md
```

### 步骤 2: 配置依赖

**pyproject.toml**:
```toml
[project]
name = "your-rag-app"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.135.0",
    "uvicorn>=0.42.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.2.2",
    "python-json-logger>=2.0.0",
]

[project.scripts]
dev = "uvicorn your_app.main:app --reload --port 8000"
```

### 步骤 3: 创建能力实现

**src/your_app/capabilities/your_query.py**:
```python
from typing import Optional
from rag_service.capabilities.base import (
    Capability, CapabilityInput, CapabilityOutput, CapabilityValidationResult
)
from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger

logger = get_logger(__name__)

class YourQueryInput(CapabilityInput):
    query: str
    top_k: int = 5
    collection_name: str = "knowledge_base"

class YourQueryOutput(CapabilityOutput):
    answer: str
    chunks: list
    retrieval_time_ms: float

class YourQueryCapability(Capability[YourQueryInput, YourQueryOutput]):
    """你的自定义查询能力"""

    def __init__(self, your_dependency=None):
        super().__init__()
        self.your_dependency = your_dependency

    async def execute(self, input: YourQueryInput) -> YourQueryOutput:
        logger.info(f"Executing query: {input.query}", extra={"trace_id": input.trace_id})

        # 你的业务逻辑
        # - 调用知识库
        # - 调用模型
        # - 组装答案

        return YourQueryOutput(
            answer="示例答案",
            chunks=[],
            retrieval_time_ms=100.0,
            trace_id=input.trace_id
        )

    def validate_input(self, input: YourQueryInput) -> CapabilityValidationResult:
        if not input.query or len(input.query.strip()) == 0:
            return CapabilityValidationResult(
                is_valid=False,
                errors=["Query cannot be empty"]
            )
        if input.top_k < 1 or input.top_k > 100:
            return CapabilityValidationResult(
                is_valid=False,
                errors=["top_k must be between 1 and 100"]
            )
        return CapabilityValidationResult(is_valid=True)
```

### 步骤 4: 创建 FastAPI 入口

**src/your_app/main.py**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rag_service.capabilities.base import get_capability_registry
from rag_service.core.logger import get_logger
from your_app.capabilities.your_query import YourQueryCapability
from your_app.api.routes import router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时注册能力
    registry = get_capability_registry()
    registry.register(YourQueryCapability(your_dependency=None))
    logger.info(f"Registered capabilities: {registry.list_capabilities()}")
    yield
    # 清理资源
    logger.info("Shutting down")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Your RAG App",
        description="基于 RAG Service 框架构建",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由
    app.include_router(router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 步骤 5: 创建 API 路由

**src/your_app/api/routes.py**:
```python
from fastapi import APIRouter, HTTPException
from your_app.api.schemas import QueryRequest, QueryResponse
from your_app.capabilities.your_query import YourQueryInput
from rag_service.capabilities.base import get_capability_registry

router = APIRouter(prefix="/api/v1", tags=["query"])

@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    registry = get_capability_registry()
    capability = registry.get("YourQueryCapability")

    input_data = YourQueryInput(
        query=request.query,
        top_k=request.top_k,
        trace_id=request.trace_id or ""
    )

    result = await capability.execute(input_data)

    return QueryResponse(
        answer=result.answer,
        chunks=result.chunks,
        trace_id=result.trace_id
    )
```

### 步骤 6: 运行

```bash
# 安装依赖
pip install -e .

# 运行
python -m your_app.main
# 或
uv run dev
```

---

## E2E 测试集成

### 创建测试文件

**tests/your_test.json**:
```json
{
  "name": "Your RAG App Test",
  "description": "测试自定义 RAG 应用",
  "base_url": "http://localhost:8000",
  "tests": [
    {
      "name": "Basic query test",
      "endpoint": "/api/v1/query",
      "method": "POST",
      "body": {
        "query": "什么是RAG？",
        "top_k": 5
      },
      "expected": {
        "success": true,
        "contains": ["answer", "chunks"]
      }
    }
  ]
}
```

### 运行测试

```bash
# 使用 E2E 测试框架
uv run python -m e2e_test.cli run tests/your_test.json

# 输出 JSON 报告
uv run python -m e2e_test.cli run tests/your_test.json --format json --output results.json
```

### 复用外部 KB 客户端

```python
from rag_service.clients.external_kb_client import (
    ExternalKBClient, ExternalKBClientConfig
)

# 配置客户端
config = ExternalKBClientConfig(
    base_url="http://your-kb-api.com",
    endpoint="/api/query",
    xtoken="your-token",
    timeout=30
)

client = ExternalKBClient(config)

# 查询
chunks = await client.query(
    query="你的问题",
    comp_id="N000131",
    file_type="PublicDocDispatch",
    topk=10
)
```

### 复用 Prompt Service SDK

```python
from prompt_service.client.sdk import PromptServiceClient

# 初始化客户端
prompt_client = PromptServiceClient(
    base_url="http://localhost:8002"
)

# 获取提示词
prompt = await prompt_client.get_prompt(
    template_id="rag_template",
    variables={"context": "...", "question": "..."}
)

# A/B 测试
result = await prompt_client.get_prompt_with_ab_test(
    template_id="rag_template",
    user_id="user_123",
    variables={"context": "...", "question": "..."}
)
```

---

## 常用命令

### 开发

```bash
# 运行开发服务器
uvicorn your_app.main:app --reload --port 8000

# 检查健康
curl http://localhost:8000/api/v1/health

# 查看文档
# 浏览器访问 http://localhost:8000/docs
```

### 测试

```bash
# E2E 测试
uv run python -m e2e_test.cli run tests/test.json

# 单元测试
pytest tests/

# 带覆盖率
pytest --cov=your_app --cov-report=html
```

### Docker

```bash
# 构建镜像
docker build -t your-rag-app .

# 运行
docker run -p 8000:8000 your-rag-app
```

---

## 项目模板

### 完整目录结构

```
your_rag_app/
├── src/
│   └── your_app/
│       ├── __init__.py
│       ├── main.py              # FastAPI 入口
│       ├── config.py            # 配置管理
│       ├── capabilities/        # 能力层
│       │   ├── __init__.py
│       │   └── your_query.py    # 自定义能力
│       ├── api/                 # API 层
│       │   ├── __init__.py
│       │   ├── routes.py        # 路由定义
│       │   └── schemas.py       # 请求/响应模型
│       └── clients/             # 外部客户端
│           ├── __init__.py
│           └── kb_client.py     # KB 客户端
├── tests/
│   ├── unit/
│   ├── integration/
│   └── test.json              # E2E 测试
├── questions/                  # 测试问题集
├── pyproject.toml
├── README.md
└── .env
```

---

## 最佳实践

### 1. 能力设计

- ✅ 每个能力只做一件事
- ✅ 使用 `trace_id` 传播
- ✅ 实现输入验证
- ✅ 返回结构化输出

### 2. 错误处理

- ✅ 使用自定义异常（继承 `RAGServiceError`）
- ✅ 记录完整上下文
- ✅ 返回用户友好的错误信息

### 3. 日志

```python
from rag_service.core.logger import get_logger

logger = get_logger(__name__)
logger.info("Processing query", extra={"query": query, "trace_id": trace_id})
```

### 4. 配置

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Your RAG App"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 参考资料

- [Spec 1: RAG Service MVP](../specs/001-rag-service-mvp/spec.md)
- [Spec 2: E2E Test Framework](../specs/002-e2e-test-interface/spec.md)
- [Spec 3: Prompt Service](../specs/003-prompt-service/spec.md)
- [CLAUDE.md](../CLAUDE.md) - 项目开发指南
