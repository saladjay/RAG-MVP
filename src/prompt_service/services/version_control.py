"""
Version Control Service for prompt template management.

This service handles:
- Tracking version history for prompt templates
- Creating version snapshots on updates
- Rolling back to previous versions
- Retrieving version history

The service maintains a history of all published prompt versions
enabling safe rollback to any previous state.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_service.core.exceptions import PromptNotFoundError, PromptServiceError, PromptValidationError
from prompt_service.core.logger import get_logger
from prompt_service.models.prompt import PromptTemplate, StructuredSection, VariableDef, VersionHistory
from prompt_service.services.langfuse_client import get_langfuse_client

logger = get_logger(__name__)


class VersionControlService:
    """Service for managing prompt version history.

    This service tracks all changes to prompt templates and provides
    rollback functionality to restore previous versions.

    Attributes:
        _history: Storage for version history (keyed by template_id)
        _langfuse_client: Langfuse client wrapper
    """

    def __init__(self):
        """Initialize the version control service."""
        self._langfuse_client = get_langfuse_client()
        self._history: Dict[str, List[VersionHistory]] = {}

        logger.info("VersionControlService initialized")

    def create_version_snapshot(
        self,
        template: PromptTemplate,
        change_description: str,
        changed_by: str,
    ) -> VersionHistory:
        """Create a snapshot for a new version.

        Args:
            template: The template being versioned
            change_description: Description of changes
            changed_by: User making the change

        Returns:
            Created version history entry
        """
        # Create content snapshot
        content_snapshot = {
            "name": template.name,
            "description": template.description,
            "sections": [
                {
                    "name": s.name,
                    "content": s.content,
                    "is_required": s.is_required,
                    "order": s.order,
                    "variables": s.variables,
                }
                for s in template.sections
            ],
            "variables": {
                name: {
                    "description": var_def.description,
                    "type": var_def.type.value,
                    "default_value": var_def.default_value,
                    "is_required": var_def.is_required,
                }
                for name, var_def in template.variables.items()
            },
            "tags": template.tags,
            "metadata": template.metadata,
        }

        # Create version history entry
        history_entry = VersionHistory(
            template_id=template.template_id,
            version=template.version,
            change_description=change_description,
            changed_by=changed_by,
            content_snapshot=content_snapshot,
            created_at=template.updated_at or datetime.utcnow(),
        )

        # Store in history
        if template.template_id not in self._history:
            self._history[template.template_id] = []

        self._history[template.template_id].append(history_entry)

        logger.info(
            "Version snapshot created",
            extra={
                "template_id": template.template_id,
                "version": template.version,
                "changed_by": changed_by,
            }
        )

        return history_entry

    def get_history(
        self,
        template_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> List[VersionHistory]:
        """Get version history for a template.

        Args:
            template_id: Template identifier
            page: Page number (1-indexed)
            page_size: Page size

        Returns:
            List of version history entries (newest first)
        """
        if template_id not in self._history:
            return []

        # Get history sorted by version descending
        history = sorted(
            self._history[template_id],
            key=lambda h: h.version,
            reverse=True,
        )

        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size

        return history[start:end]

    async def rollback(
        self,
        template_id: str,
        target_version: int,
        rolled_back_by: str,
    ) -> PromptTemplate:
        """Rollback a template to a previous version.

        Creates a new version with the content from the target version.

        Args:
            template_id: Template identifier
            target_version: Version to rollback to
            rolled_back_by: User performing the rollback

        Returns:
            New template with rolled-back content

        Raises:
            PromptNotFoundError: If template or version not found
            PromptValidationError: If validation fails
        """
        # Get version history
        history = self._history.get(template_id)
        if not history:
            raise PromptNotFoundError(
                template_id=template_id,
                trace_id=str(uuid.uuid4()),
            )

        # Find target version
        target_snapshot = None
        for entry in history:
            if entry.version == target_version:
                target_snapshot = entry
                break

        if target_snapshot is None:
            raise PromptServiceError(
                message=f"Version {target_version} not found in history",
                trace_id=str(uuid.uuid4()),
            )

        if not target_snapshot.can_rollback:
            raise PromptValidationError(
                message=f"Cannot rollback to version {target_version}",
                validation_errors=[f"Version {target_version} is marked as not restorable"],
                trace_id=str(uuid.uuid4()),
            )

        # Restore content from snapshot
        sections = []
        for section_data in target_snapshot.content_snapshot["sections"]:
            sections.append(StructuredSection(
                name=section_data["name"],
                content=section_data["content"],
                is_required=section_data["is_required"],
                order=section_data["order"],
                variables=section_data.get("variables", []),
            ))

        variables = {}
        for var_name, var_data in target_snapshot.content_snapshot["variables"].items():
            from prompt_service.models.prompt import VariableType
            var_type = VariableType.STRING
            try:
                var_type = VariableType(var_data["type"])
            except (ValueError, KeyError):
                pass

            variables[var_name] = VariableDef(
                name=var_name,
                description=var_data["description"],
                type=var_type,
                default_value=var_data.get("default_value"),
                is_required=var_data["is_required"],
            )

        # Create new template with rolled-back content
        # Get current max version
        current_max_version = max(h.version for h in history)
        new_version = current_max_version + 1

        from prompt_service.services.prompt_management import get_prompt_management_service

        management_service = get_prompt_management_service()

        # Build the template with rolled-back content
        rolled_back_template = PromptTemplate(
            template_id=template_id,
            name=target_snapshot.content_snapshot["name"],
            description=target_snapshot.content_snapshot["description"],
            version=new_version,
            created_by=rolled_back_by,
            sections=sections,
            variables=variables,
            tags=target_snapshot.content_snapshot["tags"],
            is_active=True,
            is_published=True,
            metadata=target_snapshot.content_snapshot["metadata"],
        )

        # Update the template via Langfuse
        langfuse_data = self._langfuse_client.update_prompt(
            template_id=template_id,
            prompt=self._assemble_prompt_text(sections),
            config={
                "variables": {
                    name: {
                        "type": var_def.type.value,
                        "description": var_def.description,
                        "default": var_def.default_value,
                        "required": var_def.is_required,
                    }
                    for name, var_def in variables.items()
                }
            },
            labels=target_snapshot.content_snapshot["tags"],
        )

        if langfuse_data is None:
            raise PromptServiceError(
                message="Failed to update template in Langfuse",
                trace_id=str(uuid.uuid4()),
            )

        # Create version snapshot for the rollback
        self.create_version_snapshot(
            template=rolled_back_template,
            change_description=f"Rollback to version {target_version}",
            changed_by=rolled_back_by,
        )

        # Increment rollback count on target version
        target_snapshot.rollback_count += 1

        logger.info(
            "Template rolled back",
            extra={
                "template_id": template_id,
                "target_version": target_version,
                "new_version": new_version,
                "rolled_back_by": rolled_back_by,
            }
        )

        return rolled_back_template

    def _assemble_prompt_text(self, sections: List[StructuredSection]) -> str:
        """Assemble prompt text from sections.

        Args:
            sections: List of sections

        Returns:
            Assembled prompt text
        """
        # Sort by order
        sorted_sections = sorted(sections, key=lambda s: s.order)

        parts = []
        for section in sorted_sections:
            if section.content or section.render_if_empty:
                parts.append(f"[{section.name}]")
                parts.append(section.content)

        return "\n".join(parts)


# Global service instance
_service: Optional[VersionControlService] = None


def get_version_control_service() -> VersionControlService:
    """Get the global version control service instance.

    Returns:
        Version control service instance
    """
    global _service
    if _service is None:
        _service = VersionControlService()
    return _service


def reset_version_control_service() -> None:
    """Reset the global service instance.

    This is primarily useful for testing.
    """
    global _service
    _service = None
