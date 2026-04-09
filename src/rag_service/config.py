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
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator, model_validator
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


class CloudCompletionConfig(BaseSettings):
    """Cloud HTTP completion service configuration.

    Supports direct HTTP calls to remote completion APIs without LiteLLM.
    Compatible with OpenAI-style and custom response formats.
    """

    # Service endpoint
    url: str = Field(default="", description="Cloud completion API URL")
    model: str = Field(default="Qwen3-32B", description="Model name for cloud API")
    timeout: int = Field(default=60, description="Request timeout in seconds")

    # Authentication
    auth_token: str = Field(
        default="",
        description="Basic auth token (e.g., 'base64(username:password)')"
    )

    # Retry settings
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    retry_backoff: float = Field(default=2.0, description="Exponential backoff multiplier")

    # Generation defaults
    temperature: float = Field(default=0.7, description="Default temperature")
    max_tokens: int = Field(default=1000, description="Default max tokens")
    top_p: float = Field(default=0.9, description="Default top_p (nucleus sampling)")

    model_config = SettingsConfigDict(
        env_prefix="CLOUD_COMPLETION_",
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

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, v: float) -> float:
        """Validate top_p is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"top_p must be between 0.0 and 1.0, got {v}")
        return v

    @property
    def enabled(self) -> bool:
        """Check if cloud completion is properly configured."""
        return bool(self.url)


class GLMConfig(BaseSettings):
    """GLM (智谱AI) completion service configuration.

    Supports GLM-4.5, GLM-4.5-air and other models via BigModel Open Platform API.
    API documentation: https://open.bigmodel.cn/api/paas/v4/chat/completions

    Uses Bearer token authentication (API Key).
    Compatible with OpenAI-style chat completion format.
    """

    # Service endpoint
    url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        description="GLM API endpoint URL"
    )
    model: str = Field(
        default="glm-4.5-air",
        description="GLM model name (glm-4.5, glm-4.5-air, glm-4-flash, etc.)"
    )
    timeout: int = Field(default=120, description="Request timeout in seconds")

    # Authentication (Bearer token)
    api_key: str = Field(
        default="",
        description="GLM API Key for Bearer token authentication"
    )

    # Retry settings
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    retry_backoff: float = Field(default=2.0, description="Exponential backoff multiplier")

    # Generation defaults
    temperature: float = Field(default=0.7, description="Default temperature")
    max_tokens: int = Field(default=4096, description="Default max tokens")
    top_p: float = Field(default=0.9, description="Default top_p (nucleus sampling)")

    # GLM-specific options
    enable_thinking: bool = Field(
        default=False,
        description="Enable thinking mode (thinking parameter in request body)"
    )

    model_config = SettingsConfigDict(
        env_prefix="GLM_",
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

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, v: float) -> float:
        """Validate top_p is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"top_p must be between 0.0 and 1.0, got {v}")
        return v

    @property
    def enabled(self) -> bool:
        """Check if GLM is properly configured."""
        return bool(self.api_key)


class CloudEmbeddingConfig(BaseSettings):
    """Cloud HTTP embedding service configuration."""

    url: str = Field(default="", description="Cloud embedding API URL")
    model: str = Field(default="bge-m3", description="Embedding model name")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    auth_token: str = Field(default="", description="Basic auth token")

    model_config = SettingsConfigDict(
        env_prefix="CLOUD_EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def enabled(self) -> bool:
        """Check if cloud embedding is properly configured."""
        return bool(self.url)


class CloudRerankConfig(BaseSettings):
    """Cloud HTTP rerank service configuration."""

    url: str = Field(default="", description="Cloud rerank API URL")
    model: str = Field(default="embed_rerank", description="Rerank model name")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    auth_token: str = Field(default="", description="Basic auth token")
    top_n: int = Field(default=10, description="Return top N results")

    model_config = SettingsConfigDict(
        env_prefix="CLOUD_RERANK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def enabled(self) -> bool:
        """Check if cloud rerank is properly configured."""
        return bool(self.url)


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


class QAConfig(BaseSettings):
    """QA Pipeline configuration."""

    # Query rewriting
    enable_query_rewrite: bool = Field(default=True, description="Enable query rewriting")
    query_rewrite_model: Optional[str] = Field(
        default=None, description="Model for query rewriting (default: main model)"
    )
    query_rewrite_max_length: int = Field(
        default=500, description="Maximum rewritten query length"
    )

    # Hallucination detection
    enable_hallucination_check: bool = Field(
        default=True, description="Enable hallucination detection"
    )
    hallucination_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Similarity threshold (0.0-1.0)"
    )
    hallucination_method: str = Field(
        default="similarity", description="Detection method: similarity or llm"
    )

    # Regeneration
    max_regen_attempts: int = Field(default=1, ge=0, le=3, description="Max regeneration attempts")
    regen_timeout: int = Field(default=3, ge=1, le=10, description="Regeneration timeout (seconds)")

    # Fallback
    fallback_config_path: str = Field(
        default="config/qa_fallback.yaml", description="Fallback messages config file"
    )

    # Prompts (if not using Langfuse)
    prompt_query_rewrite: Optional[str] = Field(
        default=None, description="Query rewrite prompt template"
    )
    prompt_answer_generate: Optional[str] = Field(
        default=None, description="Answer generation prompt template"
    )
    prompt_answer_strict: Optional[str] = Field(
        default=None, description="Strict answer generation prompt (for regeneration)"
    )

    @field_validator("hallucination_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Hallucination threshold must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("max_regen_attempts")
    @classmethod
    def validate_regen_attempts(cls, v: int) -> int:
        """Validate regeneration attempts."""
        if v < 0 or v > 3:
            raise ValueError(f"Max regeneration attempts must be 0-3, got {v}")
        return v

    model_config = SettingsConfigDict(
        env_prefix="QA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class MilvusKBConfig(BaseModel):
    """Milvus Internal Knowledge Base configuration.

    This is specifically for the internal Milvus KB client that provides
    hybrid search (vector + BM25/keyword) as an alternative to the external HTTP KB.

    Note: This uses BaseModel instead of BaseSettings because it's nested within
    the Settings class, and nested BaseSettings don't load env vars correctly.
    """

    milvus_uri: str = Field(default="", description="Milvus server URI (e.g., http://localhost:19530)")
    collection_name: str = Field(default="knowledge_base", description="Collection name for KB")
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    embedding_dimension: int = Field(default=1024, description="Embedding vector dimension (bge-m3: 1024)")

    # Search defaults
    default_search_type: str = Field(
        default="hybrid",
        description="Default search type: 'vector', 'keyword', or 'hybrid'"
    )
    default_limit: int = Field(default=10, description="Default max results")

    # Upload settings
    default_chunk_size: int = Field(default=512, description="Default chunk size in characters")
    default_chunk_overlap: int = Field(default=50, description="Default chunk overlap in characters")
    hybrid_ranker: str = Field(default="RRF", description="Hybrid search ranker type")
    rrf_k: int = Field(default=60, description="RRF ranker k parameter")

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError(f"Timeout must be positive, got {v}")
        return v

    @field_validator("embedding_dimension")
    @classmethod
    def validate_dimension(cls, v: int) -> int:
        """Validate dimension is positive."""
        if v <= 0:
            raise ValueError(f"Embedding dimension must be positive, got {v}")
        return v

    @field_validator("default_search_type")
    @classmethod
    def validate_search_type(cls, v: str) -> str:
        """Validate search type is supported."""
        valid_types = {"vector", "keyword", "hybrid"}
        if v not in valid_types:
            raise ValueError(f"Search type must be one of {valid_types}, got {v}")
        return v

    @model_validator(mode='before')
    @classmethod
    def load_from_env(cls, data: Any) -> Any:
        """Load configuration from environment variables.

        This is needed because nested BaseSettings don't load env vars correctly.
        """
        if isinstance(data, dict):
            import os
            # Override with environment variables if present
            if 'MILVUS_KB_URI' in os.environ:
                data['milvus_uri'] = os.environ['MILVUS_KB_URI']
            if 'MILVUS_KB_COLLECTION_NAME' in os.environ:
                data['collection_name'] = os.environ['MILVUS_KB_COLLECTION_NAME']
            if 'MILVUS_KB_TIMEOUT' in os.environ:
                data['timeout'] = int(os.environ['MILVUS_KB_TIMEOUT'])
            if 'MILVUS_KB_EMBEDDING_DIMENSION' in os.environ:
                data['embedding_dimension'] = int(os.environ['MILVUS_KB_EMBEDDING_DIMENSION'])
            if 'MILVUS_KB_DEFAULT_SEARCH_TYPE' in os.environ:
                data['default_search_type'] = os.environ['MILVUS_KB_DEFAULT_SEARCH_TYPE']
            if 'MILVUS_KB_DEFAULT_LIMIT' in os.environ:
                data['default_limit'] = int(os.environ['MILVUS_KB_DEFAULT_LIMIT'])
            if 'MILVUS_KB_DEFAULT_CHUNK_SIZE' in os.environ:
                data['default_chunk_size'] = int(os.environ['MILVUS_KB_DEFAULT_CHUNK_SIZE'])
            if 'MILVUS_KB_DEFAULT_CHUNK_OVERLAP' in os.environ:
                data['default_chunk_overlap'] = int(os.environ['MILVUS_KB_DEFAULT_CHUNK_OVERLAP'])
            if 'MILVUS_KB_HYBRID_RANKER' in os.environ:
                data['hybrid_ranker'] = os.environ['MILVUS_KB_HYBRID_RANKER']
            if 'MILVUS_KB_RRF_K' in os.environ:
                data['rrf_k'] = int(os.environ['MILVUS_KB_RRF_K'])
        return data

    @property
    def enabled(self) -> bool:
        """Check if Milvus KB is properly configured."""
        return bool(self.milvus_uri)


class Settings(BaseSettings):
    """
    Main settings class aggregating all configuration sections.

    This class provides a single entry point for all configuration
    with environment variable overrides and validation.
    """

    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    milvus_kb: MilvusKBConfig = Field(default_factory=MilvusKBConfig)
    litellm: LiteLLMConfig = Field(default_factory=LiteLLMConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    external_kb: ExternalKBConfig = Field(default_factory=ExternalKBConfig)
    qa: QAConfig = Field(default_factory=QAConfig)
    cloud_completion: CloudCompletionConfig = Field(default_factory=CloudCompletionConfig)
    cloud_embedding: CloudEmbeddingConfig = Field(default_factory=CloudEmbeddingConfig)
    cloud_rerank: CloudRerankConfig = Field(default_factory=CloudRerankConfig)
    glm: GLMConfig = Field(default_factory=GLMConfig)

    # Default model gateway selection
    default_gateway: str = Field(
        default="http",
        description="Default model gateway: 'http' for cloud completion, 'litellm' for LiteLLM, 'glm' for GLM"
    )

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
