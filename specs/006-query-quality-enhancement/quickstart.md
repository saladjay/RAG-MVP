# Quickstart: Query Quality Enhancement Module

**Feature**: 006-query-quality-enhancement
**Date**: 2026-04-09

## Overview

The Query Quality Enhancement Module analyzes user queries for missing document dimensions and guides users through multi-turn conversations to collect required information before executing searches.

## Prerequisites

1. **Dependencies**:
   - Python 3.11+
   - Redis server (for session state)
   - Prompt Service (feature 003)
   - LiteLLM gateway or compatible LLM endpoint

2. **Environment Variables** (add to `.env`):

```bash
# Redis for session state
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Session timeout (seconds)
QUERY_QUALITY_SESSION_TIMEOUT=900

# Max conversation turns
QUERY_QUALITY_MAX_TURNS=10

# Prompt Service
PROMPT_SERVICE_ENABLED=true
PROMPT_SERVICE_URL=http://localhost:8002
```

## Installation

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install dependencies
uv sync
```

## Development Setup

### 1. Start Redis

```bash
# Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or local Redis
redis-server
```

### 2. Start Prompt Service

```bash
cd src/prompt_service
uv run uvicorn main:app --reload --port 8002
```

### 3. Start RAG Service

```bash
cd src/rag_service
uv run uvicorn main:app --reload --port 8001
```

## Usage Examples

### Example 1: Missing Year Dimension

**Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "关于安全管理的通知",
    "context": {
      "company_id": "N000002",
      "file_type": "PublicDocDispatch"
    },
    "options": {
      "enable_query_quality": true
    }
  }'
```

**Response** (missing year):
```json
{
  "action": "prompt",
  "message": "请问您需要查找哪一年的安全管理通知？",
  "missing_dimensions": ["year"],
  "quality_score": 0.5,
  "session_id": "abc-123-def"
}
```

**Follow-up Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2024年的",
    "context": {
      "company_id": "N000002",
      "file_type": "PublicDocDispatch"
    },
    "options": {
      "enable_query_quality": true
    }
  }' \
  -H "X-Session-ID: abc-123-def"
```

**Response** (complete):
```json
{
  "action": "complete",
  "answer": "根据2024年的发文记录，关于安全管理的通知包括...",
  "sources": [...],
  "quality_feedback": "您的查询非常完整，包含了所有关键维度"
}
```

### Example 2: Complete Query (Single Turn)

**Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "关于印发《安全生产管理办法》的通知——粤东科〔2024〕33号",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (directly proceeds to retrieval):
```json
{
  "action": "complete",
  "answer": "根据文档《关于印发《安全生产管理办法》的通知》...",
  "sources": [...]
}
```

### Example 3: Dual Knowledge Base Search

**Request** (file_type not specified):
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "关于工会建设的文件",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (searches both 发文 and 收文):
```json
{
  "action": "complete",
  "answer": "在发文和收文知识库中找到以下关于工会建设的文件...",
  "sources": [
    {"dataset_id": "N000002_PublicDocDispatch", ...},
    {"dataset_id": "N000002_PublicDocReceive", ...}
  ],
  "metadata": {
    "search_mode": "dual",
    "collections_searched": ["N000002_PublicDocDispatch", "N000002_PublicDocReceive"]
  }
}
```

### Example 4: Meeting Minutes Query (会议纪要)

**Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "职工代表大会会议纪要",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (recognizes 会议纪要 as distinct document type):
```json
{
  "action": "complete",
  "answer": "找到以下职工代表大会会议纪要：\n1. 粤东科工会第一届第二次会员代表大会会议纪要\n2. 粤东科工会一届三次职工代表大会会议纪要",
  "sources": [...],
  "quality_feedback": "您的查询包含了准确的文档类型（会议纪要）和会议类型（职工代表大会）"
}
```

### Example 5: Colloquial Expression Mapping

**Request** (uses informal term):
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "三八节活动通知",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (maps "三八节" to "妇女节"):
```json
{
  "action": "complete",
  "answer": "根据您查询的妇女节活动通知，找到以下文档...",
  "sources": [...],
  "quality_feedback": "系统已将查询扩展为\"妇女节活动\"以匹配标准术语"
}
```

## Code Structure

### New Files

```
src/rag_service/
├── capabilities/
│   └── query_quality.py              # NEW: QueryQualityCapability
├── models/
│   └── query_quality.py              # NEW: Data models
├── services/
│   └── session_store.py              # NEW: Redis session store
└── config.py                          # MODIFY: Add query quality settings
```

### Key Classes

**QueryQualityCapability** (`src/rag_service/capabilities/query_quality.py`):
```python
class QueryQualityCapability(Capability[QueryQualityInput, QueryQualityOutput]):
    async def execute(self, input_data: QueryQualityInput) -> QueryQualityOutput:
        # 1. Get or create session
        # 2. Analyze query dimensions (LLM)
        # 3. Check for missing dimensions
        # 4. Return prompt or proceed to retrieval
```

**SessionStore** (`src/rag_service/services/session_store.py`):
```python
class SessionStore:
    async def get_session(self, trace_id: str) -> SessionState
    async def update_session(self, state: SessionState) -> None
    async def delete_session(self, trace_id: str) -> None
```

## Testing

### Run Unit Tests

```bash
cd tests/unit
uv run pytest test_query_quality.py -v
```

### Run Integration Tests

```bash
cd tests/integration
uv run pytest test_query_quality_e2e.py -v
```

### Run Contract Tests

```bash
cd tests/contract
uv run pytest test_query_quality_api.py -v
```

## Configuration

### Enable/Disable Query Quality

In request options:
```json
{
  "options": {
    "enable_query_quality": false  // Skip dimension analysis
  }
}
```

Or globally in environment:
```bash
ENABLE_QUERY_QUALITY=false
```

### Adjust Session Settings

```bash
# Session timeout (default: 900 seconds = 15 minutes)
QUERY_QUALITY_SESSION_TIMEOUT=1800  # 30 minutes

# Max turns (default: 10)
QUERY_QUALITY_MAX_TURNS=20
```

## Troubleshooting

### Redis Connection Issues

**Error**: `redis.exceptions.ConnectionError`

**Solution**:
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG
```

### Session Not Persisting

**Error**: Session state lost between requests

**Solution**:
- Ensure `X-Session-ID` header is included in follow-up requests
- Check Redis TTL is set correctly (default: 900 seconds)
- Verify Redis connection is stable

### LLM Not Returning Structured Output

**Error**: Dimension analysis fails to parse

**Solution**:
- Check Prompt Service has `query_dimension_analysis` template
- Verify LLM model supports JSON output
- Check LLM response logs in `logs/rag_service.log`

## Monitoring

### Key Metrics

- `query_quality_analysis_duration_seconds`: Time spent analyzing dimensions
- `query_quality_prompt_rate`: Percentage of queries that require prompts
- `query_quality_turn_count`: Distribution of conversation turns
- `query_quality_session_expiry_rate`: Percentage of sessions expiring

### Logs

Structured JSON logs include:
```json
{
  "trace_id": "abc-123",
  "event": "query_quality_analyzed",
  "missing_dimensions": ["year"],
  "quality_score": 0.5,
  "action": "prompt"
}
```

## Next Steps

1. Review [data-model.md](./data-model.md) for entity definitions
2. Review [contracts/query_quality_api.md](./contracts/query_quality_api.md) for API contract
3. Run `/speckit.tasks` to generate implementation tasks
