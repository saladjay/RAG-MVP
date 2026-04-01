# Feature Specification: E2E Test Framework

**Feature Branch**: `002-e2e-test-interface`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "需要保留一套全流程的测试接口，通过读取本地文件（包括问题，回答，回答内容来源文档）, 来进行完整的系统测试，本地文件可能有多种格式，需要做一层兼容。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Test Execution (Priority: P1)

A developer wants to validate the complete RAG service by running a suite of test cases stored in local files. Each test case contains a question, expected answer, and reference source documents. The developer runs the test suite and receives a report comparing actual results against expected results.

**Why this priority**: This is the core functionality - without the ability to run end-to-end tests from local files, developers cannot validate system behavior reliably.

**Independent Test**: Can be tested by creating a test file with sample questions and expected answers, running the test interface, and verifying the output report contains pass/fail results for each test case.

**Acceptance Scenarios**:

1. **Given** a test file with valid questions, expected answers, and source documents, **When** the test interface is executed, **Then** the system processes all test cases and generates a report with pass/fail status for each case
2. **Given** a test file with multiple test cases, **When** the test interface is executed, **Then** each test case is processed independently with isolated context
3. **Given** a test file with an invalid format, **When** the test interface is executed, **Then** the system returns a clear error message indicating the format issue and line number

---

### User Story 2 - Multi-Format File Support (Priority: P2)

A developer has test cases stored in different file formats (JSON, CSV, YAML, or Markdown). The system should automatically detect and parse each format without requiring manual conversion.

**Why this priority**: Supporting multiple formats enables flexibility for different team preferences and existing test data. The system works with a single format but multi-format support improves usability.

**Independent Test**: Can be tested by creating test files in different formats (JSON, CSV, YAML, Markdown) with identical test cases, running the test interface on each, and verifying consistent results across all formats.

**Acceptance Scenarios**:

1. **Given** a test file in JSON format, **When** the test interface is executed, **Then** the system parses the file and processes test cases correctly
2. **Given** a test file in CSV format, **When** the test interface is executed, **Then** the system parses the file and processes test cases correctly
3. **Given** a test file in YAML format, **When** the test interface is executed, **Then** the system parses the file and processes test cases correctly
4. **Given** a test file in Markdown format with code blocks, **When** the test interface is executed, **Then** the system extracts test cases from code blocks and processes them correctly
5. **Given** a test file with an unsupported format, **When** the test interface is executed, **Then** the system returns an error listing supported formats

---

### User Story 3 - Result Comparison and Reporting (Priority: P3)

A developer wants detailed feedback on test results including similarity scores between actual and expected answers, retrieval accuracy metrics, and overall test suite statistics.

**Why this priority**: Reporting is critical for understanding system behavior and identifying issues, but basic pass/fail results are sufficient for initial validation.

**Independent Test**: Can be tested by running a test suite with both passing and failing cases, and verifying the output report includes similarity scores, retrieval metrics, and aggregate statistics.

**Acceptance Scenarios**:

1. **Given** a test suite with varying answer quality, **When** tests complete, **Then** the report includes similarity scores comparing actual to expected answers
2. **Given** a test suite with retrieval-based tests, **When** tests complete, **Then** the report indicates whether expected source documents were retrieved
3. **Given** a completed test run, **When** viewing the report, **Then** aggregate statistics (pass rate, average similarity, total execution time) are displayed
4. **Given** a failing test case, **When** viewing the report, **Then** detailed differences between actual and expected results are shown

---

### User Story 4 - Batch and Selective Test Execution (Priority: P4)

A developer wants to run all tests in a directory, or run specific tests by name or tag, to speed up development iteration.

**Why this priority**: Selective execution improves developer productivity but is not required for basic testing functionality.

**Independent Test**: Can be tested by creating multiple test files with tags, running tests with various filters, and verifying only matching tests are executed.

**Acceptance Scenarios**:

1. **Given** multiple test files in a directory, **When** the test interface is run with the directory path, **Then** all test files are discovered and executed
2. **Given** test cases with tags or categories, **When** the test interface is run with a tag filter, **Then** only tests with matching tags are executed
3. **Given** test cases with unique identifiers, **When** the test interface is run with specific test IDs, **Then** only those tests are executed

---

### Edge Cases

- What happens when the source documents referenced in test cases are not found in the knowledge base?
- How does the system handle test cases with missing optional fields (e.g., no expected answer provided)?
- What happens when test files contain circular references or duplicate test case IDs?
- How does the system handle extremely long test cases or large document references?
- What happens when the RAG service is unavailable during test execution?
- How does the system handle tests with expected answers that reference dynamic data (timestamps, IDs)?
- What happens when file encoding issues prevent proper parsing?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a test execution interface that accepts file paths as input
- **FR-002**: System MUST support reading test cases from local files in multiple formats (JSON, CSV, YAML, Markdown)
- **FR-003**: System MUST automatically detect file format based on file extension and content
- **FR-004**: System MUST parse test cases containing: question, expected answer, and source document references
- **FR-005**: System MUST execute each test case by submitting questions to the RAG service
- **FR-006**: System MUST compare actual responses against expected answers and calculate similarity scores
- **FR-007**: System MUST verify that expected source documents are retrieved in the response
- **FR-008**: System MUST generate a test report with pass/fail status, similarity scores, and retrieval metrics
- **FR-009**: System MUST support batch execution of multiple test files from a directory
- **FR-010**: System MUST support selective test execution by test ID or tag
- **FR-011**: System MUST validate test file format before execution and provide clear error messages
- **FR-012**: System MUST isolate test case execution (no data leakage between tests)

### Key Entities

- **Test File**: A local file containing one or more test cases in a supported format
- **Test Case**: A single test definition containing: test ID, question, expected answer (optional), source document references (optional), tags (optional)
- **Expected Answer**: The reference answer that the actual response will be compared against
- **Source Document Reference**: Identifiers for documents that should be retrieved for the test question
- **Test Report**: Aggregated results including: pass/fail counts, similarity scores, retrieval accuracy, execution time, per-test details
- **Similarity Score**: A numeric measure (0-1 or 0-100) indicating how closely the actual answer matches the expected answer
- **Test Execution Context**: Isolated environment for each test case including request state and response tracking

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All supported file formats (JSON, CSV, YAML, Markdown) can be parsed and executed
- **SC-002**: Test execution completes with report generation in under 5 minutes for 100 test cases
- **SC-003**: Similarity scores between actual and expected answers are calculated and displayed
- **SC-004**: Source document retrieval verification accurately identifies correct/incorrect retrievals
- **SC-005**: Test reports include all required metrics: pass rate, similarity scores, retrieval accuracy, execution time
- **SC-006**: Invalid file formats are detected and reported with specific error messages within 1 second
- **SC-007**: Each test case executes in complete isolation (no cross-test data leakage verified)

## Assumptions

1. **Test file location**: Test files are stored locally in the file system accessible to the test runner
2. **Source document availability**: Referenced source documents are already indexed in the knowledge base before test execution
3. **Similarity algorithm**: A reasonable default similarity calculation (e.g., semantic similarity or text overlap) will be used unless otherwise specified
4. **RAG service availability**: The RAG service is running and accessible during test execution
5. **File encoding**: Test files use standard UTF-8 encoding unless otherwise specified
6. **Concurrent execution**: Test cases run sequentially by default; parallel execution is optional

## Out of Scope

The following features are explicitly out of scope for this feature:

- Test case editor or UI for creating test files
- Automatic test case generation from documentation
- Continuous integration pipeline integration
- Test result historical tracking and comparison
- Performance benchmarking and load testing
- Test data mocking or stubbing of external dependencies
- Visual test result dashboard (web UI)

## File Format Specifications (Appendix)

### JSON Format

```json
{
  "tests": [
    {
      "id": "test_001",
      "question": "What is RAG?",
      "expected_answer": "Retrieval-Augmented Generation combines...",
      "source_docs": ["doc_rag_intro"],
      "tags": ["basic", "retrieval"]
    }
  ]
}
```

### CSV Format

```csv
id,question,expected_answer,source_docs,tags
test_001,What is RAG?,Retrieval-Augmented Generation combines...,"doc_rag_intro","basic,retrieval"
```

### YAML Format

```yaml
tests:
  - id: test_001
    question: What is RAG?
    expected_answer: Retrieval-Augmented Generation combines...
    source_docs:
      - doc_rag_intro
    tags:
      - basic
      - retrieval
```

### Markdown Format

````markdown
# Test Suite

## Test Case: test_001
**Tags**: basic, retrieval

**Question**: What is RAG?

**Expected Answer**: Retrieval-Augmented Generation combines...

**Source Documents**: doc_rag_intro
````

*Note: These specifications illustrate the expected structure; implementations should handle reasonable variations.*
