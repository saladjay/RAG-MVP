"""
Prompt Retrieval Service for fetching and caching prompts.

This service handles the core prompt retrieval flow:
1. Check L1 cache for rendered prompt
2. Check for active A/B tests (future - US3)
3. Load template from Langfuse
4. Assemble prompt via PromptAssemblyService
5. Cache result for subsequent requests
6. Return assembled prompt with metadata

The service provides the primary interface for business code to
retrieve prompts without direct Langfuse dependency.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_service.config import get_config
from prompt_service.core.exceptions import PromptNotFoundError, PromptServiceUnavailableError
from prompt_service.core.logger import get_logger, set_trace_id
from prompt_service.middleware.cache import get_cache
from prompt_service.models.prompt import (
    PromptAssemblyContext,
    PromptAssemblyResult,
    PromptTemplate,
)
from prompt_service.services.langfuse_client import get_langfuse_client
from prompt_service.services.prompt_assembly import get_prompt_assembly_service

logger = get_logger(__name__)


class PromptRetrievalService:
    """Service for retrieving and rendering prompt templates.

    This service orchestrates the complete prompt retrieval flow
    including caching, Langfuse integration, and prompt assembly.

    Attributes:
        _langfuse_client: Langfuse client wrapper
        _assembly_service: Prompt assembly service
        _cache: L1 in-memory cache
        _config: Service configuration
    """

    def __init__(
        self,
        cache_enabled: Optional[bool] = None,
    ):
        """Initialize the prompt retrieval service.

        Args:
            cache_enabled: Override cache setting (uses config if None)
        """
        self._config = get_config()
        self._langfuse_client = get_langfuse_client()
        self._assembly_service = get_prompt_assembly_service()
        self._cache = get_cache()

        # Use override or config setting
        if cache_enabled is not None:
            self._cache_enabled = cache_enabled
        else:
            self._cache_enabled = self._config.cache.enabled

        logger.info(
            "PromptRetrievalService initialized",
            extra={"cache_enabled": self._cache_enabled}
        )

    async def retrieve(
        self,
        template_id: str,
        variables: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        retrieved_docs: Optional[List[Dict[str, Any]]] = None,
        version: Optional[int] = None,
        variant_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> PromptAssemblyResult:
        """Retrieve and render a prompt template.

        This is the primary entry point for prompt retrieval. It handles
        caching, template loading, and prompt assembly.

        Args:
            template_id: The prompt template identifier
            variables: Variable values for interpolation
            context: Additional runtime context
            retrieved_docs: Retrieved documents for inclusion
            version: Specific version to retrieve (uses active if None)
            variant_id: A/B test variant ID (if applicable)
            trace_id: Request trace identifier

        Returns:
            Assembled prompt with metadata

        Raises:
            PromptNotFoundError: If template not found
            PromptServiceUnavailableError: If service unavailable
            PromptValidationError: If validation fails
        """
        # Set trace_id for this request
        trace_id = trace_id or str(uuid.uuid4())
        set_trace_id(trace_id)

        variables = variables or {}
        context = context or {}
        retrieved_docs = retrieved_docs or []

        logger.info(
            "Retrieving prompt",
            extra={
                "template_id": template_id,
                "version": version,
                "variant_id": variant_id,
                "trace_id": trace_id,
            }
        )

        # Check cache first
        if self._cache_enabled:
            cached = self._cache.get(template_id, version, variant_id)
            if cached is not None:
                logger.info(
                    "Prompt retrieved from cache",
                    extra={
                        "template_id": template_id,
                        "trace_id": trace_id,
                    }
                )
                # Update from_cache flag
                cached.from_cache = True
                return cached

        # Load template from Langfuse
        template = await self._load_template(template_id, version, trace_id)
        if template is None:
            raise PromptNotFoundError(
                template_id=template_id,
                version=version,
                trace_id=trace_id,
            )

        # Check if there's an active A/B test for this template
        # Get user_id from context for deterministic routing
        user_id = context.get("user_id", "anonymous")
        if variant_id is None:
            variant_id = await self._get_ab_test_variant(template_id, user_id, trace_id)

        # Assemble the prompt
        assembly_context = PromptAssemblyContext(
            template=template,
            variables=variables,
            context=context,
            retrieved_docs=retrieved_docs,
            version_id=version,
            variant_id=variant_id,
            trace_id=trace_id,
        )

        result = self._assembly_service.assemble_prompt(assembly_context)

        # Cache the result
        if self._cache_enabled:
            self._cache.set(
                template_id=template_id,
                value=result,
                version=version,
                variant_id=variant_id,
            )

        # Record trace for analytics
        self._record_trace(
            trace_id=trace_id,
            template_id=template_id,
            template_version=template.version,
            variant_id=variant_id,
            rendered_prompt=result.content,
            variables=variables,
            context=context,
            retrieved_docs=retrieved_docs,
        )

        # Log trace to Langfuse
        self._log_trace(
            template_id=template_id,
            version=template.version,
            variant_id=variant_id,
            variables=variables,
            context=context,
            output=result.content,
            trace_id=trace_id,
        )

        return result

    def _record_trace(
        self,
        trace_id: str,
        template_id: str,
        template_version: int,
        variant_id: Optional[str],
        rendered_prompt: str,
        variables: Dict[str, Any],
        context: Dict[str, Any],
        retrieved_docs: List[Dict[str, Any]],
    ) -> None:
        """Record a trace for analytics.

        Args:
            trace_id: Trace identifier
            template_id: Template identifier
            template_version: Template version
            variant_id: Variant ID if A/B test
            rendered_prompt: Rendered prompt content
            variables: Input variables
            context: Runtime context
            retrieved_docs: Retrieved documents
        """
        from prompt_service.services.trace_analysis import get_trace_analysis_service

        try:
            analysis_service = get_trace_analysis_service()
            analysis_service.record_trace(
                trace_id=trace_id,
                template_id=template_id,
                template_version=template_version,
                variant_id=variant_id,
                rendered_prompt=rendered_prompt,
                input_variables=variables,
                context=context,
                retrieved_docs=retrieved_docs,
            )
        except Exception as e:
            # Don't fail the request if trace recording fails
            logger.warning(
                "Failed to record trace",
                extra={
                    "trace_id": trace_id,
                    "error": str(e),
                }
            )

    async def _get_ab_test_variant(
        self,
        template_id: str,
        user_id: str,
        trace_id: str,
    ) -> Optional[str]:
        """Get the A/B test variant for a template and user.

        Uses deterministic hash-based routing to ensure consistent
        variant assignment across requests.

        Args:
            template_id: Template identifier
            user_id: User ID for routing
            trace_id: Trace identifier

        Returns:
            Variant ID if an active test exists, None otherwise
        """
        from prompt_service.services.ab_testing import get_ab_testing_service

        ab_service = get_ab_testing_service()
        active_test = ab_service.get_active_test_for_template(template_id)

        if active_test is None:
            return None

        # Assign variant using deterministic routing
        variant_id = ab_service.assign_variant(active_test.test_id, user_id)

        if variant_id:
            logger.info(
                "A/B test variant assigned",
                extra={
                    "template_id": template_id,
                    "test_id": active_test.test_id,
                    "variant_id": variant_id,
                    "user_id": user_id,
                    "trace_id": trace_id,
                }
            )

        return variant_id

    async def _load_template(
        self,
        template_id: str,
        version: Optional[int],
        trace_id: str,
    ) -> Optional[PromptTemplate]:
        """Load a prompt template from Langfuse.

        Args:
            template_id: The prompt template identifier
            version: Optional specific version
            trace_id: Request trace identifier

        Returns:
            Prompt template or None if not found
        """
        langfuse_data = self._langfuse_client.get_prompt(
            template_id=template_id,
            version=version,
        )

        if langfuse_data is None:
            return None

        # Convert Langfuse data to PromptTemplate
        # For now, construct a basic template structure
        # TODO: Parse actual structured sections from Langfuse config
        from prompt_service.models.prompt import (
            StructuredSection,
            VariableDef,
            VariableType,
        )

        # Build template from Langfuse response
        template = PromptTemplate(
            template_id=template_id,
            name=langfuse_data.get("name", template_id),
            description=f"Template from Langfuse: {template_id}",
            version=langfuse_data.get("version", 1),
            created_by="langfuse",
            tags=[],
            # Parse prompt content into sections
            sections=self._parse_prompt_sections(langfuse_data.get("prompt", "")),
            # Extract variables from config
            variables=self._extract_variables(langfuse_data.get("config", {})),
            is_active=True,
            is_published=True,
            metadata=langfuse_data.get("metadata", {}),
        )

        return template

    def _parse_prompt_sections(self, prompt_content: str) -> List["StructuredSection"]:
        """Parse prompt content into structured sections.

        This is a simple parser that looks for section headers in brackets.
        A more sophisticated parser could be implemented based on needs.

        Args:
            prompt_content: The raw prompt content

        Returns:
            List of parsed sections
        """
        from prompt_service.models.prompt import StructuredSection

        sections = []
        current_section = None
        current_content = []
        order = 0

        lines = prompt_content.split("\n")
        for line in lines:
            line = line.rstrip()
            # Check for section header: [Section Name]
            if line.startswith("[") and line.endswith("]"):
                # Save previous section
                if current_section:
                    sections.append(StructuredSection(
                        name=current_section,
                        content="\n".join(current_content).strip(),
                        order=order,
                    ))
                    order += 1

                # Start new section
                current_section = line[1:-1]
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
                else:
                    # Content before first section - add as "content" section
                    current_section = "content"
                    current_content.append(line)

        # Save last section
        if current_section and current_content:
            sections.append(StructuredSection(
                name=current_section,
                content="\n".join(current_content).strip(),
                order=order,
            ))

        # Default section if no sections found
        if not sections:
            sections.append(StructuredSection(
                name="prompt",
                content=prompt_content,
                order=0,
            ))

        return sections

    def _extract_variables(
        self,
        config: Dict[str, Any],
    ) -> Dict[str, "VariableDef"]:
        """Extract variable definitions from template config.

        Args:
            config: Template configuration from Langfuse

        Returns:
            Dictionary of variable definitions
        """
        from prompt_service.models.prompt import VariableDef, VariableType

        variables = {}

        # Extract variables from config if available
        # Langfuse stores variables in config['variables']
        if "variables" in config:
            for var_name, var_config in config["variables"].items():
                var_type = VariableType.STRING
                if "type" in var_config:
                    try:
                        var_type = VariableType(var_config["type"])
                    except ValueError:
                        var_type = VariableType.STRING

                variables[var_name] = VariableDef(
                    name=var_name,
                    description=var_config.get("description", ""),
                    type=var_type,
                    default_value=var_config.get("default"),
                    is_required=var_config.get("required", True),
                )

        return variables

    def _log_trace(
        self,
        template_id: str,
        version: int,
        variant_id: Optional[str],
        variables: Dict[str, Any],
        context: Dict[str, Any],
        output: str,
        trace_id: str,
    ) -> None:
        """Log prompt retrieval trace to Langfuse.

        Args:
            template_id: Template identifier
            version: Template version
            variant_id: A/B test variant ID
            variables: Variable values
            context: Runtime context
            output: Rendered output
            trace_id: Trace identifier
        """
        self._langfuse_client.log_trace(
            trace_id=trace_id,
            template_id=template_id,
            version=version,
            variables=variables,
            context=context,
            variant_id=variant_id,
            output=output,
            metadata={
                "service": "prompt-service",
                "operation": "retrieve",
            },
        )

    def invalidate_cache(
        self,
        template_id: str,
        version: Optional[int] = None,
    ) -> int:
        """Invalidate cached prompts for a template.

        Args:
            template_id: Template identifier
            version: Optional specific version to invalidate

        Returns:
            Number of entries invalidated
        """
        return self._cache.invalidate(template_id, version)


# Global service instance
_service: Optional[PromptRetrievalService] = None


def get_prompt_retrieval_service() -> PromptRetrievalService:
    """Get the global prompt retrieval service instance.

    Returns:
        Prompt retrieval service instance
    """
    global _service
    if _service is None:
        _service = PromptRetrievalService()
    return _service


def reset_prompt_retrieval_service() -> None:
    """Reset the global service instance.

    This is primarily useful for testing.
    """
    global _service
    _service = None
