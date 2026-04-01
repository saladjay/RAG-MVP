# Tasks: E2E Test Framework

**Feature**: 002-e2e-test-interface
**Input**: Design documents from `/specs/002-e2e-test-interface/`
**Prerequisites**: spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are MANDATORY per constitution (Principle III). Use real implementations, minimize mocks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Constitution Compliance**:
- All implementation tasks must include documentation headers (Principle I)
- Testing tasks must use real implementations (Principle III)
- Python tasks must use `uv` environment (Principle IV)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **E2E Test Framework location**: `src/e2e_test/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create e2e_test project structure: src/e2e_test/{__init__.py,parsers,runners,comparators,reporters,clients,models}/
- [X] T002 Create tests directory structure: tests/{unit,integration,contract,e2e}/
- [X] T003 Initialize pyproject with dependencies: httpx, pydantic, pyyaml, rich, typer in pyproject.002-e2e-test.toml
- [X] T004 [P] Configure pytest with pytest.ini for async test support in pytest.e2e-test.ini
- [X] T005 [P] Create .gitignore patterns for Python: __pycache__/, *.pyc, .venv/, .coverage, *.egg-info/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create base exception hierarchy in src/e2e_test/core/exceptions.py (E2ETestError, RAGConnectionError, RAGTimeoutError, RAGServerError, RAGClientError)
- [X] T007 [P] Create structured logger in src/e2e_test/core/logger.py using python-json-logger
- [X] T008 [P] Create TestConfig model in src/e2e_test/models/config.py with pydantic-settings (rag_service_url, timeout, threshold, etc.)
- [X] T009 Create TestCase model in src/e2e_test/models/test_case.py with pydantic validation (id, question, expected_answer, source_docs, tags, metadata)
- [X] T010 Create TestResult model in src/e2e_test/models/test_result.py with TestStatus enum (status, similarity_score, source_docs_match, latency_ms)
- [X] T011 Create TestReport model in src/e2e_test/models/test_report.py (pass/fail counts, similarity_avg, results list)
- [X] T012 [P] Create FileFormat enum in src/e2e_test/models/file_format.py (JSON, CSV, YAML, MARKDOWN)
- [X] T013 Create OutputFormat enum in src/e2e_test/models/output_format.py (CONSOLE, JSON, HTML)
- [X] T014 Create base parser interface in src/e2e_test/parsers/base.py (Parser abstract class with parse() method)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - End-to-End Test Execution (Priority: P1) 🎯 MVP

**Goal**: Execute test cases from local files against RAG Service and generate basic pass/fail report

**Independent Test**: Create a JSON test file with 2-3 test cases, run `e2e-test run file.test.json`, verify pass/fail output

### Tests for User Story 1

- [X] T015 [P] [US1] Integration test for JSON test file parsing in tests/integration/test_json_parser.py
- [X] T016 [P] [US1] Integration test for RAG client query execution in tests/integration/test_rag_client.py
- [X] T017 [P] [US1] Integration test for test runner end-to-end flow in tests/integration/test_runner.py

### Implementation for User Story 1

- [X] T018 [P] [US1] Implement JSONParser in src/e2e_test/parsers/json_parser.py (parse JSON array of test cases)
- [X] T019 [US1] Implement RAGClient in src/e2e_test/clients/rag_client.py (async query(), health_check() with httpx)
- [X] T020 [US1] Implement similarity calculator in src/e2e_test/comparators/similarity.py (Levenshtein ratio using difflib.SequenceMatcher)
- [X] T021 [US1] Implement source docs validator in src/e2e_test/comparators/validator.py (match actual vs expected doc IDs)
- [X] T022 [US1] Implement TestRunner in src/e2e_test/runners/test_runner.py (run_tests() async execution with retry logic)
- [X] T023 [US1] Implement console reporter in src/e2e_test/reporters/console.py (rich table with pass/fail, similarity scores)
- [X] T024 [US1] Implement basic CLI in src/e2e_test/cli.py with typer (run command, file path argument, url/timeout flags)
- [X] T025 [US1] Add test result aggregation in src/e2e_test/runners/test_runner.py (build TestReport from TestResults)
- [X] T026 [US1] Add error handling for RAG Service failures in src/e2e_test/clients/rag_client.py (connection, timeout, 5xx errors)
- [X] T027 [US1] Add logging throughout test execution flow (query start, response received, test passed/failed)

**Checkpoint**: At this point, User Story 1 should be fully functional - can run JSON test files and see console report

---

## Phase 4: User Story 2 - Multi-Format File Support (Priority: P2)

**Goal**: Support CSV, YAML, and Markdown test file formats

**Independent Test**: Create test files in CSV, YAML, and MD formats with identical test cases, run each, verify consistent results

### Tests for User Story 2

- [X] T028 [P] [US2] Integration test for CSV test file parsing in tests/e2e/test_csv_parser.py
- [X] T029 [P] [US2] Integration test for YAML test file parsing in tests/e2e/test_yaml_parser.py
- [X] T030 [P] [US2] Integration test for Markdown test file parsing in tests/e2e/test_md_parser.py
- [X] T031 [P] [US2] Integration test for auto format detection in tests/e2e/test_parser_factory.py

### Implementation for User Story 2

- [X] T032 [P] [US2] Implement CSVParser in src/e2e_test/parsers/csv_parser.py (handle commas, quotes, multi-line values)
- [X] T033 [P] [US2] Implement YAMLParser in src/e2e_test/parsers/yaml_parser.py (use pyyaml, handle list structure)
- [X] T034 [P] [US2] Implement MDParser in src/e2e_test/parsers/md_parser.py (extract YAML code blocks from markdown)
- [X] T035 [US2] Implement ParserFactory in src/e2e_test/parsers/factory.py (detect format by extension, return appropriate parser)
- [X] T036 [US2] Add format validation error messages in src/e2e_test/parsers/base.py (clear hints for invalid formats)
- [X] T037 [US2] Integrate all parsers with CLI in src/e2e_test/cli.py (accept any format, auto-detect)

**Checkpoint**: At this point, all 4 file formats work - tests can be created in JSON, CSV, YAML, or Markdown ✅ COMPLETE

---

## Phase 5: User Story 3 - Result Comparison and Reporting (Priority: P3)

**Goal**: Detailed feedback with similarity scores, retrieval metrics, and JSON export

**Independent Test**: Run test suite with passing and failing cases, verify JSON output contains all metrics and similarity scores

### Tests for User Story 3

- [X] T038 [P] [US3] Integration test for JSON report generation in tests/e2e/test_json_report.py
- [X] T039 [P] [US3] Integration test for similarity calculation edge cases in tests/e2e/test_similarity.py
- [X] T040 [P] [US3] Integration test for report export in tests/e2e/test_json_report.py (covered by T038)

### Implementation for User Story 3

- [X] T041 [P] [US3] Implement JSONReporter in src/e2e_test/reporters/json_report.py (export TestReport to JSON file)
- [X] T042 [US3] Add optional advanced similarity calculation in src/e2e_test/comparators/similarity.py (sentence-transformers if installed) - Already implemented
- [X] T043 [US3] Add detailed per-test metrics in src/e2e_test/models/test_result.py (individual timing, error details) - Already implemented
- [X] T044 [US3] Add retrieval accuracy tracking in src/e2e_test/comparators/validator.py (superset/exact/subset match types) - Already implemented (SourceDocsMatch enum)
- [X] T045 [US3] Add aggregate statistics to TestReport in src/e2e_test/models/test_report.py (pass_rate, execution_time, similarity_avg) - Already implemented
- [X] T046 [US3] Add --format flag to CLI in src/e2e_test/cli.py (console/json output selection) - Already implemented
- [X] T047 [US3] Add --output flag to CLI in src/e2e_test/cli.py (specify output file path for JSON reports) - Already implemented
- [X] T048 [US3] Add verbose mode to console reporter in src/e2e_test/reporters/console.py (show detailed differences, full answers) - Already implemented

**Checkpoint**: At this point, rich reporting with multiple output formats and detailed metrics is available ✅ COMPLETE

---

## Phase 6: User Story 4 - Batch and Selective Test Execution (Priority: P4)

**Goal**: Run tests from directories, filter by tags, or select specific test IDs

**Independent Test**: Create test files with different tags, run with --tag flag, verify only matching tests execute

### Tests for User Story 4

- [X] T049 [P] [US4] Integration test for directory test discovery in tests/e2e/test_filters.py (covered by _discover_test_files)
- [X] T050 [P] [US4] Integration test for tag filtering in tests/e2e/test_filters.py
- [X] T051 [P] [US4] Integration test for test ID filtering in tests/e2e/test_filters.py

### Implementation for User Story 4

- [X] T052 [US4] Add directory discovery in src/e2e_test/cli.py (_discover_test_files with all formats)
- [X] T053 [US4] Add tag filtering in src/e2e_test/runners/test_runner.py (filter test cases by tag list)
- [X] T054 [US4] Add test ID filtering in src/e2e_test/runners/test_runner.py (select specific tests by ID)
- [X] T055 [US4] Add exclude-tag filtering in src/e2e_test/runners/test_runner.py (exclude tests with certain tags)
- [X] T056 [US4] Add --tag flag to CLI in src/e2e_test/cli.py (accept multiple tag filters)
- [X] T057 [US4] Add --exclude-tag flag to CLI in src/e2e_test/cli.py (accept tags to exclude)
- [X] T058 [US4] Add --test-id flag to CLI in src/e2e_test/cli.py (accept specific test IDs)
- [X] T059 [US4] Update console reporter to show filtered test count in src/e2e_test/reporters/console.py (already shows total_tests)

**Checkpoint**: All user stories complete - full E2E testing capability with flexible execution options ✅ COMPLETE

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T060 [P] Add docstrings to all public modules and classes in src/e2e_test/
- [ ] T061 [P] Add type hints to all functions in src/e2e_test/ (use typing module)
- [ ] T062 [P] Create example test files in tests/examples/ (basic.test.json, advanced.test.yaml, regression.test.csv)
- [ ] T063 [P] Create README.md in src/e2e_test/ with usage examples
- [ ] T064 Add HTML report generation (optional using jinja2) in src/e2e_test/reporters/html.py
- [ ] T065 Add concurrent test execution option in src/e2e_test/runners/test_runner.py (asyncio.gather with --parallel flag)
- [ ] T066 Add retry configuration in src/e2e_test/models/config.py (retry_count, backoff_factor)
- [ ] T067 Add environment variable support in src/e2e_test/models/config.py (E2E_TEST_* prefix)
- [ ] T068 Validate quickstart.md examples work with real RAG Service in tests/e2e/test_quickstart.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User Story 1 (P1): MVP - complete first for validation
  - User Stories 2-4: Can proceed in parallel after US1 validated
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends parsers from US1 but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Builds on reporters from US1 but independently testable
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Adds filtering to runner from US1 but independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Parsers before Runner
- Client before Runner
- Comparators before Runner
- Reporter before CLI
- Core implementation before integration

### Parallel Opportunities

- **Setup**: All [P] tasks (T004, T005) can run in parallel
- **Foundational**: All [P] tasks (T007, T008, T012, T013) can run in parallel
- **US1 Tests**: All [P] tests (T015, T016, T017) can run in parallel
- **US2 Tests**: All [P] tests (T028, T029, T030, T031) can run in parallel
- **US2 Parsers**: All [P] parsers (T032, T033, T034) can run in parallel
- **US3 Tests**: All [P] tests (T038, T039, T040) can run in parallel
- **US3 Reporters**: T041 can run parallel to other implementation tasks
- **US4 Tests**: All [P] tests (T049, T050, T051) can run in parallel
- **Polish**: All [P] tasks (T060, T061, T062, T063) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Integration test for JSON test file parsing in tests/integration/test_json_parser.py"
Task: "Integration test for RAG client query execution in tests/integration/test_rag_client.py"
Task: "Integration test for test runner end-to-end flow in tests/integration/test_runner.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all parsers for User Story 2 together:
Task: "Implement CSVParser in src/e2e_test/parsers/csv_parser.py"
Task: "Implement YAMLParser in src/e2e_test/parsers/yaml_parser.py"
Task: "Implement MDParser in src/e2e_test/parsers/md_parser.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Create test file, run `e2e-test run tests.test.json`, verify output
5. Demo/validate with team before proceeding

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **MVP Complete!** (JSON tests + console report)
3. Add User Story 2 → Test independently → Multi-format support
4. Add User Story 3 → Test independently → Rich reporting with JSON export
5. Add User Story 4 → Test independently → Flexible execution options

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (core execution)
   - Developer B: User Story 2 (parsers - can start after US1 models done)
   - Developer C: User Story 3 (reporters - can start after US1 models done)
3. User Story 4 can be added by any developer after US1 runner is stable

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [US1], [US2], [US3], [US4] labels map tasks to specific user stories for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- CLI framework: Typer recommended, but argparse is acceptable alternative
- Similarity: Start with difflib.SequenceMatcher (Levenshtein), optional sentence-transformers later
- HTML reporter is optional (nice-to-have), JSON export is required

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Setup | 5 tasks | Project structure and dependencies |
| Foundational | 9 tasks | Base models, exceptions, interfaces |
| US1 - MVP | 13 tasks | JSON tests + basic execution |
| US2 - Formats | 10 tasks | CSV/YAML/Markdown parsers |
| US3 - Reports | 11 tasks | JSON export, detailed metrics |
| US4 - Filtering | 11 tasks | Tags, IDs, directory scan |
| Polish | 9 tasks | Docs, examples, enhancements |
| **Total** | **68 tasks** | Full E2E test framework |

**MVP Scope**: Phases 1-3 (27 tasks) = Basic E2E testing with JSON files and console reports
