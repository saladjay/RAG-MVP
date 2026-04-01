# Client SDK Contract: Prompt Management Service

**Feature**: 003-prompt-service | **Date**: 2026-03-23
**Version**: 1.0.0 | **Package**: `prompt-service-client`

## Overview

This document defines the Python client SDK contract for the Prompt Management Service. The SDK provides a simple interface for business code to retrieve prompts without directly depending on Langfuse.

---

## Installation

```bash
# Using uv (recommended)
uv add prompt-service-client

# Using pip
pip install prompt-service-client
```

---

## Initialization

```python
from prompt_service import PromptClient

# Basic initialization
client = PromptClient(
    base_url="http://localhost:8000",
)

# With authentication (future)
client = PromptClient(
    base_url="https://prompt-service.example.com",
    api_key="your-api-key",
)

# With custom configuration
client = PromptClient(
    base_url="http://localhost:8000",
    api_key="optional-key",
    timeout=10.0,              # Request timeout in seconds
    max_retries=3,             # Number of retries on transient errors
    enable_cache=True,         # Enable local caching
    cache_ttl=300,             # Cache TTL in seconds
)
```

---

## Core API

### get_prompt()

Retrieve and render a prompt template.

**Signature**:
```python
def get_prompt(
    self,
    template_id: str,
    variables: Dict[str, Any] | None = None,
    context: Dict[str, Any] | None = None,
    retrieved_docs: List[Dict[str, Any]] | None = None,
    options: PromptOptions | None = None,
) -> PromptResponse:
    """
    Retrieve and render a prompt template.

    Args:
        template_id: The prompt template identifier
        variables: Variable values for interpolation
        context: Additional context (user_id, session_id, etc.)
        retrieved_docs: Retrieved documents for inclusion
        options: Additional options (version pinning, metadata)

    Returns:
        PromptResponse with rendered prompt and metadata

    Raises:
        PromptNotFoundError: Template does not exist
        PromptValidationError: Variable validation failed
        PromptServiceError: Service unavailable or other error
    """
```

**Usage**:
```python
# Simple retrieval
response = client.get_prompt("financial_analysis")
print(response.content)

# With variables
response = client.get_prompt(
    "financial_analysis",
    variables={"input": "Analyze AAPL stock performance"}
)
print(response.content)

# With context and retrieved docs
response = client.get_prompt(
    "financial_analysis",
    variables={"input": "Analyze AAPL stock"},
    context={"user_id": "user123", "session_id": "sess456"},
    retrieved_docs=[
        {
            "id": "doc1",
            "content": "AAPL stock price: $178.50",
            "metadata": {"source": "market_data"}
        }
    ]
)

# With version pinning (for testing)
from prompt_service import PromptOptions
response = client.get_prompt(
    "financial_analysis",
    variables={"input": "Test input"},
    options=PromptOptions(version_id=3)  # Pin specific version
)
```

**Response Object**:
```python
@dataclass
class PromptResponse:
    """Response from prompt retrieval."""

    content: str                  # Fully rendered prompt text
    template_id: str              # Template identifier
    version_id: int               # Version that was used
    variant_id: str | None        # Variant if A/B test active
    sections: List[Section] | None  # Sections if include_metadata
    metadata: Dict[str, Any]      # Version metadata
    trace_id: str                 # For tracing/debugging
    from_cache: bool              # Whether response was cached
```

---

## Data Classes

### PromptOptions

```python
@dataclass
class PromptOptions:
    """Options for prompt retrieval."""

    version_id: int | None = None         # Pin specific version
    include_metadata: bool = False        # Include sections/metadata
    include_trace_id: bool = True         # Add trace_id to metadata
```

### Section

```python
@dataclass
class Section:
    """A prompt section."""

    name: str
    content: str
    order: int
```

### RetrievedDoc

```python
@dataclass
class RetrievedDoc:
    """A retrieved document for prompt inclusion."""

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

## Exceptions

```python
class PromptServiceError(Exception):
    """Base exception for all prompt service errors."""
    error_code: str
    message: str
    trace_id: str | None

class PromptNotFoundError(PromptServiceError):
    """Raised when a prompt template is not found."""

class PromptValidationError(PromptServiceError):
    """Raised when variable validation fails."""
    validation_errors: List[str]

class PromptServiceUnavailableError(PromptServiceError):
    """Raised when the service is unavailable."""
    fallback_content: str | None
```

**Usage**:
```python
from prompt_service import (
    PromptNotFoundError,
    PromptValidationError,
    PromptServiceUnavailableError,
)

try:
    response = client.get_prompt("unknown_template")
except PromptNotFoundError as e:
    print(f"Prompt not found: {e.message}")
    print(f"Available prompts: {client.list_prompts()}")
except PromptValidationError as e:
    print(f"Validation failed: {e.validation_errors}")
except PromptServiceUnavailableError as e:
    print(f"Service unavailable: {e.message}")
    if e.fallback_content:
        print(f"Using fallback: {e.fallback_content}")
```

---

## Additional Methods

### list_prompts()

List all available prompt templates.

```python
def list_prompts(
    self,
    tag: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> List[PromptInfo]:
    """List available prompt templates."""
```

**Usage**:
```python
# List all prompts
prompts = client.list_prompts()

# Filter by tag
finance_prompts = client.list_prompts(tag="finance")

# Search
prompts = client.list_prompts(search="analysis")
```

---

### get_prompt_info()

Get detailed information about a prompt template.

```python
def get_prompt_info(
    self,
    template_id: str,
    version: int | None = None,
) -> PromptInfo:
    """Get detailed information about a prompt template."""
```

**Usage**:
```python
info = client.get_prompt_info("financial_analysis")
print(f"Name: {info.name}")
print(f"Description: {info.description}")
print(f"Variables: {info.variables}")
```

---

## Advanced Features

### Context Manager for Trace Propagation

```python
# Use trace_id from your existing request context
with client.trace_context(trace_id="my-app-trace-123"):
    response = client.get_prompt("financial_analysis")
    # The trace_id will be propagated to the prompt service
```

### Retry Configuration

```python
# Configure retry behavior
client = PromptClient(
    base_url="http://localhost:8000",
    max_retries=5,
    retry_backoff_factor=0.5,  # Exponential backoff
    retry_status_codes=[503, 504, 429],  # Retry on these
)
```

### Fallback Handling

```python
# Enable automatic fallback to cached prompts
client = PromptClient(
    base_url="http://localhost:8000",
    enable_fallback=True,
    fallback_cache_ttl=3600,  # 1 hour
)

# When service is unavailable, returns cached prompt
response = client.get_prompt("financial_analysis")
if response.from_fallback:
    print("Warning: Using cached/fallback prompt")
```

---

## Integration Examples

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from prompt_service import PromptClient, PromptNotFoundError

app = FastAPI()
client = PromptClient(base_url="http://prompt-service:8000")

@app.post("/analyze")
async def analyze_financial_data(input_data: str):
    try:
        # Get prompt with business input
        response = client.get_prompt(
            "financial_analysis",
            variables={"input": input_data},
        )

        # Use the rendered prompt
        llm_response = call_llm(response.content)

        return {
            "prompt_version": response.version_id,
            "trace_id": response.trace_id,
            "response": llm_response,
        }
    except PromptNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
```

### Background Task Integration

```python
import asyncio
from prompt_service import PromptClient

async def background_analysis(task_id: str, data: str):
    client = PromptClient(base_url="http://prompt-service:8000")

    # Async support
    response = await client.async_get_prompt(
        "financial_analysis",
        variables={"input": data},
    )

    # Process with prompt
    result = await process_with_llm(response.content)

    # Store result with trace_id for debugging
    await store_result(task_id, result, trace_id=response.trace_id)
```

### Batch Processing

```python
from prompt_service import PromptClient

client = PromptClient(base_url="http://prompt-service:8000")

# Batch retrieval with caching
inputs = ["Analyze AAPL", "Analyze GOOGL", "Analyze MSFT"]

for item in inputs:
    response = client.get_prompt(
        "financial_analysis",
        variables={"input": item}
    )
    # Second call may be cached
    print(f"Version: {response.version_id}, Cached: {response.from_cache}")
```

---

## Configuration

### Environment Variables

```bash
# Service URL
export PROMPT_SERVICE_URL="http://localhost:8000"

# API Key (optional)
export PROMPT_SERVICE_API_KEY="your-api-key"

# Timeout (seconds)
export PROMPT_SERVICE_TIMEOUT="10"

# Enable local cache
export PROMPT_SERVICE_ENABLE_CACHE="true"

# Cache TTL (seconds)
export PROMPT_SERVICE_CACHE_TTL="300"
```

### Configuration File

```python
# config.py
from prompt_service import PromptClient

# Default client instance
default_client = PromptClient.from_env()

# Use throughout app
from config import default_client

response = default_client.get_prompt("financial_analysis")
```

---

## Testing Support

### Mock Mode

```python
# For testing, use mock mode
client = PromptClient(
    base_url="http://localhost:8000",
    mock_mode=True,
    mock_responses={
        "financial_analysis": "Mock prompt content for testing"
    }
)

# Returns mock responses without calling service
response = client.get_prompt("financial_analysis")
assert "Mock prompt" in response.content
```

### Version Pinning for Regression Tests

```python
# Pin specific version for consistent tests
client = PromptClient(base_url="http://localhost:8000")

response = client.get_prompt(
    "financial_analysis",
    variables={"input": "test input"},
    options=PromptOptions(version_id=5)  # Always use version 5
)

# Assert on known output
assert response.version_id == 5
assert expected_prompt == response.content
```

---

## Performance Considerations

1. **Caching**: Enable local caching to reduce latency
2. **Connection Pooling**: Client reuses connections automatically
3. **Async Support**: Use `async_get_prompt()` for async applications
4. **Batch Operations**: Multiple calls benefit from connection reuse

---

## Version Compatibility

| SDK Version | Service API Version | Status |
|-------------|---------------------|--------|
| 1.0.0 | v1 | Current |

---

**Document Version**: 1.0 | **Last Updated**: 2026-03-23
