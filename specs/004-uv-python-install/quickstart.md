# Quick Start Guide: UV Python Runtime Management

**Feature**: 004-uv-python-install
**Version**: 1.0.0
**Last Updated**: 2026-03-20

## Prerequisites

Before you begin, ensure you have:

- **uv** installed: `pip install uv` or visit https://github.com/astral-sh/uv
- **Python 3.11+** available on your system
- **Internet connection** for downloading Python versions
- **500 MB free disk space** for Python installations
- **Write permissions** to your home directory

### Platform-Specific Requirements

**Linux/macOS**:
- bash or zsh shell
- tar command for extracting archives
- wget or curl (usually pre-installed)

**Windows**:
- PowerShell 5.1+ or Windows Terminal
- 7-Zip or built-in archive extraction

---

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### Step 2: Install Dependencies with uv

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Step 3: Verify Installation

```bash
uv-python --help
```

Expected output:
```
UV Python Runtime Management

Commands:
  list      List available Python versions
  install   Install a Python version
  uninstall Uninstall a Python version
  global    Set/display global Python version
  pin       Pin Python version to project
  verify    Verify installed Python version
  check     System health check
```

---

## First Usage

### Listing Available Python Versions

```bash
# List stable versions
uv python list

# List all versions including pre-releases
uv python list --all

# Show only installed versions
uv python list --installed
```

### Installing Python 3.11.8

```bash
uv python install 3.11.8
```

Expected output:
```
Downloading Python 3.11.8 for linux...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 28.5 MB/28.5 MB (5.2 MB/s)
Verifying checksum... ✓
Extracting to ~/.local/share/uv/python/3.11.8...
Verifying installation... ✓

Successfully installed Python 3.11.8
Binary: ~/.local/share/uv/python/3.11.8/bin/python3
```

### Setting Global Default Version

```bash
# Set global default
uv python global 3.11.8

# Verify global default
uv python global
```

### Using in a Project

```bash
# Navigate to your project
cd /path/to/project

# Pin Python version for this project
uv python pin 3.11.8

# Verify the pinned version
cat .python-version
```

---

## Common Workflows

### Setting Up a New Project

```bash
# Create project directory
mkdir myproject && cd myproject

# Initialize project
uv python pin 3.11.8

# Create virtual environment with pinned version
uv venv

# Verify Python version
python --version
# Output: Python 3.11.8
```

### Switching Between Python Versions

```bash
# Install additional version
uv python install 3.12.0

# Pin to project
uv python pin 3.12.0

# Recreate virtual environment
rm -rf .venv
uv venv

# Verify
python --version
# Output: Python 3.12.0
```

### Verifying Installation

```bash
# Check specific version
uv python verify 3.11.8

# Full system health check
uv python check
```

---

## Configuration

### Global Configuration File

Location: `~/.config/uv-python/config.toml` (Linux/macOS) or `%APPDATA%\uv-python\config.toml` (Windows)

Example configuration:
```toml
[python]
default_version = "3.11.8"

[cache]
dir = "~/.local/share/uv/python/cache"
max_size_mb = 1024

[network]
timeout = 30
retries = 3
```

### Environment Variables

```bash
# Set custom cache directory
export UV_PYTHON_CACHE_DIR="/tmp/uv-cache"

# Set network proxy
export UV_PYTHON_PROXY="http://proxy.example.com:8080"

# Disable colored output
export UV_PYTHON_NO_COLOR=1
```

---

## Troubleshooting

### Problem: Version Not Found

**Error**: `Error: Python version 99.0.0 not found`

**Solution**:
```bash
# List available versions
uv python list

# Install an available version
uv python install 3.11.8
```

### Problem: Download Fails

**Error**: `Error: DownloadFailed: Failed to download after 3 attempts`

**Solution**:
```bash
# Check internet connection
ping python.org

# Try with increased timeout
export UV_PYTHON_TIMEOUT=60
uv python install 3.11.8

# Use proxy if needed
export UV_PYTHON_PROXY="http://proxy.example.com:8080"
uv python install 3.11.8
```

### Problem: Checksum Mismatch

**Error**: `Error: ChecksumMismatch: checksum does not match`

**Solution**:
```bash
# Force reinstall
uv python install 3.11.8 --force

# Clear cache and retry
rm -rf ~/.local/share/uv/python/cache/*
uv python install 3.11.8
```

### Problem: Permission Denied

**Error**: `Error: Permission denied when writing to directory`

**Solution**:
```bash
# Ensure home directory is writable
ls -la ~/.local/share/

# Create directory with correct permissions
mkdir -p ~/.local/share/uv/python
chmod 755 ~/.local/share/uv/python
```

---

## Testing

### Run Unit Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest tests/unit/
```

### Run Integration Tests

```bash
# Note: Integration tests require network access
pytest tests/integration/
```

### Run All Tests with Coverage

```bash
pytest --cov=uv_python tests/
```

---

## Uninstallation

### Remove the Tool

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf .venv

# Remove installation
uv pip uninstall uv-python
```

### Remove Installed Python Versions

```bash
# List installed versions
uv python list --installed

# Uninstall specific version
uv python uninstall 3.11.8

# Remove all installations
rm -rf ~/.local/share/uv/python/
```

### Remove Configuration

```bash
# Remove config file
rm ~/.config/uv-python/config.toml

# Remove cache
rm -rf ~/.local/share/uv/python/cache/
```

---

## Next Steps

1. **Read the CLI contract**: `contracts/cli-contract.md` for complete command reference
2. **Review the data model**: `data-model.md` for entity definitions
3. **Check the tasks**: `tasks.md` for implementation status
4. **Explore the code**: `src/uv_python/` for implementation details

---

## Getting Help

### Command Help

```bash
# General help
uv python --help

# Command-specific help
uv python install --help
```

### Verbose Mode

```bash
# Enable verbose output for debugging
uv python install 3.11.8 --verbose
```

### Issue Reporting

If you encounter problems:

1. Check the error message for documentation link
2. Run `uv python check` for system diagnostics
3. Enable verbose mode and retry the command
4. Report issues with: `uv python --version` and error output

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `uv python list` | List available Python versions |
| `uv python install <ver>` | Install a Python version |
| `uv python uninstall <ver>` | Uninstall a Python version |
| `uv python global <ver>` | Set global default version |
| `uv python pin <ver>` | Pin version to current project |
| `uv python verify <ver>` | Verify an installation |
| `uv python check` | System health check |

---

**Estimated Setup Time**: 15 minutes
**Support**: Linux, macOS, Windows (secondary priority)
