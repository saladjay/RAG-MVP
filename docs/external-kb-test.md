# External Knowledge Base Query Test

## Overview

This test module queries the external knowledge base service using questions from a JSONL file and records the results.

## File Format

The input JSONL file should have one JSON object per line with the following format:

```json
{"title_question": "Document Title###Query Question", "answear_list": ["answer1", "answer2"]}
```

- `title_question`: Combined field with document title and query separated by `###`
- `answear_list`: List of expected answers (for reference)

## Usage

### Method 1: Using the CLI command

```bash
# Install dependencies
uv sync

# Run the external KB test
uv run python -m e2e_test.cli external-kb \
    questions/fianl_version_qa.jsonl \
    --base-url http://localhost:8001 \
    --output external_kb_results.json \
    --comp-id N000131 \
    --file-type PublicDocDispatch \
    --search-type 1 \
    --topk 10
```

### Method 2: Using the standalone test script

```bash
# Set the external KB URL
export EXTERNAL_KB_BASE_URL=http://localhost:8001

# Run the test
uv run python tests/test_external_kb_query.py
```

## Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--base-url` | `-b` | External KB service base URL | (required) |
| `--output` | `-o` | Output file path for results | `external_kb_results.json` |
| `--comp-id` | `-c` | Company ID for queries | `N000131` |
| `--file-type` | `-f` | File type filter | `PublicDocDispatch` |
| `--search-type` | `-s` | Search type (0=vector, 1=fulltext, 2=hybrid) | `1` |
| `--topk` | `-k` | Number of results to retrieve | `10` |

## Output Format

The output JSON file contains:

```json
{
  "total_tests": 5,
  "successful": 5,
  "failed": 0,
  "results": [
    {
      "title": "Document Title",
      "query": "Query Question",
      "expected_answers": ["answer1", "answer2"],
      "chunk_count": 10,
      "chunks": [
        {
          "id": "chunk_id",
          "chunk_id": "chunk_id",
          "content": "Chunk content...",
          "metadata": {
            "title": "Document title",
            "document_name": "Document name",
            "score": 0.95,
            "position": 1
          },
          "score": 0.95,
          "source_doc": "Document name"
        }
      ],
      "success": true,
      "error": null
    }
  ]
}
```

## Environment Variables

- `EXTERNAL_KB_BASE_URL`: Base URL of the external knowledge base service

## Example

```bash
# Test with the sample questions file
uv run python -m e2e_test.cli external-kb \
    questions/fianl_version_qa.jsonl \
    --base-url http://localhost:8001
```

This will:
1. Read all questions from `questions/fianl_version_qa.jsonl`
2. Parse each `title_question` field to extract the query
3. Query the external KB service
4. Save results to `external_kb_results.json`
