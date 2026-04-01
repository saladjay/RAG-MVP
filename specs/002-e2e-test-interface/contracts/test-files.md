# Test File Format Contracts

**Feature**: 002-e2e-test-interface
**Date**: 2026-03-30
**Status**: Final

---

## Overview

This document specifies the contract for test file formats supported by the E2E Test Framework. All test files must conform to one of the following formats to be successfully parsed and executed.

---

## 1. JSON Format

### File Extension
`.json` (recommended: `.test.json` or `tests.json`)

### Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "E2E Test Cases",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["id", "question"],
    "properties": {
      "id": {
        "type": "string",
        "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
        "description": "Unique test case identifier"
      },
      "question": {
        "type": "string",
        "minLength": 1,
        "description": "Question to submit to RAG Service"
      },
      "expected_answer": {
        "type": "string",
        "maxLength": 10000,
        "description": "Expected answer for similarity comparison"
      },
      "source_docs": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Expected document IDs to be retrieved"
      },
      "tags": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Tags for grouping and filtering"
      },
      "metadata": {
        "type": "object",
        "description": "Additional metadata"
      }
    }
  }
}
```

### Example

```json
[
  {
    "id": "test_basic_query",
    "question": "What is the RAG Service?",
    "expected_answer": "RAG Service is a retrieval-augmented generation service that combines vector search with LLM generation.",
    "source_docs": ["doc_rag_intro", "doc_rag_architecture"],
    "tags": ["basic", "rag"],
    "metadata": {
      "priority": "high",
      "author": "team-ai"
    }
  },
  {
    "id": "test_empty_knowledge_base",
    "question": "What happens when knowledge base is empty?",
    "tags": ["edge-case"]
  }
]
```

---

## 2. CSV Format

### File Extension
`.csv` (recommended: `.test.csv` or `tests.csv`)

### Column Definition

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| `id` | ✅ | string | Unique test identifier (Python variable name) |
| `question` | ✅ | string | Question to submit (may contain quotes) |
| `expected_answer` | ⚠️ | string | Expected answer (leave empty if not needed) |
| `source_docs` | ⚠️ | string | Comma-separated document IDs |
| `tags` | ❌ | string | Comma-separated tags |

### Rules

- **Header row**: Must include at least `id` and `question` columns
- **Encoding**: UTF-8
- **Delimiter**: Comma (`,`)
- **Quote character**: Double quote (`"`)
- **Empty values**: Use empty string or skip column

### Example

```csv
id,question,expected_answer,source_docs,tags
test_basic_query,What is the RAG Service?,RAG Service combines vector search with LLM generation.,doc_rag_intro;doc_rag_architecture,basic;rag
test_empty_knowledge_base,"What happens when knowledge base is empty?",,,edge-case
test_multiline,"Can you explain ""retrieval-augmented generation"" in detail?",,doc_rag_details,advanced
```

---

## 3. YAML Format

### File Extension
`.yaml` or `.yml` (recommended: `.test.yaml` or `tests.yaml`)

### Schema

```yaml
# Root is a list of test objects
- id: <string>           # Required: Python variable name
  question: <string>     # Required: Non-empty question
  expected_answer: <string?>   # Optional
  source_docs:           # Optional: List of strings
    - <doc_id>
    - <doc_id>
  tags:                  # Optional: List of strings
    - <tag>
  metadata:              # Optional: Arbitrary key-value pairs
    key: value
```

### Example

```yaml
# Basic test cases
- id: test_basic_query
  question: What is the RAG Service?
  expected_answer: RAG Service is a retrieval-augmented generation service.
  source_docs:
    - doc_rag_intro
    - doc_rag_architecture
  tags:
    - basic
    - rag
  metadata:
    priority: high

# Minimal test case (no expected answer)
- id: test_empty_knowledge_base
  question: What happens when knowledge base is empty?
  tags:
    - edge-case

# Test with complex metadata
- id: test_multilingual
  question: Comment fonctionne le service RAG?
  expected_answer: Le service RAG combine la recherche vectorielle avec la génération LLM.
  tags:
    - i18n
    - french
  metadata:
    language: fr
    locale: fr-FR
```

---

## 4. Markdown Format

### File Extension
`.md` (recommended: `.test.md` or `tests.md`)

### Format Specification

Each test case is defined as a code block with YAML frontmatter:

```markdown
<!-- Test case identifier as comment -->

<optional descriptive text>

```yaml
id: test_identifier
question: The question text
expected_answer: Optional expected answer
source_docs:
  - doc_id1
  - doc_id2
tags:
  - tag1
  - tag2
metadata:
  key: value
```

<optional description or notes>

---
```

### Rules

- **Test delimiter**: Three or more dashes (`---`) between test cases
- **Code block language**: Must be `yaml` (for syntax highlighting)
- **Comment lines**: Lines starting with `<!--` are ignored
- **Empty lines**: Allowed between sections

### Example

```markdown
# E2E Test Suite for RAG Service

<!-- Test Case 1: Basic Query -->

Basic test to verify RAG Service responds with relevant information.

```yaml
id: test_basic_query
question: What is the RAG Service?
expected_answer: RAG Service is a retrieval-augmented generation service that combines vector search with LLM generation.
source_docs:
  - doc_rag_intro
  - doc_rag_architecture
tags:
  - basic
  - rag
```

This test validates the basic RAG functionality.

---

<!-- Test Case 2: Empty Knowledge Base Edge Case -->

```yaml
id: test_empty_knowledge_base
question: What happens when knowledge base is empty?
tags:
  - edge-case
  - error-handling
metadata:
  expected_behavior: should_return_fallback_response
```

Tests error handling when no documents are available.

---

<!-- Test Case 3: Multilingual Support -->

```yaml
id: test_multilingual_french
question: Comment fonctionne le service RAG ?
expected_answer: Le service RAG utilise la recherche sémantique pour trouver des documents pertinents.
tags:
  - i18n
  - french
metadata:
  language: fr
```
```

---

## 5. Parser Behavior Contract

### Common Rules (All Formats)

| Rule | Description |
|------|-------------|
| **ID Uniqueness** | Test IDs must be unique within a single file |
| **ID Validation** | IDs must match `^[a-zA-Z_][a-zA-Z0-9_]*$` (Python variable name) |
| **Question Required** | Every test case must have a non-empty question |
| **Empty Optional Fields** | Missing optional fields are treated as empty/default |
| **Unknown Fields** | Unknown fields in metadata are preserved as-is |

### Error Handling

| Error Type | Behavior |
|------------|----------|
| **Invalid JSON/YAML** | Parser error with line/column information |
| **Missing required field** | Validation error listing missing fields |
| **Invalid ID format** | Validation error with regex explanation |
| **Duplicate ID** | Validation error with conflicting line numbers |
| **Empty question** | Validation error (question is required) |
| **File not found** | File not found error with path |
| **Encoding error** | Encoding error with suggested fix (try UTF-8) |

### Validation Order

1. **File existence** → File not found
2. **Format parsing** → Parse error (JSON/YAML/CSV/MD)
3. **Schema validation** → Missing/invalid fields
4. **Business rules** → ID uniqueness, question non-empty

---

## 6. Test File Naming Convention

### Recommended Patterns

| Pattern | Usage |
|---------|-------|
| `tests.json` | General test suite |
| `<feature>.test.json` | Feature-specific tests |
| `e2e_tests.json` | Explicit E2E marker |
| `integration_tests.yaml` | Integration test suite |
| `smoke_tests.md` | Quick smoke tests |

### Supported Patterns (Glob)

```bash
# All test files
**/*.test.{json,yaml,yml,csv,md}
**/tests.{json,yaml,yml,csv,md}
**/test_cases.{json,yaml,yml,csv,md}

# Example discovery
e2e-test run **/*.test.json
e2e-test run tests/
e2e-test run specific_test.yaml
```

---

## 7. File Size Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| **Max file size** | 10 MB | Prevent memory exhaustion |
| **Max test cases per file** | 10,000 | Practical limit for reporting |
| **Max question length** | 10,000 chars | API and UI limits |
| **Max answer length** | 10,000 chars | Truncated if longer |

---

**Status**: ✅ Test file format contracts defined
