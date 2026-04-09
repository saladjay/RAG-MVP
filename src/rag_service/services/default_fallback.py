"""
Default Fallback Service for RAG QA Pipeline.

This service manages predefined fallback messages for error scenarios
when the external knowledge base is unavailable or returns empty results.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class FallbackErrorType(str, Enum):
    """Types of errors that trigger fallback responses."""

    KB_UNAVAILABLE = "kb_unavailable"
    KB_EMPTY = "kb_empty"
    KB_ERROR = "kb_error"
    HALLUCINATION_FAILED = "hallucination_failed"
    REGENERATION_FAILED = "regeneration_failed"
    TIMEOUT = "timeout"


class FallbackRequest(BaseModel):
    """Request for fallback message."""

    error_type: FallbackErrorType = Field(..., description="Type of error")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context for template interpolation"
    )
    language: str = Field(default="zh", description="Language for fallback message")


class FallbackResponse(BaseModel):
    """Fallback message response."""

    message: str = Field(..., description="Fallback message")
    error_type: FallbackErrorType = Field(..., description="Error type")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggestions for user"
    )


class DefaultFallbackService:
    """
    Service for managing default fallback messages.

    This service loads predefined fallback messages from configuration
    and provides templated responses for various error scenarios.

    Features:
    - YAML-based message configuration
    - Multi-language support (zh, en)
    - Template variable interpolation
    - Configurable message suggestions
    """

    def __init__(self, config_path: str = "config/qa_fallback.yaml") -> None:
        """
        Initialize Default Fallback Service.

        Args:
            config_path: Path to fallback messages configuration file.
        """
        self._config_path = Path(config_path)
        self._messages: Dict[str, Dict[str, str]] = {}
        self._load_messages()

    def _load_messages(self) -> None:
        """Load fallback messages from configuration file."""
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    self._messages = config.get("fallback_messages", {})
            else:
                # Use default messages if config file not found
                self._messages = self._get_default_messages()
        except Exception as e:
            # Fall back to defaults if loading fails
            self._messages = self._get_default_messages()

    def _get_default_messages(self) -> Dict[str, Dict[str, str]]:
        """Get default fallback messages."""
        return {
            "kb_unavailable": {
                "zh": "抱歉，知识库暂时无法访问。请稍后再试。",
                "en": "Sorry, the knowledge base is temporarily unavailable. Please try again later.",
            },
            "kb_empty": {
                "zh": "抱歉，没有找到与您的问题相关的信息。",
                "en": "Sorry, no relevant information was found for your question.",
            },
            "kb_error": {
                "zh": "抱歉，查询知识库时发生错误。",
                "en": "Sorry, an error occurred while querying the knowledge base.",
            },
            "hallucination_failed": {
                "zh": "抱歉，无法验证答案的准确性。请谨慎参考。",
                "en": "Sorry, the answer could not be verified. Please use with caution.",
            },
            "regeneration_failed": {
                "zh": "抱歉，生成答案时遇到困难。",
                "en": "Sorry, difficulties were encountered while generating the answer.",
            },
            "timeout": {
                "zh": "抱歉，处理请求超时。",
                "en": "Sorry, the request processing timed out.",
            },
        }

    def get_fallback(
        self,
        error_type: FallbackErrorType,
        context: Optional[Dict[str, Any]] = None,
        language: str = "zh",
    ) -> FallbackResponse:
        """
        Get fallback message for error type.

        Args:
            error_type: Type of error that occurred.
            context: Optional context for template interpolation.
            language: Language for message (zh or en).

        Returns:
            Fallback response with message and suggestions.
        """
        error_key = error_type.value if isinstance(error_type, Enum) else error_type

        # Get message template
        messages_for_type = self._messages.get(error_key, {})
        message_template = messages_for_type.get(language, messages_for_type.get("zh", ""))

        # Interpolate context variables if provided
        if context and message_template:
            try:
                message = message_template.format(**context)
            except KeyError:
                # If template variables are missing, use template as-is
                message = message_template
        else:
            message = message_template

        # Generate suggestions based on error type
        suggestions = self._get_suggestions(error_type, language)

        return FallbackResponse(
            message=message,
            error_type=error_type,
            suggestions=suggestions,
        )

    def _get_suggestions(
        self, error_type: FallbackErrorType, language: str
    ) -> List[str]:
        """Get user suggestions for error type."""
        if language == "zh":
            suggestions_map = {
                FallbackErrorType.KB_UNAVAILABLE: ["请稍后再试", "联系管理员"],
                FallbackErrorType.KB_EMPTY: ["尝试重新表述您的问题", "使用更具体的关键词"],
                FallbackErrorType.KB_ERROR: ["联系管理员并提供错误详情", "稍后重试"],
                FallbackErrorType.HALLUCINATION_FAILED: ["谨慎参考以下内容", "尝试重新表述问题"],
                FallbackErrorType.REGENERATION_FAILED: ["尝试重新表述您的问题", "稍后重试"],
                FallbackErrorType.TIMEOUT: ["简化您的问题", "稍后重试"],
            }
        else:
            suggestions_map = {
                FallbackErrorType.KB_UNAVAILABLE: ["Please try again later", "Contact administrator"],
                FallbackErrorType.KB_EMPTY: ["Try rephrasing your question", "Use more specific keywords"],
                FallbackErrorType.KB_ERROR: ["Contact administrator with error details", "Retry later"],
                FallbackErrorType.HALLUCINATION_FAILED: ["Use the content with caution", "Try rephrasing"],
                FallbackErrorType.REGENERATION_FAILED: ["Try rephrasing your question", "Retry later"],
                FallbackErrorType.TIMEOUT: ["Simplify your question", "Retry later"],
            }

        return suggestions_map.get(error_type, [])

    def reload_messages(self) -> None:
        """Reload fallback messages from configuration file."""
        self._load_messages()
