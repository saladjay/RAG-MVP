# OA Component Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-07

## Active Technologies
- Python 3.11+ + FastAPI, LiteLLM, Pydantic, Pydantic Settings, Phidata, Langfuse SDK, Milvus, httpx (008-rag-architecture-refactor)
- Milvus (vector DB), Redis (session state) (008-rag-architecture-refactor)
- Python 3.11+ + FastAPI, Pydantic, Pydantic Settings, typing.Protocol (stdlib) (009-atomic-pipeline)
- Redis (sessions/belief state), Milvus (vector search) — existing, unchanged (009-atomic-pipeline)

### Languages
- Python 3.11+ (primary language across all services)

### Web Frameworks
- FastAPI - Async web framework for REST APIs (features 001, 003)

### AI/ML Libraries
- LiteLLM - Unified model gateway for multi-provider access (feature 001)
- Langfuse SDK - Observability platform for prompt management and traces (feature 001, 003)
- Phidata - Agent orchestration and behavior observation (feature 001)
- OpenAI API - LLM inference (feature 001)
- sentence-transformers - Text embeddings for similarity-based hallucination detection (feature 005)

### Data Storage
- Milvus - Vector database for knowledge chunks (feature 001)

### HTTP Clients
- httpx - Async HTTP client for SDK and E2E testing (features 002, 003)

### Configuration & Validation
- Pydantic - Data validation and settings management (features 001, 003)
- Pydantic Settings - Configuration from environment variables (feature 001)

### Template Engines
- Jinja2 - Template rendering for prompt interpolation and HTML reports (features 002, 003)

### File Parsing
- pyyaml - YAML file parsing for test cases (feature 002)

### Caching
- cachetools - In-memory caching with LRU (feature 003)
- Redis - Optional L2 cache layer (feature 003)

### Logging
- python-json-logger - Structured JSON logging (features 001, 003)

### Testing
- pytest - Testing framework (features 001, 003)
- pytest-asyncio - Async test support (features 001, 003)
- pytest-cov - Coverage reporting (features 001, 003)

### Package Management
- uv - Python dependency management (constitution requirement, feature 004)

### ASGI Servers
- uvicorn - ASGI server for FastAPI (features 001, 003)

### Utilities
- packaging - Version parsing (feature 004)
- rich - Terminal progress display and formatted output (features 002, 004)

## Project Structure

The repository uses a feature-based structure with separate branches for each service:

```
src/
├── rag_service/                    # Feature 001: RAG Service MVP / Feature 005: QA Pipeline
│   ├── main.py                     # FastAPI application
│   ├── config.py                   # Pydantic settings
│   ├── core/                       # Exceptions, logger
│   ├── capabilities/               # Capability interface layer
│   │   ├── qa_pipeline.py          # QA pipeline orchestration (005)
│   │   ├── query_rewrite.py        # Query rewriting capability (005)
│   │   └── hallucination_detection.py  # Hallucination detection (005)
│   ├── services/                   # Business logic
│   │   └── default_fallback.py     # Default fallback messages (005)
│   ├── clients/                    # External service clients
│   │   └── external_kb_client.py   # External KB HTTP client (001, updated 005)
│   └── api/                        # Routes, schemas
│       ├── qa_routes.py            # QA API endpoints (005)
│       └── qa_schemas.py           # QA request/response models (005)
│
├── prompt_service/                 # Feature 003: Prompt Service
│   ├── main.py                     # FastAPI application
│   ├── config.py                   # Pydantic settings
│   ├── core/                       # Exceptions, logger
│   ├── models/                     # Data models
│   ├── services/                   # Business logic
│   ├── api/                        # Routes, schemas
│   ├── middleware/                 # Caching
│   └── client/                     # Python SDK
│
└── e2e_test/                       # Feature 002: E2E Test Framework
    ├── cli.py                      # CLI entry point
    ├── parsers/                    # File parsers (JSON/CSV/YAML/MD)
    ├── runners/                    # Test execution engine
    ├── comparators/                # Similarity calculation
    ├── reporters/                  # Report generation (console/JSON)
    └── clients/                    # RAG API client

tests/
├── contract/                       # API contract tests
├── integration/                    # Service integration tests
└── unit/                           # Unit tests

scripts/
└── uv-python/                      # Feature 004: UV Python 脚本工具集
    ├── list.ps1 / list.sh          # 列出 Python 版本
    ├── install.ps1 / install.sh    # 安装 Python 版本
    └── verify.ps1 / verify.sh      # 验证 Python 安装
```

**Core Architecture Principle**: All services use a **Capability Interface Layer** between HTTP endpoints and underlying components. This ensures:
- Components are never directly exposed to the API layer
- Components can be swapped without API changes
- Clean abstraction boundaries for testing
- Unified trace_id propagation across all layers

## Commands

### uv (Python Package Management)
```bash
# Install dependencies
uv sync

# Add a dependency
uv add <package>

# Run Python with virtual environment
uv run python script.py

# Run tests
uv run pytest

# Python version management (directly using uv)
uv python list
uv python install 3.11.8
uv python find 3.11
```

### UV Python 脚本工具集 (Feature 004)
```powershell
# Windows PowerShell
.\scripts\uv-python\list.ps1
.\scripts\uv-python\install.ps1 -Version 3.11.8
.\scripts\uv-python\verify.ps1 -Version 3.11.8
```

```bash
# Linux/macOS
./scripts/uv-python/list.sh
./scripts/uv-python/install.sh --version 3.11.8
./scripts/uv-python/verify.sh --version 3.11.8
```

### pytest (Testing)
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_specific.py

# Run async tests
uv run pytest -q
```

### FastAPI Development
```bash
# Run development server
uv run uvicorn <module>:app --reload

# Run with specific port
uv run uvicorn <module>:app --port 8000
```

### Typer CLI (feature 004)
```bash
# Run CLI
uv run python -m uv_python.cli.main

# Run specific command
uv run python -m uv_python.cli.main list
```

### E2E Test CLI (feature 002)
```bash
# Run E2E tests
uv run python -m e2e_test.cli run tests.test.json

# Run with verbose output
uv run python -m e2e_test.cli run tests.test.json --verbose

# Run with custom RAG Service URL
uv run python -m e2e_test.cli run tests.test.json --url http://localhost:8001

# Generate JSON report
uv run python -m e2e_test.cli run tests.test.json --format json --output results.json
```

### Git Branch Workflow
```bash
# Create feature branch
git checkout -b ###-feature-name

# Switch between features
git checkout 001-rag-service-mvp
git checkout 003-prompt-service
git checkout 004-uv-python-install
```

## Code Style

### Python (PEP 8)
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Imports: standard library → third-party → local (separated by blank lines)
- Class names: `CamelCase`
- Function/variable names: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Type Hints (Required)
All function signatures must include type hints:

```python
from typing import List, Optional, Dict, Any

def get_prompt(
    template_id: str,
    variables: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> PromptResponse:
    """Retrieve and render a prompt template."""
    ...
```

### Docstrings (Required)
All public functions and classes must have docstrings:

```python
class PromptRetrievalService:
    """Service for retrieving and rendering prompt templates.

    This service handles prompt template loading, A/B test routing,
    and variable interpolation using Jinja2.
    """

    async def execute(self, input_data: PromptInput) -> PromptOutput:
        """Execute prompt retrieval.

        Args:
            input_data: Prompt retrieval parameters.

        Returns:
            Rendered prompt with version metadata.

        Raises:
            PromptNotFoundError: If template doesn't exist.
        """
        ...
```

### Error Handling
- Use custom exception hierarchy inheriting from base exception
- Include trace_id in all error responses
- Log errors with context before raising
- Use specific exception types (not generic Exception)

### Async/Await Patterns
- Use `async def` for I/O-bound operations
- Use `await` for async calls
- Use `asyncio.gather()` for concurrent independent operations
- Never block the event loop (no sync I/O in async functions)

## Recent Changes
- 009-atomic-pipeline: Added Python 3.11+ + FastAPI, Pydantic, Pydantic Settings, typing.Protocol (stdlib)
- 008-rag-architecture-refactor: Added Python 3.11+ + FastAPI, LiteLLM, Pydantic, Pydantic Settings, Phidata, Langfuse SDK, Milvus, httpx

### Feature 005: RAG QA Pipeline (2026-04-01)
Added complete question-answering pipeline to RAG Service. Introduces:
- Query rewriting capability for improved retrieval

### Feature 004: UV Python Install (2026-03-20)
Added CLI tool for Python runtime management using uv. Introduces:

### Feature 001: RAG Service MVP (2026-03-20)
Added RAG service with three-layer observability. Introduces:

### Feature 003: Prompt Service (2026-03-23)
Added prompt management middleware service. Introduces:

### Feature 002: E2E Test Framework (2026-03-30)
Added E2E testing framework for validating RAG Service responses. Introduces:

<!-- MANUAL ADDITIONS START -->

## Architecture Review (2026-05-07)

### 问题：MVP 单体膨胀

当前 `rag_service` 将 001/005/006/007 四个 feature 的代码混在一起：
- `config.py` 941 行，15 个 Config 类
- `capabilities/` 13+ 个 Capability（spec 001 仅设计 7 个）
- 3 套推理网关（LiteLLM / HTTP Cloud / GLM）并列暴露，违反设计意图
- QueryQuality 和 ConversationalQuery 功能高度重叠

### 设计原则

> **Capability 的粒度应对齐调用者意图，而非实现者分工。**

- Capability 是面向**调用者**的抽象（"我问个问题"），不是面向**实现**的拆分（"我调 Milvus"还是"我调 ExternalKB"）
- 多个实现（Milvus / ExternalKB）应在 Capability **内部**用策略模式切换，不应拆成多个 Capability
- LiteLLM 是唯一的推理入口，HTTP Cloud / GLM 是 LiteLLM 内部的 provider 实现，不应作为独立 Gateway 暴露给调用方
- 006/007 的功能（QueryQuality、ConversationalQuery）是 QueryCapability 内部的策略，不是独立 Capability

### 目标架构

```
API Layer (4 端点)
  ├── POST /query
  ├── GET /models
  ├── GET /traces/{id}
  └── GET /health

Capability Layer (3 个)
  ├── QueryCapability        (检索 + 推理 + 回答, 内部策略切换)
  ├── ManagementCapability   (文档增删改查)
  └── TraceCapability        (追踪查询)

Infrastructure (1 套)
  ├── Gateway   (LiteLLM 唯一入口, HTTP Cloud/GLM 是内部 provider)
  ├── Store     (统一存储, milvus/external_kb 策略切换)
  └── Observer  (统一观测, litellm + phidata + langfuse)
```

### Gateway 设计意图澄清

```
设计意图（正确）:
  调用者 → LiteLLM（唯一门面）→ 内部路由 → Ollama / OpenAI / Claude / GLM / HTTP Cloud
                                       ↑
                                  GLM 和 HTTP Cloud 是 LiteLLM 的内部实现细节，
                                  不是并列的 Gateway，不暴露给 RAG 或其他模块。

当前代码（错误）:
  调用者 → default_gateway="litellm" → LiteLLMGateway
  调用者 → default_gateway="http"    → HTTPCompletionGateway
  调用者 → default_gateway="glm"     → GLMGateway
  ↑ 三个 Gateway 并列，调用者需要知道用哪个
```

### 详细分析

参见 `docs/compliance-check-report.md` 和 `docs/architecture.md`
<!-- MANUAL ADDITIONS END -->
