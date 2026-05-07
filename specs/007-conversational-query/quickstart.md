# Quickstart: Conversational Query Enhancement Module

**Feature**: 007-conversational-query
**Date**: 2026-04-10

## Overview

The Conversational Query Enhancement Module enables multi-turn dialogue for query refinement, colloquial expression recognition, and intelligent query expansion. The system maintains conversation context, maps informal language to formal terminology, and generates multiple query variations for improved retrieval.

## Prerequisites

1. **Dependencies**:
   - Python 3.11+
   - Redis server (for conversation state)
   - Prompt Service (feature 003)
   - LiteLLM gateway or compatible LLM endpoint
   - RAG QA Pipeline (feature 005)

2. **Environment Variables** (add to `.env`):

```bash
# Redis for conversation state
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Session timeout (seconds)
CONVERSATIONAL_SESSION_TIMEOUT=900

# Max conversation turns
CONVERSATIONAL_MAX_TURNS=10

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

### Example 1: Multi-Turn Conversation with Missing Information

**Request** (initial):
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "我想找关于安全的规定",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (prompting for year):
```json
{
  "action": "prompt",
  "message": "请问您需要查找哪一年的安全规定？",
  "missing_slots": ["year"],
  "belief_state": {
    "trace_id": "trace-123",
    "turn_count": 1,
    "accumulated_slots": {
      "domain": "safety",
      "topic": "安全规定"
    }
  }
}
```

**Follow-up Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: trace-123" \
  -d '{
    "query": "2024年的",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (proceeds with generation):
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "2024年安全生产相关规定有哪些？",
    "q2": "2024年安全生产制度包括哪些内容？",
    "q3": "2024年关于安全生产的规定文件",
    "must_include": ["2024", "安全生产", "规定"],
    "keywords": ["2024", "安全生产", "规定", "制度", "办法", "细则", "管理"]
  }
}
```

### Example 2: Colloquial Expression Recognition

**Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "有没有关于防火的规定",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (with mapping applied):
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "消防管理相关规定有哪些？",
    "q2": "消防安全制度包括什么内容？",
    "q3": "关于消防的规定和标准"
  },
  "applied_mappings": {
    "防火": "消防"
  },
  "extracted_elements": {
    "domain": "safety",
    "confidence": "high"
  }
}
```

### Example 3: Finance Domain Query with City

**Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "北京的住宿标准是多少",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (domain-specific generation):
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "北京住宿报销标准是多少？",
    "q2": "北京市酒店费用报销上限是多少？",
    "q3": "京地区住宿费用标准如何规定？"
  },
  "must_include": ["北京", "住宿", "报销", "标准"],
  "keywords": ["北京", "京", "住宿", "酒店", "住宿费", "报销", "标准", "额度", "上限"],
  "domain_context": "business_query:finance"
}
```

### Example 4: Meeting Query with 2025 Updates

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

**Response** (recognizes meeting type):
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "职工代表大会会议纪要有哪些内容？",
    "q2": "职工代表大会会议纪要包含哪些决议？",
    "q3": "关于职工代表大会的会议纪要文件"
  },
  "must_include": ["职工代表大会", "会议纪要"],
  "keywords": ["职工代表大会", "职代会", "会议纪要", "会议记录", "决议", "工会"],
  "domain_context": "business_query:union"
},
"applied_mappings": {
  "职代会": "职工代表大会"
}
```

### Example 5: Meta Info Query

**Request**:
```bash
curl -X POST http://localhost:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "公司共有多少份制度",
    "context": {
      "company_id": "N000002"
    }
  }'
```

**Response** (meta info domain):
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "公司现行制度目录有哪些？",
    "q2": "公司共有多少份制度文件？",
    "q3": "如何检索公司所有制度？"
  },
  "domain_context": "meta_info"
}
```

## Code Structure

### New Files

```
src/rag_service/
├── capabilities/
│   └── conversational_query.py       # NEW: ConversationalQueryCapability
├── models/
│   └── conversational_query.py       # NEW: Data models
├── services/
│   ├── belief_state_store.py         # NEW: Redis belief state store
│   └── colloquial_mapper.py          # NEW: Colloquial term mapping
└── config.py                          # MODIFY: Add conversational query settings
```

### Key Classes

**ConversationalQueryCapability** (`src/rag_service/capabilities/conversational_query.py`):
```python
class ConversationalQueryCapability(Capability[ConversationalQueryInput, ConversationalQueryOutput]):
    async def execute(self, input_data: ConversationalQueryInput) -> ConversationalQueryOutput:
        # 1. Get or create belief state
        # 2. Extract slots from query (LLM)
        # 3. Detect follow-up queries
        # 4. Merge slots with belief state
        # 5. Determine action (proceed/prompt/complete)
        # 6. Generate queries if proceeding
```

**BeliefStateStore** (`src/rag_service/services/belief_state_store.py`):
```python
class BeliefStateStore:
    async def get_state(self, trace_id: str) -> BeliefState
    async def update_state(self, state: BeliefState) -> None
    async def delete_state(self, trace_id: str) -> None
```

**ColloquialMapper** (`src/rag_service/services/colloquial_mapper.py`):
```python
class ColloquialMapper:
    def map_term(self, term: str, domain: Optional[str] = None) -> List[str]
    def load_mappings(self, config_path: str) -> None
```

## Testing

### Run Unit Tests

```bash
cd tests/unit
uv run pytest test_conversational_query.py -v
```

### Run Integration Tests

```bash
cd tests/integration
uv run pytest test_conversational_query_e2e.py -v
```

### Run Contract Tests

```bash
cd tests/contract
uv run pytest test_conversational_query_api.py -v
```

## Configuration

### Enable/Disable Conversational Query

In request options:
```json
{
  "options": {
    "enable_conversational_query": false
  }
}
```

Or globally in environment:
```bash
ENABLE_CONVERSATIONAL_QUERY=false
```

### Adjust Session Settings

```bash
# Session timeout (default: 900 seconds = 15 minutes)
CONVERSATIONAL_SESSION_TIMEOUT=1800  # 30 minutes

# Max turns (default: 10)
CONVERSATIONAL_MAX_TURNS=20
```

### Colloquial Mappings Configuration

Create a JSON configuration file:
```json
{
  "mappings": [
    {
      "colloquial": "防火",
      "formal": ["消防"],
      "domain": "safety"
    },
    {
      "colloquial": "会议记录",
      "formal": ["会议纪要"],
      "domain": null
    }
  ]
}
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

**Error**: Slot extraction fails to parse

**Solution**:
- Check Prompt Service has slot extraction templates
- Verify LLM model supports JSON output
- Check LLM response logs in `logs/rag_service.log`

### Query Generation Fails

**Error**: No queries generated

**Solution**:
- Verify belief state has required slots
- Check domain classification succeeded
- Ensure query generation templates exist in Prompt Service

## Monitoring

### Key Metrics

- `conversational_slot_extraction_duration_seconds`: Time spent extracting slots
- `conversational_query_generation_duration_seconds`: Time spent generating queries
- `conversational_turn_count`: Distribution of conversation turns
- `conversational_session_expiry_rate`: Percentage of sessions expiring
- `conversational_colloquial_mapping_rate`: Percentage of queries with mappings applied

### Logs

Structured JSON logs include:
```json
{
  "trace_id": "abc-123",
  "event": "slots_extracted",
  "query_type": "business_query",
  "domain": "safety",
  "confidence": "high",
  "turn_count": 2
}
```

## Next Steps

1. Review [data-model.md](./data-model.md) for entity definitions
2. Review [contracts/conversational_query_api.md](./contracts/conversational_query_api.md) for API contract
3. Run `/speckit.tasks` to generate implementation tasks
