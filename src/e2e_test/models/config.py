"""
Configuration model for E2E Test Framework.

Uses pydantic-settings to load from environment variables with E2E_TEST_ prefix.
"""

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OutputFormat(str, Enum):
    """Output format for test reports."""
    CONSOLE = "console"
    JSON = "json"
    HTML = "html"


class TestConfig(BaseSettings):
    """Configuration for E2E Test Framework.

    Loaded from environment variables with E2E_TEST_ prefix.
    """

    # RAG Service connection
    rag_service_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the RAG Service"
    )

    # Execution settings
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds"
    )

    max_concurrent: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Maximum concurrent test executions (1 = sequential)"
    )

    # Similarity settings
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for test to pass"
    )

    # Retry settings
    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts on failure"
    )

    retry_backoff: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Backoff multiplier between retries in seconds"
    )

    # Output settings
    output_format: OutputFormat = Field(
        default=OutputFormat.CONSOLE,
        description="Report output format"
    )

    verbose: bool = Field(
        default=False,
        description="Enable verbose output with detailed information"
    )

    # File discovery
    recursive_discovery: bool = Field(
        default=True,
        description="Recursively discover test files in directories"
    )

    model_config = SettingsConfigDict(
        env_prefix="E2E_TEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("rag_service_url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Remove trailing slash from URL."""
        return v.rstrip("/")
