# Prompt Management Service

A FastAPI-based service for managing, retrieving, and analyzing prompt templates with A/B testing, versioning, and analytics support.

## Features

- **Prompt Retrieval**: Retrieve and render prompt templates with variable interpolation
- **Online Editing**: Create, update, and manage prompt templates without deployment
- **A/B Testing**: Compare prompt variants with deterministic traffic routing
- **Trace Analytics**: View aggregate metrics and performance insights
- **Version Control**: Track version history and rollback to previous versions
- **Python Client SDK**: Convenient async client for Python applications

## Quick Start

### Prerequisites

- **Python 3.11+** installed
- **uv** package manager: `pip install uv`
- **Langfuse** account (for prompt management)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd 代码组件

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ./pyproject.prompt-service.toml
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Langfuse Configuration
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key

# Service Configuration
PROMPT_SERVICE_PORT=8000
PROMPT_SERVICE_LOG_LEVEL=info

# Cache Configuration
CACHE_ENABLED=true
CACHE_TTL=300
```

### Running the Service

```bash
# Start the FastAPI server
uvicorn prompt_service.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Docker Deployment

```bash
# Build the image
docker build -f Dockerfile.prompt-service -t prompt-service .

# Run the container
docker run -p 8000:8000 --env-file .env prompt-service
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Prompt Retrieval
```bash
POST /api/v1/prompts/{template_id}/retrieve
Content-Type: application/json

{
  "variables": {"user_input": "Hello"},
  "context": {"user_id": "123"},
  "options": {"include_metadata": true}
}
```

### Prompt Management
```bash
# List prompts
GET /api/v1/prompts?page=1&page_size=20

# Create prompt
POST /api/v1/prompts
{
  "template_id": "my_prompt",
  "name": "My Prompt",
  "description": "Description",
  "sections": [{"name": "角色", "content": "You are a helpful assistant"}],
  "variables": {},
  "tags": ["chat"]
}

# Update prompt
PUT /api/v1/prompts/{template_id}

# Delete prompt
DELETE /api/v1/prompts/{template_id}
```

### A/B Testing
```bash
# Create A/B test
POST /api/v1/ab-tests

# List A/B tests
GET /api/v1/ab-tests

# Get test results
GET /api/v1/ab-tests/{test_id}/results

# Select winner
POST /api/v1/ab-tests/{test_id}/winner
```

### Analytics
```bash
# Get prompt metrics
GET /api/v1/analytics/prompts/{template_id}

# Search traces
GET /api/v1/analytics/traces?template_id={id}
```

### Version Control
```bash
# Get version history
GET /api/v1/prompts/{template_id}/versions

# Rollback to version
POST /api/v1/prompts/{template_id}/rollback
```

## Python Client SDK

### Installation

```bash
pip install prompt-service-client
```

### Usage

```python
import asyncio
from prompt_service.client import create_client

async def main():
    # Create client
    client = await create_client(base_url="http://localhost:8000")

    # Retrieve a prompt
    response = await client.get_prompt(
        template_id="financial_analysis",
        variables={"user_input": "Analyze AAPL stock"}
    )
    print(response.content)

    # List all prompts
    prompts = await client.list_prompts()
    for prompt in prompts.prompts:
        print(f"{prompt.template_id}: {prompt.name}")

    # Get prompt info
    info = await client.get_prompt_info("financial_analysis")
    print(f"Version: {info.version}")
    print(f"Variables: {list(info.variables.keys())}")

    await client.close()

asyncio.run(main())
```

### With Context Manager

```python
from prompt_service.client import PromptClient

async with PromptClient(base_url="http://localhost:8000") as client:
    response = await client.get_prompt(
        template_id="my_prompt",
        variables={"user_input": "Hello"}
    )
    print(response.content)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      HTTP API Layer                         │
│                    (FastAPI Routes)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────────┐ ┌──────────┐ ┌──────────────┐
│ Prompt Service │ │AB Testing│ │   Analytics  │
│   Services     │ │ Service  │ │   Service    │
├────────────────┤ └──────────┘ └──────────────┘
│ Retrieval      │      ┌──────────────┐
│ Management     │ ───▶ │ Version      │
│ Assembly       │      │ Control      │
│                 │      │ Service      │
└────────┬───────┘      └──────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Langfuse Client                          │
│              (with graceful degradation)                    │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
src/prompt_service/
├── api/                # HTTP interface (routes, schemas)
├── core/               # Exceptions, logging, config
├── models/             # Data models (prompt, ab_test, trace)
├── services/           # Business logic services
├── middleware/         # Caching middleware
├── client/             # Python SDK
│   ├── sdk.py          # Main client
│   ├── models.py       # Data models
│   └── exceptions.py   # Exception classes
└── main.py             # FastAPI application
```

## Documentation

- [Quick Start Guide](specs/003-prompt-service/quickstart.md)
- [API Contract](specs/003-prompt-service/contracts/api-contract.md)
- [Data Model](specs/003-prompt-service/data-model.md)
- [Research & Technical Decisions](specs/003-prompt-service/research.md)

## Development

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest --cov=prompt_service --cov-report=html tests/
```

### Constitution Compliance

This project follows the OA Component Constitution:
- **Principle I**: All files include comprehensive documentation headers
- **Principle III**: Tests use real implementations (minimal mocks)
- **Principle IV**: Python uses uv-managed virtual environments

## License

MIT
