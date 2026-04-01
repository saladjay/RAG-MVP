# Tasks: UV Python Runtime Management

**Input**: Design documents from `/specs/004-uv-python-install/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md, quickstart.md

**Technical Stack** (from plan.md and research.md):
- Language: Python 3.11+
- CLI Framework: Typer
- HTTP Client: requests
- Configuration: toml, platformdirs
- Version Parsing: packaging.version
- Progress Display: rich
- Dependencies: uv-managed (per constitution Principle VI)

**Tests**: Tests are MANDATORY per constitution (Principle III). Use real implementations, minimize mocks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Constitution Compliance**:
- All implementation tasks must include documentation headers (Principle I)
- Testing tasks must use real implementations (Principle III)
- Python tasks must use `uv` environment (Principle IV)

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency resolution, and basic structure

- [X] T001 Create pyproject.toml in project root with project metadata and dependencies
- [X] T002 Initialize uv virtual environment and install dependencies using uv
- [X] T003 [P] Create src/uv_python/ package structure with __init__.py
- [X] T004 [P] Create tests/ directory structure with unit/, integration/, contract/ subdirectories
- [X] T005 [P] Configure pytest with pytest.ini for test discovery and async support
- [X] T006 [P] Create tests/conftest.py with shared fixtures for Python version management testing
- [X] T007 [P] Setup .env.example file with all required environment variables
- [X] T008 [P] Create .gitignore for Python, uv, and IDE files
- [X] T009 [P] Create README.md with quick start guide
- [X] T010 [P] Create CLI entry point script in pyproject.toml

**Status**: COMPLETE

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Configuration & Core

- [X] T011 Create src/uv_python/config.py with environment variable loading and validation
- [X] T012 [P] Create src/uv_python/core/exceptions.py with custom exception classes
- [X] T013 [P] Create src/uv_python/core/logger.py with structured logging configuration

### Data Models

- [X] T014 [P] Create src/uv_python/models/python_version.py with PythonVersion dataclass
- [X] T015 [P] Create src/uv_python/models/installation.py with Installation dataclass
- [X] T016 [P] Create src/uv_python/models/project_config.py with ProjectConfiguration dataclass
- [X] T017 [P] Create src/uv_python/models/global_config.py with GlobalConfiguration dataclass
- [X] T018 [P] Create src/uv_python/models/download_task.py with DownloadTask dataclass

### Python Source Integration

- [X] T019 Create src/uv_python/python_source.py with interface for fetching available Python versions
- [X] T020 [P] Implement python.org API client in src/uv_python/python_source.py for version discovery
- [X] T021 [P] Implement GitHub releases API client in src/uv_python/python_source.py as backup source

### CLI Framework

- [X] T022 Create src/uv_python/cli/main.py with Typer app initialization
- [X] T023 [P] Create src/uv_python/cli/commands.py module structure for command handlers

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

**Status**: COMPLETE

---

## Phase 3: User Story 1 - Python Version Discovery and Selection (Priority: P1) 🎯 MVP

**Goal**: List available Python versions and install specific versions on demand

**Independent Test**: Run CLI command to list Python versions, then install a specific version and verify it's available locally

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T024 [P] [US1] Write unit test for Python version listing in tests/unit/test_python_source.py
- [ ] T025 [P] [US1] Write unit test for Python version download in tests/unit/test_installer.py
- [ ] T026 [P] [US1] Write integration test for version listing CLI command in tests/integration/test_cli_commands.py
- [ ] T027 [P] [US1] Write integration test for Python installation workflow in tests/integration/test_installation.py
- [ ] T028 [P] [US1] Write contract test for python.org API in tests/contract/test_python_org_api.py

### Implementation for User Story 1

- [ ] T029 [P] [US1] Create src/uv_python/services/version_discovery.py with version listing service
- [ ] T030 [P] [US1] Create src/uv_python/services/installer.py with Python installation service
- [ ] T031 [US1] Implement download functionality with retry logic in src/uv_python/services/installer.py
- [ ] T032 [US1] Implement checksum verification in src/uv_python/services/installer.py
- [ ] T033 [US1] Implement local caching of downloaded Python versions in src/uv_python/services/installer.py
- [ ] T034 [P] [US1] Create src/uv_python/services/installed_versions.py for querying installed versions
- [ ] T034a [US1] Implement installation metadata storage (.uv-python.json) in src/uv_python/services/installer.py
- [ ] T034b [P] [US1] Create src/uv_python/services/uninstaller.py for removing installed Python versions
- [ ] T035 [US1] Implement `uv python list` CLI command in src/uv_python/cli/commands.py with --all, --installed, --format options
- [ ] T035a [US1] Implement JSON output format for list command in src/uv_python/cli/commands.py
- [ ] T036 [US1] Implement `uv python install` CLI command in src/uv_python/cli/commands.py
- [ ] T036a [US1] Implement `uv python uninstall` CLI command in src/uv_python/cli/commands.py
- [ ] T037 [US1] Add progress display for downloads in src/uv_python/services/installer.py
- [ ] T037a [US1] Implement DownloadTask state management (downloading→completed/failed) in src/uv_python/services/installer.py
- [ ] T038 [US1] Implement error handling for missing/invalid versions in src/uv_python/services/version_discovery.py
- [ ] T039 [US1] Add OS compatibility validation in src/uv_python/services/installer.py
- [ ] T040 [US1] Support both stable and pre-release versions in src/uv_python/services/version_discovery.py
- [ ] T040a [P] [US1] Add common CLI options (--verbose, --quiet, --config) in src/uv_python/cli/main.py

**Checkpoint**: User Story 1 complete - can list and install Python versions

---

## Phase 4: User Story 2 - Project-Specific Python Version Pinning (Priority: P1)

**Goal**: Associate Python versions with projects for team consistency

**Independent Test**: Create project with pinned Python version, run commands in that directory, verify correct version is used

### Tests for User Story 2

- [ ] T041 [P] [US2] Write unit test for project config detection in tests/unit/test_project_config.py
- [ ] T042 [P] [US2] Write unit test for semantic version resolution in tests/unit/test_version_resolver.py
- [ ] T043 [P] [US2] Write integration test for project-specific version usage in tests/integration/test_project_workflow.py
- [ ] T043a [P] [US2] Write unit test for pin command in tests/unit/test_pin_command.py

### Implementation for User Story 2

- [ ] T044 [P] [US2] Create src/uv_python/services/project_detector.py for detecting project config files
- [ ] T045 [P] [US2] Create src/uv_python/services/version_resolver.py with semantic version resolution
- [ ] T046 [US2] Implement .python-version file detection and parsing in src/uv_python/services/project_detector.py
- [ ] T047 [US2] Implement pyproject.toml [requires.python] detection in src/uv_python/services/project_detector.py
- [ ] T048 [US2] Implement version requirement parsing (e.g., "3.11", ">=3.11", "3.11.*") in src/uv_python/services/version_resolver.py
- [ ] T049 [US2] Implement `uv python pin` CLI command for writing version to project config files in src/uv_python/cli/commands.py
- [ ] T049a [US2] Implement --file option for pin command to select config file (.python-version vs pyproject.toml)
- [ ] T050 [US2] Integrate project version detection into all relevant CLI commands in src/uv_python/cli/commands.py
- [ ] T051 [US2] Implement auto-installation prompt for missing required versions in src/uv_python/cli/commands.py
- [ ] T052 [US2] Add fallback to available alternatives when required version is missing in src/uv_python/services/version_resolver.py

**Checkpoint**: User Stories 1 AND 2 complete - can manage Python versions with project-specific pinning

---

## Phase 5: User Story 3 - Global Python Version Management (Priority: P2)

**Goal**: Set system-wide default Python version for projects without explicit requirements

**Independent Test**: Set global Python version, run commands outside project directories, verify global default is used

### Tests for User Story 3

- [ ] T054 [P] [US3] Write unit test for global config storage in tests/unit/test_global_config.py
- [ ] T055 [P] [US3] Write integration test for global version precedence in tests/integration/test_global_version.py

### Implementation for User Story 3

- [ ] T056 [P] [US3] Create src/uv_python/services/global_config.py for managing global Python version
- [ ] T057 [US3] Implement global config storage (~/.config/uv-python/config.toml) in src/uv_python/services/global_config.py
- [ ] T058 [US3] Implement `uv python global` CLI command in src/uv_python/cli/commands.py
- [ ] T059 [US3] Implement global version resolution with project override logic in src/uv_python/services/global_config.py
- [ ] T060 [US3] Add precedence logic: project > global > system default in src/uv_python/cli/commands.py
- [ ] T060a [US3] Implement --unset option for global command in src/uv_python/cli/commands.py

**Checkpoint**: User Stories 1, 2, AND 3 complete - full Python version management with global defaults

---

## Phase 6: User Story 4 - Python Version Verification and Validation (Priority: P3)

**Goal**: Verify Python installations and validate compatibility

**Independent Test**: Run verification command on installed Python versions, confirm validation works

### Tests for User Story 4

- [ ] T061 [P] [US4] Write unit test for installation verification in tests/unit/test_verifier.py
- [ ] T062 [P] [US4] Write integration test for system health check in tests/integration/test_verification.py

### Implementation for User Story 4

- [ ] T063 [P] [US4] Create src/uv_python/services/verifier.py with installation verification service
- [ ] T064 [US4] Implement Python binary validation in src/uv_python/services/verifier.py
- [ ] T065 [US4] Implement compatibility checking for project requirements in src/uv_python/services/verifier.py
- [ ] T066 [US4] Implement `uv python verify` CLI command in src/uv_python/cli/commands.py
- [ ] T067 [US4] Implement --checksum and --binary options for verify command in src/uv_python/cli/commands.py
- [ ] T068 [US4] Implement `uv python check` CLI command for system-wide health check in src/uv_python/cli/commands.py
- [ ] T069 [US4] Implement --format option for check command (table/json output) in src/uv_python/cli/commands.py
- [ ] T070 [US4] Add suggestion logic for alternative compatible versions in src/uv_python/services/verifier.py

**Checkpoint**: All 4 user stories complete - full Python runtime management with verification

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T071 [P] Add comprehensive documentation headers to all source files (Principle I)
- [ ] T072 [P] Run pytest with --cov to verify 80%+ test coverage (Principle III)
- [ ] T073 [P] Add type hints to all function signatures in src/uv_python/
- [ ] T074 Implement graceful handling of network interruptions across all download operations
- [ ] T075 [P] Implement disk space checking before downloads
- [ ] T076 [P] Add permission error handling for installation directories
- [ ] T077 [P] Handle corrupt cache/partial downloads with cleanup and retry
- [ ] T078 [P] Add proxy support for corporate firewalls
- [ ] T079 Create run_tests.sh script for test execution
- [ ] T080 [P] Performance test: verify list command completes within 5 seconds
- [ ] T081 [P] Performance test: verify install completes within 2 minutes on broadband
- [ ] T082 [P] Security review: validate all inputs and sanitize error messages
- [ ] T083 Add man page generation for CLI commands
- [ ] T084 Run end-to-end validation of all user stories
- [ ] T085 Generate and verify API documentation matches docstrings
- [ ] T086 [P] Implement Installation state transitions (pending→valid/invalid) in src/uv_python/services/verifier.py
- [ ] T087 [P] Implement DownloadTask state transitions (downloading→paused/completed/failed) in src/uv_python/services/installer.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Extends US1 with project pinning via pin command
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Adds global version management, depends on US1/US2 for version resolution
- **User Story 4 (P3)**: Can start after Foundational (Phase 2) - Adds verification capabilities, depends on US1 for installations to verify

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before CLI commands
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models and independent services within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T024: Unit test for Python version listing
Task T025: Unit test for Python version download
Task T026: Integration test for version listing CLI
Task T027: Integration test for installation workflow
Task T028: Contract test for python.org API
Task T043a: Unit test for pin command

# Launch all services for User Story 1 together:
Task T029: Version discovery service
Task T030: Installation service
Task T034: Installed versions query service
Task T034b: Uninstaller service
```

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task T041: Unit test for project config detection
Task T042: Unit test for semantic version resolution
Task T043: Integration test for project-specific version usage
Task T043a: Unit test for pin command

# Launch all services for User Story 2 together:
Task T044: Project detector service
Task T045: Version resolver service
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Python Version Discovery and Selection)
4. Complete Phase 4: User Story 2 (Project-Specific Version Pinning)
5. **STOP and VALIDATE**: Test both user stories independently
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (Enhanced MVP!)
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Version Discovery and Selection)
   - Developer B: User Story 2 (Project-Specific Pinning)
   - Developer C: User Story 3 (Global Version Management)
3. Stories complete and integrate independently
4. Developer D: User Story 4 (Verification) - can start anytime after Foundational

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Task Summary

- **Total Tasks**: 87 (increased from 81)
- **Tasks per User Story**:
  - US1 (Python Version Discovery and Selection): 20 tasks (T024-T040a)
  - US2 (Project-Specific Version Pinning): 12 tasks (T041-T052)
  - US3 (Global Python Version Management): 7 tasks (T054-T060a)
  - US4 (Python Version Verification): 10 tasks (T061-T070)
- **Setup Tasks**: 10 tasks (T001-T010)
- **Foundational Tasks**: 13 tasks (T011-T023)
- **Polish Tasks**: 17 tasks (T071-T087)

### Parallel Opportunities Identified

- **Setup Phase**: 9/10 tasks can run in parallel
- **Foundational Phase**: 10/13 tasks can run in parallel
- **User Story 1**: 11/20 tasks can run in parallel (6 tests + 5 services)
- **User Story 2**: 4/12 tasks can run in parallel (4 tests)
- **User Story 3**: 2/7 tasks can run in parallel (2 tests)
- **User Story 4**: 2/10 tasks can run in parallel (2 tests)
- **Polish Phase**: 13/17 tasks can run in parallel

### New Tasks Added

| Task ID | Description | User Story |
|---------|-------------|------------|
| T034a | Installation metadata storage (.uv-python.json) | US1 |
| T034b | Create uninstaller service | US1 |
| T035a | JSON output format for list command | US1 |
| T036a | Implement uninstall CLI command | US1 |
| T037a | DownloadTask state management | US1 |
| T040a | Common CLI options (--verbose, --quiet, --config) | US1 |
| T049 | Implement pin CLI command | US2 |
| T049a | --file option for pin command | US2 |
| T043a | Unit test for pin command | US2 |
| T060a | --unset option for global command | US3 |
| T067 | --checksum and --binary options for verify command | US4 |
| T069 | --format option for check command | US4 |
| T086 | Installation state transitions | Polish |
| T087 | DownloadTask state transitions | Polish |

### MVP Scope Recommendation

**MVP = Phase 1 + Phase 2 + Phase 3 (User Story 1) + Phase 4 (User Story 2)**

This delivers:
- Working Python version discovery and installation
- Uninstall capability for Python versions
- Project-specific Python version pinning via pin command
- Team consistency for Python versions
- Basic integration with uv tooling
- Complete test coverage for core functionality

**Estimated Effort**: ~57 tasks (Setup + Foundational + US1 + US2)

**Critical Note**: User Stories 1 and 2 are both P1 priority - they should be delivered together as a complete MVP for Python runtime management.
