"""
Prompt Client for RAG Service.

This module provides a convenient interface to the Prompt Service,
supporting template retrieval, variable interpolation, and A/B testing.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from rag_service.core.logger import get_logger

logger = get_logger(__name__)

# Prompt template IDs
TEMPLATE_QUERY_REWRITE = "qa_query_rewrite"
TEMPLATE_ANSWER_GENERATION = "qa_answer_generation"
TEMPLATE_ANSWER_GENERATION_STRICT = "qa_answer_generation_strict"
TEMPLATE_HALLUCINATION_DETECTION = "qa_hallucination_detection"
TEMPLATE_RAG_AGENT_INSTRUCTIONS = "rag_agent_instructions"
TEMPLATE_FALLBACK_RESPONSE = "qa_fallback_response"


class PromptClient:
    """
    Client for accessing Prompt Service.

    This client provides a simple interface for retrieving and rendering
    prompt templates, with fallback to hardcoded prompts if the service
    is unavailable.
    """

    def __init__(
        self,
        enabled: bool = True,
        cache_enabled: bool = True,
        timeout: float = 5.0,
    ):
        """Initialize the prompt client.

        Args:
            enabled: Whether to use Prompt Service (fallback to hardcoded if False)
            cache_enabled: Whether to enable prompt caching
            timeout: Timeout for Prompt Service requests
        """
        self._enabled = enabled
        self._cache_enabled = cache_enabled
        self._timeout = timeout
        self._service_available = None  # Cached availability status
        self._fallback_prompts = self._load_fallback_prompts()

        logger.info(
            "PromptClient initialized",
            extra={
                "enabled": enabled,
                "cache_enabled": cache_enabled,
            },
        )

    def _load_fallback_prompts(self) -> Dict[str, str]:
        """Load fallback hardcoded prompts.

        Returns:
            Dictionary mapping template_id to prompt template string
        """
        return {
            TEMPLATE_QUERY_REWRITE: self._query_rewrite_fallback(),
            TEMPLATE_ANSWER_GENERATION: self._answer_generation_fallback(),
            TEMPLATE_ANSWER_GENERATION_STRICT: self._answer_generation_strict_fallback(),
            TEMPLATE_HALLUCINATION_DETECTION: self._hallucination_detection_fallback(),
            TEMPLATE_RAG_AGENT_INSTRUCTIONS: self._rag_agent_instructions_fallback(),
            TEMPLATE_FALLBACK_RESPONSE: "抱歉，知识库暂时无法访问。请稍后再试或联系管理员获取帮助。",
        }

    async def get_prompt(
        self,
        template_id: str,
        variables: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        version: Optional[int] = None,
        variant_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """
        Get a rendered prompt template.

        Args:
            template_id: The prompt template identifier
            variables: Variable values for interpolation
            context: Additional runtime context
            version: Specific version to retrieve
            variant_id: A/B test variant ID
            trace_id: Request trace identifier

        Returns:
            Rendered prompt string
        """
        variables = variables or {}
        context = context or {}

        # Try Prompt Service if enabled
        if self._enabled and (self._service_available is None or self._service_available):
            try:
                result = await self._fetch_from_service(
                    template_id, variables, context, version, variant_id, trace_id
                )
                if result:
                    self._service_available = True
                    return result
            except Exception as e:
                logger.warning(
                    "Prompt Service unavailable, using fallback",
                    extra={
                        "template_id": template_id,
                        "error": str(e),
                        "trace_id": trace_id,
                    },
                )
                self._service_available = False

        # Use fallback prompt
        return self._render_fallback(template_id, variables, context)

    async def _fetch_from_service(
        self,
        template_id: str,
        variables: Dict[str, Any],
        context: Dict[str, Any],
        version: Optional[int],
        variant_id: Optional[str],
        trace_id: Optional[str],
    ) -> Optional[str]:
        """Fetch prompt from Prompt Service.

        Args:
            template_id: Template identifier
            variables: Variable values
            context: Runtime context
            version: Specific version
            variant_id: A/B test variant
            trace_id: Trace ID

        Returns:
            Rendered prompt or None if unavailable
        """
        try:
            # Import Prompt Service client
            from prompt_service.client.sdk import PromptServiceClient

            client = PromptServiceClient()

            # Retrieve prompt
            result = await client.retrieve(
                template_id=template_id,
                variables=variables,
                context=context,
                version=version,
                variant_id=variant_id,
                trace_id=trace_id,
            )

            logger.info(
                "Prompt retrieved from service",
                extra={
                    "template_id": template_id,
                    "version": result.version_id,
                    "variant_id": result.variant_id,
                    "from_cache": result.from_cache,
                    "trace_id": trace_id,
                },
            )

            return result.content

        except ImportError:
            logger.debug("Prompt Service client not available")
            return None
        except Exception as e:
            logger.warning(
                "Failed to fetch from Prompt Service",
                extra={"error": str(e), "template_id": template_id},
            )
            return None

    def _render_fallback(
        self,
        template_id: str,
        variables: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Render fallback prompt with variables.

        Args:
            template_id: Template identifier
            variables: Variable values
            context: Runtime context

        Returns:
            Rendered prompt string
        """
        template = self._fallback_prompts.get(template_id)
        if template is None:
            logger.warning(
                "Fallback prompt not found",
                extra={"template_id": template_id},
            )
            return ""

        # Simple variable substitution ({{var_name}} format)
        for key, value in variables.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))

        return template

    # Fallback prompt templates
    def _query_rewrite_fallback(self) -> str:
        """Fallback query rewrite prompt."""
        return """你是一个专业的查询优化助手。你的任务是将用户的查询重写为更具体、更容易检索的形式。

原始查询: {{original_query}}

上下文信息:
{{context_str}}
当前日期: {{current_year}}年{{current_month}}月

重写规则:
1. 保持查询的原意不变
2. 添加时间上下文（例如：将"春节"改为"{{current_year}}年春节"）
3. 使用更正式、更具体的术语
4. 如果查询涉及公司制度，添加"公司"或"制度"等关键词
5. 保持查询简洁，不要添加不相关的信息
6. 只返回重写后的查询，不要解释

重写后的查询:"""

    def _answer_generation_fallback(self) -> str:
        """Fallback answer generation prompt."""
        return """You are a helpful assistant that answers questions based on the provided document excerpts.

User question: {{query}}

Relevant document excerpts:
{{chunks_text}}

Instructions:
1. Answer the question using ONLY the information from the provided excerpts
2. If the excerpts don't contain enough information, say so clearly
3. Cite the source documents in your answer using the document names
4. Be accurate and concise
5. Use the same language as the question (Chinese or English)

Answer:"""

    def _answer_generation_strict_fallback(self) -> str:
        """Fallback strict answer generation prompt."""
        return """You are a helpful assistant that answers questions STRICTLY based on the provided document excerpts.

User question: {{query}}

Relevant document excerpts:
{{chunks_text}}

CRITICAL INSTRUCTIONS:
1. You MUST answer using ONLY the information from the provided excerpts
2. Do NOT include any information that is not explicitly stated in the excerpts
3. If the excerpts don't contain enough information, say "根据现有信息，我无法完全回答这个问题" clearly
4. Cite the source documents in your answer using the document names
5. Be accurate and concise
6. Use the same language as the question (Chinese or English)

Remember: It is better to say you don't know than to make up information.

Answer:"""

    def _hallucination_detection_fallback(self) -> str:
        """Fallback hallucination detection prompt."""
        return """你是一个专业的事实核查助手。你的任务是验证给定的回答是否基于提供的参考内容。

参考内容:
{{context}}

待验证的回答:
{{answer}}

请分析待验证的回答，判断其是否符合以下标准：
1. 回答中的关键信息都能在参考内容中找到依据
2. 没有凭空捏造参考内容中没有的信息
3. 没有对参考内容进行歪曲或错误解读

请以JSON格式返回你的分析结果，格式如下:
{
    "is_supported": true/false,
    "confidence": 0.0-1.0之间的置信度分数,
    "reasoning": "详细的分析理由，说明回答是否符合事实以及为什么",
    "issues": ["列出回答中可能存在的问题或没有依据的内容，如果没有则返回空数组"]
}

请只返回JSON，不要包含其他内容:"""

    def _rag_agent_instructions_fallback(self) -> str:
        """Fallback RAG agent instructions."""
        return """You are a helpful AI assistant that answers questions based on retrieved context.

[Retrieved Context]
{{context}}

[User Question]
{{question}}

[Instructions]
Based on the retrieved context above, answer the user's question. If the context doesn't contain relevant information, say so explicitly. Use specific details from the context when possible."""

    async def check_health(self) -> Dict[str, Any]:
        """Check Prompt Service health.

        Returns:
            Health status dictionary
        """
        health = {
            "enabled": self._enabled,
            "service_available": False,
            "fallback_mode": False,
        }

        if self._enabled:
            try:
                from prompt_service.client.sdk import PromptServiceClient

                client = PromptServiceClient()
                # Try to retrieve a simple prompt
                await client.get_prompt(TEMPLATE_FALLBACK_RESPONSE)
                health["service_available"] = True
            except Exception as e:
                health["service_available"] = False
                health["error"] = str(e)

        health["fallback_mode"] = not health["service_available"] and self._enabled
        return health


# Global prompt client instance
_prompt_client: Optional[PromptClient] = None
_client_lock = asyncio.Lock()


async def get_prompt_client() -> PromptClient:
    """Get the global prompt client instance.

    Returns:
        Prompt client instance
    """
    global _prompt_client

    if _prompt_client is None:
        async with _client_lock:
            if _prompt_client is None:
                # Check if Prompt Service should be enabled
                from rag_service.config import get_settings

                settings = get_settings()
                enabled = getattr(settings, "prompt_service_enabled", True)

                _prompt_client = PromptClient(enabled=enabled)
                logger.info("Initialized global prompt client")

    return _prompt_client


def reset_prompt_client() -> None:
    """Reset the global prompt client instance.

    This is primarily useful for testing.
    """
    global _prompt_client
    _prompt_client = None
