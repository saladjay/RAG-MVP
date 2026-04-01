# External Knowledge Base Configuration

## Overview

The RAG Service can query an external HTTP knowledge base service to retrieve relevant documents and chunks. This guide shows you how to configure it.

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# External HTTP Knowledge Base Configuration
EXTERNAL_KB_BASE_URL=http://128.23.77.226:9981
EXTERNAL_KB_ENDPOINT=/ai-parsing-file/ai/file-knowledge/queryKnowledge
EXTERNAL_KB_TIMEOUT=30
EXTERNAL_KB_MAX_RETRIES=3
EXTERNAL_KB_ENABLED=true
```

### Variable Descriptions

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `EXTERNAL_KB_BASE_URL` | Base URL of the external KB service | `http://128.23.77.226:9981` | (required) |
| `EXTERNAL_KB_ENDPOINT` | API endpoint path | `/ai-parsing-file/ai/file-knowledge/queryKnowledge` | `/ai-parsing-file/ai/file-knowledge/queryKnowledge` |
| `EXTERNAL_KB_TIMEOUT` | Request timeout in seconds | `30` | `30` |
| `EXTERNAL_KB_MAX_RETRIES` | Maximum retry attempts for failed requests | `3` | `3` |
| `EXTERNAL_KB_ENABLED` | Enable/disable external KB integration | `true` | `true` |

## API Request Format

The external KB client sends requests in this format:

```json
{
  "query": "search query text",
  "compId": "N000131",
  "fileType": "PublicDocDispatch",
  "docDate": "",
  "keyword": "",
  "topk": 10,
  "scoreMin": 0.0,
  "searchType": 1
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Primary search query |
| `compId` | string | Yes | Company unique code (e.g., N000131) |
| `fileType` | string | Yes | File type: `PublicDocReceive` or `PublicDocDispatch` |
| `docDate` | string | No | Document date filter |
| `keyword` | string | No | Secondary search keyword |
| `topk` | int | No | Number of results to return (default: 10) |
| `scoreMin` | float | No | Minimum score threshold (default: 0.0) |
| `searchType` | int | Yes | Search type: 0=vector, 1=fulltext, 2=hybrid |

## Expected Response Format

The external KB service should return responses in this format:

```json
{
  "result": [
    {
      "metadata": {
        "score": 0.95,
        "position": 1,
        "_source": "data_source_name",
        "dataset_id": "dataset_123",
        "dataset_name": "My Dataset",
        "document_id": "doc_456",
        "document_name": "Document.pdf",
        "data_source_type": "file",
        "segment_id": "seg_789",
        "retriever_from": "external_kb",
        "doc_metadata": {
          "author": "John Doe",
          "created_date": "2025-01-01"
        }
      },
      "title": "Document Title",
      "content": "The actual chunk content text..."
    }
  ]
}
```

## Testing the Configuration

### 1. Test with Mock Mode (No Service Required)

```bash
uv run python -m e2e_test.cli external-kb \
    questions/fianl_version_qa.jsonl \
    --base-url http://localhost:8001 \
    --mock \
    --limit 5
```

### 2. Test with Real Service

```bash
# Make sure your .env file has EXTERNAL_KB_BASE_URL set
uv run python -m e2e_test.cli external-kb \
    questions/fianl_version_qa.jsonl \
    --base-url http://128.23.77.226:9981 \
    --output results.json \
    --limit 10
```

### 3. Manual API Test with curl

```bash
curl -X POST "http://128.23.77.226:9981/ai-parsing-file/ai/file-knowledge/queryKnowledge" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "compId": "N000131",
    "fileType": "PublicDocDispatch",
    "searchType": 1,
    "topk": 5
  }'
```

## Troubleshooting

### Service Not Responding (502 Bad Gateway)

1. **Check if service is running:**
   ```bash
   curl http://your-service-url:port/health
   ```

2. **Check network connectivity:**
   ```bash
   ping your-service-url
   ```

3. **Verify the endpoint path is correct**

### Timeout Errors

Increase `EXTERNAL_KB_TIMEOUT` in your `.env` file:
```bash
EXTERNAL_KB_TIMEOUT=60
```

### Connection Refused

1. Check firewall settings
2. Verify the service port is accessible
3. Check if the service is binding to the correct interface (0.0.0.0 vs localhost)

### Authentication Issues

If your external KB requires authentication, you may need to modify `ExternalKBClient` to add headers. Check the service documentation for required authentication methods.

## Example .env File

```bash
# RAG Service Configuration

# External Knowledge Base
EXTERNAL_KB_BASE_URL=http://128.23.77.226:9981
EXTERNAL_KB_ENDPOINT=/ai-parsing-file/ai/file-knowledge/queryKnowledge
EXTERNAL_KB_TIMEOUT=30
EXTERNAL_KB_MAX_RETRIES=3
EXTERNAL_KB_ENABLED=true

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

## Next Steps

1. Set up your `.env` file with the correct values
2. Test connectivity with curl
3. Run the E2E test with `--mock` flag to verify the framework
4. Run with real service to validate the integration
