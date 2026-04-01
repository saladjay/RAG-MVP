# Implementation Plan: UV Python Runtime Management

**Branch**: `004-uv-python-install` | **Date**: 2026-03-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-uv-python-install/spec.md`

## Summary

Build a Python runtime management tool that integrates with uv to enable discovery, installation, and management of Python versions. The tool will provide CLI commands for listing available Python versions from official sources, downloading and installing specific versions, pinning versions to projects, and managing global defaults. All operations will integrate with existing uv tooling and configuration patterns.

**Technical Approach**: Python-based CLI tool using Typer framework for command interface, with integration to uv's existing capabilities. Python versions are sourced from official python.org API and GitHub releases. Version detection uses standard project configuration files (.python-version, pyproject.toml). All operations respect uv's cache directory and configuration patterns.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer (CLI), requests (HTTP), toml (configuration), packaging (version parsing), rich (progress display)
**Configuration**: TOML format for local config, standard Python version files
**Project Type**: CLI tool (command-line interface)
**Performance Goals**:
- List command: <5 seconds
- Install command: <2 minutes on broadband
- Version detection: <1 second
**Constraints**:
  - Must integrate with existing uv tooling
  - User-space installation only (~/.local/share/uv)
  - Must support Linux and macOS (Windows secondary)
  - Network operations must be resilient with retry logic
**Scale/Scope**:
  - Support all stable CPython releases (3.7+)
  - Manage 10+ installed versions per system
  - Handle concurrent download requests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Documentation Standards (Principle I & II)
- [x] All files will include header with content and API brief description
- [x] Documentation headers will be updated immediately on content changes
- [x] Call flow diagrams will be generated at `.specify/specs/004-uv-python-install/research.md`

### Testing Standards (Principle III & IV)
- [x] Tests will use real implementations (minimal mocks)
  - Only python.org/GitHub API may use mocks when test environments unavailable
  - Local file operations will use real implementations in tests
- [x] CLI tool tests will include command execution fixtures
- [x] Python execution will use `uv`-managed virtual environment
- [x] Blocking points for real test implementation will be documented

### Component Governance (Principle V)
- [x] New base components have not been created without approval
  - This project uses existing components: Typer, requests, toml, packaging, rich
- [x] Existing base components are documented
  - Will document usage patterns in research.md
- [x] Package management uses `uv` for Python dependencies

### Additional Test Coverage Requirement
- [x] Each service/CLI command will have a complete set of unit tests
  - Test structure: tests/unit/{module}/test_{component}.py
  - Target coverage: 80%+ per constitution
  - Integration tests for CLI commands
  - Contract tests for external APIs

## Project Structure

### Documentation (this feature)

```text
specs/004-uv-python-install/
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (technical decisions)
├── data-model.md        # Phase 1 output (entity definitions)
├── quickstart.md        # Phase 1 output (setup guide)
├── contracts/           # Phase 1 output (CLI interface contracts)
│   └── cli-contract.md  # Command schema and contracts
└── tasks.md             # Task list (already generated - needs validation)
```

### Source Code (repository root)

```text
src/
├── uv_python/
│   ├── __init__.py
│   ├── main.py                 # Entry point for CLI
│   ├── config.py               # Configuration management
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py       # Custom exception classes
│   │   └── logger.py           # Structured logging
│   ├── models/
│   │   ├── __init__.py
│   │   ├── python_version.py   # PythonVersion dataclass
│   │   ├── installation.py     # Installation dataclass
│   │   ├── project_config.py   # ProjectConfiguration dataclass
│   │   ├── global_config.py    # GlobalConfiguration dataclass
│   │   └── download_task.py    # DownloadTask dataclass
│   ├── python_source/
│   │   ├── __init__.py
│   │   └── client.py           # python.org/GitHub API client
│   ├── services/
│   │   ├── __init__.py
│   │   ├── version_discovery.py # Version listing service
│   │   ├── installer.py        # Python installation service
│   │   ├── installed_versions.py # Installed version queries
│   │   ├── project_detector.py # Project config detection
│   │   ├── version_resolver.py # Semantic version resolution
│   │   ├── global_config.py    # Global version management
│   │   └── verifier.py         # Installation verification
│   └── cli/
│       ├── __init__.py
│       ├── main.py             # Typer app initialization
│       └── commands.py         # CLI command handlers

tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── unit/
│   ├── test_python_source.py   # API client tests
│   ├── test_installer.py       # Installation service tests
│   ├── test_project_config.py  # Project detection tests
│   ├── test_version_resolver.py # Version resolution tests
│   ├── test_global_config.py   # Global config tests
│   └── test_verifier.py        # Verification tests
└── integration/
    ├── test_cli_commands.py    # CLI integration tests
    ├── test_installation.py    # End-to-end installation tests
    └── test_project_workflow.py # Project-based workflow tests

pyproject.toml                  # uv-managed dependencies
README.md                        # User documentation
```

**Structure Decision**: Single project with modular package structure. The `src/uv_python/` directory contains all application code organized by responsibility (models, services, cli). Tests mirror the source structure with unit/ and integration/ directories. Using uv for dependency management satisfies constitution Principle VI.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | No constitution violations identified | All principles (I-VI) are addressed in plan |

## Phase 0: Research & Decisions

**Status**: IN PROGRESS

### Research Tasks Required

1. **Python distribution API research**: Investigate python.org API structure and GitHub releases API
2. **CLI framework selection**: Compare Typer vs Click for command interface
3. **Version resolution library**: Research packaging.version and semver libraries
4. **uv integration patterns**: Understand uv's configuration and cache structure
5. **Progress display libraries**: Research rich, tqdm for download progress
6. **Checksum verification**: Determine hashlib strategies for Python binaries
7. **Platform-specific installation**: Research CPython binary locations for Linux/macOS/Windows
8. **Configuration file standards**: Investigate .python-version and pyproject.toml formats

**Output**: research.md with all technical decisions documented

## Phase 1: Design & Contracts

**Status**: PENDING (requires Phase 0 completion)

### Data Model

**Status**: PENDING
**Output**: data-model.md with entity definitions and relationships

### CLI Contracts

**Status**: PENDING
**Output**: cli-contract.md with command schemas and interfaces

### Quickstart Guide

**Status**: PENDING
**Output**: quickstart.md with setup and usage instructions

## Implementation Phases Summary

| Phase | Deliverables | Status |
|-------|--------------|--------|
| 0 | research.md with technical decisions | IN PROGRESS |
| 1 | data-model.md, cli-contract.md, quickstart.md | PENDING |
| 2 | tasks.md validation | COMPLETE (needs review against plan) |
