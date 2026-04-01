# Quickstart Guide: RAG Service MVP

**Feature**: 001-rag-service-mvp
**Date**: 2026-03-20

## Overview

This guide provides step-by-step instructions to set up and run the RAG Service MVP locally.

## Prerequisites

### Required Software

| Software | Version | Installation |
|----------|---------|--------------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| uv | Latest | `pip install uv` or https://github.com/astral-sh/uv |
| Docker | Latest | https://docs.docker.com/get-docker/ (for Milvus) |
| Ollama | Latest | https://ollama.com/download (optional, for local models) |

### Optional Services

| Service | Purpose | Installation |
|---------|---------|--------------|
| Ollama | Local LLM inference | `ollama pull llama3` |
| OpenAI API | Cloud LLM inference | https://platform.openai.com/api-keys |
| Anthropic API | Cloud Claude inference | https://console.anthropic.com/settings/keys |
| Langfuse | Observability | https://cloud.langfuse.com (or self-host) |

---

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd 代码组件

# Create uv virtual environment
uv venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

---

## Step 2: Install Dependencies

```bash
# Install dependencies using uv
uv pip install -e .

# Or install from pyproject.toml directly
uv pip install fastapi phidata litellm pymilvus langfuse openai uvicorn
```

---

## Step 3: Start External Services

### Option A: Docker Compose (Recommended)

```bash
# Start all services (Milvus, LiteLLM)
docker-compose up -d

# Verify services are running
docker-compose ps
```

### Option B: Manual Setup

#### Milvus

```bash
# Start Milvus standalone with Docker
docker run -d \
  --name milvus-standalone \
  -p 19530:19530 \
  -p 9091:9091 \
  -v /path/to/milvus:/var/lib/milvus \
  milvusdb/milvus:latest
```

#### LiteLLM

```bash
# Install LiteLLM
pip install litellm

# Start LiteLLM proxy
litellm --config litellm_config.yaml --port 4000
```

#### Ollama (Optional)

```bash
# Start Ollama service
ollama serve

# Pull a model
ollama pull llama3
```

---

## Step 4: Configure Environment

Create a `.env` file in the project root:

```bash
# .env

# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530

# LiteLLM Configuration
LITELLM_HOST=localhost
LITELLM_PORT=4000

# OpenAI Configuration (for embeddings)
OPENAI_API_KEY=sk-your-openai-key-here

# Anthropic Configuration (optional)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Langfuse Configuration (optional)
LANGFUSE_PUBLIC_KEY=pf-your-key
LANGFUSE_SECRET_KEY=sk-your-secret
LANGFUSE_HOST=https://cloud.langfuse.com

# Application Configuration
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=10
```

---

## Step 5: Initialize Knowledge Base

```bash
# Run the knowledge base initialization script
python scripts/init_knowledge_base.py

# Or manually load documents via API (see API documentation)
```

---

## Step 6: Start the RAG Service

```bash
# Development mode with auto-reload
uvicorn rag_service.main:app --reload --port 8000

# Production mode
uvicorn rag_service.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Expected Output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 7: Verify Health Check

```bash
curl http://localhost:8000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-20T10:00:00Z",
  "dependencies": {
    "milvus": "connected",
    "litellm": "connected",
    "langfuse": "connected"
  }
}
```

---

## Step 8: Make Your First Query

```bash
curl -X POST http://localhost:8000/ai/agent \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Retrieval-Augmented Generation?"}'
```

**Expected Response**:
```json
{
  "answer": "Retrieval-Augmented Generation (RAG) is an AI framework...",
  "chunks": [
    {
      "chunk_id": "chunk_123",
      "content": "RAG combines retrieval systems with generative models...",
      "score": 0.95,
      "source_doc": "doc_rag_intro",
      "timestamp": "2026-03-20T09:00:00Z"
    }
  ],
  "trace_id": "trace_abc123",
  "metadata": {
    "model_used": "ollama/llama3",
    "total_latency_ms": 2340
  }
}
```

---

## Step 9: View Traces (Optional)

If Langfuse is configured:

```bash
# Get trace ID from query response
TRACE_ID="trace_abc123"

# View trace details
curl http://localhost:8000/traces/$TRACE_ID

# Or visit Langfuse dashboard
# https://cloud.langfuse.com
```

---

## Testing

### Run Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=rag_service --cov-report=html

# Run specific test module
pytest tests/unit/test_agent.py

# Run integration tests
pytest tests/integration/
```

### Run Contract Tests

```bash
# Test external service integrations
pytest tests/contract/
```

---

## Troubleshooting

### Milvus Connection Failed

```bash
# Check if Milvus is running
docker ps | grep milvus

# Check Milvus logs
docker logs milvus-standalone

# Verify connection
curl http://localhost:19530/healthz
```

### LiteLLM Connection Failed

```bash
# Check if LiteLLM is running
curl http://localhost:4000/health/status

# Check LiteLLM logs
# Logs are in the terminal where litellm is running
```

### Ollama Models Not Available

```bash
# List available models
ollama list

# Pull a model if needed
ollama pull llama3

# Test Ollama directly
curl http://localhost:11434/api/generate -d '{
  "model": "llama3",
  "prompt": "Hello"
}'
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill process or use different port
uvicorn rag_service.main:app --port 8001
```

---

## Development Workflow

### Add New Documents to Knowledge Base

```bash
# Via API
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New Document",
    "content": "Document content here...",
    "source": "internal"
  }'

# Via Python script
python scripts/add_document.py --file document.txt
```

### Test Different Models

```bash
# Use specific model
curl -X POST http://localhost:8000/ai/agent \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Your question",
    "model_hint": "openai/gpt-4"
  }'

# List available models
curl http://localhost:8000/models
```

---

## Project Structure Reference

```
rag-service/
├── src/rag_service/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration
│   ├── api/                 # API routes and schemas
│   ├── core/                # Agent and tracing logic
│   ├── retrieval/           # Knowledge base and embeddings
│   ├── inference/           # Model gateway
│   └── observability/       # Langfuse integration
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── contract/            # Contract tests
├── scripts/                 # Utility scripts
├── pyproject.toml           # uv dependencies
├── docker-compose.yml       # Local services
└── .env                     # Environment configuration
```

---

## Next Steps

1. **Review API Documentation**: See [contracts/api-contract.md](./contracts/api-contract.md)
2. **Read Data Model**: See [data-model.md](./data-model.md)
3. **Understand Architecture**: See [research.md](./research.md)
4. **Run Tests**: Execute `pytest` to verify setup

---

## Support

For issues or questions:
- Check logs in the terminal where the service is running
- Review trace data in Langfuse dashboard
- Consult the main specification: [spec.md](./spec.md)
