"""
Base data models for Prompt Management Service.

This module defines the core data models for prompt templates,
structured sections, and variable definitions.

Models:
- StructuredSection: A labeled component of a prompt template
- VariableDef: Definition of a template variable
- VariableType: Enum for variable types
- PromptTemplate: A reusable prompt definition
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VariableType(str, Enum):
    """Supported variable types for prompt templates.

    Types:
        STRING: Text string values
        NUMBER: Numeric values (int or float)
        LIST: List/array of values
        DICT: Dictionary/object with key-value pairs
        BOOLEAN: True/false values
    """

    STRING = "string"
    NUMBER = "number"
    LIST = "list"
    DICT = "dict"
    BOOLEAN = "boolean"


class StructuredSection(BaseModel):
    """A labeled component of a prompt template.

    Sections are assembled in order to create the final prompt.
    Standard sections include: [角色], [任务], [约束], [输入], [输出格式]

    Attributes:
        name: Section label (e.g., "角色", "任务")
        content: Section content template (may include variable placeholders)
        is_required: Whether section must have non-empty content
        order: Display/assembly order (lower = earlier)
        variables: List of variable names used in this section
        render_if_empty: Whether to render section when content is empty
        separator_before: Content to insert before section
        separator_after: Content to insert after section
    """

    name: str = Field(..., description="Section label")
    content: str = Field(..., description="Section content template")
    is_required: bool = Field(default=True, description="Whether section must have content")
    order: int = Field(default=0, description="Assembly order")
    variables: List[str] = Field(default_factory=list, description="Variables used in content")
    render_if_empty: bool = Field(default=False, description="Render section even if empty")
    separator_before: str = Field(default="", description="Content before section")
    separator_after: str = Field(default="", description="Content after section")

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class VariableDef(BaseModel):
    """Definition of a template variable.

    Variables are placeholders in prompt templates that are replaced
    with actual values at runtime via Jinja2 interpolation.

    Attributes:
        name: Variable name (e.g., "user_input")
        description: What this variable represents
        type: Variable type from VariableType enum
        default_value: Default value if not provided
        is_required: Whether value must be provided at runtime
        validation: Optional validation regex or rule
        schema: Schema for complex types (LIST, DICT)
    """

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$", description="Variable name")
    description: str = Field(..., description="Variable description")
    type: VariableType = Field(default=VariableType.STRING, description="Variable type")
    default_value: Any = Field(default=None, description="Default value")
    is_required: bool = Field(default=True, description="Whether value is required")
    validation: Optional[str] = Field(default=None, description="Validation regex or rule")
    schema: Optional[Dict[str, Any]] = Field(default=None, description="Schema for complex types")

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: type) -> None:
            """Add custom JSON schema properties."""
            # Propagate this for future customization
            pass


class PromptTemplate(BaseModel):
    """A reusable prompt definition with structured sections.

    Templates contain ordered sections that define the prompt structure,
    along with variable definitions for runtime interpolation.

    Attributes:
        template_id: Unique identifier (e.g., "financial_analysis")
        name: Human-readable name
        description: Purpose and usage notes
        version: Monotonically increasing version number
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        created_by: User who created the prompt
        tags: Categorization tags
        sections: Ordered prompt sections
        variables: Variable definitions keyed by name
        is_active: Whether this version is the active one
        is_published: Whether published (visible to retrieval)
        metadata: Custom metadata
    """

    # Identity
    template_id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*$",
        min_length=2,
        max_length=50,
        description="Template identifier",
    )
    name: str = Field(..., max_length=200, description="Human-readable name")
    description: str = Field(..., description="Purpose and usage")
    version: int = Field(default=1, ge=1, description="Version number")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update")
    created_by: str = Field(..., description="Creator user ID")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")

    # Content
    sections: List[StructuredSection] = Field(
        default_factory=list,
        description="Ordered prompt sections"
    )
    variables: Dict[str, VariableDef] = Field(
        default_factory=dict,
        description="Variable definitions"
    )

    # Status
    is_active: bool = Field(default=False, description="Whether this is the active version")
    is_published: bool = Field(default=False, description="Whether published")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def get_section(self, name: str) -> Optional[StructuredSection]:
        """Get a section by name.

        Args:
            name: Section name to find

        Returns:
            The section if found, None otherwise
        """
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def get_required_sections(self) -> List[StructuredSection]:
        """Get all required sections.

        Returns:
            List of sections marked as required
        """
        return [s for s in self.sections if s.is_required]

    def get_variable(self, name: str) -> Optional[VariableDef]:
        """Get a variable definition by name.

        Args:
            name: Variable name

        Returns:
            Variable definition if found, None otherwise
        """
        return self.variables.get(name)

    def get_required_variables(self) -> List[str]:
        """Get names of all required variables.

        Returns:
            List of required variable names
        """
        return [
            name for name, var_def in self.variables.items()
            if var_def.is_required
        ]


@dataclass
class PromptAssemblyContext:
    """Context for prompt assembly operation.

    Attributes:
        template: The template being assembled
        variables: Variable values for interpolation
        context: Additional runtime context (user_id, session_id, etc.)
        retrieved_docs: Retrieved documents for inclusion
        version_id: Specific version to use (optional)
        variant_id: A/B test variant ID (if applicable)
        trace_id: Request trace identifier
    """

    template: PromptTemplate
    variables: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)
    version_id: Optional[int] = None
    variant_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class PromptAssemblyResult:
    """Result of prompt assembly operation.

    Attributes:
        content: Fully rendered prompt text
        template_id: Template identifier
        version_id: Version that was used
        variant_id: A/B test variant ID (if applicable)
        trace_id: Request trace identifier for correlation
        sections: Rendered sections (if include_metadata)
        metadata: Version metadata
        from_cache: Whether response was from cache
    """

    content: str
    template_id: str
    version_id: int
    variant_id: Optional[str] = None
    trace_id: Optional[str] = None
    sections: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    from_cache: bool = False


class VersionHistory(BaseModel):
    """A record of a prompt version in its history.

    Tracks who changed what and when for each published version.

    Attributes:
        template_id: Template identifier
        version: Version number
        change_description: Human-readable change summary
        changed_by: User who made the change
        content_snapshot: Full prompt state at this version
        created_at: When this version was created
        can_rollback: Whether this version can be restored
        rollback_count: Number of times rolled back to this version
    """

    template_id: str = Field(..., description="Template ID")
    version: int = Field(..., ge=1, description="Version number")
    change_description: str = Field(..., description="Change description")
    changed_by: str = Field(..., description="User who made the change")
    content_snapshot: Dict[str, Any] = Field(..., description="Content snapshot")
    created_at: datetime = Field(..., description="Created at")
    can_rollback: bool = Field(default=True, description="Can rollback to this version")
    rollback_count: int = Field(default=0, ge=0, description="Rollback count")
