# E2E Test Framework - Quick Start Guide

**Feature**: 002-e2e-test-interface
**Date**: 2026-03-30
**Status**: Final

---

## Overview

The E2E Test Framework validates RAG Service responses by:
1. Reading test cases from local files (JSON/CSV/YAML/Markdown)
2. Querying the RAG Service with each test question
3. Comparing actual responses against expected results
4. Generating detailed test reports

---

## Prerequisites

### Required

- **Python 3.11+**
- **uv** (Python package manager)
- **RAG Service** running and accessible

### RAG Service Setup

```bash
# Start RAG Service (if not already running)
cd src/rag_service
uv run uvicorn main:app --reload --port 8000

# Verify it's running
curl http://localhost:8000/health
```

---

## Installation

```bash
# Navigate to project root
cd D:/project/OA/svn/代码组件

# Install E2E test framework dependencies
uv sync --extra dev

# Or install specific package
uv add httpx pydantic pyyaml rich
```

---

## Creating Your First Test

### Option 1: JSON Format (Recommended)

Create `tests/basic.test.json`:

```json
[
  {
    "id": "test_rag_basics",
    "question": "What is the RAG Service?",
    "expected_answer": "RAG Service combines vector search with LLM generation.",
    "source_docs": ["doc_rag_intro"],
    "tags": ["basic"]
  }
]
```

### Option 2: CSV Format

Create `tests/basic.test.csv`:

```csv
id,question,expected_answer,source_docs,tags
test_rag_basics,What is the RAG Service?,RAG Service combines vector search with LLM generation.,doc_rag_intro,basic
```

### Option 3: YAML Format

Create `tests/basic.test.yaml`:

```yaml
- id: test_rag_basics
  question: What is the RAG Service?
  expected_answer: RAG Service combines vector search with LLM generation.
  source_docs:
    - doc_rag_intro
  tags:
    - basic
```

### Option 4: Markdown Format

Create `tests/basic.test.md`:

```markdown
# Basic E2E Tests

```yaml
id: test_rag_basics
question: What is the RAG Service?
expected_answer: RAG Service combines vector search with LLM generation.
source_docs:
  - doc_rag_intro
tags:
  - basic
```
```

---

## Running Tests

### Basic Usage

```bash
# Run all tests in a file
uv run python -m e2e_test.cli run tests/basic.test.json

# Run with verbose output
uv run python -m e2e_test.cli run tests/basic.test.json --verbose

# Run with custom RAG Service URL
uv run python -m e2e_test.cli run tests/basic.test.json --url http://localhost:8001

# Run multiple files
uv run python -m e2e_test.cli run tests/*.test.json
```

### Output Formats

```bash
# Console output (default)
uv run python -m e2e_test.cli run tests/basic.test.json

# JSON output for CI/CD
uv run python -m e2e_test.cli run tests/basic.test.json --format json

# HTML report
uv run python -m e2e_test.cli run tests/basic.test.json --format html --output report.html
```

---

## Understanding Test Results

### Console Output Example

```
╭─────────────────────────────────────────────────────────────────╮
│                    E2E Test Report                              │
╰─────────────────────────────────────────────────────────────────╯

Test Suite: basic.test.json
──────────────────────────────────────────────────────────────────

✅ test_rag_basics                          PASSED   Similarity: 0.92
   Question: What is the RAG Service?
   Source docs match: ✓

──────────────────────────────────────────────────────────────────

Summary
─────────────
Total Tests: 1    Passed: 1    Failed: 0    Errors: 0
Pass Rate: 100%   Avg Similarity: 0.92   Time: 1.2s
```

### JSON Output Example

```json
{
  "suite_name": "basic.test.json",
  "total_tests": 1,
  "passed": 1,
  "failed": 0,
  "errors": 0,
  "similarity_avg": 0.92,
  "total_latency_ms": 1200,
  "results": [
    {
      "test_id": "test_rag_basics",
      "status": "passed",
      "similarity_score": 0.92,
      "source_docs_match": true,
      "latency_ms": 1200
    }
  ]
}
```

---

## Configuration

### Environment Variables

```bash
# .env file or export in shell
E2E_TEST_RAG_SERVICE_URL=http://localhost:8000
E2E_TEST_TIMEOUT_SECONDS=30
E2E_TEST_SIMILARITY_THRESHOLD=0.7
E2E_TEST_MAX_CONCURRENT=1
E2E_TEST_OUTPUT_FORMAT=console
```

### CLI Flags

```bash
uv run python -m e2e_test.cli run tests.test.json \
  --url http://localhost:8000 \
  --timeout 60 \
  --threshold 0.8 \
  --format json \
  --output results.json \
  --verbose
```

---

## Advanced Examples

### Test with Multiple Tags

```json
[
  {
    "id": "test_rag_basics",
    "question": "What is the RAG Service?",
    "tags": ["basic", "smoke", "regression"]
  },
  {
    "id": "test_rag_advanced",
    "question": "How does vector search work?",
    "tags": ["advanced", "vector", "regression"]
  }
]
```

### Filter by Tags

```bash
# Run only smoke tests
uv run python -m e2e_test.cli run tests.test.json --tag smoke

# Run multiple tag patterns
uv run python -m e2e_test.cli run tests.test.json --tag smoke --tag regression

# Exclude tags
uv run python -m e2e_test.cli run tests.test.json --exclude-tag integration
```

### Test with Expected Documents

```json
{
  "id": "test_doc_retrieval",
  "question": "What are the system architecture components?",
  "expected_answer": "The system consists of API Gateway, RAG Service, and Vector Database.",
  "source_docs": ["doc_architecture", "doc_components"],
  "metadata": {
    "min_docs": 2,
    "requires_specific_docs": true
  }
}
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Start RAG Service
        run: |
          cd src/rag_service
          uv run uvicorn main:app --port 8000 &
          sleep 10

      - name: Run E2E tests
        run: |
          uv run python -m e2e_test.cli run tests/*.test.json --format json --output results.json

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: e2e-results
          path: results.json
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    stages {
        stage('Install') {
            steps {
                sh 'uv sync --extra dev'
            }
        }
        stage('Start RAG Service') {
            steps {
                sh 'cd src/rag_service && uv run uvicorn main:app --port 8000 &'
                sleep(time: 10, unit: 'SECONDS')
            }
        }
        stage('Run E2E Tests') {
            steps {
                sh 'uv run python -m e2e_test.cli run tests/*.test.json --format json --output results.json'
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'results.json'
        }
    }
}
```

---

## Troubleshooting

### Common Issues

#### Issue: "Connection refused"

```
ERROR: Cannot connect to RAG Service at http://localhost:8000
```

**Solution**: Ensure RAG Service is running:
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

#### Issue: "Timeout waiting for response"

```
ERROR: Request timeout after 30 seconds
```

**Solution**: Increase timeout or check RAG Service performance:
```bash
uv run python -m e2e_test.cli run tests.test.json --timeout 60
```

#### Issue: "Low similarity score"

```
⚠️  test_id: FAILED - Similarity: 0.45 (threshold: 0.7)
```

**Solution**:
1. Review `expected_answer` - is it realistic?
2. Check if RAG Service has relevant documents
3. Adjust threshold: `--threshold 0.5`
4. Consider removing `expected_answer` if exact match isn't critical

#### Issue: "Source docs don't match"

```
⚠️  test_id: FAILED - Expected docs: [doc_a], Got: [doc_b]
```

**Solution**:
1. Verify document IDs in knowledge base
2. Check if documents are indexed in Milvus
3. Update `source_docs` or remove validation

---

## Project Structure

```
src/e2e_test/
├── __init__.py
├── cli.py                 # CLI entry point
├── parsers/               # File parsers
│   ├── json_parser.py
│   ├── csv_parser.py
│   ├── yaml_parser.py
│   └── md_parser.py
├── runners/               # Test execution
│   └── test_runner.py
├── comparators/           # Result comparison
│   ├── similarity.py
│   └── validator.py
├── reporters/             # Report generation
│   ├── console.py
│   └── json_report.py
└── clients/               # RAG API client
    └── rag_client.py

tests/
├── basic.test.json
├── advanced.test.yaml
└── regression.test.csv
```

---

## Next Steps

1. **Create test suite**: Add test cases covering your RAG Service functionality
2. **Configure thresholds**: Adjust similarity thresholds based on your use case
3. **Integrate with CI**: Add E2E tests to your CI/CD pipeline
4. **Monitor results**: Track similarity scores and pass rates over time
5. **Extend functionality**: Add custom reporters or validators as needed

---

**Status**: ✅ Quick start guide complete
