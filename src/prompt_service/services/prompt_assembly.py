"""
Prompt Assembly Service for dynamic prompt construction.

This service handles the assembly of prompt templates into rendered
prompts by combining:
- Base template with structured sections
- Dynamic context section
- Retrieved documents section
- Variable interpolation via Jinja2

The service uses Jinja2 for template rendering with strict undefined
handling to catch missing variables early.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import Environment, StrictUndefined, TemplateError, UndefinedError

from prompt_service.core.logger import get_logger
from prompt_service.core.exceptions import PromptValidationError
from prompt_service.models.prompt import (
    PromptAssemblyContext,
    PromptAssemblyResult,
    PromptTemplate,
    StructuredSection,
)

logger = get_logger(__name__)


class PromptAssemblyService:
    """Service for assembling prompts from templates.

    This service takes a prompt template and assembles it with
    provided variables, context, and retrieved documents.

    Features:
    - Renders structured sections in order
    - Injects dynamic context section
    - Formats retrieved documents section
    - Interpolates variables via Jinja2
    - Strict validation for missing variables

    Attributes:
        _jinja_env: Jinja2 environment for template rendering
    """

    def __init__(self):
        """Initialize the prompt assembly service."""
        self._jinja_env = Environment(
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        logger.info("PromptAssemblyService initialized")

    def assemble_prompt(self, context: PromptAssemblyContext) -> PromptAssemblyResult:
        """Assemble a prompt from template and context.

        Args:
            context: Assembly context with template, variables, etc.

        Returns:
            Prompt assembly result with rendered content

        Raises:
            PromptValidationError: If validation fails
        """
        template = context.template
        variables = context.variables.copy()
        trace_id = context.trace_id or str(uuid.uuid4())

        logger.info(
            "Assembling prompt",
            extra={
                "template_id": template.template_id,
                "version": template.version,
                "trace_id": trace_id,
            }
        )

        # Validate required variables are provided
        self._validate_variables(template, variables, trace_id)

        # Build the complete variable set for template rendering
        render_variables = self._build_render_variables(
            variables=variables,
            context=context.context,
            retrieved_docs=context.retrieved_docs,
        )

        # Render sections
        sections_content = self._render_sections(
            template.sections,
            render_variables,
        )

        # Assemble final prompt
        content = self._assemble_content(
            sections=sections_content,
            context=context.context,
            retrieved_docs=context.retrieved_docs,
        )

        # Build sections metadata if needed
        sections_metadata = None
        # if context.include_metadata:
        #     sections_metadata = self._build_sections_metadata(template.sections)

        result = PromptAssemblyResult(
            content=content,
            template_id=template.template_id,
            version_id=template.version,
            variant_id=context.variant_id,
            trace_id=trace_id,
            sections=sections_metadata,
            metadata={
                "template_name": template.name,
                "assembled_at": datetime.utcnow().isoformat(),
                "variable_count": len(variables),
                "section_count": len(template.sections),
            },
        )

        logger.info(
            "Prompt assembled successfully",
            extra={
                "template_id": template.template_id,
                "trace_id": trace_id,
                "content_length": len(content),
            }
        )

        return result

    def _validate_variables(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any],
        trace_id: str,
    ) -> None:
        """Validate that all required variables are provided.

        Args:
            template: The prompt template
            variables: Provided variable values
            trace_id: Request trace identifier

        Raises:
            PromptValidationError: If required variables are missing
        """
        errors = []

        for var_name in template.get_required_variables():
            if var_name not in variables:
                errors.append(f"Missing required variable: {var_name}")

        if errors:
            raise PromptValidationError(
                message="Variable validation failed",
                validation_errors=errors,
                trace_id=trace_id,
            )

    def _build_render_variables(
        self,
        variables: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        retrieved_docs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the complete variable set for rendering.

        Args:
            variables: User-provided variables
            context: Additional context
            retrieved_docs: Retrieved documents

        Returns:
            Complete variable set for Jinja2 rendering
        """
        render_vars = variables.copy()

        # Add context as a top-level variable
        if context:
            render_vars["context"] = context

        # Add retrieved docs as a top-level variable
        if retrieved_docs:
            render_vars["retrieved_docs"] = retrieved_docs

        return render_vars

    def _render_sections(
        self,
        sections: List[StructuredSection],
        variables: Dict[str, Any],
    ) -> List[tuple[str, str]]:
        """Render all template sections.

        Args:
            sections: List of sections to render
            variables: Variables for interpolation

        Returns:
            List of (name, content) tuples sorted by order
        """
        rendered = []

        for section in sorted(sections, key=lambda s: s.order):
            try:
                # Create Jinja2 template from section content
                jinja_template = self._jinja_env.from_string(section.content)

                # Render with variables
                content = jinja_template.render(**variables)

                rendered.append((section.name, content))

            except UndefinedError as e:
                # Missing variable in template
                logger.warning(
                    "Undefined variable in section",
                    extra={
                        "section": section.name,
                        "error": str(e),
                    }
                )
                # Render with error indicator
                rendered.append((
                    section.name,
                    f"[ERROR: Missing variable in section '{section.name}']"
                ))

            except TemplateError as e:
                logger.error(
                    "Template rendering error",
                    extra={
                        "section": section.name,
                        "error": str(e),
                    }
                )
                rendered.append((
                    section.name,
                    f"[ERROR: Failed to render section '{section.name}']"
                ))

        return rendered

    def _assemble_content(
        self,
        sections: List[tuple[str, str]],
        context: Optional[Dict[str, Any]],
        retrieved_docs: List[Dict[str, Any]],
    ) -> str:
        """Assemble the final prompt content.

        Combines rendered sections with optional context and
        retrieved docs sections.

        Args:
            sections: Rendered sections as (name, content) tuples
            context: Additional context for dynamic section
            retrieved_docs: Retrieved documents for docs section

        Returns:
            Assembled prompt content
        """
        parts = []

        # Add rendered sections
        for name, content in sections:
            if content:  # Only add non-empty content
                parts.append(f"[{name}]")
                parts.append(content)
                parts.append("")  # Blank line after section

        # Add dynamic context section if provided
        if context:
            parts.append("[上下文]")
            # Format context as key-value pairs
            for key, value in context.items():
                if isinstance(value, dict):
                    parts.append(f"{key}:")
                    for k, v in value.items():
                        parts.append(f"  {k}: {v}")
                else:
                    parts.append(f"{key}: {value}")
            parts.append("")

        # Add retrieved docs section if provided
        if retrieved_docs:
            parts.append("[检索文档]")
            for doc in retrieved_docs:
                content = doc.get("content", "")
                metadata = doc.get("metadata", {})
                # Add source if available
                if "source" in metadata:
                    parts.append(f"- 来源: {metadata['source']}")
                else:
                    parts.append(f"- 文档: {doc.get('id', 'unknown')}")
                parts.append(f"  {content}")
            parts.append("")

        return "\n".join(parts).strip()

    def _build_sections_metadata(
        self,
        sections: List[StructuredSection],
    ) -> List[Dict[str, Any]]:
        """Build metadata for sections.

        Args:
            sections: List of sections

        Returns:
            List of section metadata dictionaries
        """
        return [
            {
                "name": s.name,
                "is_required": s.is_required,
                "order": s.order,
                "variable_count": len(s.variables),
            }
            for s in sections
        ]


# Global service instance
_service: Optional[PromptAssemblyService] = None


def get_prompt_assembly_service() -> PromptAssemblyService:
    """Get the global prompt assembly service instance.

    Returns:
        Prompt assembly service instance
    """
    global _service
    if _service is None:
        _service = PromptAssemblyService()
    return _service


def reset_prompt_assembly_service() -> None:
    """Reset the global service instance.

    This is primarily useful for testing.
    """
    global _service
    _service = None
