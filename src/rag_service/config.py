"""
Configuration management for RAG Service.

Consolidated from 16 config classes to 5 sections:
- MilvusConfig: Vector DB connection, search, embedding
- LiteLLMConfig: Unified inference gateway (includes HTTP Cloud, GLM as internal providers)
- LangfuseConfig: Observability (unchanged)
- ServerConfig: Server, CORS, feature flags
- QueryConfig: QA pipeline, quality enhancement, external KB, Redis sessions

Backward compatibility:
- Old env vars (CLOUD_COMPLETION_*, GLM_*, QA_*, etc.) are still accepted
- Old Settings attributes (settings.cloud_completion, settings.glm, etc.) work via property aliases
- Deprecation warnings are logged for old env vars

Configuration Sources (in priority order):
1. Environment variables (highest priority)
2. .env file (if present)
3. Default values
"""

import os
import warnings
from functools import lru_cache
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================================
# Milvus Configuration (Consolidated: MilvusConfig + MilvusKBConfig + EmbeddingConfig)
# ============================================================================


class MilvusConfig(BaseSettings):
    """Milvus vector database configuration.

    Consolidates: MilvusConfig, MilvusKBConfig, EmbeddingConfig.
    """

    # Connection
    host: str = Field(default="localhost", description="Milvus server host")
    port: int = Field(default=19530, description="Milvus server port")
    collection_name: str = Field(default="knowledge_base", description="Default collection name")

    # Vector search
    dimension: int = Field(default=1024, description="Embedding vector dimension (bge-m3: 1024)")
    index_type: str = Field(default="IVF_FLAT", description="Vector index type")
    metric_type: str = Field(default="L2", description="Distance metric type")
    consistency_level: str = Field(default="Strong", description="Consistency level for queries")

    # Hybrid search
    default_search_type: str = Field(default="hybrid", description="Search type: vector, keyword, or hybrid")
    default_limit: int = Field(default=10, description="Default max results")

    # Upload/chunking
    chunk_size: int = Field(default=512, description="Default chunk size in characters")
    chunk_overlap: int = Field(default=50, description="Default chunk overlap in characters")
    hybrid_ranker: str = Field(default="RRF", description="Hybrid search ranker type")
    rrf_k: int = Field(default=60, description="RRF ranker k parameter")
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    # Embedding (local sentence-transformers for hallucination detection)
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Local embedding model")
    embedding_device: str = Field(default="cpu", description="Device for embeddings (cpu/cuda)")
    embedding_batch_size: int = Field(default=32, description="Batch size for embedding generation")

    # Milvus KB URI (for hybrid search client)
    milvus_uri: str = Field(default="", description="Milvus server URI override for KB client")

    model_config = SettingsConfigDict(
        env_prefix="MILVUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def connection_url(self) -> str:
        """Get Milvus connection URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def enabled(self) -> bool:
        """Check if Milvus KB is properly configured."""
        return bool(self.milvus_uri) or bool(self.host)


# ============================================================================
# LiteLLM Configuration (Consolidated: LiteLLM + CloudCompletion + GLM + CloudEmbedding + CloudRerank)
# ============================================================================


class ProviderConfig(BaseModel):
    """Internal provider configuration within LiteLLM."""

    url: str = Field(default="", description="Provider API URL")
    model: str = Field(default="", description="Provider model name")
    api_key: str = Field(default="", description="API key for Bearer token auth")
    auth_token: str = Field(default="", description="Basic auth token")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    temperature: float = Field(default=0.7, description="Default temperature")
    max_tokens: int = Field(default=4096, description="Default max tokens")
    top_p: float = Field(default=0.9, description="Default top_p")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    retry_backoff: float = Field(default=2.0, description="Exponential backoff multiplier")
    # GLM-specific
    enable_thinking: bool = Field(default=False, description="Enable GLM thinking mode")

    @property
    def enabled(self) -> bool:
        """Check if provider is properly configured."""
        return bool(self.url or self.api_key)


class LiteLLMConfig(BaseSettings):
    """Unified inference gateway configuration.

    Consolidates: LiteLLMConfig, CloudCompletionConfig, GLMConfig,
    CloudEmbeddingConfig, CloudRerankConfig.

    LITELLM_PROVIDER selects the active provider:
    - "openai": Standard OpenAI-compatible via LiteLLM
    - "cloud_http": HTTP Cloud Completion (internal provider)
    - "glm": GLM/BigModel (internal provider)
    """

    # Active provider selection
    provider: str = Field(default="openai", description="Active provider: openai, cloud_http, or glm")

    # Main LiteLLM settings
    api_key: str = Field(default="", description="LiteLLM API key")
    api_base: str = Field(default="https://api.openai.com/v1", description="LiteLLM API base URL")
    model: str = Field(default="gpt-3.5-turbo", description="Default model to use")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    temperature: float = Field(default=0.7, description="Default temperature for generation")
    max_tokens: int = Field(default=1000, description="Maximum tokens in response")

    # Internal provider configurations (populated from old env vars)
    cloud_http: Optional[ProviderConfig] = Field(default=None, description="Cloud HTTP provider config")
    glm: Optional[ProviderConfig] = Field(default=None, description="GLM provider config")

    # Embedding service (internal)
    embedding_url: str = Field(default="", description="Cloud embedding API URL")
    embedding_model: str = Field(default="bge-m3", description="Embedding model name")
    embedding_timeout: int = Field(default=30, description="Embedding request timeout")
    embedding_auth_token: str = Field(default="", description="Embedding auth token")

    # Rerank service (internal)
    rerank_url: str = Field(default="", description="Cloud rerank API URL")
    rerank_model: str = Field(default="embed_rerank", description="Rerank model name")
    rerank_top_n: int = Field(default=10, description="Rerank top N results")

    model_config = SettingsConfigDict(
        env_prefix="LITELLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {v}")
        return v

    @model_validator(mode="after")
    def load_legacy_providers(self) -> "LiteLLMConfig":
        """Load provider configs from legacy env vars (CLOUD_COMPLETION_*, GLM_*)."""
        # Load Cloud HTTP from CLOUD_COMPLETION_* env vars
        cloud_url = os.environ.get("CLOUD_COMPLETION_URL", "")
        if cloud_url and self.cloud_http is None:
            warnings.warn(
                "CLOUD_COMPLETION_* env vars are deprecated. "
                "Use LITELLM_PROVIDER=cloud_http and LITELLM_CLOUD_HTTP_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.cloud_http = ProviderConfig(
                url=cloud_url,
                model=os.environ.get("CLOUD_COMPLETION_MODEL", "Qwen3-32B"),
                auth_token=os.environ.get("CLOUD_COMPLETION_AUTH_TOKEN", ""),
                timeout=int(os.environ.get("CLOUD_COMPLETION_TIMEOUT", "60")),
                temperature=float(os.environ.get("CLOUD_COMPLETION_TEMPERATURE", "0.7")),
                max_tokens=int(os.environ.get("CLOUD_COMPLETION_MAX_TOKENS", "1000")),
                top_p=float(os.environ.get("CLOUD_COMPLETION_TOP_P", "0.9")),
                max_retries=int(os.environ.get("CLOUD_COMPLETION_MAX_RETRIES", "3")),
                retry_delay=float(os.environ.get("CLOUD_COMPLETION_RETRY_DELAY", "1.0")),
                retry_backoff=float(os.environ.get("CLOUD_COMPLETION_RETRY_BACKOFF", "2.0")),
            )

        # Load GLM from GLM_* env vars
        glm_key = os.environ.get("GLM_API_KEY", "")
        if glm_key and self.glm is None:
            warnings.warn(
                "GLM_* env vars are deprecated. "
                "Use LITELLM_PROVIDER=glm and LITELLM_GLM_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.glm = ProviderConfig(
                url=os.environ.get("GLM_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
                model=os.environ.get("GLM_MODEL", "glm-4.5-air"),
                api_key=glm_key,
                timeout=int(os.environ.get("GLM_TIMEOUT", "120")),
                temperature=float(os.environ.get("GLM_TEMPERATURE", "0.7")),
                max_tokens=int(os.environ.get("GLM_MAX_TOKENS", "4096")),
                top_p=float(os.environ.get("GLM_TOP_P", "0.9")),
                max_retries=int(os.environ.get("GLM_MAX_RETRIES", "3")),
                retry_delay=float(os.environ.get("GLM_RETRY_DELAY", "1.0")),
                retry_backoff=float(os.environ.get("GLM_RETRY_BACKOFF", "2.0")),
                enable_thinking=os.environ.get("GLM_ENABLE_THINKING", "false").lower() == "true",
            )

        # Load embedding from CLOUD_EMBEDDING_* env vars
        emb_url = os.environ.get("CLOUD_EMBEDDING_URL", "")
        if emb_url and not self.embedding_url:
            warnings.warn(
                "CLOUD_EMBEDDING_* env vars are deprecated. "
                "Use LITELLM_EMBEDDING_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.embedding_url = emb_url
            self.embedding_model = os.environ.get("CLOUD_EMBEDDING_MODEL", self.embedding_model)
            self.embedding_timeout = int(os.environ.get("CLOUD_EMBEDDING_TIMEOUT", str(self.embedding_timeout)))
            self.embedding_auth_token = os.environ.get("CLOUD_EMBEDDING_AUTH_TOKEN", "")

        # Auto-detect provider from DEFAULT_GATEWAY (legacy)
        gateway = os.environ.get("DEFAULT_GATEWAY", "")
        if gateway and self.provider == "openai":
            warnings.warn(
                "DEFAULT_GATEWAY env var is deprecated. Use LITELLM_PROVIDER.",
                DeprecationWarning,
                stacklevel=2,
            )
            mapping = {"http": "cloud_http", "glm": "glm", "litellm": "openai"}
            self.provider = mapping.get(gateway, gateway)

        return self

    @property
    def active_provider(self) -> ProviderConfig:
        """Get the active provider configuration based on provider field."""
        if self.provider == "cloud_http" and self.cloud_http:
            return self.cloud_http
        if self.provider == "glm" and self.glm:
            return self.glm
        # Default: return a basic provider from main LiteLLM settings
        return ProviderConfig(
            url=self.api_base,
            model=self.model,
            api_key=self.api_key,
            timeout=self.timeout,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_retries=self.max_retries,
        )


# ============================================================================
# Langfuse Configuration (Unchanged)
# ============================================================================


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


# ============================================================================
# Server Configuration (Consolidated: ServerConfig + CORSConfig + FeatureFlags)
# ============================================================================


class ServerConfig(BaseSettings):
    """Server and operational configuration.

    Consolidates: ServerConfig, CORSConfig, FeatureFlags.
    """

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    log_level: str = Field(default="INFO", description="Logging level")
    reload: bool = Field(default=False, description="Enable auto-reload")

    # CORS
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials")
    cors_allow_methods: list[str] = Field(default=["GET", "POST", "PUT", "DELETE"], description="Allowed methods")
    cors_allow_headers: list[str] = Field(default=["*"], description="Allowed headers")

    # Feature flags
    enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    non_blocking_tracing: bool = Field(default=True, description="Make tracing non-blocking")

    model_config = SettingsConfigDict(
        env_prefix="SERVER_",
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


# ============================================================================
# Query Configuration (Consolidated: QA + QueryQuality + ConversationalQuery + ExternalKB)
# ============================================================================


class ExternalKBSettings(BaseModel):
    """External HTTP Knowledge Base settings (nested in QueryConfig)."""

    base_url: str = Field(default="", description="External KB base URL")
    endpoint: str = Field(default="/cloudoa-ai/ai/file-knowledge/queryKnowledge", description="API endpoint")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    enabled: bool = Field(default=True, description="Enable external KB integration")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP auth headers")
    auth_token: str = Field(default="", description="Bearer auth token shortcut")
    token: str = Field(default="", description="Deprecated: X-Token header")


class QueryConfig(BaseSettings):
    """Unified query pipeline configuration.

    Consolidates: QAConfig, QueryQualityConfig, ConversationalQueryConfig, ExternalKBConfig.

    Strategy selection:
    - retrieval_backend: "milvus" or "external_kb"
    - quality_mode: "basic", "dimension_gather", or "conversational"
    """

    # Strategy selection
    retrieval_backend: str = Field(default="external_kb", description="Retrieval backend: milvus or external_kb")
    quality_mode: str = Field(default="basic", description="Quality mode: basic, dimension_gather, or conversational")

    # Pipeline toggles
    enable_query_rewrite: bool = Field(default=True, description="Enable query rewriting")
    query_rewrite_model: Optional[str] = Field(default=None, description="Model for query rewriting")
    query_rewrite_max_length: int = Field(default=500, description="Max rewritten query length")
    enable_hallucination_check: bool = Field(default=True, description="Enable hallucination detection")
    hallucination_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    hallucination_method: str = Field(default="similarity", description="Detection method: similarity or llm")
    max_regen_attempts: int = Field(default=1, ge=0, le=3, description="Max regeneration attempts")
    regen_timeout: int = Field(default=3, ge=1, le=10, description="Regeneration timeout (seconds)")
    fallback_config_path: str = Field(default="config/qa_fallback.yaml", description="Fallback messages config")

    # Prompt templates
    prompt_query_rewrite: Optional[str] = Field(default=None, description="Query rewrite prompt template")
    prompt_answer_generate: Optional[str] = Field(default=None, description="Answer generation prompt")
    prompt_answer_strict: Optional[str] = Field(default=None, description="Strict answer prompt (regeneration)")

    # External KB
    external_kb: ExternalKBSettings = Field(default_factory=ExternalKBSettings)

    # Session settings (shared by dimension_gather and conversational)
    redis_host: str = Field(default="localhost", description="Redis server host")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis server port")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    redis_password: str = Field(default="", description="Redis password")
    redis_ttl: int = Field(default=900, ge=60, le=86400, description="Redis key TTL in seconds")
    session_timeout: int = Field(default=900, ge=60, le=3600, description="Session timeout in seconds")
    max_turns: int = Field(default=10, ge=1, le=20, description="Max conversation turns")

    # Query quality specific
    enable_auto_enrich: bool = Field(default=True, description="Auto-enrich queries with defaults")
    require_all_dimensions: bool = Field(default=False, description="Require all dimensions before search")
    enable_quality_feedback: bool = Field(default=True, description="Provide quality feedback")
    dimension_analysis_template: str = Field(default="query_dimension_analysis", description="Dimension analysis prompt ID")
    dimension_completion_template: str = Field(default="query_dimension_completion", description="Dimension completion prompt ID")

    # Conversational query specific
    enable_colloquial_mapping: bool = Field(default=True, description="Enable colloquial term mapping")
    enable_domain_routing: bool = Field(default=True, description="Enable domain-based routing")
    enable_followup_detection: bool = Field(default=True, description="Enable pronoun-based follow-up detection")
    enable_synonym_expansion: bool = Field(default=True, description="Enable synonym expansion")
    slot_extraction_template: str = Field(default="slot_extraction", description="Slot extraction prompt ID")
    query_generation_template: str = Field(default="query_generation", description="Query generation prompt ID")
    min_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Min confidence for auto-proceed")
    high_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="High confidence threshold")
    query_generation_count: int = Field(default=3, ge=1, le=5, description="Query variations to generate")
    max_expanded_keywords: int = Field(default=10, ge=5, le=20, description="Max expanded keywords")

    model_config = SettingsConfigDict(
        env_prefix="QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def load_legacy_config(self) -> "QueryConfig":
        """Load config from legacy env vars (QA_*, QUERY_QUALITY_*, CONVERSATIONAL_QUERY_*, EXTERNAL_KB_*)."""
        # QA_ legacy
        qa_rewrite = os.environ.get("QA_ENABLE_QUERY_REWRITE")
        if qa_rewrite is not None:
            warnings.warn(
                "QA_* env vars are deprecated. Use QUERY_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.enable_query_rewrite = qa_rewrite.lower() in ("true", "1", "yes")

        # External KB legacy
        ekb_url = os.environ.get("EXTERNAL_KB_BASE_URL", "")
        if ekb_url and not self.external_kb.base_url:
            warnings.warn(
                "EXTERNAL_KB_* env vars are deprecated. Use QUERY_EXTERNAL_KB_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.external_kb.base_url = ekb_url
            self.external_kb.endpoint = os.environ.get("EXTERNAL_KB_ENDPOINT", self.external_kb.endpoint)
            self.external_kb.timeout = int(os.environ.get("EXTERNAL_KB_TIMEOUT", str(self.external_kb.timeout)))
            self.external_kb.max_retries = int(os.environ.get("EXTERNAL_KB_MAX_RETRIES", str(self.external_kb.max_retries)))
            self.external_kb.auth_token = os.environ.get("EXTERNAL_KB_AUTH_TOKEN", "")

        # Query Quality legacy
        qq_redis = os.environ.get("QUERY_QUALITY_REDIS_HOST")
        if qq_redis and self.redis_host == "localhost":
            warnings.warn(
                "QUERY_QUALITY_* env vars are deprecated. Use QUERY_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.redis_host = qq_redis
            self.redis_port = int(os.environ.get("QUERY_QUALITY_REDIS_PORT", str(self.redis_port)))
            self.redis_db = int(os.environ.get("QUERY_QUALITY_REDIS_DB", str(self.redis_db)))
            self.redis_password = os.environ.get("QUERY_QUALITY_REDIS_PASSWORD", "")
            self.redis_ttl = int(os.environ.get("QUERY_QUALITY_REDIS_TTL", str(self.redis_ttl)))

        # Conversational Query legacy
        cq_redis = os.environ.get("CONVERSATIONAL_QUERY_REDIS_HOST")
        if cq_redis and self.redis_host == "localhost":
            warnings.warn(
                "CONVERSATIONAL_QUERY_* env vars are deprecated. Use QUERY_* vars.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.redis_host = cq_redis
            self.redis_port = int(os.environ.get("CONVERSATIONAL_QUERY_REDIS_PORT", str(self.redis_port)))
            self.redis_db = int(os.environ.get("CONVERSATIONAL_QUERY_REDIS_DB", str(self.redis_db)))
            self.redis_password = os.environ.get("CONVERSATIONAL_QUERY_REDIS_PASSWORD", "")
            self.redis_ttl = int(os.environ.get("CONVERSATIONAL_QUERY_REDIS_TTL", str(self.redis_ttl)))

        return self


# ============================================================================
# Settings (Aggregation with backward-compat aliases)
# ============================================================================


class Settings(BaseSettings):
    """Main settings class aggregating all configuration sections.

    Provides 5 consolidated config sections and backward-compatible
    property aliases for legacy attribute access.
    """

    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    litellm: LiteLLMConfig = Field(default_factory=LiteLLMConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ----------------------------------------------------------------
    # Backward-compat property aliases (old attribute names still work)
    # ----------------------------------------------------------------

    @property
    def cors(self) -> object:
        """Backward-compat: CORS config is now part of ServerConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            origins=self.server.cors_origins,
            allow_credentials=self.server.cors_allow_credentials,
            allow_methods=self.server.cors_allow_methods,
            allow_headers=self.server.cors_allow_headers,
        )

    @property
    def features(self) -> object:
        """Backward-compat: Feature flags are now part of ServerConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            enable_tracing=self.server.enable_tracing,
            enable_metrics=self.server.enable_metrics,
            non_blocking_tracing=self.server.non_blocking_tracing,
        )

    @property
    def cloud_completion(self) -> object:
        """Backward-compat: Cloud completion is now part of LiteLLMConfig."""
        p = self.litellm.cloud_http or ProviderConfig()
        return p

    @property
    def glm(self) -> object:
        """Backward-compat: GLM config is now part of LiteLLMConfig."""
        return self.litellm.glm or ProviderConfig()

    @property
    def cloud_embedding(self) -> object:
        """Backward-compat: Cloud embedding is now part of LiteLLMConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            enabled=bool(self.litellm.embedding_url),
            url=self.litellm.embedding_url,
            model=self.litellm.embedding_model,
            timeout=self.litellm.embedding_timeout,
            auth_token=self.litellm.embedding_auth_token,
        )

    @property
    def cloud_rerank(self) -> object:
        """Backward-compat: Cloud rerank is now part of LiteLLMConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            enabled=bool(self.litellm.rerank_url),
            url=self.litellm.rerank_url,
            model=self.litellm.rerank_model,
            top_n=self.litellm.rerank_top_n,
        )

    @property
    def embedding(self) -> object:
        """Backward-compat: Local embedding config is now part of MilvusConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            model=self.milvus.embedding_model,
            device=self.milvus.embedding_device,
            batch_size=self.milvus.embedding_batch_size,
        )

    @property
    def external_kb(self) -> object:
        """Backward-compat: External KB config is now part of QueryConfig."""
        return self.query.external_kb

    @property
    def qa(self) -> object:
        """Backward-compat: QA config is now part of QueryConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            enable_query_rewrite=self.query.enable_query_rewrite,
            query_rewrite_model=self.query.query_rewrite_model,
            query_rewrite_max_length=self.query.query_rewrite_max_length,
            enable_hallucination_check=self.query.enable_hallucination_check,
            hallucination_threshold=self.query.hallucination_threshold,
            hallucination_method=self.query.hallucination_method,
            max_regen_attempts=self.query.max_regen_attempts,
            regen_timeout=self.query.regen_timeout,
            fallback_config_path=self.query.fallback_config_path,
            prompt_query_rewrite=self.query.prompt_query_rewrite,
            prompt_answer_generate=self.query.prompt_answer_generate,
            prompt_answer_strict=self.query.prompt_answer_strict,
        )

    @property
    def query_quality(self) -> object:
        """Backward-compat: QueryQuality config is now part of QueryConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            session_timeout=self.query.session_timeout,
            max_turns=self.query.max_turns,
            redis_host=self.query.redis_host,
            redis_port=self.query.redis_port,
            redis_db=self.query.redis_db,
            redis_password=self.query.redis_password,
            redis_ttl=self.query.redis_ttl,
            enable_auto_enrich=self.query.enable_auto_enrich,
            require_all_dimensions=self.query.require_all_dimensions,
            enable_quality_feedback=self.query.enable_quality_feedback,
            dimension_analysis_template=self.query.dimension_analysis_template,
            dimension_completion_template=self.query.dimension_completion_template,
        )

    @property
    def conversational_query(self) -> object:
        """Backward-compat: ConversationalQuery config is now part of QueryConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            session_timeout=self.query.session_timeout,
            max_turns=self.query.max_turns,
            redis_host=self.query.redis_host,
            redis_port=self.query.redis_port,
            redis_db=self.query.redis_db,
            redis_password=self.query.redis_password,
            redis_ttl=self.query.redis_ttl,
            enable_colloquial_mapping=self.query.enable_colloquial_mapping,
            enable_domain_routing=self.query.enable_domain_routing,
            enable_followup_detection=self.query.enable_followup_detection,
            enable_synonym_expansion=self.query.enable_synonym_expansion,
            slot_extraction_template=self.query.slot_extraction_template,
            query_generation_template=self.query.query_generation_template,
            min_confidence_threshold=self.query.min_confidence_threshold,
            high_confidence_threshold=self.query.high_confidence_threshold,
            query_generation_count=self.query.query_generation_count,
            max_expanded_keywords=self.query.max_expanded_keywords,
        )

    @property
    def milvus_kb(self) -> object:
        """Backward-compat: MilvusKB config is now part of MilvusConfig."""
        from types import SimpleNamespace
        return SimpleNamespace(
            milvus_uri=self.milvus.milvus_uri,
            collection_name=self.milvus.collection_name,
            timeout=self.milvus.timeout,
            embedding_dimension=self.milvus.dimension,
            default_search_type=self.milvus.default_search_type,
            default_limit=self.milvus.default_limit,
            default_chunk_size=self.milvus.chunk_size,
            default_chunk_overlap=self.milvus.chunk_overlap,
            hybrid_ranker=self.milvus.hybrid_ranker,
            rrf_k=self.milvus.rrf_k,
            enabled=self.milvus.enabled,
        )

    @property
    def default_gateway(self) -> str:
        """Backward-compat: default_gateway derived from litellm.provider."""
        mapping = {"cloud_http": "http", "glm": "glm", "openai": "litellm"}
        return mapping.get(self.litellm.provider, self.litellm.provider)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()


def reset_settings() -> None:
    """Reset the settings cache (primarily for testing)."""
    get_settings.cache_clear()


# ============================================================================
# Backward-compat class aliases (old class names still importable)
# ============================================================================

# Legacy code imports these class names directly. These stub classes
# allow the imports to succeed. Actual config is accessed via Settings properties.
# After all consumers are updated, remove these aliases.

MilvusKBConfig = type("MilvusKBConfig", (), {})
CloudCompletionConfig = type("CloudCompletionConfig", (), {})
GLMConfig = type("GLMConfig", (), {})
CloudEmbeddingConfig = type("CloudEmbeddingConfig", (), {})
CloudRerankConfig = type("CloudRerankConfig", (), {})
CORSConfig = type("CORSConfig", (), {})
FeatureFlags = type("FeatureFlags", (), {})
QAConfig = type("QAConfig", (), {})
QueryQualityConfig = type("QueryQualityConfig", (), {})
ConversationalQueryConfig = type("ConversationalQueryConfig", (), {})
ExternalKBConfig = type("ExternalKBConfig", (), {})
EmbeddingConfig = type("EmbeddingConfig", (), {})
