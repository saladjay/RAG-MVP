"""
Configuration management for uv_python.

This module provides environment variable loading and validation for
application configuration. It supports both environment variables and
configuration file-based settings.
"""

import os
import platform
from pathlib import Path
from typing import Optional

import platformdirs
import toml

from uv_python.core.exceptions import ConfigurationError


class Config:
    """
    Application configuration manager.

    Loads configuration from environment variables and configuration files.
    Environment variables take precedence over file-based configuration.

    Attributes:
        default_version: Global default Python version
        cache_dir: Directory for caching downloaded Python versions
        config_dir: Directory for configuration files
        install_dir: Directory for Python installations
        network_timeout: Network request timeout in seconds
        max_retries: Maximum download retry attempts
        proxy_url: HTTP proxy URL for downloads
        verbose: Enable verbose output
        quiet: Suppress non-error output
        no_color: Disable colored output
    """

    DEFAULT_CONFIG_FILE = "config.toml"
    DEFAULT_NETWORK_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_CACHE_SIZE_MB = 1024

    def __init__(self, config_file: Optional[Path] = None) -> None:
        """
        Initialize configuration from environment and config file.

        Args:
            config_file: Optional path to custom configuration file.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        self._config_file: Optional[Path] = config_file
        self._config_data: dict = {}

        # Set platform-specific directories
        self.system = platform.system().lower()
        self.architecture = platform.machine().lower()

        # Load configuration
        self._load_from_file()
        self._load_from_env()

    @property
    def config_dir(self) -> Path:
        """Get configuration directory path."""
        if env_config := os.getenv("UV_PYTHON_CONFIG"):
            return Path(env_config).parent
        return Path(platformdirs.user_config_dir("uv-python"))

    @property
    def config_file(self) -> Path:
        """Get configuration file path."""
        if custom := self._config_file:
            return custom
        return self.config_dir / self.DEFAULT_CONFIG_FILE

    @property
    def cache_dir(self) -> Path:
        """Get cache directory path."""
        if env_cache := os.getenv("UV_PYTHON_CACHE_DIR"):
            return Path(env_cache)
        # Check config file
        if cache_path := self._config_data.get("cache", {}).get("dir"):
            return Path(cache_path).expanduser()
        # Default to platform-specific location
        return Path(platformdirs.user_data_dir("uv")) / "python" / "cache"

    @property
    def install_dir(self) -> Path:
        """Get Python installation directory path."""
        return Path(platformdirs.user_data_dir("uv")) / "python"

    @property
    def network_timeout(self) -> int:
        """Get network timeout in seconds."""
        if env_timeout := os.getenv("UV_PYTHON_TIMEOUT"):
            try:
                timeout = int(env_timeout)
                if timeout < 1:
                    raise ConfigurationError("Network timeout must be >= 1 second")
                return timeout
            except ValueError as e:
                raise ConfigurationError(f"Invalid UV_PYTHON_TIMEOUT: {e}")
        # Check config file
        if timeout := self._config_data.get("network", {}).get("timeout"):
            return int(timeout)
        return self.DEFAULT_NETWORK_TIMEOUT

    @property
    def max_retries(self) -> int:
        """Get maximum download retry attempts."""
        if env_retries := os.getenv("UV_PYTHON_RETRIES"):
            try:
                retries = int(env_retries)
                if retries < 0:
                    raise ConfigurationError("Max retries must be >= 0")
                return retries
            except ValueError as e:
                raise ConfigurationError(f"Invalid UV_PYTHON_RETRIES: {e}")
        # Check config file
        if retries := self._config_data.get("network", {}).get("retries"):
            return int(retries)
        return self.DEFAULT_MAX_RETRIES

    @property
    def proxy_url(self) -> Optional[str]:
        """Get HTTP proxy URL for downloads."""
        if proxy := os.getenv("UV_PYTHON_PROXY"):
            return proxy
        # Check config file
        return self._config_data.get("network", {}).get("proxy") or None

    @property
    def default_version(self) -> Optional[str]:
        """Get global default Python version."""
        if version := self._config_data.get("python", {}).get("default_version"):
            return version
        return None

    @property
    def verbose(self) -> bool:
        """Check if verbose output is enabled."""
        return os.getenv("UV_PYTHON_VERBOSE", "0").lower() in ("1", "true", "yes")

    @property
    def quiet(self) -> bool:
        """Check if quiet mode is enabled."""
        return os.getenv("UV_PYTHON_QUIET", "0").lower() in ("1", "true", "yes")

    @property
    def no_color(self) -> bool:
        """Check if colored output is disabled."""
        return os.getenv("UV_PYTHON_NO_COLOR", "0").lower() in ("1", "true", "yes")

    def _load_from_file(self) -> None:
        """Load configuration from TOML file."""
        if not self.config_file.exists():
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self._config_data = toml.load(f)
        except (OSError, toml.TomlDecodeError) as e:
            raise ConfigurationError(f"Failed to load config file {self.config_file}: {e}")

    def _load_from_env(self) -> None:
        """Load configuration overrides from environment variables."""
        # Environment variables are already handled in properties
        pass

    def save_default_version(self, version: str) -> None:
        """
        Save the global default Python version to config file.

        Args:
            version: Python version to set as default.

        Raises:
            ConfigurationError: If config file cannot be written.
        """
        self._config_data.setdefault("python", {})["default_version"] = version

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                toml.dump(self._config_data, f)
        except OSError as e:
            raise ConfigurationError(f"Failed to write config file {self.config_file}: {e}")

    def unset_default_version(self) -> None:
        """
        Remove the global default Python version from config file.

        Raises:
            ConfigurationError: If config file cannot be written.
        """
        if "python" in self._config_data:
            self._config_data["python"].pop("default_version", None)

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                toml.dump(self._config_data, f)
        except OSError as e:
            raise ConfigurationError(f"Failed to write config file {self.config_file}: {e}")

    def ensure_directories(self) -> None:
        """
        Create required directories if they don't exist.

        Raises:
            ConfigurationError: If directories cannot be created.
        """
        directories = [
            self.config_dir,
            self.cache_dir,
            self.install_dir,
        ]

        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ConfigurationError(f"Failed to create directory {directory}: {e}")


# Global configuration instance
_config: Optional[Config] = None


def get_config(config_file: Optional[Path] = None) -> Config:
    """
    Get the global configuration instance.

    Args:
        config_file: Optional path to custom configuration file.

    Returns:
        The global Config instance.
    """
    global _config
    if _config is None:
        _config = Config(config_file)
    return _config


def reset_config() -> None:
    """Reset the global configuration instance (primarily for testing)."""
    global _config
    _config = None
