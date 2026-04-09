"""
Query Rewrite Capability for RAG Service.

This capability rewrites user queries to improve retrieval accuracy
from the knowledge base using LLM-based prompting with Prompt Service integration.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from rag_service.api.qa_schemas import QAContext
from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.exceptions import GenerationError
from rag_service.core.logger import get_logger
from rag_service.config import get_settings
from rag_service.services.prompt_client import (
    get_prompt_client,
    TEMPLATE_QUERY_REWRITE,
)


# Module logger
logger = get_logger(__name__)


class QueryRewriteInput(CapabilityInput):
    """Input for query rewriting."""

    original_query: str = Field(..., description="Original user query")
    context: Optional[QAContext] = Field(default=None, description="Query context")


class QueryRewriteOutput(CapabilityOutput):
    """Output from query rewriting."""

    rewritten_query: str = Field(..., description="Rewritten query")
    original_query: str = Field(..., description="Original query")
    was_rewritten: bool = Field(..., description="Whether query was modified")
    rewrite_reason: Optional[str] = Field(
        default=None, description="Reason for rewrite (e.g., 'added temporal context')"
    )


class QueryRewriteCapability(Capability[QueryRewriteInput, QueryRewriteOutput]):
    """
    Capability for query rewriting.

    This capability uses LLM-based prompting to rewrite user queries
    for better retrieval from the knowledge base.

    Features:
    - Context-aware rewriting (company, document type)
    - Temporal context injection (current date, year)
    - Formal terminology conversion
    - Fallback to original query on failure

    The rewriting process:
    1. Builds a prompt with the original query and context
    2. Calls LLM to generate a more specific query
    3. Validates the rewritten query (not empty, not too long)
    4. Returns rewritten query or falls back to original
    """

    def __init__(self, litellm_client: Optional[Any] = None) -> None:
        """
        Initialize Query Rewrite Capability.

        Args:
            litellm_client: LiteLLM gateway for LLM calls.
        """
        super().__init__()
        self._litellm_client = litellm_client
        self._max_length = get_settings().qa.query_rewrite_max_length
        self._prompt_client = None  # Will be initialized lazily

    async def _get_prompt_client(self):
        """Get or create the prompt client."""
        if self._prompt_client is None:
            self._prompt_client = await get_prompt_client()
        return self._prompt_client

    async def execute(self, input_data: QueryRewriteInput) -> QueryRewriteOutput:
        """
        Execute query rewriting.

        Args:
            input_data: Query rewrite input with original query and context.

        Returns:
            Rewritten query with metadata.

        Raises:
            GenerationError: If LLM call fails and fallback is disabled.
        """
        trace_id = input_data.trace_id
        original_query = input_data.original_query.strip()

        # Handle empty query
        if not original_query:
            logger.warning(
                "Empty query provided for rewriting",
                extra={"trace_id": trace_id},
            )
            return QueryRewriteOutput(
                rewritten_query="",
                original_query="",
                was_rewritten=False,
                trace_id=trace_id,
            )

        # Check if LLM client is available
        if self._litellm_client is None:
            logger.warning(
                "LiteLLM client not configured for query rewriting, using original query",
                extra={"trace_id": trace_id},
            )
            return QueryRewriteOutput(
                rewritten_query=original_query,
                original_query=original_query,
                was_rewritten=False,
                trace_id=trace_id,
            )

        logger.info(
            "Starting query rewriting",
            extra={
                "trace_id": trace_id,
                "original_query": original_query[:100],
            },
        )

        # Build the rewrite prompt with context using Prompt Service
        prompt = await self._build_rewrite_prompt(
            original_query,
            input_data.context,
            trace_id,
        )

        # Call LLM to rewrite query
        try:
            response = await self._litellm_client.acomplete(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3,  # Lower temperature for more deterministic output
            )

            rewritten_query = response.text.strip()

            # Validate the rewritten query
            if not self._is_valid_rewrite(rewritten_query, original_query):
                logger.info(
                    "Rewritten query failed validation, using original",
                    extra={
                        "trace_id": trace_id,
                        "rewritten_query": rewritten_query[:100] if rewritten_query else "",
                    },
                )
                return QueryRewriteOutput(
                    rewritten_query=original_query,
                    original_query=original_query,
                    was_rewritten=False,
                    trace_id=trace_id,
                )

            # Check if query was actually changed
            was_rewritten = rewritten_query.lower() != original_query.lower()
            rewrite_reason = self._get_rewrite_reason(
                original_query,
                rewritten_query,
                input_data.context,
            ) if was_rewritten else None

            logger.info(
                "Query rewriting completed",
                extra={
                    "trace_id": trace_id,
                    "was_rewritten": was_rewritten,
                    "rewritten_query": rewritten_query[:100],
                },
            )

            return QueryRewriteOutput(
                rewritten_query=rewritten_query,
                original_query=original_query,
                was_rewritten=was_rewritten,
                rewrite_reason=rewrite_reason,
                trace_id=trace_id,
            )

        except (GenerationError, Exception) as e:
            logger.error(
                "Query rewriting failed, using original query",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            # Fallback to original query on error
            return QueryRewriteOutput(
                rewritten_query=original_query,
                original_query=original_query,
                was_rewritten=False,
                trace_id=trace_id,
            )

    async def _build_rewrite_prompt(
        self,
        original_query: str,
        context: Optional[QAContext],
        trace_id: str,
    ) -> str:
        """
        Build prompt for query rewriting using Prompt Service.

        Args:
            original_query: Original user query.
            context: Optional query context.
            trace_id: Request trace identifier.

        Returns:
            Prompt string for LLM.
        """
        # Get current date for temporal context
        current_date = datetime.now()
        current_year = str(current_date.year)
        current_month = str(current_date.month)

        # Build context information
        context_parts = []

        if context:
            if context.company_id:
                context_parts.append(f"公司代码: {context.company_id}")
            if context.file_type:
                file_type_desc = {
                    "PublicDocReceive": "收文",
                    "PublicDocDispatch": "发文",
                }.get(context.file_type, context.file_type)
                context_parts.append(f"文档类型: {file_type_desc}")

        context_str = "\n".join(context_parts) if context_parts else "无"

        # Get prompt from Prompt Service
        prompt_client = await self._get_prompt_client()

        variables = {
            "original_query": original_query,
            "context_str": context_str,
            "current_year": current_year,
            "current_month": current_month,
        }

        prompt = await prompt_client.get_prompt(
            template_id=TEMPLATE_QUERY_REWRITE,
            variables=variables,
            trace_id=trace_id,
        )

        return prompt

    def _is_valid_rewrite(self, rewritten_query: str, original_query: str) -> bool:
        """
        Validate that the rewritten query is acceptable.

        Args:
            rewritten_query: The LLM-generated rewritten query.
            original_query: The original user query.

        Returns:
            True if rewritten query is valid, False otherwise.
        """
        # Must not be empty
        if not rewritten_query:
            return False

        # Must not be too long
        if len(rewritten_query) > self._max_length:
            return False

        # Should be reasonably similar to original (not completely unrelated)
        # This is a basic check - more sophisticated checks could be added
        return True

    def _get_rewrite_reason(
        self,
        original_query: str,
        rewritten_query: str,
        context: Optional[QAContext],
    ) -> str:
        """
        Determine the reason for query rewrite.

        Args:
            original_query: Original user query.
            rewritten_query: Rewritten query.
            context: Query context.

        Returns:
            Description of why the query was rewritten.
        """
        reasons = []

        # Check if temporal context was added
        current_year = str(datetime.now().year)
        if current_year in rewritten_query and current_year not in original_query:
            reasons.append("添加时间上下文")

        # Check if formal terminology was added
        formal_terms = ["公司", "制度", "规定", "通知", "办法"]
        if any(term in rewritten_query for term in formal_terms):
            if not any(term in original_query for term in formal_terms):
                reasons.append("使用正式术语")

        # Check if query became more specific
        if len(rewritten_query) > len(original_query) * 1.5:
            reasons.append("增加查询细节")

        return ", ".join(reasons) if reasons else "优化查询表述"

    def validate_input(self, input_data: QueryRewriteInput) -> CapabilityValidationResult:
        """Validate query rewrite input."""
        errors = []
        warnings = []

        # Validate query
        if not input_data.original_query:
            errors.append("Original query cannot be empty")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_health(self) -> dict:
        """Get health status of query rewriting."""
        health = {
            "status": "ready" if self._litellm_client else "not_configured",
            "litellm": "connected" if self._litellm_client else "not_configured",
            "max_length": self._max_length,
        }
        return health
