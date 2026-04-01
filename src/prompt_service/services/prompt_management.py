"""
Prompt Management Service for CRUD operations on prompt templates.

This service handles:
- Creating new prompt templates
- Updating existing templates (creates new versions)
- Deleting templates (soft delete)
- Listing all templates with filtering

All operations go through the Langfuse client wrapper for
graceful degradation when Langfuse is unavailable.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_service.core.exceptions import PromptNotFoundError, PromptValidationError
from prompt_service.core.logger import get_logger
from prompt_service.middleware.cache import get_cache
from prompt_service.models.prompt import PromptTemplate, StructuredSection, VariableDef

logger = get_logger(__name__)


class PromptManagementService:
    """Service for prompt template management.

    This service provides CRUD operations for prompt templates,
    with automatic versioning and cache management.

    Attributes:
        _langfuse_client: Langfuse client wrapper
        _cache: L1 in-memory cache
    """

    def __init__(self):
        """Initialize the prompt management service."""
        from prompt_service.services.langfuse_client import get_langfuse_client

        self._langfuse_client = get_langfuse_client()
        self._cache = get_cache()

        logger.info("PromptManagementService initialized")

    async def create(
        self,
        template_id: str,
        name: str,
        description: str,
        sections: List[StructuredSection],
        variables: Dict[str, VariableDef],
        tags: List[str],
        created_by: str,
        is_published: bool = True,
    ) -> PromptTemplate:
        """Create a new prompt template.

        Args:
            template_id: Template identifier
            name: Human-readable name
            description: Purpose and usage
            sections: Ordered prompt sections
            variables: Variable definitions
            tags: Categorization tags
            created_by: Creator user ID
            is_published: Whether to publish immediately

        Returns:
            Created prompt template

        Raises:
            PromptValidationError: If validation fails
        """
        # Validate input
        self._validate_template_id(template_id)
        self._validate_sections(sections)
        self._validate_variables(variables)

        # Build prompt content from sections
        prompt_content = self._build_prompt_content(sections)

        # Build config for Langfuse
        config = self._build_config(variables)

        # Create in Langfuse
        langfuse_result = self._langfuse_client.create_prompt(
            template_id=template_id,
            prompt=prompt_content,
            config=config,
            metadata={
                "name": name,
                "description": description,
                "tags": tags,
                "created_by": created_by,
            },
        )

        if langfuse_result is None:
            raise PromptValidationError(
                message="Failed to create prompt in Langfuse",
                trace_id=str(uuid.uuid4()),
            )

        # Build PromptTemplate object
        template = PromptTemplate(
            template_id=template_id,
            name=name,
            description=description,
            version=langfuse_result.get("version", 1),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by=created_by,
            tags=tags,
            sections=sections,
            variables=variables,
            is_active=is_published,
            is_published=is_published,
            metadata=langfuse_result.get("metadata", {}),
        )

        # Create version snapshot
        from prompt_service.services.version_control import get_version_control_service
        version_service = get_version_control_service()
        version_service.create_version_snapshot(
            template=template,
            change_description="Initial version",
            changed_by=created_by,
        )

        logger.info(
            "Prompt template created",
            extra={
                "template_id": template_id,
                "version": template.version,
                "created_by": created_by,
            }
        )

        return template

    async def update(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sections: Optional[List[StructuredSection]] = None,
        variables: Optional[Dict[str, VariableDef]] = None,
        tags: Optional[List[str]] = None,
        change_description: str = "",
        updated_by: str = "",
    ) -> PromptTemplate:
        """Update an existing prompt template (creates new version).

        Args:
            template_id: Template identifier
            name: New human-readable name
            description: New purpose and usage
            sections: New ordered prompt sections
            variables: New variable definitions
            tags: New categorization tags
            change_description: Description of changes
            updated_by: User making the update

        Returns:
            Updated prompt template (new version)

        Raises:
            PromptNotFoundError: If template not found
            PromptValidationError: If validation fails
        """
        # Get current template to validate it exists
        current = await self.get(template_id)
        if current is None:
            raise PromptNotFoundError(
                template_id=template_id,
                trace_id=str(uuid.uuid4()),
            )

        # Use provided values or fall back to current
        final_name = name or current.name
        final_description = description or current.description
        final_sections = sections or current.sections
        final_variables = variables or dict(current.variables)
        final_tags = tags or current.tags

        # Validate
        if sections:
            self._validate_sections(sections)
        if variables:
            self._validate_variables(variables)

        # Build prompt content
        prompt_content = self._build_prompt_content(final_sections)

        # Build config
        config = self._build_config(final_variables)

        # Update in Langfuse (creates new version)
        langfuse_result = self._langfuse_client.update_prompt(
            template_id=template_id,
            prompt=prompt_content,
            config=config,
            metadata={
                "name": final_name,
                "description": final_description,
                "tags": final_tags,
                "change_description": change_description,
                "updated_by": updated_by,
            },
        )

        if langfuse_result is None:
            raise PromptValidationError(
                message="Failed to update prompt in Langfuse",
                trace_id=str(uuid.uuid4()),
            )

        # Invalidate cache
        self._cache.invalidate(template_id)

        # Build updated template
        new_version = langfuse_result.get("version", current.version + 1)

        template = PromptTemplate(
            template_id=template_id,
            name=final_name,
            description=final_description,
            version=new_version,
            created_at=current.created_at,
            updated_at=datetime.utcnow(),
            created_by=current.created_by,
            tags=final_tags,
            sections=final_sections,
            variables=final_variables,
            is_active=True,
            is_published=current.is_published,
            metadata=langfuse_result.get("metadata", {}),
        )

        # Create version snapshot
        from prompt_service.services.version_control import get_version_control_service
        version_service = get_version_control_service()
        version_service.create_version_snapshot(
            template=template,
            change_description=change_description or f"Updated to version {new_version}",
            changed_by=updated_by,
        )

        logger.info(
            "Prompt template updated",
            extra={
                "template_id": template_id,
                "old_version": current.version,
                "new_version": new_version,
                "updated_by": updated_by,
            }
        )

        return template

    async def delete(
        self,
        template_id: str,
        deleted_by: str = "",
    ) -> bool:
        """Delete a prompt template (soft delete).

        Args:
            template_id: Template identifier
            deleted_by: User performing deletion

        Returns:
            True if deleted successfully

        Raises:
            PromptNotFoundError: If template not found
        """
        # Check if template exists
        current = await self.get(template_id)
        if current is None:
            raise PromptNotFoundError(
                template_id=template_id,
                trace_id=str(uuid.uuid4()),
            )

        # Soft delete via metadata
        # In a real implementation, we'd mark as deleted in Langfuse
        # For now, we'll invalidate cache and log

        self._cache.invalidate(template_id)

        logger.info(
            "Prompt template deleted (soft delete)",
            extra={
                "template_id": template_id,
                "deleted_by": deleted_by,
            }
        )

        return True

    async def list(
        self,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
    page_size: int = 20,
    ) -> List[PromptTemplate]:
        """List all prompt templates with filtering.

        Args:
            tag: Filter by tag
            search: Search in name/description
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            List of prompt templates
        """
        # TODO: Implement actual listing from Langfuse
        # For now, return empty list
        logger.info(
            "Listing prompt templates",
            extra={
                "tag": tag,
                "search": search,
                "page": page,
                "page_size": page_size,
            }
        )

        return []

    async def get(
        self,
        template_id: str,
        version: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """Get a specific prompt template.

        Args:
            template_id: Template identifier
            version: Optional specific version

        Returns:
            Prompt template or None if not found
        """
        langfuse_data = self._langfuse_client.get_prompt(
            template_id=template_id,
            version=version,
        )

        if langfuse_data is None:
            return None

        # Convert to PromptTemplate
        from prompt_service.services.prompt_retrieval import PromptRetrievalService

        retrieval_service = PromptRetrievalService()
        return await retrieval_service._load_template(template_id, version, str(uuid.uuid4()))

    def _validate_template_id(self, template_id: str) -> None:
        """Validate template ID format.

        Args:
            template_id: Template identifier to validate

        Raises:
            PromptValidationError: If format is invalid
        """
        import re

        if not re.match(r"^[a-z][a-z0-9_]*$", template_id):
            raise PromptValidationError(
                message=f"Invalid template_id format: {template_id}",
                validation_errors=[
                    "Template ID must start with lowercase letter and contain only lowercase letters, numbers, and underscores"
                ],
                trace_id=str(uuid.uuid4()),
            )

        if len(template_id) < 2 or len(template_id) > 50:
            raise PromptValidationError(
                message=f"Template ID must be 2-50 characters: {template_id}",
                validation_errors=[
                    "Template ID length must be between 2 and 50 characters"
                ],
                trace_id=str(uuid.uuid4()),
            )

    def _validate_sections(self, sections: List[StructuredSection]) -> None:
        """Validate prompt sections.

        Args:
            sections: Sections to validate

        Raises:
            PromptValidationError: If validation fails
        """
        errors = []

        # Check for standard sections
        standard_sections = {"角色", "任务", "约束", "输入", "输出格式"}
        has_standard = any(s.name in standard_sections for s in sections)

        if not has_standard:
            errors.append("Prompt should include at least one standard section: 角色, 任务, 约束, 输入, 输出格式")

        # Check for duplicate names
        names = [s.name for s in sections]
        if len(names) != len(set(names)):
            errors.append("Section names must be unique")

        # Check order uniqueness
        orders = [s.order for s in sections]
        if len(orders) != len(set(orders)):
            errors.append("Section orders must be unique")

        if errors:
            raise PromptValidationError(
                message="Section validation failed",
                validation_errors=errors,
                trace_id=str(uuid.uuid4()),
            )

    def _validate_variables(self, variables: Dict[str, VariableDef]) -> None:
        """Validate variable definitions.

        Args:
            variables: Variables to validate

        Raises:
            PromptValidationError: If validation fails
        """
        errors = []

        for var_name, var_def in variables.items():
            # Check name format
            import re

            if not re.match(r"^[a-z][a-z0-9_]*$", var_name):
                errors.append(f"Invalid variable name: {var_name}")

            # Check for description
            if not var_def.description:
                errors.append(f"Variable {var_name} must have a description")

        if errors:
            raise PromptValidationError(
                message="Variable validation failed",
                validation_errors=errors,
                trace_id=str(uuid.uuid4()),
            )

    def _build_prompt_content(self, sections: List[StructuredSection]) -> str:
        """Build prompt content from sections.

        Args:
            sections: Ordered sections

        Returns:
            Prompt content as string
        """
        parts = []

        for section in sorted(sections, key=lambda s: s.order):
            parts.append(f"[{section.name}]")
            parts.append(section.content)
            parts.append("")  # Blank line after section

        return "\n".join(parts).strip()

    def _build_config(self, variables: Dict[str, VariableDef]) -> Dict[str, Any]:
        """Build Langfuse config from variables.

        Args:
            variables: Variable definitions

        Returns:
            Config dictionary for Langfuse
        """
        config_vars = {}

        for var_name, var_def in variables.items():
            config_vars[var_name] = {
                "type": var_def.type.value,
                "description": var_def.description,
                "default": var_def.default_value,
                "required": var_def.is_required,
            }

        return {
            "variables": config_vars,
        }


# Global service instance
_service: Optional[PromptManagementService] = None


def get_prompt_management_service() -> PromptManagementService:
    """Get the global prompt management service instance.

    Returns:
        Prompt management service instance
    """
    global _service
    if _service is None:
        _service = PromptManagementService()
    return _service


def reset_prompt_management_service() -> None:
    """Reset the global service instance.

    This is primarily useful for testing.
    """
    global _service
    _service = None
