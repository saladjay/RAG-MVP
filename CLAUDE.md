# OA Component Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-30

## Active Technologies

### Languages
- Python 3.11+ (primary language across all services)

### Web Frameworks
- FastAPI - Async web framework for REST APIs (features 001, 003)

### AI/ML Libraries
- LiteLLM - Unified model gateway for multi-provider access (feature 001)
- Langfuse SDK - Observability platform for prompt management and traces (feature 001, 003)
- Phidata - Agent orchestration and behavior observation (feature 001)
- OpenAI API - LLM inference (feature 001)

### Data Storage
- Milvus - Vector database for knowledge chunks (feature 001)

### CLI Frameworks
- Typer - Command-line interface framework (feature 004)

### HTTP Clients
- httpx - Async HTTP client for SDK and E2E testing (features 002, 003)
- requests - Sync HTTP client (feature 004)

### Configuration & Validation
- Pydantic - Data validation and settings management (features 001, 003)
- Pydantic Settings - Configuration from environment variables (feature 001)
- toml - TOML configuration parsing (feature 004)

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
- pytest - Testing framework (features 001, 003, 004)
- pytest-asyncio - Async test support (features 001, 003)
- pytest-cov - Coverage reporting (features 001, 003, 004)

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
├── rag_service/                    # Feature 001: RAG Service MVP
│   ├── main.py                     # FastAPI application
│   ├── config.py                   # Pydantic settings
│   ├── core/                       # Exceptions, logger
│   ├── capabilities/               # Capability interface layer
│   ├── services/                   # Business logic
│   └── api/                        # Routes, schemas
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
└── uv_python/                      # Feature 004: UV Python Install
    ├── cli/                        # Typer CLI
    ├── core/                       # Exceptions, logger
    ├── models/                     # Data models
    └── python_source/              # API clients

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

### Feature 004: UV Python Install (2026-03-20)
Added CLI tool for Python runtime management using uv. Introduces:
- Typer-based CLI framework
- Integration with python.org and GitHub APIs
- Version detection from project files
- User-space Python installation

### Feature 001: RAG Service MVP (2026-03-20)
Added RAG service with three-layer observability. Introduces:
- Capability interface layer architecture pattern
- LiteLLM gateway for multi-provider access
- Phidata agent orchestration
- Milvus vector database integration
- Langfuse prompt management and tracing
- Unified trace_id propagation across layers

### Feature 003: Prompt Service (2026-03-23)
Added prompt management middleware service. Introduces:
- Prompt retrieval without direct Langfuse dependency
- A/B testing with deterministic hash-based routing
- Online prompt editing without deployment
- Trace analysis and insights
- Python SDK for business code integration
- Jinja2 template rendering for prompts

### Feature 002: E2E Test Framework (2026-03-30)
Added E2E testing framework for validating RAG Service responses. Introduces:
- Multi-format test file support (JSON/CSV/YAML/Markdown)
- Async test execution with httpx
- Similarity calculation using Levenshtein distance
- Rich console output and JSON report generation
- Source document validation
- Configurable thresholds and retry logic

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
