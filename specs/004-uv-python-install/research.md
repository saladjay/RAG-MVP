# Research & Technical Decisions: UV Python Runtime Management

**Feature**: 004-uv-python-install
**Date**: 2026-03-20
**Status**: Complete

## Overview

This document consolidates research findings for the UV Python Runtime Management implementation. Each technical decision includes rationale and alternatives considered.

## Technical Decisions

### 1. Python Version Selection

**Decision**: Python 3.11+

**Rationale**:
- Stable and widely adopted (released Oct 2022)
- Full compatibility with uv (which requires 3.8+)
- Excellent performance for I/O-bound operations (CLI tool)
- Best balance of stability and modern features

**Alternatives Considered**:
| Version | Pros | Cons | Decision |
|---------|------|------|----------|
| 3.11 | Stable, mature, fast | None significant | **SELECTED** |
| 3.12 | Latest features | Newer, less tested | Deferred |
| 3.10 | Widely compatible | Older pattern matching | Rejected |

### 2. CLI Framework Selection

**Decision**: Typer for command-line interface

**Rationale**:
- Built on Typer (which uses Click internally)
- Excellent type hint support for automatic CLI generation
- Modern Pythonic API with less boilerplate than Click
- Built-in help text generation from docstrings
- Async support for future extensibility

**Integration Pattern**:
```python
# src/uv_python/cli/main.py
import typer

app = typer.Typer(help="UV Python Runtime Management")

@app.command()
def list(
    all: bool = typer.Option(False, "--all", help="Include pre-release versions"),
    installed: bool = typer.Option(False, "--installed", help="Show only installed")
):
    """List available Python versions"""
    # Implementation

@app.command()
def install(version: str):
    """Install a specific Python version"""
    # Implementation
```

**Alternatives Considered**:
| Framework | Pros | Cons | Decision |
|-----------|------|------|----------|
| Typer | Type hints, modern, less boilerplate | Newer ecosystem | **SELECTED** |
| Click | Mature, widely used | More boilerplate | Rejected |
| argparse | Built-in | Verbose, less user-friendly | Rejected |
| click 8.0+ | Good async support | More setup than Typer | Rejected |

### 3. Python Distribution API Strategy

**Decision**: Multi-source approach with python.org as primary, GitHub as fallback

**Rationale**:
- python.org provides official JSON API for version listing
- GitHub releases serves as reliable backup
- Both sources provide checksums for verification
- Enables resilience if one source is unavailable

**API Endpoints**:
```python
# Primary: python.org API
PYTHON_ORG_API = "https://www.python.org/api/v2/downloads/"

# Fallback: GitHub releases
GITHUB_API = "https://api.github.com/repos/python/cpython/releases"
```

**Integration Pattern**:
```python
# src/uv_python/python_source/client.py
import requests
from typing import List

class PythonSourceClient:
    def __init__(self):
        self.session = requests.Session()
        self.sources = [
            {"name": "python_org", "url": "https://www.python.org/api/v2/downloads/"},
            {"name": "github", "url": "https://api.github.com/repos/python/cpython/releases"}
        ]

    def list_versions(self, include_prerelease: bool = False) -> List[PythonVersion]:
        for source in self.sources:
            try:
                return self._fetch_from_source(source, include_prerelease)
            except Exception as e:
                logger.warning(f"Failed to fetch from {source['name']}: {e}")
        raise AllSourcesFailedError("All Python sources are unavailable")
```

**Best Practices**:
- Use requests.Session for connection pooling
- Implement timeout (5 seconds) for all API calls
- Cache version list locally for 24 hours
- Validate response structure before processing
- Handle rate limiting gracefully

**Alternatives Considered**:
| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Multi-source API | Resilient, official data | More complex | **SELECTED** |
| python.org only | Simplest | Single point of failure | Rejected |
| Web scraping | Most complete | Fragile, violates ToS | Rejected |

### 4. Version Resolution Strategy

**Decision**: Use packaging library for semantic version parsing

**Rationale**:
- packaging.version is the de facto standard for Python version parsing
- Handles complex version ranges (>=3.11, ~=3.11, 3.11.*)
- Official library used by pip and poetry
- Compatible with PEP 440 version specification

**Integration Pattern**:
```python
# src/uv_python/services/version_resolver.py
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet

class VersionResolver:
    def resolve_version(self, requirement: str, available: List[PythonVersion]) -> PythonVersion:
        """Resolve a version requirement to a specific version"""
        try:
            spec = SpecifierSet(requirement)
            for version in sorted(available, reverse=True):
                if Version(version.version_string) in spec:
                    return version
        except InvalidVersion as e:
            raise VersionRequirementError(f"Invalid version requirement: {requirement}")
        raise NoCompatibleVersionError(f"No version matches requirement: {requirement}")
```

**Best Practices**:
- Validate version strings before parsing
- Sort versions in descending order for "latest match" behavior
- Cache parsed version objects for performance
- Provide clear error messages for invalid requirements

**Alternatives Considered**:
| Library | Pros | Cons | Decision |
|---------|------|------|----------|
| packaging | Official, PEP 440 compliant | Can be strict | **SELECTED** |
| semver | Simpler API | Not PEP 440 compliant | Rejected |
| Custom parsing | Full control | Maintenance burden | Rejected |

### 5. Download Progress Display

**Decision**: Use rich library for terminal progress display

**Rationale**:
- rich provides beautiful, cross-platform terminal output
- Built-in progress bar with download speed and ETA
- Supports colors and formatting for better UX
- Integrates well with Typer
- Graceful degradation for non-TTY environments

**Integration Pattern**:
```python
# src/uv_python/services/installer.py
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn

class PythonInstaller:
    def download_with_progress(self, url: str, dest: Path) -> None:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Downloading {url}", total=None)
            # Download with progress updates
```

**Best Practices**:
- Detect TTY environment and disable colors/progress if not present
- Provide simple progress indicators for CI/CD environments
- Show download speed and ETA for long downloads
- Support cancellation on SIGINT

**Alternatives Considered**:
| Library | Pros | Cons | Decision |
|---------|------|------|----------|
| rich | Beautiful, feature-rich | Additional dependency | **SELECTED** |
| tqdm | Lightweight | Less pretty output | Rejected |
| No progress | Fewer dependencies | Poor UX for large downloads | Rejected |

### 6. Checksum Verification Strategy

**Decision**: SHA256 verification using hashlib

**Rationale**:
- Python.org provides SHA256 checksums for all releases
- hashlib is built into Python standard library
- SHA256 is cryptographically secure and widely adopted
- Fast computation on modern hardware

**Integration Pattern**:
```python
# src/uv_python/services/installer.py
import hashlib

class PythonInstaller:
    def verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest() == expected_sha256.lower()
```

**Best Practices**:
- Compute checksum during download (streaming)
- Compare case-insensitive (checksums may be uppercase/lowercase)
- Delete corrupted files immediately after detection
- Log checksum verification for audit trail

**Alternatives Considered**:
| Algorithm | Pros | Cons | Decision |
|-----------|------|------|----------|
| SHA256 | Secure, standard | Slower than MD5 | **SELECTED** |
| SHA512 | More secure | Overkill for this use case | Rejected |
| MD5 | Fast | Cryptographically broken | Rejected |

### 7. Installation Directory Strategy

**Decision**: User-space installation following XDG Base Directory specification

**Rationale**:
- No system privileges required
- Follows platform conventions
- Compatible with uv's existing cache structure
- Supports multiple Python versions without conflicts

**Directory Layout**:
```text
Linux/macOS:
~/.local/share/uv/python/
├── 3.11.8/
│   ├── bin/
│   │   ├── python3
│   │   └── pip3
│   └── lib/
Windows:
%USERPROFILE%\.local\share\uv\python\
├── 3.11.8\
│   ├── python.exe
│   └── Scripts\
```

**Best Practices**:
- Use platformdirs library for cross-platform paths
- Create directory structure atomically
- Set executable permissions on Unix binaries
- Register installation in metadata file

**Alternatives Considered**:
| Location | Pros | Cons | Decision |
|----------|------|------|----------|
| ~/.local/share/uv/python/ | User-space, XDG compliant | Non-standard | **SELECTED** |
| /usr/local/bin/ | Standard location | Requires root | Rejected |
| ~/pyenv/ | Familiar to pyenv users | Conflicts with pyenv | Rejected |

### 8. Configuration File Format

**Decision**: Support both .python-version and pyproject.toml

**Rationale**:
- .python-version is simple and widely adopted (pyenv, asdf)
- pyproject.toml is the modern Python standard
- Supporting both provides maximum compatibility
- Allows migration path from simple to complex configs

**File Formats**:
```text
# .python-version (simple)
3.11.8
```

```toml
# pyproject.toml (standard)
[project]
requires-python = ">=3.11"
```

**Integration Pattern**:
```python
# src/uv_python/services/project_detector.py
class ProjectDetector:
    def detect_version_requirement(self, path: Path) -> Optional[str]:
        # Check .python-version first (simple, explicit)
        python_version_file = path / ".python-version"
        if python_version_file.exists():
            return python_version_file.read_text().strip()

        # Check pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.load(pyproject)
            return data.get("project", {}).get("requires-python")

        return None
```

**Best Practices**:
- .python-version takes precedence (more explicit)
- Parse pyproject.toml using tomllib (Python 3.11+)
- Validate file syntax before reading
- Cache parsed configuration

**Alternatives Considered**:
| Format | Pros | Cons | Decision |
|---------|------|------|----------|
| Both .python-version and pyproject.toml | Maximum compatibility | More complex parsing | **SELECTED** |
| Only .python-version | Simple | Not standard for new projects | Rejected |
| Only pyproject.toml | Standard | Verbose for simple projects | Rejected |

### 9. Global Configuration Storage

**Decision**: TOML file in XDG config directory

**Rationale**:
- Human-readable and editable
- Follows XDG Base Directory specification
- Compatible with uv's configuration approach
- Supports future configuration expansion

**Config Location**:
```text
Linux: ~/.config/uv-python/config.toml
macOS: ~/Library/Application Support/uv-python/config.toml
Windows: %APPDATA%\uv-python\config.toml
```

**Config Structure**:
```toml
# config.toml
[python]
default_version = "3.11.8"
cache_dir = "~/.local/share/uv/python/cache"

[network]
timeout = 30
retries = 3
proxy = ""
```

**Best Practices**:
- Create config directory with parents=True
- Provide defaults for missing values
- Validate config on load
- Support environment variable overrides

**Alternatives Considered**:
| Format | Pros | Cons | Decision |
|---------|------|------|----------|
| TOML | Readable, standard | Requires library | **SELECTED** |
| JSON | Built-in support | Less readable | Rejected |
| YAML | Popular | Additional dependency | Rejected |

### 10. Error Handling Strategy

**Decision**: Custom exception hierarchy with user-friendly messages

**Rationale**:
- Clear separation of error types
- Enables specific error handling
- User-friendly messages for CLI
- Detailed logging for debugging

**Exception Hierarchy**:
```python
# src/uv_python/core/exceptions.py
class UVPythonError(Exception):
    """Base exception for all uv-python errors"""
    pass

class VersionNotFoundError(UVPythonError):
    """Requested Python version not found"""
    pass

class DownloadFailedError(UVPythonError):
    """Download failed after retries"""
    pass

class ChecksumMismatchError(UVPythonError):
    """Downloaded file checksum doesn't match expected"""
    pass

class InstallationError(UVPythonError):
    """Installation process failed"""
    pass
```

**Best Practices**:
- Include actionable error messages
- Log full error context before raising
- Provide error codes for scripting
- Suggest resolution steps in messages

**Alternatives Considered**:
| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Custom exceptions | Clear, type-specific | More code | **SELECTED** |
| Built-in exceptions | Simple | Less context | Rejected |
| Error codes only | Scripting-friendly | Not user-friendly | Rejected |

## Architecture Reference

### Component Responsibilities

| Component | File | Responsibility | Dependencies |
|-----------|------|-----------------|--------------|
| CLI App | cli/main.py | Command registration and routing | Typer |
| Command Handlers | cli/commands.py | CLI command implementations | All services |
| Version Discovery | services/version_discovery.py | List and filter Python versions | python_source client |
| Installer | services/installer.py | Download and install Python | requests, hashlib, rich |
| Project Detector | services/project_detector.py | Detect project config files | pathlib, tomllib |
| Version Resolver | services/version_resolver.py | Resolve version requirements | packaging |
| Global Config | services/global_config.py | Manage global Python version | platformdirs, tomllib |
| Verifier | services/verifier.py | Verify installations | subprocess, pathlib |
| API Client | python_source/client.py | Fetch from python.org/GitHub | requests |

### CLI Commands

| Command | Purpose | Arguments | Output |
|---------|---------|-----------|--------|
| `uv python list` | List available versions | --all, --installed | Table of versions |
| `uv python install <ver>` | Install Python version | version, --force | Progress + success message |
| `uv python global <ver>` | Set global default | version | Confirmation message |
| `uv python verify <ver>` | Verify installation | version | Validation report |
| `uv python check` | System health check | None | All installations status |

## Data Flow Summary

```
1. User runs: `uv python install 3.11.8`
2. CLI → VersionDiscovery.list_versions() → fetch from python.org/GitHub
3. CLI → VersionResolver.resolve_version("3.11.8") → find matching version
4. CLI → Installer.install(version) → download with progress
5. Download → verify SHA256 checksum → validate integrity
6. Extract to ~/.local/share/uv/python/3.11.8/
7. CLI → Verifier.verify("3.11.8") → check binary works
8. Return success message to user
```

## Open Questions & Risks

### Resolved
- ✅ CLI framework: Typer selected
- ✅ Python distribution sources: python.org primary, GitHub fallback
- ✅ Version resolution: packaging.version library
- ✅ Progress display: rich library
- ✅ Installation location: ~/.local/share/uv/python/

### Monitoring
- ⚠️ python.org API rate limiting
- ⚠️ Large downloads (>500MB) on slow connections
- ⚠️ Platform-specific binary extraction issues

### Mitigations
- Implement caching to reduce API calls
- Add resume support for interrupted downloads
- Test on all target platforms (Linux, macOS, Windows)

## References

- [Python Downloads API](https://www.python.org/api/v2/downloads/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [packaging.version](https://packaging.pypa.io/en/stable/version/)
- [rich Progress](https://rich.readthedocs.io/en/stable/progress.html)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
