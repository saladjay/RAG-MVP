"""
Configuration management for Prompt Management Service.

This module defines all configuration settings using Pydantic Settings.
Settings are loaded from environment variables with sensible defaults.

Core Settings:
- Langfuse: Langfuse observability platform connection
- Cache: Prompt caching configuration
- Service: Server and logging configuration
"""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LangfuseConfig(BaseSettings):
    """Langfuse observability platform configuration.

    Attributes:
        host: Langfuse server URL (default: https://langfuse.cloud)
        public_key: Langfuse public key for authentication
        secret_key: Langfuse secret key for authentication
        enabled: Whether Langfuse integration is enabled
    """

    host: str = Field(
        default="https://langfuse.cloud",
        description="Langfuse server URL"
    )
    public_key: Optional[str] = Field(
        default=None,
        description="Langfuse public key"
    )
    secret_key: Optional[str] = Field(
        default=None,
        description="Langfuse secret key"
    )
    enabled: bool = Field(
        default=True,
        description="Enable Langfuse integration"
    )

    @field_validator("enabled")
    @classmethod
    def check_credentials(cls, v: bool, info) -> bool:
        """Disable Langfuse if credentials are not provided."""
        if v and not info.data.get("public_key"):
            return False
        return v

    model_config = SettingsConfigDict(
        env_prefix="LANGFUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class CacheConfig(BaseSettings):
    """Prompt caching configuration.

    Attributes:
        enabled: Whether L1 (in-memory) caching is enabled
        ttl_seconds: Time-to-live for cached prompts in seconds
        max_size: Maximum number of prompts to cache (LRU eviction)
    """

    enabled: bool = Field(
        default=True,
        description="Enable in-memory L1 caching"
    )
    ttl_seconds: int = Field(
        default=300,
        ge=0,
        description="Cache TTL in seconds (5 minutes default)"
    )
    max_size: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of cached prompts"
    )

    model_config = SettingsConfigDict(
        env_prefix="PROMPT_CACHE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ServiceConfig(BaseSettings):
    """Service configuration.

    Attributes:
        host: Service bind address
        port: Service port number
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        environment: Deployment environment (development, staging, production)
    """

    host: str = Field(
        default="0.0.0.0",
        description="Service bind address"
    )
    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Service port"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    environment: str = Field(
        default="development",
        description="Deployment environment"
    )

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase."""
        return v.upper()

    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Config:
    """Aggregate configuration container.

    This class provides a single entry point for all configuration
    settings. Individual config sections can be accessed as properties.
    """

    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    service: ServiceConfig = Field(default_factory=ServiceConfig)

    def __init__(self):
        """Initialize configuration from environment variables."""
        super().__init__()
        self.langfuse = LangfuseConfig()
        self.cache = CacheConfig()
        self.service = ServiceConfig()

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.service.environment.lower() in ("production", "prod")

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.service.environment.lower() in ("development", "dev")


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    The configuration is loaded once from environment variables
    and cached for subsequent calls.

    Returns:
        Config: The global configuration instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset the global configuration instance.

    This is primarily useful for testing to ensure
    clean configuration between test cases.
    """
    global _config
    _config = None
