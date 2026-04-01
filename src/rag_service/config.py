"""
Configuration management for RAG Service.

This module provides environment-based configuration loading with validation
for all RAG service components. It supports both environment variables and
optional config files for flexible deployment.

Configuration Sources (in priority order):
1. Environment variables (highest priority)
2. .env file (if present)
3. Default values
"""

import os
from functools import lru_cache
from typing import Optional, Dict

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MilvusConfig(BaseSettings):
    """Milvus vector database configuration."""

    host: str = Field(default="localhost", description="Milvus server host")
    port: int = Field(default=19530, description="Milvus server port")
    collection_name: str = Field(default="knowledge_base", description="Default collection name")
    dimension: int = Field(default=384, description="Embedding vector dimension")
    index_type: str = Field(default="IVF_FLAT", description="Vector index type")
    metric_type: str = Field(default="L2", description="Distance metric type")
    consistency_level: str = Field(default="Strong", description="Consistency level for queries")

    model_config = SettingsConfigDict(
        env_prefix="MILVUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Milvus port must be between 1 and 65535, got {v}")
        return v

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: int) -> int:
        """Validate dimension is positive."""
        if v <= 0:
            raise ValueError(f"Dimension must be positive, got {v}")
        return v

    @property
    def connection_url(self) -> str:
        """Get Milvus connection URL."""
        return f"http://{self.host}:{self.port}"


class LiteLLMConfig(BaseSettings):
    """LiteLLM gateway configuration."""

    api_key: str = Field(default="", description="LiteLLM API key")
    api_base: str = Field(default="https://api.openai.com/v1", description="LiteLLM API base URL")
    model: str = Field(default="gpt-3.5-turbo", description="Default model to use")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    temperature: float = Field(default=0.7, description="Default temperature for generation")
    max_tokens: int = Field(default=1000, description="Maximum tokens in response")

    model_config = SettingsConfigDict(
        env_prefix="LITELLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("max_retries")
    @classmethod
    def validate_retries(cls, v: int) -> int:
        """Validate retries is non-negative."""
        if v < 0:
            raise ValueError(f"Max retries must be non-negative, got {v}")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError(f"Timeout must be positive, got {v}")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v


class LangfuseConfig(BaseSettings):
    """Langfuse observability configuration."""

    public_key: str = Field(default="", description="Langfuse public key")
    secret_key: str = Field(default="", description="Langfuse secret key")
    host: str = Field(default="https://cloud.langfuse.com", description="Langfuse server URL")
    release: str = Field(default="production", description="Release environment")
    sample_rate: float = Field(default=1.0, description="Trace sampling rate (0-1)")

    model_config = SettingsConfigDict(
        env_prefix="LANGFUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        """Validate sample rate is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Sample rate must be between 0.0 and 1.0, got {v}")
        return v

    @property
    def enabled(self) -> bool:
        """Check if Langfuse is properly configured."""
        return bool(self.public_key and self.secret_key)


class EmbeddingConfig(BaseSettings):
    """Embedding model configuration."""

    model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Embedding model name"
    )
    device: str = Field(default="cpu", description="Device for embeddings (cpu/cuda)")
    batch_size: int = Field(default=32, description="Batch size for embedding generation")

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device is supported."""
        if v not in ("cpu", "cuda"):
            raise ValueError(f"Device must be 'cpu' or 'cuda', got {v}")
        return v


class ServerConfig(BaseSettings):
    """Server configuration."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    log_level: str = Field(default="INFO", description="Logging level")
    reload: bool = Field(default=False, description="Enable auto-reload")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Server port must be between 1 and 65535, got {v}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}, got {v}")
        return v_upper


class CORSConfig(BaseSettings):
    """CORS configuration."""

    origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    allow_credentials: bool = Field(default=True, description="Allow credentials")
    allow_methods: list[str] = Field(default=["GET", "POST", "PUT", "DELETE"], description="Allowed HTTP methods")
    allow_headers: list[str] = Field(default=["*"], description="Allowed HTTP headers")

    model_config = SettingsConfigDict(
        env_prefix="CORS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ExternalKBConfig(BaseSettings):
    """External HTTP Knowledge Base configuration.

    Supports flexible authentication through HTTP headers.
    Common patterns:
    - Bearer token: {"Authorization": "Bearer your-token"}
    - API key: {"x-api-key": "your-api-key"}
    - Custom token: {"X-Token": "your-token"}
    """

    base_url: str = Field(default="", description="External KB base URL")
    endpoint: str = Field(
        default="/cloudoa-ai/ai/file-knowledge/queryKnowledge",
        description="External KB API endpoint"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    enabled: bool = Field(default=True, description="Enable external KB integration")

    # Flexible authentication
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers for authentication. "
                    "Examples: "
                    "- Bearer token: {'Authorization': 'Bearer token'} "
                    "- API key: {'x-api-key': 'api-key'} "
                    "- Custom: {'X-Custom-Auth': 'value'}"
    )
    auth_token: str = Field(
        default="",
        description="Auth token for 'Authorization: Bearer <token>' (shortcut for common Bearer pattern)"
    )

    # Deprecated: Use 'headers' instead
    token: str = Field(
        default="",
        deprecated="Use 'headers'={'xtoken': 'xxx'} or 'auth_token' instead",
        description="Deprecated: Simple token for X-Token header"
    )

    model_config = SettingsConfigDict(
        env_prefix="EXTERNAL_KB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError(f"Timeout must be positive, got {v}")
        return v


class FeatureFlags(BaseSettings):
    """Feature flags for RAG service."""

    enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    non_blocking_tracing: bool = Field(default=True, description="Make tracing non-blocking")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    """
    Main settings class aggregating all configuration sections.

    This class provides a single entry point for all configuration
    with environment variable overrides and validation.
    """

    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    litellm: LiteLLMConfig = Field(default_factory=LiteLLMConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    external_kb: ExternalKBConfig = Field(default_factory=ExternalKBConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function caches the settings to avoid repeated
    environment variable lookups and validation.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()


def reset_settings() -> None:
    """
    Reset the settings cache.

    This is primarily used for testing to allow settings
    to be reloaded between tests.
    """
    get_settings.cache_clear()
