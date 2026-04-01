# Quickstart Guide: Prompt Management Service

**Feature**: 003-prompt-service | **Date**: 2026-03-23

## Overview

This guide helps you integrate with the Prompt Management Service in different scenarios. Choose the scenario that matches your use case.

---

## Scenario 1: Backend Engineer - Simple Prompt Retrieval

**Use Case**: Your business code needs prompts but shouldn't know about Langfuse.

### Step 1: Install the SDK

```bash
uv add prompt-service-client
```

### Step 2: Initialize the Client

```python
from prompt_service import PromptClient

client = PromptClient(
    base_url="http://localhost:8000"  # or your service URL
)
```

### Step 3: Retrieve Prompts

```python
# Simple retrieval
response = client.get_prompt("financial_analysis")
prompt_text = response.content

# With variables
response = client.get_prompt(
    "financial_analysis",
    variables={"input": "Analyze AAPL stock"}
)
prompt_text = response.content

# Pass to LLM
llm_response = openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt_text}]
)
```

**That's it!** The service handles:
- Prompt versioning (you always get the active version)
- A/B testing (automatically assigned if active)
- Variable interpolation
- Context and retrieved_docs formatting

---

## Scenario 2: Product Manager - Creating and Editing Prompts

**Use Case**: You need to update prompts without code deployment.

### Step 1: Access the Management UI

Navigate to: `http://your-service:3000` (React management UI)

Or use the API directly:

```bash
# List existing prompts
curl http://your-service:8000/api/v1/prompts

# View a specific prompt
curl http://your-service:8000/api/v1/prompts/financial_analysis
```

### Step 2: Create a New Prompt

```bash
curl -X POST http://your-service:8000/api/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "customer_support",
    "name": "Customer Support Response",
    "description": "Generate helpful customer support responses",
    "sections": [
      {
        "name": "角色",
        "content": "你是一个友好的客服代表",
        "is_required": true,
        "order": 0
      },
      {
        "name": "任务",
        "content": "回答用户的问题",
        "is_required": true,
        "order": 1
      },
      {
        "name": "约束",
        "content": "- 保持友好和专业\n- 解决用户问题",
        "is_required": true,
        "order": 2
      },
      {
        "name": "输出格式",
        "content": "简洁的段落形式",
        "is_required": true,
        "order": 3
      }
    ],
    "variables": {
      "user_question": {
        "name": "user_question",
        "description": "The customer's question",
        "type": "string",
        "is_required": true
      }
    },
    "tags": ["support", "customer"],
    "is_published": true
  }'
```

### Step 3: Edit and Publish

```bash
# Update the prompt (creates new version)
curl -X PUT http://your-service:8000/api/v1/prompts/customer_support \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Generate helpful customer support responses (updated)",
    "sections": [...],  # updated sections
    "change_description": "Added empathy constraint"
  }'
```

**The new prompt is immediately active!** No deployment needed.

---

## Scenario 3: Data Scientist - A/B Testing

**Use Case**: You want to compare two prompt versions.

### Step 1: Create an A/B Test

```bash
curl -X POST http://your-service:8000/api/v1/ab-tests \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "customer_support",
    "name": "Test: Empathetic vs Concise",
    "description": "Compare empathetic vs concise responses",
    "variants": [
      {
        "variant_id": "empathetic",
        "template_version": 1,
        "traffic_percentage": 50,
        "is_control": true
      },
      {
        "variant_id": "concise",
        "template_version": 2,
        "traffic_percentage": 50,
        "is_control": false
      }
    ],
    "success_metric": "user_rating",
    "min_sample_size": 500
  }'
```

### Step 2: Wait for Data Collection

The service automatically:
- Routes traffic based on `user_id` hash (consistent assignment)
- Tracks impressions and metrics
- Records which variant was used for each trace

### Step 3: Check Results

```bash
curl http://your-service:8000/api/v1/ab-tests/ab_test_123
```

Response:
```json
{
  "variants": [
    {
      "variant_id": "empathetic",
      "impressions": 500,
      "user_rating": 4.2
    },
    {
      "variant_id": "concise",
      "impressions": 500,
      "user_rating": 4.5
    }
  ],
  "recommendation": {
    "winner": "concise",
    "confidence": "high"
  }
}
```

### Step 4: Select Winner

```bash
curl -X POST http://your-service:8000/api/v1/ab-tests/ab_test_123/winner \
  -H "Content-Type: application/json" \
  -d '{
    "variant_id": "concise",
    "reason": "Higher user rating"
  }'
```

The winning version becomes the new active prompt.

---

## Scenario 4: AI Engineer - Debugging with Traces

**Use Case**: You need to debug why a prompt produced unexpected output.

### Step 1: Capture the trace_id

When your code calls the service:

```python
response = client.get_prompt("financial_analysis", variables={...})
trace_id = response.trace_id  # Save this!
```

### Step 2: View the Trace

```bash
curl http://your-service:8000/api/v1/analytics/traces?trace_id={trace_id}
```

Or use the Management UI to view:
- Exact prompt version used
- Variable values passed
- Context and retrieved_docs
- Model response
- Performance metrics

### Step 3: Analyze Patterns

View aggregated analytics:

```bash
curl "http://your-service:8000/api/v1/analytics/prompts/financial_analysis?start_date=2026-03-20&end_date=2026-03-23"
```

Response shows:
- Usage statistics
- Error rates
- Latency percentiles
- Top error patterns

---

## Scenario 5: Tester - Regression Testing

**Use Case**: You need consistent prompts for automated testing.

### Option 1: Version Pinning

```python
from prompt_service import PromptClient, PromptOptions

client = PromptClient(base_url="http://localhost:8000")

# Always use version 5 for tests
response = client.get_prompt(
    "financial_analysis",
    variables={"input": "test input"},
    options=PromptOptions(version_id=5)
)

assert response.version_id == 5
assert expected_output in response.content
```

### Option 2: Mock Mode

```python
client = PromptClient(
    base_url="http://localhost:8000",
    mock_mode=True,
    mock_responses={
        "financial_analysis": "Fixed prompt for testing"
    }
)

# Returns mock content, no service call
response = client.get_prompt("financial_analysis")
assert "Fixed prompt" in response.content
```

---

## Local Development

### Running the Service Locally

```bash
# Clone the repo
git clone <repo-url>
cd 003-prompt-service

# Install dependencies with uv
uv sync

# Set environment variables
export LANGFUSE_PUBLIC_KEY="your-key"
export LANGFUSE_SECRET_KEY="your-secret"
export LANGFUSE_HOST="https://langfuse.cloud"

# Run the service
uv run uvicorn prompt_service.main:app --reload --port 8000
```

### Running the Management UI Locally

```bash
cd ui
npm install
npm start
# Navigate to http://localhost:3000
```

### Seeding Test Data

```bash
# Create sample prompts
uv run python scripts/seed_prompts.py

# Create sample A/B test
uv run python scripts/seed_ab_test.py
```

---

## Docker Deployment

### Using Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  prompt-service:
    image: prompt-service:latest
    ports:
      - "8000:8000"
    environment:
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - LANGFUSE_HOST=https://langfuse.cloud
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

```bash
docker-compose up -d
```

---

## Troubleshooting

### "Prompt not found" Error

**Cause**: Template doesn't exist or isn't published.

**Solution**:
```python
# List available prompts
prompts = client.list_prompts()
print([p.template_id for p in prompts])
```

### "Variable validation failed" Error

**Cause**: Missing or invalid variable values.

**Solution**:
```python
# Check required variables
info = client.get_prompt_info("financial_analysis")
print(info.variables)  # See what's required

# Provide all required variables
response = client.get_prompt(
    "financial_analysis",
    variables={"input": "required value"}  # Include all required
)
```

### "Service unavailable" Error

**Cause**: Can't connect to prompt service.

**Solution**:
1. Check service is running: `curl http://localhost:8000/health`
2. Enable fallback mode:
   ```python
   client = PromptClient(
       base_url="http://localhost:8000",
       enable_fallback=True
   )
   ```

### Slow Prompt Retrieval

**Cause**: Not using cache.

**Solution**:
```python
client = PromptClient(
    base_url="http://localhost:8000",
    enable_cache=True,  # Enable caching
    cache_ttl=300       # 5 minutes
)
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROMPT_SERVICE_URL` | Service base URL | `http://localhost:8000` |
| `PROMPT_SERVICE_API_KEY` | API key (future) | None |
| `PROMPT_SERVICE_TIMEOUT` | Request timeout (seconds) | 10 |
| `PROMPT_SERVICE_ENABLE_CACHE` | Enable local cache | `true` |
| `PROMPT_SERVICE_CACHE_TTL` | Cache TTL (seconds) | 300 |
| `LANGFUSE_PUBLIC_KEY` | Langfuse key | Required |
| `LANGFUSE_SECRET_KEY` | Langfuse secret | Required |
| `LANGFUSE_HOST` | Langfuse host | `https://langfuse.cloud` |

---

## Next Steps

1. **Read the API Contract**: `contracts/api-contract.md`
2. **Read the Client SDK Contract**: `contracts/client-contract.md`
3. **Explore the Data Model**: `data-model.md`
4. **Review Technical Decisions**: `research.md`

---

**Document Version**: 1.0 | **Last Updated**: 2026-03-23
