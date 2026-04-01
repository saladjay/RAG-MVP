# Feature Specification: UV Python Runtime Management

**Feature Branch**: `004-uv-python-install`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "使用uv安装python" (Use uv to install Python)

## Clarifications

### Session 2026-03-30

- **Q: Spec 004 与 uv 内置 Python 管理的区别是什么？**
  - **A:** Spec 004 应该简化为 **PowerShell/Bash 脚本集合**，而非完整的 Python 运行时管理系统。uv 已提供 `uv python install/list` 等命令，Spec 004 只是提供更友好的脚本包装。

- **Q: 如何简化 uv 命令的使用体验？**
  - **A:** 使用 **PowerShell 或 Bash 脚本**包装 uv 命令，而非构建复杂的 CLI 框架。

- **Q: 需要验证哪些安装状态？**
  - **A:** 主要验证 **安装完整性**（检查 Python 可执行文件是否完整），而非复杂的功能测试或安全扫描。

- **Q: Spec 004 的定位调整**
  - **A:** 从"独立 Python 管理工具"调整为"uv 脚本工具集"，大幅简化范围：
    - 不需要复杂的数据模型和服务层
    - 不需要独立的 CLI 框架（直接使用脚本）
    - 不需要完整的测试套件（测试脚本即可）
    - 主要价值：简化常用操作、提供安装完整性检查

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Python Version Discovery and Selection (Priority: P1)

A developer wants to see available Python versions and select a specific version for their project. The developer needs to discover which Python versions are available and install a specific version without manually downloading from python.org.

**Why this priority**: This is the foundational capability - without knowing available versions and being able to select one, no other operations can proceed. This is the entry point for all Python runtime management.

**Independent Test**: Can be tested by running the tool to list available Python versions and selecting a specific version to install, then verifying the correct version is available locally.

**Acceptance Scenarios**:

1. **Given** the tool is installed, **When** a user runs the list command, **Then** the system displays all available Python versions with their stability status (stable, pre-release)
2. **Given** a list of available versions, **When** a user selects a specific version (e.g., 3.11.8), **Then** the system downloads and installs that Python version
3. **Given** an installed Python version, **When** a user queries installed versions, **Then** the system shows the installation path and version details

---

### User Story 2 - Project-Specific Python Version Pinning (Priority: P1)

A developer wants to associate a specific Python version with their project so that team members use the same version automatically. The developer needs to specify the required Python version in a way that uv can detect and use.

**Why this priority**: Team consistency is critical for reproducible development. Different Python versions can cause subtle bugs, making this a high-priority concern for any team project.

**Independent Test**: Can be tested by creating a project configuration file specifying a Python version, then running uv commands in that project directory and verifying the correct version is used.

**Acceptance Scenarios**:

1. **Given** a project directory, **When** a user specifies Python 3.11.8 in the project config, **Then** uv automatically uses that version for all operations in that directory
2. **Given** a project with a pinned Python version, **When** another developer runs uv commands in that directory, **Then** the same Python version is automatically detected and used
3. **Given** a missing pinned Python version, **When** a user runs uv commands, **Then** uv prompts to install the required version or offers to use an available alternative

---

### User Story 3 - Global Python Version Management (Priority: P2)

A developer wants to set a default Python version for their system when no project-specific version is specified. The developer needs a way to manage a global default that applies to all projects without explicit version requirements.

**Why this priority**: Global default is convenient but less critical than project-specific pinning since projects should override global settings. This is a quality-of-life improvement rather than a core requirement.

**Independent Test**: Can be tested by setting a global Python version, then running uv commands outside any project directory and verifying the global default is used.

**Acceptance Scenarios**:

1. **Given** no project-specific Python version, **When** a user runs uv commands globally, **Then** the system uses the configured global default version
2. **Given** an existing global version, **When** a user changes the global default, **Then** subsequent global operations use the new version
3. **Given** both global and project-specific versions, **When** a user runs commands in a project directory, **Then** the project-specific version takes precedence over the global default

---

### User Story 4 - Python Version Verification and Validation (Priority: P3)

A developer wants to verify that installed Python versions are correctly configured and meet project requirements. The developer needs commands to check Python installation integrity and validate compatibility.

**Why this priority**: Verification is important for troubleshooting but is not required for basic functionality. This supports the core features rather than enabling them.

**Independent Test**: Can be tested by running verification commands on installed Python versions and confirming that valid installations pass verification while corrupted or incomplete installations are detected.

**Acceptance Scenarios**:

1. **Given** an installed Python version, **When** a user runs the verification command, **Then** the system reports whether the installation is complete and functional
2. **Given** a Python version specified in project requirements, **When** a user runs validation, **Then** the system confirms compatibility or suggests alternative compatible versions
3. **Given** multiple installed Python versions, **When** a user runs a system check, **Then** the system reports the status of each installation

---

### Edge Cases

- What happens when the user requests a Python version that doesn't exist or has been withdrawn?
- How does the system handle network interruptions during Python installation?
- What happens when disk space is insufficient during Python download or installation?
- How does the system handle permission issues when installing Python to system directories?
- What happens when the specified Python version is incompatible with the operating system?
- How does the system handle corrupt Python downloads or incomplete installations?
- What happens when multiple Python versions with the same minor version but different patch versions are installed?
- How does the system behave when project configuration specifies an invalid or unavailable Python version?
- What happens when uv's Python cache becomes corrupted or contains partial downloads?
- How does the system handle proxy settings and corporate firewalls during Python download?

## Requirements *(mandatory)*

### Functional Requirements

**简化范围说明**: 以下功能通过 PowerShell/Bash 脚本实现，调用 uv 的内置命令。

- **FR-001**: Scripts MUST provide simple wrapper commands for common uv python operations
- **FR-002**: Scripts MUST support `uv python list` with human-readable output formatting
- **FR-003**: Scripts MUST support `uv python install` with progress indication and error handling
- **FR-004**: Scripts MUST support project Python version detection via `.python-version` or `pyproject.toml`
- **FR-005**: Scripts MUST provide installation integrity verification (checking executable files exist and are runnable)
- **FR-006**: Scripts MUST handle common error cases (network failure, insufficient disk space, permission denied)
- **FR-007**: Scripts MUST be cross-platform compatible (PowerShell for Windows, Bash for Linux/macOS)
- **FR-008**: Scripts MUST support Chinese language error messages and help text

### Key Entities

**简化范围说明**: 不需要复杂数据模型，使用脚本直接调用 uv 命令。

- **Script Files**: PowerShell (.ps1) for Windows, Bash (.sh) for Linux/macOS scripts
- **Configuration Files**: Simple INI or JSON files for default settings (optional)
- **Verification State**: Simple exit codes (0=success, 1=failure) and console output

## Success Criteria *(mandatory)*

### Measurable Outcomes

**简化范围说明**: 脚本工具的成功标准，而非完整应用程序的标准。

- **SC-001**: Scripts can be executed directly without additional setup beyond uv installation
- **SC-002**: List command displays Python versions in human-readable format (not raw JSON)
- **SC-003**: Install command provides clear progress indication and Chinese error messages
- **SC-004**: Verify command can detect corrupted Python installations (missing executables, failed imports)
- **SC-005**: Scripts handle common errors (network timeout, disk space, permissions) with helpful messages
- **SC-006**: Scripts work on Windows (PowerShell) and Linux/macOS (Bash) with identical functionality

## Assumptions

1. **Python Distribution Sources**: Official Python distribution sources (python.org, GitHub releases) are accessible and reliably host Python versions
2. **Network Connectivity**: Users have internet connectivity for downloading Python versions, with caching available for offline scenarios
3. **Operating System Support**: Initial implementation targets Linux and macOS, with Windows support as a secondary priority
4. **uv Integration**: This feature integrates with existing uv tooling and follows uv's configuration and command patterns
5. **User Permissions**: Users have appropriate permissions to install Python in user-writable directories (~/.local/share/uv or equivalent)
6. **Project Configuration Standards**: Projects use standard Python version specification formats (.python-version, pyproject.toml requires.python)
7. **Existing Python Installations**: Users may have existing Python installations that should be detected and optionally managed by uv
8. **Semantic Versioning**: Python versions follow semantic versioning (MAJOR.MINOR.PATCH) and are comparable for version range resolution

## Out of Scope

The following features are explicitly out of scope for this script-based implementation:

- **独立 Python 管理系统**: uv 已经提供 Python 管理功能，我们只做脚本包装，不重新实现
- **CLI 框架**: 不使用 Typer 等框架，直接使用 PowerShell/Bash 脚本
- **复杂服务层**: 不需要 PythonSource, Installer, Verifier 等服务类
- **数据库或状态存储**: 脚本是无状态的，直接调用 uv 命令
- **完整的测试套件**: 不需要 contract/unit/integration 测试分层
- **Web UI 或仪表板**: 仅限命令行脚本
- **并行下载/批量操作**: 脚本顺序执行，不处理并发
- **自定义 Python 构建**: 仅使用 uv 提供的预编译二进制

**依赖关系**: 本功能完全依赖 uv 工具，假设 uv 已正确安装在系统中。
