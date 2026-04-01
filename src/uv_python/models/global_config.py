"""
Global configuration data model.

This module provides the GlobalConfiguration dataclass for representing
system-wide Python version defaults and settings.
"""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from packaging.version import Version


@dataclass
class GlobalConfiguration:
    """
    Represents system-wide Python version defaults and settings.

    This dataclass captures global configuration including default Python
    version, cache directory, and network settings.

    Attributes:
        default_version: Global default Python version (e.g., "3.11.8").
        config_path: Path to config file.
        cache_dir: Download cache directory.
        network_timeout: Network request timeout in seconds.
        max_retries: Maximum download retry attempts.
        proxy_url: Optional HTTP proxy URL.
        last_updated: Last configuration update timestamp.
    """

    default_version: str
    config_path: Path
    cache_dir: Path
    network_timeout: int
    max_retries: int
    proxy_url: Optional[str]
    last_updated: datetime

    def __post_init__(self) -> None:
        """Validate GlobalConfiguration fields after initialization."""
        # Validate default version
        try:
            Version(self.default_version)
        except ValueError as e:
            raise ValueError(f"Invalid default_version '{self.default_version}': {e}")

        # Validate paths
        if not isinstance(self.config_path, Path):
            self.config_path = Path(self.config_path)
        if not isinstance(self.cache_dir, Path):
            self.cache_dir = Path(self.cache_dir)

        # Validate numeric values
        if self.network_timeout < 1:
            raise ValueError("network_timeout must be >= 1")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        # Validate proxy URL if present
        if self.proxy_url and not (self.proxy_url.startswith("http://") or self.proxy_url.startswith("https://")):
            raise ValueError("proxy_url must use http:// or https://")

    def to_dict(self) -> dict:
        """
        Convert GlobalConfiguration to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "default_version": self.default_version,
            "config_path": str(self.config_path),
            "cache_dir": str(self.cache_dir),
            "network_timeout": self.network_timeout,
            "max_retries": self.max_retries,
            "proxy_url": self.proxy_url,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GlobalConfiguration":
        """
        Create GlobalConfiguration from dictionary.

        Args:
            data: Dictionary containing configuration data.

        Returns:
            GlobalConfiguration instance.
        """
        last_updated = data.get("last_updated")
        if last_updated:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        else:
            last_updated = datetime.now()

        return cls(
            default_version=data["default_version"],
            config_path=Path(data["config_path"]),
            cache_dir=Path(data["cache_dir"]),
            network_timeout=data.get("network_timeout", 30),
            max_retries=data.get("max_retries", 3),
            proxy_url=data.get("proxy_url"),
            last_updated=last_updated,
        )

    def save(self) -> None:
        """
        Save configuration to TOML file.

        Raises:
            OSError: If file cannot be written.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {
            "python": {
                "default_version": self.default_version,
            },
            "cache": {
                "dir": str(self.cache_dir),
            },
            "network": {
                "timeout": self.network_timeout,
                "retries": self.max_retries,
                "proxy": self.proxy_url or "",
            },
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            import toml
            toml.dump(config_data, f)

        self.last_updated = datetime.now()

    @classmethod
    def load(cls, config_path: Path) -> Optional["GlobalConfiguration"]:
        """
        Load configuration from TOML file.

        Args:
            config_path: Path to config file.

        Returns:
            GlobalConfiguration instance or None if file doesn't exist.
        """
        if not config_path.exists():
            return None

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            return None

        python_config = data.get("python", {})
        cache_config = data.get("cache", {})
        network_config = data.get("network", {})

        return cls(
            default_version=python_config.get("default_version", ""),
            config_path=config_path,
            cache_dir=Path(cache_config.get("dir", "~/.local/share/uv/python/cache")).expanduser(),
            network_timeout=network_config.get("timeout", 30),
            max_retries=network_config.get("retries", 3),
            proxy_url=network_config.get("proxy") or None,
            last_updated=datetime.now(),
        )

    @classmethod
    def create(
        cls,
        default_version: str,
        config_path: Path,
        cache_dir: Path,
        network_timeout: int = 30,
        max_retries: int = 3,
        proxy_url: Optional[str] = None,
    ) -> "GlobalConfiguration":
        """
        Create a new GlobalConfiguration instance.

        Args:
            default_version: Default Python version.
            config_path: Path to config file.
            cache_dir: Cache directory path.
            network_timeout: Network timeout in seconds.
            max_retries: Maximum retry attempts.
            proxy_url: Optional proxy URL.

        Returns:
            GlobalConfiguration instance.
        """
        return cls(
            default_version=default_version,
            config_path=config_path,
            cache_dir=cache_dir,
            network_timeout=network_timeout,
            max_retries=max_retries,
            proxy_url=proxy_url,
            last_updated=datetime.now(),
        )

    def update_default_version(self, version: str) -> None:
        """
        Update the default Python version.

        Args:
            version: New default version.
        """
        try:
            Version(version)
        except ValueError as e:
            raise ValueError(f"Invalid version '{version}': {e}")

        self.default_version = version
        self.last_updated = datetime.now()

    def clear_default_version(self) -> None:
        """Clear the default Python version."""
        self.default_version = ""
        self.last_updated = datetime.now()

    def __str__(self) -> str:
        """Return string representation."""
        parts = [f"Global: {self.default_version or 'not set'}"]
        if self.proxy_url:
            parts.append(f" (proxy: {self.proxy_url})")
        return "".join(parts)
