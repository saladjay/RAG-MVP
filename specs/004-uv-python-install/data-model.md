# Data Model: UV Python Runtime Management

**Feature**: 004-uv-python-install
**Date**: 2026-03-20
**Status**: Complete

## Overview

This document defines all data entities for the UV Python Runtime Management feature, including their fields, relationships, validation rules, and state transitions.

## Entities

### 1. PythonVersion

**Purpose**: Represents a specific Python release available for installation

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| version | str | Yes | Version string (e.g., "3.11.8") | Must be valid semver |
| major | int | Yes | Major version number | 2, 3 |
| minor | int | Yes | Minor version number | 7+ for Python 3 |
| patch | int | Yes | Patch version number | >= 0 |
| release_status | str | Yes | "stable", "pre-release", "dev" | Must be enum value |
| download_url | str | Yes | URL to download binary archive | Must be valid URL |
| checksum | str | Yes | SHA256 checksum of downloaded file | Must be 64 hex chars |
| file_size | int | Yes | Size in bytes | > 0 |
| published_at | datetime | Yes | Release publication date | Valid ISO datetime |
| python_org_id | Optional[int] | No | python.org API ID | > 0 if present |
| platforms | List[str] | Yes | Supported platforms | ["linux", "macos", "windows"] |

**Validation Rules**:
- version must parse as valid `packaging.version.Version`
- release_status must be one of: stable, pre-release, dev
- checksum must be 64 hexadecimal characters
- file_size must be positive integer
- download_url must use HTTPS protocol

**State Machine**: N/A (immutable entity)

---

### 2. Installation

**Purpose**: Represents a Python installation on the local system

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| version | str | Yes | Installed Python version | Must match PythonVersion.version |
| install_path | Path | Yes | Installation directory path | Must be absolute path |
| installed_at | datetime | Yes | Installation timestamp | Valid ISO datetime |
| platform | str | Yes | Platform identifier | linux, macos, windows |
| architecture | str | Yes | CPU architecture | x86_64, arm64, etc. |
| validation_status | str | Yes | "valid", "invalid", "pending" | Must be enum value |
| binary_path | Path | Yes | Path to Python executable | Must exist if status=valid |
| last_verified | Optional[datetime] | No | Last verification timestamp | Valid ISO datetime |
| checksum_verified | bool | Yes | Whether checksum was verified | true/false |

**Validation Rules**:
- install_path must exist and be a directory
- binary_path must point to an executable file
- validation_status must be one of: valid, invalid, pending
- installed_at cannot be in the future

**State Machine**:
```
┌──────────┐  verify()  ┌──────────┐
│  pending │───────────▶│   valid   │
└──────────┘            └──────────┘
    │                        │
    │  verify()              │  re-verify()
    ▼                        ▼
┌──────────┐  re-verify() ┌──────────┐
│ invalid  │─────────────▶│   valid   │
└──────────┘              └──────────┘
```

**States**:
- **pending**: Installation just completed, not yet verified
- **valid**: Binary exists and executes successfully
- **invalid**: Binary corrupted or missing

**Transitions**:
- pending → valid: Successful verification
- pending → invalid: Failed verification (corrupted download, extraction error)
- invalid → valid: Re-download and verify
- valid → valid: Re-verification (no change)

---

### 3. ProjectConfiguration

**Purpose**: Represents project-specific Python version requirements

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| project_path | Path | Yes | Path to project directory | Must exist |
| config_source | str | Yes | "python-version", "pyproject.toml", "none" | Must be enum value |
| required_version | Optional[str] | No | Explicit version requirement | Valid version spec |
| version_range | Optional[str] | No | Semantic version range | Valid specifier set |
| detected_at | datetime | Yes | When config was detected | Valid ISO datetime |
| is_valid | bool | Yes | Whether config is valid | true/false |

**Validation Rules**:
- project_path must be an existing directory
- If required_version is set, it must parse as valid version or range
- version_range must be valid `packaging.specifiers.SpecifierSet`
- config_source must be one of: python-version, pyproject-toml, none

**State Machine**: N/A (derived from file system)

---

### 4. GlobalConfiguration

**Purpose**: Represents system-wide Python version defaults

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| default_version | str | Yes | Global default Python version | Must be installed |
| config_path | Path | Yes | Path to config file | Must be valid path |
| cache_dir | Path | Yes | Download cache directory | Must be writable |
| network_timeout | int | Yes | Network request timeout (seconds) | >= 1 |
| max_retries | int | Yes | Download retry attempts | >= 0 |
| proxy_url | Optional[str] | No | HTTP proxy for downloads | Valid URL if set |
| last_updated | datetime | Yes | Last configuration update | Valid ISO datetime |

**Validation Rules**:
- default_version must correspond to an installed Python version
- cache_dir must be writable or creatable
- network_timeout must be positive (>= 1)
- max_retries must be non-negative (>= 0)
- proxy_url must be valid HTTP/HTTPS URL if set

**State Machine**: N/A (managed by file I/O)

---

### 5. DownloadTask

**Purpose**: Represents an in-progress Python version download

**Fields**:
| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| task_id | str | Yes | Unique task identifier | UUID v4 |
| target_version | str | Yes | Python version being downloaded | Must be available |
| download_url | str | Yes | Source URL | Must be valid HTTPS URL |
| destination_path | Path | Yes | Local file destination | Parent must exist |
| total_bytes | int | Yes | Total file size in bytes | > 0 |
| downloaded_bytes | int | Yes | Bytes downloaded so far | 0 <= downloaded <= total |
| started_at | datetime | Yes | Download start time | Valid ISO datetime |
| status | str | Yes | "downloading", "paused", "completed", "failed" | Must be enum value |
| retry_count | int | Yes | Number of retry attempts | >= 0 |
| error_message | Optional[str] | No | Error details if failed | Set if status=failed |

**Validation Rules**:
- task_id must be valid UUID v4
- downloaded_bytes must be between 0 and total_bytes inclusive
- status must be one of: downloading, paused, completed, failed
- retry_count must be non-negative
- error_message must be set if status=failed

**State Machine**:
```
┌─────────────┐  pause()   ┌─────────┐
│ downloading │───────────▶│ paused  │
└─────────────┘            └─────────┘
     │                          │
     │  complete()              │  resume()
     ▼                          ▼
┌─────────────┐  retry()   ┌─────────────┐
│  completed  │◀───────────│   failed    │
└─────────────┘            └─────────────┘
```

**States**:
- **downloading**: Actively downloading from source
- **paused**: Download paused by user or system
- **completed**: Download finished successfully
- **failed**: Download failed after all retries

**Transitions**:
- downloading → paused: User pauses download
- downloading → completed: Download finishes successfully
- downloading → failed: Download fails after retries exhausted
- paused → downloading: User resumes download
- paused → failed: Resume fails immediately
- failed → downloading: User retries download

## Entity Relationships

```
┌─────────────────┐
│  GlobalConfig   │
│  (system-wide)  │
└─────────────────┘
        │
        │ default_version
        ▼
┌─────────────────┐         ┌─────────────────┐
│  Installation   │─────────▶│  PythonVersion  │
│  (local system) │ uses    │  (available)    │
└─────────────────┘         └─────────────────┘
        ▲
        │
        │ required_version
        │
┌─────────────────┐
│ProjectConfig    │
│  (per-project)  │
└─────────────────┘

┌─────────────────┐
│  DownloadTask   │
│  (transient)    │
└─────────────────┘
        │
        │ downloads
        ▼
┌─────────────────┐
│  PythonVersion  │
└─────────────────┘
```

## Relationship Definitions

### Installation → PythonVersion
- **Type**: Many-to-One
- **Description**: Each Installation corresponds to one PythonVersion
- **Foreign Key**: Installation.version → PythonVersion.version
- **Cardinality**: Multiple installations can exist for same version (different platforms)

### ProjectConfiguration → Installation
- **Type**: Many-to-One (optional)
- **Description**: ProjectConfiguration may reference a required Installation
- **Foreign Key**: ProjectConfiguration.required_version → Installation.version
- **Cardinality**: One project requires one version; one version may be required by many projects

### GlobalConfiguration → Installation
- **Type**: Many-to-One
- **Description**: GlobalConfiguration's default_version references an Installation
- **Foreign Key**: GlobalConfiguration.default_version → Installation.version
- **Cardinality**: One global default; may be changed to reference different installation

### DownloadTask → PythonVersion
- **Type**: Many-to-One
- **Description**: Each DownloadTask downloads one PythonVersion
- **Foreign Key**: DownloadTask.target_version → PythonVersion.version
- **Cardinality**: Multiple concurrent downloads possible for same version

## Storage Mapping

| Entity | Storage | Format | Location |
|--------|---------|--------|----------|
| PythonVersion | N/A | API data | Runtime only (fetched from API) |
| Installation | File system | JSON metadata | ~/.local/share/uv/python/{version}/.uv-python.json |
| ProjectConfiguration | File system | .python-version or pyproject.toml | Project root directory |
| GlobalConfiguration | File system | TOML | ~/.config/uv-python/config.toml |
| DownloadTask | Memory | Python object | Runtime only |

## Example Data

### PythonVersion Example
```json
{
  "version": "3.11.8",
  "major": 3,
  "minor": 11,
  "patch": 8,
  "release_status": "stable",
  "download_url": "https://www.python.org/ftp/python/3.11.8/python-3.11.8-macos11.pkg",
  "checksum": "a1b2c3d4e5f6...",
  "file_size": 28456542,
  "published_at": "2024-02-25T12:00:00Z",
  "python_org_id": 12345,
  "platforms": ["macos"]
}
```

### Installation Example
```json
{
  "version": "3.11.8",
  "install_path": "/Users/username/.local/share/uv/python/3.11.8",
  "installed_at": "2024-03-20T10:30:00Z",
  "platform": "macos",
  "architecture": "arm64",
  "validation_status": "valid",
  "binary_path": "/Users/username/.local/share/uv/python/3.11.8/bin/python3",
  "last_verified": "2024-03-20T10:31:00Z",
  "checksum_verified": true
}
```

### ProjectConfiguration Example
```json
{
  "project_path": "/Users/username/dev/myproject",
  "config_source": "pyproject.toml",
  "required_version": "3.11",
  "version_range": ">=3.11,<3.12",
  "detected_at": "2024-03-20T09:00:00Z",
  "is_valid": true
}
```

### GlobalConfiguration Example
```toml
[python]
default_version = "3.11.8"
cache_dir = "/Users/username/.local/share/uv/python/cache"

[network]
timeout = 30
retries = 3
proxy = ""
```
