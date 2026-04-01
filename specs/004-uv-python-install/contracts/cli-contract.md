# CLI Contract: UV Python Runtime Management

**Feature**: 004-uv-python-install
**Version**: 1.0.0
**Date**: 2026-03-20

## Overview

This document defines the CLI contract for the UV Python Runtime Management tool. All commands use standard POSIX conventions and provide consistent output formats.

## Base Command

```bash
uv python <command> [options] [arguments]
```

## Common Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--help` | `-h` | flag | Show help message and exit |
| `--verbose` | `-v` | flag | Enable verbose output |
| `--quiet` | `-q` | flag | Suppress non-error output |
| `--config` | | string | Path to custom config file |

## Common Exit Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 0 | Success | Command completed successfully |
| 1 | General Error | Command failed (check error message) |
| 2 | Invalid Usage | Wrong arguments or options |
| 3 | Network Error | Failed to fetch from API |
| 4 | Checksum Error | Download integrity verification failed |
| 5 | Permission Error | Insufficient permissions |
| 6 | Version Not Found | Requested version not available |

---

## Command: list

List available Python versions from official sources.

### Syntax

```bash
uv python list [options]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--all` | `-a` | flag | false | Include pre-release versions |
| `--installed` | | flag | false | Show only installed versions |
| `--stable` | `-s` | flag | true | Show only stable versions |
| `--format` | `-f` | string | "table" | Output format: table, json, plain |

### Examples

```bash
# List all stable versions
uv python list

# List all versions including pre-releases
uv python list --all

# Show only installed versions
uv python list --installed

# Output as JSON
uv python list --format json
```

### Output Format (table)

```
┏━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Version  ┃ Status     ┃ Platform  ┃ Installed           ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ 3.11.8   │ stable     │ linux     │ ✓                   │
│ 3.11.7   │ stable     │ macos     │ ✓                   │
│ 3.12.0   │ stable     │ windows   │                     │
│ 3.13.0a1 │ pre-release│ linux     │                     │
└──────────┴────────────┴───────────┴────────────────────┘
```

### Output Format (json)

```json
{
  "versions": [
    {
      "version": "3.11.8",
      "status": "stable",
      "platforms": ["linux", "macos", "windows"],
      "installed": true,
      "installed_at": "2024-03-20T10:30:00Z"
    }
  ]
}
```

---

## Command: install

Install a specific Python version.

### Syntax

```bash
uv python install <version> [options]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `version` | string | Python version to install (e.g., "3.11.8", "3.11", "latest") |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--force` | `-f` | flag | false | Reinstall if already installed |
| `--no-cache` | | flag | false | Skip cache, force download |
| `--no-verify` | | flag | false | Skip checksum verification |

### Examples

```bash
# Install specific version
uv python install 3.11.8

# Install latest 3.11
uv python install 3.11

# Reinstall existing version
uv python install 3.11.8 --force

# Install without cache
uv python install 3.12.0 --no-cache
```

### Output Format

```
Downloading Python 3.11.8 for linux...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 28.5 MB/28.5 MB (5.2 MB/s)
Verifying checksum... ✓
Extracting to ~/.local/share/uv/python/3.11.8...
Verifying installation... ✓

Successfully installed Python 3.11.8
Binary: ~/.local/share/uv/python/3.11.8/bin/python3
```

### Error Output

```
Error: Python version 99.0.0 not found
Available versions: 3.7.0 - 3.12.0
```

---

## Command: uninstall

Uninstall a specific Python version.

### Syntax

```bash
uv python uninstall <version> [options]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `version` | string | Python version to uninstall |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--force` | `-f` | flag | false | Force removal without confirmation |

### Examples

```bash
# Uninstall specific version
uv python uninstall 3.11.8

# Force uninstall without confirmation
uv python uninstall 3.11.8 --force
```

---

## Command: global

Set or display the global default Python version.

### Syntax

```bash
uv python global [version] [options]
```

### Arguments

| Argument | Type | Description | Required |
|----------|------|-------------|----------|
| `version` | string | Python version to set as global | No |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--unset` | `-u` | flag | false | Unset global version |

### Examples

```bash
# Set global version
uv python global 3.11.8

# Display current global version
uv python global

# Unset global version
uv python global --unset
```

### Output Format (with argument)

```
Global Python version set to 3.11.8
Config file: ~/.config/uv-python/config.toml
```

### Output Format (without argument)

```
Global Python version: 3.11.8
Binary: ~/.local/share/uv/python/3.11.8/bin/python3
```

---

## Command: pin

Pin a Python version to the current project.

### Syntax

```bash
uv python pin <version> [options]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `version` | string | Python version to pin (e.g., "3.11.8", ">=3.11") |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--file` | `-f` | string | auto | Config file to use (.python-version or pyproject.toml) |

### Examples

```bash
# Pin exact version to .python-version
uv python pin 3.11.8

# Pin version range to pyproject.toml
uv python pin ">=3.11" --file pyproject.toml

# Pin to current directory
uv python pin 3.11.8
```

### Output Format

```
Pinned Python 3.11.8 to .python-version
Project: /current/directory
```

---

## Command: verify

Verify an installed Python version.

### Syntax

```bash
uv python verify <version> [options]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `version` | string | Python version to verify |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--checksum` | `-c` | flag | true | Verify checksum |
| `--binary` | `-b` | flag | true | Verify binary works |

### Examples

```bash
# Verify installation
uv python verify 3.11.8

# Quick verification (no checksum)
uv python verify 3.11.8 --no-checksum
```

### Output Format (success)

```
✓ Python 3.11.8 is valid
  Checksum: verified
  Binary: working
  Last verified: 2024-03-20T16:00:00Z
```

### Output Format (failure)

```
✗ Python 3.11.8 verification failed
  Checksum: mismatch (expected: a1b2..., got: c3d4...)
  Suggestion: Reinstall with --force
```

---

## Command: check

Perform system health check.

### Syntax

```bash
uv python check [options]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--format` | `-f` | string | "table" | Output format: table, json |

### Examples

```bash
# System health check
uv python check

# Output as JSON
uv python check --format json
```

### Output Format (table)

```
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Version     ┃ Status                           ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 3.11.8      │ ✓ Valid, checksum verified      │
│ 3.12.0      │ ✗ Invalid: binary not found     │
│ 3.10.0      │ ⚠ Pending verification          │
└─────────────┴──────────────────────────────────┘

System: Linux x86_64
Config: ~/.config/uv-python/config.toml
Cache: ~/.local/share/uv/python/cache (284 MB used)
```

---

## Error Message Format

All error messages follow this structure:

```
Error: <error_type>: <human_readable_message>

Context: <additional_context>
Suggestion: <actionable_suggestion>

Documentation: https://github.com/uvtool/uv-python/docs/<error_code>
```

### Example Error Messages

```
Error: VersionNotFound: Python version 99.0.0 is not available

Context: Requested version does not exist in python.org releases
Available versions: 3.7.0 through 3.12.0

Suggestion: Run 'uv python list' to see available versions
Documentation: https://github.com/uvtool/uv-python/docs/ERR-001
```

```
Error: DownloadFailed: Failed to download Python 3.11.8 after 3 attempts

Context: Network timeout after 30 seconds
Suggestion: Check your internet connection or try again later
Documentation: https://github.com/uvtool/uv-python/docs/ERR-002
```

```
Error: ChecksumMismatch: Downloaded file checksum does not match

Context: Expected: a1b2c3d4..., Got: e5f6g7h8...
Suggestion: Reinstall with: uv python install 3.11.8 --force
Documentation: https://github.com/uvtool/uv-python/docs/ERR-003
```

---

## Progress Display Format

Download progress uses the following format:

```
<action> <version> for <platform>...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ <percentage> <downloaded>/<total> (<speed>)
```

### Examples

```
Downloading Python 3.11.8 for linux...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 45% 12.8 MB/28.5 MB (4.2 MB/s)

Verifying checksum...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% Computing SHA256...

Extracting...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 67% 4523/6742 files
```

---

## Configuration File Format

### Global Config (~/.config/uv-python/config.toml)

```toml
[python]
default_version = "3.11.8"

[cache]
dir = "~/.local/share/uv/python/cache"
max_size_mb = 1024

[network]
timeout = 30
retries = 3
proxy = ""

[display]
color = "auto"
progress = "auto"
```

### Project Config (.python-version)

```
3.11.8
```

### Project Config (pyproject.toml)

```toml
[project]
requires-python = ">=3.11"
```

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `UV_PYTHON_CONFIG` | Path to custom config file | `/path/to/config.toml` |
| `UV_PYTHON_CACHE_DIR` | Override cache directory | `/tmp/uv-cache` |
| `UV_PYTHON_TIMEOUT` | Network timeout in seconds | `60` |
| `UV_PYTHON_PROXY` | HTTP proxy for downloads | `http://proxy.example.com:8080` |
| `UV_PYTHON_NO_COLOR` | Disable colored output | `1` |
| `UV_PYTHON_QUIET` | Suppress all output | `1` |
| `UV_PYTHON_VERBOSE` | Enable verbose logging | `1` |

---

## Version Specification Formats

| Format | Description | Example |
|--------|-------------|---------|
| Exact | Exact version match | `3.11.8` |
| Minor | Latest patch in minor series | `3.11` |
| Major | Latest version in major series | `3` |
| Latest | Absolute latest version | `latest` |
| Greater than | Minimum version | `>=3.11` |
| Caret | Compatible version (semantic) | `^3.11` |
| Tilde | Minimum version with compatibility | `~3.11.8` |
